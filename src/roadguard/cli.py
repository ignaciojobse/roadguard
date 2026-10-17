"""Interfaz de linea de comandos (seccion 2.3: CLI y archivos YAML).

El proyecto no expone API publica ni servicio web.

Uso:
    python -m roadguard --video datos/videos/sec01.mp4 \\
                        --config configs/camara_ejemplo.yaml \\
                        --salida salidas/sec01
"""

from __future__ import annotations

import argparse


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="roadguard",
        description=(
            "Prototipo de apoyo para analizar videos de camaras fijas. "
            "Las alertas son experimentales y requieren revision humana."
        ),
    )
    parser.add_argument("--video", required=True, help="Ruta del MP4 de entrada")
    parser.add_argument("--config", required=True, help="Ruta del YAML de camara")
    parser.add_argument("--salida", required=True, help="Directorio de salidas")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    from roadguard.pipeline import ejecutar

    ejecutar(args.video, args.config, args.salida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
