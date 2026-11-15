"""Perfila el pipeline completo por etapa, a la resolucion que pide la propuesta.

El criterio de rendimiento (§2.5) es **>= 15 FPS a 720p en Colab T4**.
UA-DETRAC es 960x540, asi que este script escala el video a 1280x720 (o al
alto que se pida) y escala la configuracion en la misma proporcion: region de
interes, poligonos de carril y `homografia.puntos_imagen`. Los puntos del
camino quedan en metros, sin cambios, de modo que la geometria es la misma.
El procedimiento de escalado se declara en el informe (PRD de datos, §5).

Uso, desde la raiz del repo (en Colab, igual desde la carpeta del repo):

    python scripts/perfilar_fps.py --video datos/videos/MVI_39271.mp4 \\
        --config configs/MVI_39271.yaml --alto 720 --dispositivo cuda

Opciones utiles: `--max-cuadros 500` (por defecto, el video completo),
`--alto 0` (sin escalar), `--sin-video` (no escribe el MP4 anotado),
`--pesos datos/modelos/yolov8n.pt`.

Antes de medir hace una inferencia de calentamiento, para que la carga del
modelo y la inicializacion de CUDA o MPS no se cuenten como deteccion.
Imprime una tabla por etapa (ms por cuadro y FPS) y escribe `perfil.json` en
`--salida` con la maquina, el dispositivo, la resolucion y los tiempos.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path

import cv2
import yaml

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from roadguard.m1_ingesta.config import cargar_configuracion  # noqa: E402
from roadguard.m1_ingesta.video import leer_metadatos  # noqa: E402
from roadguard.pipeline import Pipeline  # noqa: E402

OBJETIVO_FPS = 15.0
ETAPAS = ("deteccion", "seguimiento", "geometria", "reglas", "salidas")


def _escalar_puntos(puntos, factor: float):
    return [[round(x * factor, 2), round(y * factor, 2)] for x, y in puntos]


def escalar_config(datos: dict, factor: float) -> dict:
    """Copia de la configuracion con las coordenadas de imagen escaladas."""
    datos = json.loads(json.dumps(datos))  # copia profunda de tipos YAML simples
    if "region_interes" in datos:
        datos["region_interes"] = _escalar_puntos(datos["region_interes"], factor)
    for carril in datos.get("carriles", []):
        carril["poligono"] = _escalar_puntos(carril["poligono"], factor)
    homografia = datos.get("homografia")
    if homografia and homografia.get("puntos_imagen"):
        homografia["puntos_imagen"] = _escalar_puntos(homografia["puntos_imagen"], factor)
    return datos


def escalar_video(origen: str, destino: str, alto: int, max_cuadros: int | None) -> tuple[int, int]:
    """Escribe `destino` reescalado a `alto` px conservando aspecto y FPS."""
    meta = leer_metadatos(origen)
    ancho = int(round(meta.ancho * alto / meta.alto))
    ancho += ancho % 2
    captura = cv2.VideoCapture(origen)
    escritor = cv2.VideoWriter(destino, cv2.VideoWriter_fourcc(*"mp4v"), meta.fps, (ancho, alto))
    n = 0
    try:
        while max_cuadros is None or n < max_cuadros:
            ok, imagen = captura.read()
            if not ok:
                break
            escritor.write(cv2.resize(imagen, (ancho, alto), interpolation=cv2.INTER_LINEAR))
            n += 1
    finally:
        captura.release()
        escritor.release()
    return ancho, alto


def _dispositivo_real(dispositivo: str | None) -> str:
    try:
        import torch
    except ImportError:  # pragma: no cover
        return dispositivo or "desconocido"
    if dispositivo:
        nombre = dispositivo
    elif torch.cuda.is_available():
        nombre = "cuda"
    elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        nombre = "mps"
    else:
        nombre = "cpu"
    if nombre.startswith("cuda") and torch.cuda.is_available():
        return f"cuda ({torch.cuda.get_device_name(0)})"
    return nombre


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--video", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--salida", default="salidas/perfil")
    parser.add_argument("--alto", type=int, default=720, help="Alto objetivo en px; 0 = sin escalar")
    parser.add_argument("--pesos", default="yolov8n.pt")
    parser.add_argument("--dispositivo", default=None, help="cpu, cuda, cuda:0 o mps")
    parser.add_argument("--max-cuadros", type=int, default=None)
    parser.add_argument("--sin-video", action="store_true", help="No escribir el MP4 anotado")
    args = parser.parse_args(argv)

    os.makedirs(args.salida, exist_ok=True)
    meta = leer_metadatos(args.video)
    video, ruta_cfg = args.video, args.config
    if args.alto and args.alto != meta.alto:
        factor = args.alto / meta.alto
        nombre = Path(args.video).stem
        video = os.path.join(args.salida, f"{nombre}_{args.alto}p.mp4")
        ancho, _ = escalar_video(args.video, video, args.alto, args.max_cuadros)
        with open(args.config, encoding="utf-8") as f:
            datos = yaml.safe_load(f)
        ruta_cfg = os.path.join(args.salida, f"{Path(args.config).stem}_{args.alto}p.yaml")
        with open(ruta_cfg, "w", encoding="utf-8") as f:
            yaml.safe_dump(escalar_config(datos, factor), f, allow_unicode=True, sort_keys=False)
        print(f"Video escalado a {ancho}x{args.alto} (factor {factor:.4f}): {video}")

    from roadguard.m2_deteccion.detector import DetectorVehiculos

    cfg = cargar_configuracion(ruta_cfg)
    detector = DetectorVehiculos(cfg, pesos=args.pesos, dispositivo=args.dispositivo)
    captura = cv2.VideoCapture(video)
    ok, primero = captura.read()
    captura.release()
    if not ok:
        print(f"No se pudo leer el primer cuadro de {video}", file=sys.stderr)
        return 1
    t0 = time.perf_counter()
    for _ in range(3):
        detector.detectar(primero)
    calentamiento = time.perf_counter() - t0

    inicio = time.perf_counter()
    resultado = Pipeline(cfg, detector, ruta_config=ruta_cfg).ejecutar(
        video, args.salida, max_cuadros=args.max_cuadros, escribir_video=not args.sin_video
    )
    pared = time.perf_counter() - inicio
    r = resultado.resumen
    n = r.n_cuadros_procesados
    ms = {e: (1000.0 / r.fps_por_etapa[e] if r.fps_por_etapa.get(e) else 0.0) for e in ETAPAS}
    ms_total = 1000.0 / r.fps_procesamiento if r.fps_procesamiento else 0.0
    ms["lectura y otros"] = max(0.0, ms_total - sum(ms.values()))

    meta_proc = leer_metadatos(video)
    dispositivo = _dispositivo_real(args.dispositivo)
    print(f"\nMaquina: {platform.platform()} · {platform.processor() or platform.machine()}")
    print(f"Dispositivo: {dispositivo} · {r.version_modelo}")
    print(f"Video: {meta_proc.ancho}x{meta_proc.alto} a {meta_proc.fps:g} FPS · {n} cuadros")
    print(f"Calentamiento (3 inferencias, no se cuenta): {calentamiento:.2f} s\n")
    print(f"{'Etapa':<18}{'ms/cuadro':>10}{'FPS':>10}")
    for etapa, valor in ms.items():
        fps = 1000.0 / valor if valor > 0 else float("inf")
        print(f"{etapa:<18}{valor:>10.2f}{fps:>10.1f}")
    print(f"{'TOTAL':<18}{ms_total:>10.2f}{r.fps_procesamiento:>10.1f}")
    cumple = r.fps_procesamiento >= OBJETIVO_FPS
    print(f"\nObjetivo >= {OBJETIVO_FPS:g} FPS: {'CUMPLE' if cumple else 'NO CUMPLE'}")

    perfil = {
        "maquina": platform.platform(),
        "procesador": platform.processor() or platform.machine(),
        "python": platform.python_version(),
        "dispositivo": dispositivo,
        "modelo": r.version_modelo,
        "video_original": args.video,
        "video_medido": video,
        "resolucion": [meta_proc.ancho, meta_proc.alto],
        "escribe_video": not args.sin_video,
        "n_cuadros": n,
        "segundos_pared": round(pared, 3),
        "calentamiento_s": round(calentamiento, 3),
        "fps_total": round(r.fps_procesamiento, 2),
        "ms_por_etapa": {k: round(v, 3) for k, v in ms.items()},
        "fps_por_etapa": {k: round(v, 1) for k, v in r.fps_por_etapa.items()},
        "objetivo_fps": OBJETIVO_FPS,
        "cumple": cumple,
        "eventos": r.n_eventos,
    }
    with open(os.path.join(args.salida, "perfil.json"), "w", encoding="utf-8") as f:
        json.dump(perfil, f, ensure_ascii=False, indent=2)
    print(f"Perfil: {os.path.join(args.salida, 'perfil.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
