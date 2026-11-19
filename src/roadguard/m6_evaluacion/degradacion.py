"""Degradacion de trayectorias y F1 de reglas de punta a punta (seccion 2.5).

El criterio de reglas pide comparar las alertas del sistema contra eventos de
referencia sobre trayectorias *degradadas*: la referencia se calcula sobre la
trayectoria limpia de NGSIM, y el sistema recibe esa misma trayectoria con
los defectos que introduce la camara. Asi el F1 mide reglas y percepcion
juntas, no reglas sobre datos perfectos.

Que se degrada (magnitudes medidas sobre UA-DETRAC con
`scripts/medir_ruido_m3.py`, nunca inventadas):

1. **Remuestreo a 25 Hz.** NGSIM viene a 10 Hz y el video a 25 FPS; se
   interpola linealmente para que el suavizado de M3 vea la misma cantidad
   de muestras por segundo que en video.
2. **Error de posicion.** Ruido gaussiano AR(1) por vehiculo, longitudinal y
   lateral por separado: el error de un detector se parece mucho de un cuadro
   al siguiente (autocorrelacion medida de 0,94 a 0,98).
3. **Perdidas (oclusion).** Cadena de Markov visible/oculto por vehiculo con
   la fraccion perdida y la duracion media de hueco medidas.
4. **Cambios de ID.** Con la tasa medida por vehiculo y segundo, el vehiculo
   pasa a tener un ID nuevo desde ese instante (fragmentacion de trayectoria).

Despues, la trayectoria degradada recorre el mismo camino que el video:
`HistorialCausal` (velocidad causal), asignacion de carril con confianza,
`DetectorCambioCarril`, `calcular_relaciones` y `MotorReglas`. Los eventos se
devuelven con el ID original del vehiculo para compararlos con la referencia:
un vehiculo fragmentado sigue siendo el mismo vehiculo, y lo que cuesta la
fragmentacion es la historia que se pierde, no la etiqueta.
"""

from __future__ import annotations

import dataclasses
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from statistics import median
from typing import Optional

import numpy as np

from roadguard.m3_geometria.carriles import DetectorCambioCarril
from roadguard.m3_geometria.relaciones import calcular_relaciones
from roadguard.m3_geometria.trayectorias import HistorialCausal
from roadguard.m4_reglas.motor import MotorReglas
from roadguard.m6_evaluacion.emparejamiento import (
    ResultadoEventos,
    evaluar_eventos,
    resultado_global,
)
from roadguard.m6_evaluacion.ngsim import FPS_NGSIM, CuadroReferencia
from roadguard.m6_evaluacion.referencia import EventoReferencia, eventos_referencia
from roadguard.tipos import Evento, Regla, Umbrales

_EPS = 1e-9
# En US-101 los carriles 6 (auxiliar), 7 (entrada) y 8 (salida) ocupan la
# misma franja lateral en tramos distintos del camino: se distinguen por x.
_ZONA_AUXILIAR = (6, 7, 8)
_PRIMER_ID_NUEVO = 10_000_000


@dataclass(frozen=True)
class ParametrosDegradacion:
    """Defectos que se aplican a la trayectoria limpia. Todo en cero = limpia."""

    sigma_x: float = 0.0  # m, error longitudinal
    sigma_y: float = 0.0  # m, error lateral
    autocorrelacion_x: float = 0.0  # de un cuadro al siguiente, a `fps`
    autocorrelacion_y: float = 0.0
    fraccion_perdida: float = 0.0  # de las observaciones
    duracion_hueco: float = 1.0  # s, media de cada perdida
    cambios_id_por_s: float = 0.0  # por vehiculo y segundo observado
    fps: float = 25.0
    semilla: int = 0

    def escalado(self, factor: float) -> "ParametrosDegradacion":
        """Mismo escenario con el error de posicion multiplicado por `factor`."""
        return dataclasses.replace(
            self, sigma_x=self.sigma_x * factor, sigma_y=self.sigma_y * factor
        )


@dataclass(frozen=True)
class Observacion:
    id_degradado: int
    id_original: int
    x: float
    y: float


@dataclass(frozen=True)
class CuadroDegradado:
    cuadro: int
    t: float
    observaciones: list[Observacion]


