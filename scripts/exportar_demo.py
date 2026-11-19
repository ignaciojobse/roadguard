"""Prepara los datos de la demo interactiva (`demo_web/`) para una o mas secuencias.

Si la secuencia no tiene una corrida con `estados.csv`, la hace (sin video
anotado, con `--tracks --estados`) y luego escribe
`demo_web/datos/<secuencia>.json`, que la pagina carga junto con los JPG
originales de `datos/ua-detrac/<secuencia>/`.

Uso, desde la raiz del repo:

    python scripts/exportar_demo.py MVI_39271 MVI_40243 MVI_40712 MVI_40714 MVI_40742
    python scripts/exportar_demo.py MVI_39271 --rehacer     # vuelve a correr el pipeline
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from roadguard.m1_ingesta.config import cargar_configuracion  # noqa: E402
from roadguard.m5_salidas.demo import construir_demo  # noqa: E402

DESTINO = RAIZ / "demo_web" / "datos"
# Orden y rotulos de las camaras en la pagina (titulo, subtitulo).
CAMARAS = {
    "MVI_39271": ("Día", "avenida · MVI_39271"),
    "MVI_40243": ("Autopista", "65 km/h · MVI_40243"),
    "MVI_40712": ("Semáforo", "cruce · MVI_40712"),
    "MVI_40714": ("Cola densa", "taco · MVI_40714"),
    "MVI_40742": ("Noche", "sin calibración · MVI_40742"),
}


def actualizar_indice() -> Path:
    """Escribe demo_web/datos/indice.json con las camaras que tienen datos."""
    disponibles = {p.stem for p in DESTINO.glob("MVI_*.json")}
    orden = [s for s in CAMARAS if s in disponibles] + sorted(disponibles - set(CAMARAS))
    indice = [
        {"secuencia": s, "titulo": CAMARAS.get(s, (s, ""))[0], "subtitulo": CAMARAS.get(s, ("", s))[1]}
        for s in orden
    ]
    ruta = DESTINO / "indice.json"
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False, indent=1)
    return ruta


def preparar(secuencia: str, rehacer: bool, pesos: str, dispositivo: str | None) -> Path:
    corrida = RAIZ / "salidas" / "demo_web" / secuencia
    if rehacer or not (corrida / "estados.csv").is_file():
        comando = [
            sys.executable, "-m", "roadguard", "procesar",
            "--video", str(RAIZ / "datos" / "videos" / f"{secuencia}.mp4"),
            "--config", str(RAIZ / "configs" / f"{secuencia}.yaml"),
            "--salida", str(corrida),
            "--pesos", pesos, "--sin-video", "--tracks", "--estados",
        ]
        if dispositivo:
            comando += ["--dispositivo", dispositivo]
        print(f"{secuencia}: corriendo el pipeline...", flush=True)
        entorno = {"PYTHONPATH": str(RAIZ / "src"), "YOLO_OFFLINE": "1"}
        import os
        subprocess.run(comando, check=True, cwd=RAIZ, env={**os.environ, **entorno})
        metricas = RAIZ / "salidas" / secuencia / "metricas.json"
        if metricas.is_file() and not (corrida / "metricas.json").is_file():
            (corrida / "metricas.json").write_bytes(metricas.read_bytes())
    cfg = cargar_configuracion(str(RAIZ / "configs" / f"{secuencia}.yaml"))
    documento = construir_demo(
        secuencia, cfg, corrida, f"../datos/ua-detrac/{secuencia}/img{{:05d}}.jpg"
    )
    DESTINO.mkdir(parents=True, exist_ok=True)
    salida = DESTINO / f"{secuencia}.json"
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(documento, f, ensure_ascii=False, separators=(",", ":"))
    tam = salida.stat().st_size / 1e6
    print(f"{secuencia}: {documento['n_cuadros']} cuadros, {len(documento['eventos'])} eventos -> {salida.relative_to(RAIZ)} ({tam:.1f} MB)")
    return salida


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("secuencias", nargs="+")
    parser.add_argument("--rehacer", action="store_true", help="Volver a correr el pipeline")
    parser.add_argument("--pesos", default=str(RAIZ / "datos" / "modelos" / "yolov8n.pt"))
    parser.add_argument("--dispositivo", choices=("cpu", "cuda", "mps"), default=None)
    args = parser.parse_args(argv)
    for s in args.secuencias:
        preparar(s, args.rehacer, args.pesos, args.dispositivo)
    print(f"Indice: {actualizar_indice().relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
