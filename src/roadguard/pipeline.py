"""Integracion end-to-end de RoadGuard: de MP4 + YAML a MP4 anotado, CSV y JSON.

Por cada cuadro, en orden temporal estricto (RF5, Paso 2):

    leer -> detectar -> seguir -> proyectar al camino -> carril y estado
    cinematico -> relaciones (THW/TTC) -> reglas y puntaje -> anotar -> escribir

El motor de reglas se inyecta. Debe cumplir la interfaz `MotorReglas`:

    actualizar(t, estados, relaciones, cambios) -> (eventos, puntajes)
    finalizar() -> eventos

donde `eventos` son los eventos CONFIRMADOS y cerrados en ese cuadro (cada
uno se entrega una sola vez; van al CSV) y `puntajes` es el puntaje RF10/RF11
vigente por vehiculo (va al video). El motor por defecto es `m4_reglas.motor.MotorReglas`
(RF7 a RF11). `MotorCercania` queda como motor minimo de respaldo y para
pruebas: envuelve `DetectorCercania` (RF7) y
acumula el puntaje con los umbrales RF10/RF11 de `tipos.Umbrales`.

Sin calibracion (sin homografia) el pipeline no se detiene: se mantienen
cajas, ID, carril y una advertencia visible; distancia, THW y TTC quedan en
None y las reglas que dependen de ellos no producen eventos (Paso 5).
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
import time
from dataclasses import dataclass, field
from typing import Iterable, Optional, Protocol

from roadguard.m1_ingesta.config import (
    ADVERTENCIA_SIN_CALIBRACION_CORTA,
    validar_consistencia,
)
from roadguard.m1_ingesta.video import iterar_cuadros, leer_metadatos
from roadguard.m2_deteccion.tracker import SeguidorByteTrack
from roadguard.m3_geometria.carriles import DetectorCambioCarril
from roadguard.m3_geometria.homografia import ProyectorCamino
from roadguard.m3_geometria.relaciones import calcular_relaciones
from roadguard.m3_geometria.trayectorias import HistorialCausal
from roadguard.m4_reglas.cercania import DetectorCercania
from roadguard.m4_reglas.motor import MotorReglas as MotorReglasM4
from roadguard.m5_salidas.dibujo import anotar_cuadro
from roadguard.m5_salidas.escritor import EscritorVideo
from roadguard.m5_salidas.exportar import (
    EscritorTracks,
    escribir_eventos_csv,
    escribir_resumen_json,
)
from roadguard.tipos import (
    CambioCarril,
    Configuracion,
    Deteccion,
    EstadoCinematico,
    Evento,
    MetadatosVideo,
    NivelRiesgo,
    PuntajeRiesgo,
    Regla,
    Relacion,
    ResumenEjecucion,
    ResumenVehiculo,
    Track,
    Umbrales,
)

NOMBRE_VIDEO = "anotado.mp4"
NOMBRE_EVENTOS = "eventos.csv"
NOMBRE_RESUMEN = "resumen.json"
NOMBRE_TRACKS = "tracks.csv"


class Detector(Protocol):
    """Lo que el pipeline necesita de M2: detecciones por imagen."""

    def detectar(self, imagen: object) -> list[Deteccion]: ...


class MotorReglas(Protocol):
    """Interfaz del motor de reglas (M4) que consume el pipeline."""

    def actualizar(
        self,
        t: float,
        estados: dict[int, EstadoCinematico],
        relaciones: list[Relacion],
        cambios: list[CambioCarril],
    ) -> tuple[list[Evento], dict[int, PuntajeRiesgo]]: ...

    def finalizar(self) -> list[Evento]: ...


def nivel_por_puntaje(puntaje: int, umbrales: Umbrales) -> NivelRiesgo:
    """Banda RF11 de un puntaje: verde, amarillo o rojo."""
    if puntaje <= umbrales.banda_verde_max:
        return NivelRiesgo.VERDE
    if puntaje <= umbrales.banda_amarillo_max:
        return NivelRiesgo.AMARILLO
    return NivelRiesgo.ROJO


class MotorCercania:
    """Motor minimo: RF7 (cercania) mas puntaje RF10 y bandas RF11.

    Puntaje (RF10): cada tramo de cercania confirmado aporta
    `aporte_cercania` mientras esta activo y su aporte caduca
    `vigencia_aporte` segundos despues de su ultima observacion; la suma se
    acota a `puntaje_maximo`. Un mismo tramo cuenta una sola vez aunque se
    observe en muchos cuadros. Zigzag (RF8) y corte (RF9) no se evaluan aca:
    `cambios` se acepta por contrato y se ignora.

    Devuelve un puntaje para cada vehiculo presente en `estados`. Las
    advertencias de RF7 se acumulan sin repetir en `advertencias`.
    """

    def __init__(self, umbrales: Optional[Umbrales] = None) -> None:
        self.umbrales = umbrales if umbrales is not None else Umbrales()
        self._detector = DetectorCercania(self.umbrales)
        self._cuadro = -1
        # id_vehiculo -> {(regla, t_inicio): (t_caducidad, aporte)}
        self._aportes: dict[int, dict[tuple[str, float], tuple[float, int]]] = {}
        self.advertencias: list[str] = []

    def actualizar(
        self,
        t: float,
        estados: dict[int, EstadoCinematico],
        relaciones: list[Relacion],
        cambios: list[CambioCarril],
    ) -> tuple[list[Evento], dict[int, PuntajeRiesgo]]:
        lista_estados = list(estados.values())
        cuadro = lista_estados[0].cuadro if lista_estados else self._cuadro + 1
        self._cuadro = cuadro
        resultado = self._detector.actualizar(cuadro, t, lista_estados, relaciones)
        for adv in resultado.advertencias:
            if adv not in self.advertencias:
                self.advertencias.append(adv)
        for ev in resultado.activos:
            clave = (ev.regla.value, ev.t_inicio)
            self._aportes.setdefault(ev.id_vehiculo, {})[clave] = (
                ev.t_fin + self.umbrales.vigencia_aporte,
                ev.aporte_puntaje,
            )
        puntajes = {ident: self._puntaje(ident, t) for ident in estados}
        return list(resultado.cerrados), puntajes

    def finalizar(self) -> list[Evento]:
        return self._detector.finalizar()

    def _puntaje(self, ident: int, t: float) -> PuntajeRiesgo:
        vigentes = {
            k: v for k, v in self._aportes.get(ident, {}).items() if t <= v[0]
        }
        if vigentes:
            self._aportes[ident] = vigentes
        else:
            self._aportes.pop(ident, None)
        total = min(self.umbrales.puntaje_maximo, sum(a for _, a in vigentes.values()))
        return PuntajeRiesgo(ident, t, total, nivel_por_puntaje(total, self.umbrales))


@dataclass
class _Acumulado:
    clase: str
    t_primera: float
    t_ultima: float
    n_eventos: dict[str, int] = field(default_factory=dict)
    puntaje_maximo: int = 0
    nivel_maximo: NivelRiesgo = NivelRiesgo.VERDE


@dataclass
class ResultadoPipeline:
    """Lo que devuelve `Pipeline.ejecutar`, ademas de los archivos en disco."""

    resumen: ResumenEjecucion
    vehiculos: list[ResumenVehiculo]
    eventos: list[Evento]
    ruta_video: Optional[str]
    ruta_eventos: str
    ruta_resumen: str
    ruta_tracks: Optional[str] = None


class Pipeline:
    """Encadena M1 a M5 sobre un video y escribe las tres salidas (RF12).

    `detector` se inyecta para poder correr sin YOLO en las pruebas. `motor`
    debe cumplir `MotorReglas`; por defecto es `m4_reglas.motor.MotorReglas`
    (RF7 a RF11). Ante Ctrl+C la corrida se corta, pero las salidas se
    escriben con lo procesado y `completada=False`.
    """

    def __init__(
        self,
        cfg: Configuracion,
        detector: Detector,
        motor: Optional[MotorReglas] = None,
        version_modelo: Optional[str] = None,
        ruta_config: Optional[str] = None,
    ) -> None:
        self.cfg = cfg
        self.detector = detector
        self.motor: MotorReglas = motor if motor is not None else MotorReglasM4(cfg.umbrales)
        self.version_modelo = version_modelo or getattr(
            detector, "version_modelo", type(detector).__name__
        )
        self.ruta_config = ruta_config
        self.proyector = ProyectorCamino(cfg.homografia)

    def ejecutar(
        self,
        ruta_video: str,
        dir_salida: str,
        max_cuadros: Optional[int] = None,
        escribir_video: bool = True,
        escribir_tracks: bool = False,
    ) -> ResultadoPipeline:
        """Procesa el video completo (o `max_cuadros`) y escribe las salidas.

        Con `escribir_tracks` se agrega `tracks.csv` (una fila por vehiculo y
        cuadro) para evaluar deteccion y seguimiento contra una referencia.
        """
        metadatos = leer_metadatos(ruta_video)
        os.makedirs(dir_salida, exist_ok=True)
        ruta_anotado = os.path.join(dir_salida, NOMBRE_VIDEO) if escribir_video else None
        ruta_eventos = os.path.join(dir_salida, NOMBRE_EVENTOS)
        ruta_resumen = os.path.join(dir_salida, NOMBRE_RESUMEN)
        ruta_tracks = os.path.join(dir_salida, NOMBRE_TRACKS) if escribir_tracks else None

        advertencias = validar_consistencia(self.cfg)
        if not self.proyector.disponible and self.proyector.motivo_no_disponible:
            motivo = f"Proyeccion al camino no disponible: {self.proyector.motivo_no_disponible}"
            if motivo not in advertencias:
                advertencias.append(motivo)
        rotulo = None if self.proyector.disponible else ADVERTENCIA_SIN_CALIBRACION_CORTA

        seguidor = SeguidorByteTrack(fps=metadatos.fps)
        historial = HistorialCausal(metadatos.fps, self.proyector, self.cfg.carriles)
        cambios_carril = DetectorCambioCarril(
            self.cfg.confianza_min_carril, self.cfg.permanencia_cambio_carril
        )
        acumulados: dict[int, _Acumulado] = {}
        eventos: list[Evento] = []
        tiempos = {"deteccion": 0.0, "seguimiento": 0.0, "geometria": 0.0, "reglas": 0.0, "salidas": 0.0}
        n_cuadros = 0
        completada = False
        escritor = EscritorVideo.desde_metadatos(ruta_anotado, metadatos) if ruta_anotado else None
        escritor_tracks = EscritorTracks(ruta_tracks) if ruta_tracks else None
        inicio = time.perf_counter()
        try:
            try:
                for cuadro, t, imagen in iterar_cuadros(ruta_video):
                    if max_cuadros is not None and cuadro >= max_cuadros:
                        break
                    tracks, estados, relaciones, cambios, puntajes, cerrados = self._procesar_cuadro(
                        cuadro, t, imagen, seguidor, historial, cambios_carril, tiempos
                    )
                    eventos.extend(cerrados)
                    self._acumular(acumulados, tracks, puntajes)
                    if escritor_tracks is not None:
                        escritor_tracks.escribir(tracks, estados)
                    if escritor is not None:
                        t0 = time.perf_counter()
                        anotado = anotar_cuadro(
                            imagen, tracks, estados, self.cfg.carriles, rotulo, puntajes
                        )
                        escritor.escribir(anotado)
                        tiempos["salidas"] += time.perf_counter() - t0
                    n_cuadros += 1
                completada = True
            except KeyboardInterrupt:
                # Ctrl+C (por ejemplo, en la demo en vivo): se conserva lo
                # procesado. Los eventos abiertos se cierran y las salidas se
                # escriben igual, marcadas como corrida incompleta.
                advertencias.append(
                    f"Corrida interrumpida por el usuario tras {n_cuadros} cuadros; "
                    "salidas parciales"
                )
            eventos.extend(self.motor.finalizar())
        finally:
            if escritor is not None:
                escritor.cerrar()
            if escritor_tracks is not None:
                escritor_tracks.cerrar()
        duracion = time.perf_counter() - inicio

        for ev in eventos:
            acumulado = acumulados.get(ev.id_vehiculo)
            if acumulado is not None:
                acumulado.n_eventos[ev.regla.value] = acumulado.n_eventos.get(ev.regla.value, 0) + 1
        for adv in getattr(self.motor, "advertencias", []):
            if adv not in advertencias:
                advertencias.append(adv)
        if historial.reinicios:
            advertencias.append(
                f"Historial reiniciado por identidad dudosa en {len(historial.reinicios)} "
                "ocasiones (riesgos 4.4)"
            )

        vehiculos = [
            ResumenVehiculo(
                id_vehiculo=ident,
                clase=a.clase,
                t_primera_aparicion=a.t_primera,
                t_ultima_aparicion=a.t_ultima,
                n_eventos=dict(sorted(a.n_eventos.items())),
                puntaje_maximo=a.puntaje_maximo,
                nivel_maximo=a.nivel_maximo,
            )
            for ident, a in sorted(acumulados.items())
        ]
        resumen = ResumenEjecucion(
            video=metadatos.ruta,
            configuracion=self.ruta_config or "",
            version_modelo=self.version_modelo,
            fps_video=metadatos.fps,
            fps_procesamiento=n_cuadros / duracion if duracion > 0 else 0.0,
            n_cuadros_procesados=n_cuadros,
            calibrado=self.proyector.disponible,
            advertencias=advertencias,
            configuracion_sha256=_sha256_archivo(self.ruta_config),
            parametros=dataclasses.asdict(self.cfg),
            n_eventos=conteo_por_regla(eventos),
            fps_por_etapa={
                etapa: (n_cuadros / s if s > 0 else 0.0) for etapa, s in tiempos.items()
            },
            completada=completada,
        )
        escribir_eventos_csv(ruta_eventos, eventos)
        escribir_resumen_json(ruta_resumen, resumen, vehiculos)
        return ResultadoPipeline(
            resumen, vehiculos, eventos, ruta_anotado, ruta_eventos, ruta_resumen, ruta_tracks
        )

    def _procesar_cuadro(
        self,
        cuadro: int,
        t: float,
        imagen: object,
        seguidor: SeguidorByteTrack,
        historial: HistorialCausal,
        cambios_carril: DetectorCambioCarril,
        tiempos: dict[str, float],
    ) -> tuple[
        list[Track], list[EstadoCinematico], list[Relacion], list[CambioCarril],
        dict[int, PuntajeRiesgo], list[Evento],
    ]:
        t0 = time.perf_counter()
        detecciones = self.detector.detectar(imagen)
        t1 = time.perf_counter()
        tracks = seguidor.actualizar(detecciones, cuadro, t)
        t2 = time.perf_counter()

        estados: list[EstadoCinematico] = []
        cambios: list[CambioCarril] = []
        for track in tracks:
            estado = historial.actualizar(track)
            estados.append(estado)
            cambio = cambios_carril.actualizar(
                track.id_vehiculo, estado.carril, t, estado.confianza_carril
            )
            if cambio is not None:
                cambios.append(cambio)
        for ident in historial.purgar(t):
            cambios_carril.olvidar(ident)
        relaciones = calcular_relaciones(estados, cuadro, t)
        t3 = time.perf_counter()

        cerrados, puntajes = self.motor.actualizar(
            t, {e.id_vehiculo: e for e in estados}, relaciones, cambios
        )
        t4 = time.perf_counter()
        tiempos["deteccion"] += t1 - t0
        tiempos["seguimiento"] += t2 - t1
        tiempos["geometria"] += t3 - t2
        tiempos["reglas"] += t4 - t3
        return tracks, estados, relaciones, cambios, puntajes, cerrados

    @staticmethod
    def _acumular(
        acumulados: dict[int, _Acumulado],
        tracks: Iterable[Track],
        puntajes: dict[int, PuntajeRiesgo],
    ) -> None:
        for track in tracks:
            a = acumulados.get(track.id_vehiculo)
            if a is None:
                a = _Acumulado(track.clase, track.t, track.t)
                acumulados[track.id_vehiculo] = a
            a.clase = track.clase
            a.t_ultima = track.t
            p = puntajes.get(track.id_vehiculo)
            if p is not None and p.puntaje >= a.puntaje_maximo:
                a.puntaje_maximo = p.puntaje
                a.nivel_maximo = p.nivel


def conteo_por_regla(eventos: Iterable[Evento]) -> dict[str, int]:
    """Cantidad de eventos por regla, con las tres reglas siempre presentes."""
    conteo = {r.value: 0 for r in Regla}
    for ev in eventos:
        conteo[ev.regla.value] = conteo.get(ev.regla.value, 0) + 1
    return conteo


def _sha256_archivo(ruta: Optional[str]) -> str:
    if not ruta or not os.path.isfile(ruta):
        return ""
    with open(ruta, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()