class AsignadorCarrilNGSIM:
    """Carril y confianza desde la posicion lateral, como hace M3 con poligonos.

    Los centros de carril son la mediana lateral observada en la trayectoria
    limpia; los bordes, los puntos medios entre centros vecinos. La confianza
    vale 1 en el centro y cae linealmente a 0 en el borde, igual que
    `asignar_carril`. En la zona auxiliar (6, 7 y 8) el carril se elige por
    el tramo longitudinal en que se observo cada uno.
    """

    def __init__(self, centros: list[float], tramos_auxiliares: dict[int, tuple[float, float]]):
        if len(centros) < 2:
            raise ValueError("Se necesitan al menos dos carriles")
        self.centros = centros
        self.bordes = [(a + b) / 2 for a, b in zip(centros, centros[1:])]
        self.tramos_auxiliares = tramos_auxiliares

    @classmethod
    def desde_cuadros(cls, cuadros: list[CuadroReferencia]) -> "AsignadorCarrilNGSIM":
        laterales: dict[int, list[float]] = defaultdict(list)
        longitudinales: dict[int, list[float]] = defaultdict(list)
        for c in cuadros:
            for e in c.estados:
                zona = _ZONA_AUXILIAR[0] if e.carril in _ZONA_AUXILIAR else e.carril
                laterales[zona].append(e.y_camino)
                longitudinales[e.carril].append(e.x_camino)
        centros = [median(laterales[k]) for k in sorted(laterales)]
        tramos = {
            k: (min(longitudinales[k]), max(longitudinales[k]))
            for k in _ZONA_AUXILIAR
            if k in longitudinales
        }
        return cls(centros, tramos)

    def asignar(self, x: float, y: float) -> tuple[Optional[int], float]:
        k = bisect_right(self.bordes, y)  # 0-based
        izq = self.bordes[k - 1] if k > 0 else None
        der = self.bordes[k] if k < len(self.bordes) else None
        if izq is None:
            izq = 2 * self.centros[k] - der
        if der is None:
            der = 2 * self.centros[k] - izq
        if y < izq or y > der:
            return None, 0.0
        centro = self.centros[k]
        medio_ancho = (der - centro) if y >= centro else (centro - izq)
        confianza = max(0.0, 1.0 - abs(y - centro) / medio_ancho) if medio_ancho > 0 else 0.0
        carril = k + 1
        if carril == _ZONA_AUXILIAR[0] and self.tramos_auxiliares:
            carril = self._carril_auxiliar(x)
        return carril, confianza

    def _carril_auxiliar(self, x: float) -> int:
        for carril, (desde, hasta) in self.tramos_auxiliares.items():
            if desde <= x <= hasta:
                return carril
        cercano = min(
            self.tramos_auxiliares.items(),
            key=lambda kv: min(abs(x - kv[1][0]), abs(x - kv[1][1])),
        )
        return cercano[0]


def trayectorias(cuadros: list[CuadroReferencia]) -> dict[int, list[tuple[float, float, float]]]:
    """(t, x, y) por vehiculo, en orden temporal."""
    por_vehiculo: dict[int, list[tuple[float, float, float]]] = defaultdict(list)
    for c in cuadros:
        for e in c.estados:
            por_vehiculo[e.id_vehiculo].append((c.t, e.x_camino, e.y_camino))
    for lista in por_vehiculo.values():
        lista.sort()
    return dict(por_vehiculo)


def remuestrear(
    muestras: list[tuple[float, float, float]], fps: float, paso_origen: float = 1 / FPS_NGSIM
) -> list[tuple[int, float, float]]:
    """Interpola linealmente a una grilla de `fps`. Devuelve (indice, x, y).

    Solo interpola entre muestras consecutivas del origen; un hueco en el
    origen queda como hueco. El indice es `round(t * fps)`.
    """
    salida: list[tuple[int, float, float]] = []
    for (t0, x0, y0), (t1, x1, y1) in zip(muestras, muestras[1:]):
        if t1 - t0 > paso_origen + _EPS:
            continue
        i0 = int(np.ceil(t0 * fps - _EPS))
        i1 = int(np.floor(t1 * fps - _EPS))  # el extremo final lo pone el par siguiente
        for i in range(i0, i1 + 1):
            a = (i / fps - t0) / (t1 - t0)
            salida.append((i, x0 + a * (x1 - x0), y0 + a * (y1 - y0)))
    if muestras:
        t, x, y = muestras[-1]
        i = round(t * fps)
        if abs(i / fps - t) < _EPS and (not salida or salida[-1][0] < i):
            salida.append((i, x, y))
    return salida


