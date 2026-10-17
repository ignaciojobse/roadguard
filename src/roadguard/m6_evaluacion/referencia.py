"""Eventos de referencia desde trayectorias limpias (seccion 2.5).

El criterio de reglas compara las alertas de RoadGuard contra eventos de
referencia calculados desde highD o NGSIM. Este modulo calcula esos eventos
con las definiciones de RF7, RF8 y RF9 aplicadas fuera de linea sobre la
trayectoria completa. No es el motor de reglas (M4): es el patron contra el
que se mide.

Decisiones de la referencia (knowledge/projects/datos-y-evaluacion/PRD.md):
  - Los cambios de carril se confirman con el mismo DetectorCambioCarril de
    M3, para que "cambio completo" signifique lo mismo en ambos lados.
  - Las ventanas de zigzag y corte se miden desde `t_cruce`, que es cuando
    ocurrio la maniobra. La latencia de confirmacion de M4 la absorbe la
    tolerancia del emparejamiento.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from typing import Optional

from roadguard.m3_geometria.carriles import DetectorCambioCarril
from roadguard.m6_evaluacion.ngsim import CuadroReferencia
from roadguard.tipos import CambioCarril, Regla, Relacion, Umbrales

_EPS = 1e-9


@dataclass(frozen=True)
class EventoReferencia:
    """Evento esperado: vehiculo, regla e intervalo."""

    id_vehiculo: int
    regla: Regla
    t_inicio: float
    t_fin: float
    id_relacionado: Optional[int] = None


def cambios_de_carril(
    cuadros: list[CuadroReferencia], permanencia: float = 1.0
) -> list[CambioCarril]:
    """Cambios completos confirmados sobre la trayectoria limpia."""
    detector = DetectorCambioCarril(confianza_min=0.0, permanencia=permanencia)
    cambios: list[CambioCarril] = []
    for c in cuadros:
        for e in c.estados:
            cambio = detector.actualizar(e.id_vehiculo, e.carril, e.t, e.confianza_carril)
            if cambio is not None:
                cambios.append(cambio)
    return cambios


def eventos_referencia(
    cuadros: list[CuadroReferencia],
    umbrales: Umbrales,
    permanencia_cambio: float = 1.0,
) -> list[EventoReferencia]:
    """Eventos de cercania, zigzag y corte sobre la trayectoria completa."""
    cambios = cambios_de_carril(cuadros, permanencia_cambio)
    return (
        _cercania(cuadros, umbrales)
        + _zigzag(cambios, umbrales)
        + _corte(cuadros, cambios, umbrales)
    )


@dataclass
class _Tramo:
    id_predecesor: Optional[int]
    cuadro_ultimo: int
    t_inicio: float
    t_ultimo: float


def _cercania(cuadros: list[CuadroReferencia], u: Umbrales) -> list[EventoReferencia]:
    """RF7: v > minimo y THW < maximo sostenido durante la persistencia.

    Un tramo se corta si falta un cuadro o si cambia el predecesor, para que
    cada evento quede atado a un solo vehiculo delantero.
    """
    eventos: list[EventoReferencia] = []
    abiertos: dict[int, _Tramo] = {}

    def cerrar(id_vehiculo: int) -> None:
        tramo = abiertos.pop(id_vehiculo)
        if tramo.t_ultimo - tramo.t_inicio >= u.cercania_persistencia - _EPS:
            eventos.append(
                EventoReferencia(
                    id_vehiculo, Regla.CERCANIA, tramo.t_inicio, tramo.t_ultimo,
                    tramo.id_predecesor,
                )
            )

    for c in cuadros:
        velocidad = {e.id_vehiculo: e.velocidad for e in c.estados}
        activos: set[int] = set()
        for r in c.relaciones:
            v = velocidad.get(r.id_seguidor)
            if not _cumple_cercania(r, v, u):
                continue
            activos.add(r.id_seguidor)
            tramo = abiertos.get(r.id_seguidor)
            continua = (
                tramo is not None
                and tramo.cuadro_ultimo == c.cuadro - 1
                and tramo.id_predecesor == r.id_predecesor
            )
            if tramo is not None and not continua:
                cerrar(r.id_seguidor)
            if continua:
                tramo.cuadro_ultimo = c.cuadro
                tramo.t_ultimo = c.t
            else:
                abiertos[r.id_seguidor] = _Tramo(r.id_predecesor, c.cuadro, c.t, c.t)
        for id_vehiculo in [i for i in abiertos if i not in activos]:
            cerrar(id_vehiculo)
    for id_vehiculo in list(abiertos):
        cerrar(id_vehiculo)
    return eventos


def _cumple_cercania(r: Relacion, v: Optional[float], u: Umbrales) -> bool:
    return (
        r.id_predecesor is not None
        and v is not None
        and r.thw is not None
        and v > u.cercania_velocidad_min
        and r.thw < u.cercania_thw_max
    )


def _zigzag(cambios: list[CambioCarril], u: Umbrales) -> list[EventoReferencia]:
    """RF8: al menos N cambios completos con cruces dentro de la ventana.

    Ventanas que se solapan en el mismo vehiculo forman un solo evento.
    """
    por_vehiculo: dict[int, list[CambioCarril]] = {}
    for cambio in cambios:
        por_vehiculo.setdefault(cambio.id_vehiculo, []).append(cambio)

    eventos: list[EventoReferencia] = []
    for id_vehiculo, lista in por_vehiculo.items():
        lista.sort(key=lambda c: c.t_cruce)
        actual: Optional[EventoReferencia] = None
        for i, cambio in enumerate(lista):
            ventana = [
                c for c in lista[: i + 1]
                if cambio.t_cruce - c.t_cruce <= u.zigzag_ventana + _EPS
            ]
            if len(ventana) < u.zigzag_cambios_min:
                continue
            inicio, fin = ventana[0].t_cruce, cambio.t_confirmacion
            if actual is not None and inicio <= actual.t_fin + _EPS:
                actual = EventoReferencia(id_vehiculo, Regla.ZIGZAG, actual.t_inicio, fin)
            else:
                if actual is not None:
                    eventos.append(actual)
                actual = EventoReferencia(id_vehiculo, Regla.ZIGZAG, inicio, fin)
        if actual is not None:
            eventos.append(actual)
    return eventos


def _corte(
    cuadros: list[CuadroReferencia], cambios: list[CambioCarril], u: Umbrales
) -> list[EventoReferencia]:
    """RF9: tras un cambio, el nuevo seguidor queda con THW o TTC bajo umbral.

    El nuevo seguidor es el primer vehiculo observado detras del que cambio,
    en el carril de destino, dentro de la ventana posterior al cruce.
    """
    tiempos = [c.t for c in cuadros]
    eventos: list[EventoReferencia] = []
    for cambio in cambios:
        fin_ventana = cambio.t_cruce + u.corte_ventana_post_cambio + _EPS
        seguidor: Optional[int] = None
        t_ultima_falta: Optional[float] = None
        for c in cuadros[bisect_left(tiempos, cambio.t_cruce - _EPS):]:
            if c.t > fin_ventana:
                break
            for r in c.relaciones:
                if r.id_predecesor != cambio.id_vehiculo or r.carril != cambio.carril_destino:
                    continue
                if seguidor is None:
                    seguidor = r.id_seguidor
                if r.id_seguidor != seguidor:
                    continue
                thw_bajo = r.thw is not None and r.thw < u.corte_thw_max
                ttc_bajo = r.ttc is not None and r.ttc < u.corte_ttc_max
                if thw_bajo or ttc_bajo:
                    t_ultima_falta = c.t
        if seguidor is not None and t_ultima_falta is not None:
            eventos.append(
                EventoReferencia(
                    cambio.id_vehiculo, Regla.CORTE, cambio.t_cruce, t_ultima_falta, seguidor
                )
            )
    return eventos
