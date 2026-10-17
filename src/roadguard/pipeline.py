"""Orquestacion de la cadena completa (seccion 4.3).

Secuencia de procesamiento y manejo de casos limite:

Paso 1. Validar video, FPS y YAML; rechazar configuraciones incoherentes
        antes de crear salidas.
Paso 2. Procesar cuadros en orden temporal y actualizar detecciones, tracks
        y estado geometrico sin acceder a cuadros futuros.
Paso 3. Calcular velocidad y metricas unicamente con historial suficiente;
        representar como no disponible cualquier division invalida o
        ausencia de predecesor.
Paso 4. Confirmar un cambio de carril solo tras permanencia estable en el
        nuevo carril.
Paso 5. Suspender o degradar alertas dependientes de distancia cuando no
        exista calibracion metrica, manteniendo deteccion, seguimiento y una
        advertencia visible.
Paso 6. Cerrar archivos de salida de forma segura e incluir configuracion,
        version del modelo, FPS y resumen de eventos para reproducibilidad.
"""

from __future__ import annotations

import hashlib
import os
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from typing import Optional, Protocol

from roadguard.m1_ingesta.config import (
    ADVERTENCIA_SIN_CALIBRACION,
    ADVERTENCIA_SIN_CALIBRACION_CORTA,
    cargar_configuracion,
    validar_consistencia,
)
from roadguard.m1_ingesta.video import iterar_cuadros, leer_metadatos
from roadguard.m2_deteccion.tracker import SeguidorByteTrack
from roadguard.m3_geometria.carriles import DetectorCambioCarril
from roadguard.m3_geometria.homografia import ProyectorCamino
from roadguard.m3_geometria.relaciones import calcular_relaciones
from roadguard.m3_geometria.trayectorias import HistorialCausal
from roadguard.m4_reglas.motor import MotorReglas
from roadguard.m4_reglas.puntaje import nivel_desde_puntaje
from roadguard.m5_salidas.anotacion import AnotadorVideo
from roadguard.m5_salidas.registros import exportar_eventos_csv, exportar_resumen_json
from roadguard.m6_evaluacion.rendimiento import medir_fps
from roadguard.tipos import Deteccion, Evento, Regla, ResumenEjecucion, ResumenVehiculo

NOMBRE_VIDEO = "video_anotado.mp4"
NOMBRE_EVENTOS = "eventos.csv"
NOMBRE_RESUMEN = "resumen.json"


class Detector(Protocol):
    version_modelo: str

    def detectar(self, imagen: "object") -> list[Deteccion]: ...


