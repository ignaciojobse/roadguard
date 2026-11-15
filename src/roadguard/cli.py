"""Linea de comandos de RoadGuard.

    python -m roadguard procesar --video RUTA.mp4 --config RUTA.yaml --salida DIR
        [--pesos yolov8n.pt] [--max-cuadros N] [--sin-video] [--tracks]
        [--dispositivo cpu|cuda|mps]

Genera en DIR: anotado.mp4, eventos.csv y resumen.json (y tracks.csv con
--tracks), e imprime cuadros
procesados, FPS de procesamiento y eventos por regla. Las alertas son
experimentales y orientan la revision humana (seccion 1.1).
"""

from __future__ import annotations

import argparse
import sys
from typing import Callable, Optional, Sequence

from roadguard.m1_ingesta.config import ErrorConfiguracion, cargar_configuracion
from roadguard.m1_ingesta.video import ErrorVideo
from roadguard.m5_salidas.escritor import ErrorSalida
from roadguard.pipeline import Detector, Pipeline, ResultadoPipeline
from roadguard.tipos import Configuracion

FabricaDetector = Callable[[Configuracion, argparse.Namespace], Detector]


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="roadguard",
        description="Prototipo de apoyo para analizar patrones de conduccion en video de camara fija.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)
    p = sub.add_parser("procesar", help="Procesa un MP4 y escribe video anotado, CSV y JSON")
    p.add_argument("--video", required=True, help="Ruta al MP4 de entrada (RF1)")
    p.add_argument("--config", required=True, help="Ruta al YAML de la camara (RF1)")
    p.add_argument("--salida", required=True, help="Directorio de salida")
    p.add_argument("--pesos", default="yolov8n.pt", help="Pesos de YOLOv8 (por defecto yolov8n.pt)")
    p.add_argument("--max-cuadros", type=int, default=None, help="Procesar solo los primeros N cuadros")
    p.add_argument("--sin-video", action="store_true", help="No escribir anotado.mp4")
    p.add_argument(
        "--tracks", action="store_true",
        help="Escribir ademas tracks.csv (cuadro, id, clase, caja, carril y confianza) para evaluacion",
    )
    p.add_argument(
        "--dispositivo", choices=("cpu", "cuda", "mps"), default=None,
        help="Dispositivo de inferencia; por defecto lo elige Ultralytics",
    )
    return parser


def _detector_yolo(cfg: Configuracion, args: argparse.Namespace) -> Detector:
    from roadguard.m2_deteccion.detector import DetectorVehiculos

    return DetectorVehiculos(cfg, pesos=args.pesos, dispositivo=args.dispositivo)


def procesar(args: argparse.Namespace, fabrica_detector: FabricaDetector) -> ResultadoPipeline:
    cfg = cargar_configuracion(args.config)
    detector = fabrica_detector(cfg, args)
    pipeline = Pipeline(cfg, detector, ruta_config=args.config)
    return pipeline.ejecutar(
        args.video,
        args.salida,
        max_cuadros=args.max_cuadros,
        escribir_video=not args.sin_video,
        escribir_tracks=args.tracks,
    )


def imprimir_resumen(resultado: ResultadoPipeline, salida=None) -> None:
    salida = sys.stdout if salida is None else salida
    r = resultado.resumen
    print(f"Cuadros procesados: {r.n_cuadros_procesados}", file=salida)
    print(f"FPS de procesamiento: {r.fps_procesamiento:.2f} (video a {r.fps_video:.2f})", file=salida)
    print("Eventos por regla:", file=salida)
    for regla, n in r.n_eventos.items():
        print(f"  {regla}: {n}", file=salida)
    if not r.calibrado:
        print("SIN CALIBRACION: distancia, THW y TTC no disponibles (Paso 5)", file=salida)
    for adv in r.advertencias:
        print(f"Advertencia: {adv}", file=salida)
    print("Salidas:", file=salida)
    for ruta in (
        resultado.ruta_video, resultado.ruta_eventos, resultado.ruta_resumen, resultado.ruta_tracks
    ):
        if ruta:
            print(f"  {ruta}", file=salida)


def main(
    argv: Optional[Sequence[str]] = None,
    fabrica_detector: FabricaDetector = _detector_yolo,
) -> int:
    """Punto de entrada. `fabrica_detector` permite inyectar un detector falso."""
    args = construir_parser().parse_args(argv)
    if args.max_cuadros is not None and args.max_cuadros <= 0:
        print("--max-cuadros debe ser positivo", file=sys.stderr)
        return 2
    try:
        resultado = procesar(args, fabrica_detector)
    except (ErrorConfiguracion, ErrorVideo, ErrorSalida) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    imprimir_resumen(resultado)
    return 0