def _ruido_ar1(rng: np.random.Generator, n: int, sigma: float, rho: float) -> np.ndarray:
    if sigma <= 0 or n == 0:
        return np.zeros(n)
    rho = min(max(rho, 0.0), 0.999)
    e = np.empty(n)
    e[0] = rng.normal(0.0, sigma)
    innovacion = sigma * np.sqrt(1 - rho**2)
    for k in range(1, n):
        e[k] = rho * e[k - 1] + rng.normal(0.0, innovacion)
    return e


def _visibles(rng: np.random.Generator, n: int, p: ParametrosDegradacion) -> np.ndarray:
    """Cadena visible/oculto con la fraccion perdida y el hueco medio pedidos."""
    if p.fraccion_perdida <= 0 or n == 0:
        return np.ones(n, dtype=bool)
    dt = 1.0 / p.fps
    q = min(1.0, dt / max(p.duracion_hueco, dt))  # oculto -> visible
    f = min(p.fraccion_perdida, 0.99)
    r = min(1.0, q * f / (1 - f))  # visible -> oculto, para que la estacionaria sea f
    visible = np.empty(n, dtype=bool)
    visible[0] = rng.random() >= f
    for k in range(1, n):
        u = rng.random()
        visible[k] = (u >= r) if visible[k - 1] else (u < q)
    return visible


def degradar(cuadros: list[CuadroReferencia], p: ParametrosDegradacion) -> list[CuadroDegradado]:
    """Trayectorias limpias -> observaciones como las entregaria la camara."""
    por_indice: dict[int, list[Observacion]] = defaultdict(list)
    siguiente_id = _PRIMER_ID_NUEVO
    for vid, muestras in sorted(trayectorias(cuadros).items()):
        serie = remuestrear(muestras, p.fps)
        n = len(serie)
        rng = np.random.default_rng([p.semilla, vid])
        ex = _ruido_ar1(rng, n, p.sigma_x, p.autocorrelacion_x)
        ey = _ruido_ar1(rng, n, p.sigma_y, p.autocorrelacion_y)
        visible = _visibles(rng, n, p)
        prob_cambio = p.cambios_id_por_s / p.fps
        id_actual = vid
        for k, (i, x, y) in enumerate(serie):
            if not visible[k]:
                continue
            if prob_cambio > 0 and rng.random() < prob_cambio:
                id_actual = siguiente_id
                siguiente_id += 1
            por_indice[i].append(Observacion(id_actual, vid, x + ex[k], y + ey[k]))
    return [
        CuadroDegradado(i, i / p.fps, por_indice[i]) for i in sorted(por_indice)
    ]


def simular_sistema(
    cuadros: list[CuadroDegradado],
    umbrales: Umbrales,
    asignador: AsignadorCarrilNGSIM,
    fps: float,
    confianza_min_carril: float = 0.6,
    permanencia_cambio: float = 1.0,
) -> list[Evento]:
    """M3 y M4 sobre observaciones degradadas, en el mismo orden que el pipeline.

    Devuelve los eventos con `id_vehiculo` e `id_relacionado` originales.
    """
    historial = HistorialCausal(fps)
    detector_cambios = DetectorCambioCarril(confianza_min_carril, permanencia_cambio)
    motor = MotorReglas(umbrales)
    original: dict[int, int] = {}
    eventos: list[Evento] = []
    for c in cuadros:
        estados = []
        cambios = []
        for o in c.observaciones:
            original[o.id_degradado] = o.id_original
            carril, confianza = asignador.asignar(o.x, o.y)
            estado = historial.actualizar_camino(
                o.id_degradado, c.cuadro, c.t, (o.x, o.y), carril, confianza
            )
            estados.append(estado)
            cambio = detector_cambios.actualizar(o.id_degradado, carril, c.t, confianza)
            if cambio is not None:
                cambios.append(cambio)
        for ident in historial.purgar(c.t):
            detector_cambios.olvidar(ident)
        relaciones = calcular_relaciones(estados, c.cuadro, c.t)
        cerrados, _ = motor.actualizar(
            c.t, {e.id_vehiculo: e for e in estados}, relaciones, cambios
        )
        eventos.extend(cerrados)
    eventos.extend(motor.finalizar())
    return [
        dataclasses.replace(
            ev,
            id_vehiculo=original.get(ev.id_vehiculo, ev.id_vehiculo),
            id_relacionado=None
            if ev.id_relacionado is None
            else original.get(ev.id_relacionado, ev.id_relacionado),
        )
        for ev in eventos
    ]