def ejecutar(
    ruta_video: str,
    ruta_config: str,
    directorio_salida: str,
    detector: Optional[Detector] = None,
    pesos: str = "yolov8n.pt",
    dispositivo: Optional[str] = None,
) -> ResumenEjecucion:
    """Proceso por lotes: MP4 + YAML -> MP4 anotado + CSV + JSON (seccion 1.3).

    Orden de la cadena (seccion 1.3):
        M1 ingesta -> M2 deteccion/seguimiento -> M3 geometria y relaciones
        -> M4 reglas y puntaje -> M5 video anotado y registros.

    `detector` permite inyectar un detector alternativo (pruebas o modelos
    reentrenados); por defecto se usa YOLOv8n con `pesos`.
    """
    # Paso 1: todo se valida antes de crear cualquier salida.
    cfg = cargar_configuracion(ruta_config)
    meta = leer_metadatos(ruta_video)
    advertencias = validar_consistencia(cfg)
    proyector = ProyectorCamino(cfg.homografia)
    if cfg.homografia.disponible and not proyector.disponible:
        advertencias.insert(0, ADVERTENCIA_SIN_CALIBRACION)
        advertencias.append(f"Homografia no utilizable: {proyector.motivo_no_disponible}")
    if detector is None:
        from roadguard.m2_deteccion.detector import DetectorVehiculos

        detector = DetectorVehiculos(cfg, pesos=pesos, dispositivo=dispositivo)
    version_modelo = getattr(detector, "version_modelo", type(detector).__name__)
    with open(ruta_config, "rb") as f:
        sha_config = hashlib.sha256(f.read()).hexdigest()

    os.makedirs(directorio_salida, exist_ok=True)
    ruta_mp4 = os.path.join(directorio_salida, NOMBRE_VIDEO)
    ruta_csv = os.path.join(directorio_salida, NOMBRE_EVENTOS)
    ruta_json = os.path.join(directorio_salida, NOMBRE_RESUMEN)

    seguidor = SeguidorByteTrack(meta.fps)
    historial = HistorialCausal(meta.fps, proyector, cfg.carriles)
    detector_cambios = DetectorCambioCarril(cfg.confianza_min_carril, cfg.permanencia_cambio_carril)
    motor = MotorReglas(cfg.umbrales)
    en_pantalla = [
        ADVERTENCIA_SIN_CALIBRACION_CORTA if a == ADVERTENCIA_SIN_CALIBRACION else a
        for a in advertencias
    ]

    eventos: list[Evento] = []
    vigentes: list[Evento] = []
    tiempos: dict[str, list[float]] = defaultdict(list)
    vehiculos: dict[int, dict] = {}
    n_cuadros = 0
    completada = False
    t_reloj = time.perf_counter()

    anotador = AnotadorVideo(ruta_mp4, meta)
    try:
        lector = iterar_cuadros(ruta_video)
        while True:
            r0 = time.perf_counter()
            siguiente = next(lector, None)
            if siguiente is None:
                break
            cuadro, t, imagen = siguiente
            r1 = time.perf_counter()

            # M2
            detecciones = detector.detectar(imagen)
            r2 = time.perf_counter()
            tracks = seguidor.actualizar(detecciones, cuadro, t)
            r3 = time.perf_counter()

            # M3: estado causal, cambios completos y relaciones
            estados = [historial.actualizar(tr) for tr in tracks]
            for id_dudoso in historial.reinicios:
                detector_cambios.olvidar(id_dudoso)
                motor.olvidar(id_dudoso)
            historial.reinicios.clear()
            for id_perdido in historial.purgar(t):
                detector_cambios.olvidar(id_perdido)
            cambios = []
            for e in estados:
                cambio = detector_cambios.actualizar(e.id_vehiculo, e.carril, t, e.confianza_carril)
                if cambio is not None:
                    cambios.append(cambio)
            relaciones = calcular_relaciones(estados, cuadro, t)
            r4 = time.perf_counter()

            # M4
            nuevos = motor.procesar_cuadro(t, estados, relaciones, cambios)
            eventos.extend(nuevos)
            puntajes = motor.puntajes([tr.id_vehiculo for tr in tracks], t)
            vigentes = [e for e in vigentes + nuevos if t - e.t_fin < cfg.umbrales.vigencia_aporte]
            r5 = time.perf_counter()

            # M5
            anotador.escribir_cuadro(imagen, tracks, puntajes, vigentes, en_pantalla)
            r6 = time.perf_counter()

            for tr in tracks:
                v = vehiculos.setdefault(
                    tr.id_vehiculo,
                    {"clases": Counter(), "t_primera": t, "t_ultima": t, "puntaje_max": 0},
                )
                v["clases"][tr.clase] += 1
                v["t_ultima"] = t
                v["puntaje_max"] = max(v["puntaje_max"], puntajes[tr.id_vehiculo].puntaje)

            for etapa, dt in (
                ("lectura", r1 - r0),
                ("deteccion", r2 - r1),
                ("seguimiento", r3 - r2),
                ("geometria", r4 - r3),
                ("reglas", r5 - r4),
                ("anotacion", r6 - r5),
            ):
                tiempos[etapa].append(dt)
            n_cuadros += 1
        completada = True
    finally:
        # Paso 6: cerrar y dejar evidencia incluso si la corrida falla.
        anotador.cerrar()
        duracion = time.perf_counter() - t_reloj
        if not completada:
            advertencias.append(
                f"Ejecucion interrumpida tras {n_cuadros} cuadros: salidas parciales."
            )
        n_eventos = {r.value: sum(1 for e in eventos if e.regla is r) for r in Regla}
        parametros = _limpiar_dict(asdict(cfg))
        parametros["error_reproyeccion_m"] = proyector.error_reproyeccion
        parametros["ruta_config"] = os.path.abspath(ruta_config)
        ejecucion = ResumenEjecucion(
            video=os.path.abspath(ruta_video),
            configuracion=os.path.abspath(ruta_config),
            version_modelo=version_modelo,
            fps_video=meta.fps,
            fps_procesamiento=n_cuadros / duracion if duracion > 0 else 0.0,
            n_cuadros_procesados=n_cuadros,
            calibrado=proyector.disponible,
            advertencias=advertencias,
            configuracion_sha256=sha_config,
            parametros=parametros,
            n_eventos=n_eventos,
            fps_por_etapa=medir_fps(dict(tiempos)),
            completada=completada,
        )
        resumenes = _resumenes_vehiculo(vehiculos, eventos, cfg.umbrales)
        try:
            exportar_eventos_csv(eventos, ruta_csv)
            exportar_resumen_json(resumenes, ejecucion, ruta_json)
        except Exception:
            if completada:
                raise
            # si ya hay una excepcion en curso, no se oculta con esta
    return ejecucion


def _resumenes_vehiculo(vehiculos: dict[int, dict], eventos: list[Evento], umbrales) -> list[ResumenVehiculo]:
    conteos: dict[int, Counter] = defaultdict(Counter)
    for e in eventos:
        conteos[e.id_vehiculo][e.regla.value] += 1
    resumenes = []
    for id_v, v in vehiculos.items():
        resumenes.append(
            ResumenVehiculo(
                id_vehiculo=id_v,
                clase=v["clases"].most_common(1)[0][0],
                t_primera_aparicion=v["t_primera"],
                t_ultima_aparicion=v["t_ultima"],
                n_eventos={r.value: conteos[id_v][r.value] for r in Regla},
                puntaje_maximo=v["puntaje_max"],
                nivel_maximo=nivel_desde_puntaje(v["puntaje_max"], umbrales),
            )
        )
    return resumenes


def _limpiar_dict(d):
    if isinstance(d, dict):
        return {k: _limpiar_dict(v) for k, v in d.items()}
    if isinstance(d, (list, tuple)):
        return [_limpiar_dict(v) for v in d]
    return d