def eventos_m4_limpio(
    cuadros: list[CuadroReferencia],
    umbrales: Umbrales,
    permanencia_cambio: float = 1.0,
) -> list[Evento]:
    """M4 directo sobre los estados y relaciones limpios de NGSIM.

    Sirve de control: si las reglas implementan lo especificado, el F1
    contra la referencia es 1. Los cambios de carril salen del mismo
    `DetectorCambioCarril` que usa la referencia.
    """
    motor = MotorReglas(umbrales)
    detector = DetectorCambioCarril(0.0, permanencia_cambio)
    eventos: list[Evento] = []
    for c in cuadros:
        cambios = []
        for e in c.estados:
            cambio = detector.actualizar(e.id_vehiculo, e.carril, e.t, e.confianza_carril)
            if cambio is not None:
                cambios.append(cambio)
        cerrados, _ = motor.actualizar(
            c.t, {e.id_vehiculo: e for e in c.estados}, c.relaciones, cambios
        )
        eventos.extend(cerrados)
    eventos.extend(motor.finalizar())
    return eventos


def fraccion_con_respaldo(detectados, referencia, tolerancia: float = 1.0) -> Optional[float]:
    """Fraccion de alertas que tocan un evento real del mismo vehiculo y regla.

    Complementa al F1: un tramo real que el sistema parte en dos da un acierto
    y un falso positivo en el F1 uno a uno, pero las dos alertas tienen
    respaldo. Responde a "cuando el sistema alerta, hay algo real ahi".
    None si no hay alertas (Paso 3).
    """
    detectados = list(detectados)
    if not detectados:
        return None
    por_clave: dict[tuple[int, Regla], list] = defaultdict(list)
    for r in referencia:
        por_clave[(r.id_vehiculo, r.regla)].append(r)
    con_respaldo = sum(
        any(
            min(r.t_fin, d.t_fin) - max(r.t_inicio, d.t_inicio) + 2 * tolerancia >= 0
            for r in por_clave.get((d.id_vehiculo, d.regla), [])
        )
        for d in detectados
    )
    return con_respaldo / len(detectados)


@dataclass(frozen=True)
class ResultadoDegradacion:
    parametros: ParametrosDegradacion
    por_regla: dict[Regla, ResultadoEventos]
    detectados: int
    referencia: int
    con_respaldo: dict[Regla, Optional[float]] = dataclasses.field(default_factory=dict)

    @property
    def global_(self) -> ResultadoEventos:
        return resultado_global(self.por_regla)


def evaluar_degradacion(
    cuadros: list[CuadroReferencia],
    p: ParametrosDegradacion,
    umbrales: Optional[Umbrales] = None,
    referencia: Optional[list[EventoReferencia]] = None,
    asignador: Optional[AsignadorCarrilNGSIM] = None,
    tolerancia: float = 1.0,
    confianza_min_carril: float = 0.6,
) -> ResultadoDegradacion:
    """F1 por regla del sistema sobre la trayectoria degradada con `p`."""
    umbrales = umbrales if umbrales is not None else Umbrales()
    if referencia is None:
        referencia = eventos_referencia(cuadros, umbrales)
    if asignador is None:
        asignador = AsignadorCarrilNGSIM.desde_cuadros(cuadros)
    detectados = simular_sistema(
        degradar(cuadros, p), umbrales, asignador, p.fps, confianza_min_carril
    )
    por_regla = evaluar_eventos(detectados, referencia, tolerancia)
    for regla in Regla:
        por_regla.setdefault(regla, ResultadoEventos(0, 0, 0))
    respaldo = {
        regla: fraccion_con_respaldo(
            [d for d in detectados if d.regla == regla],
            [r for r in referencia if r.regla == regla],
            tolerancia,
        )
        for regla in Regla
    }
    return ResultadoDegradacion(p, por_regla, len(detectados), len(referencia), respaldo)
