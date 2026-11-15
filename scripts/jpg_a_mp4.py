"""Convierte una carpeta de cuadros JPG de UA-DETRAC en un MP4, sin ffmpeg.

UA-DETRAC entrega cada secuencia como `img00001.jpg, img00002.jpg, ...` a
25 FPS. El prototipo solo acepta MP4 (RF1), asi que hay que armarlo
conservando la tasa de cuadros real, porque todo `t` se deriva de ella.

Uso, desde la raiz del repo:

    python scripts/jpg_a_mp4.py MVI_39271                  # una secuencia
    python scripts/jpg_a_mp4.py MVI_39271 MVI_40714 MVI_40742

Lee `datos/ua-detrac/<secuencia>/img*.jpg` y escribe
`datos/videos/<secuencia>.mp4` con el codec `mp4v` de OpenCV. Con ffmpeg
instalado da lo mismo usar el comando del PRD de datos (H.264, CRF 18); este
script existe para que la maquina de la demo no dependa de ffmpeg.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

RAIZ = Path(__file__).resolve().parents[1]
ORIGEN = RAIZ / "datos" / "ua-detrac"
DESTINO = RAIZ / "datos" / "videos"
FPS_UA_DETRAC = 25.0


def convertir(dir_cuadros: Path, ruta_mp4: Path, fps: float = FPS_UA_DETRAC) -> int:
    """Escribe los JPG de `dir_cuadros`, en orden de nombre, como MP4.

    Devuelve la cantidad de cuadros escritos. Falla si la carpeta no tiene
    JPG o si un cuadro no tiene el tamano del primero.
    """
    cuadros = sorted(dir_cuadros.glob("img*.jpg"))
    if not cuadros:
        raise FileNotFoundError(f"No hay img*.jpg en {dir_cuadros}")
    primero = cv2.imread(str(cuadros[0]))
    if primero is None:
        raise ValueError(f"No se pudo leer {cuadros[0]}")
    alto, ancho = primero.shape[:2]
    ruta_mp4.parent.mkdir(parents=True, exist_ok=True)
    escritor = cv2.VideoWriter(str(ruta_mp4), cv2.VideoWriter_fourcc(*"mp4v"), fps, (ancho, alto))
    if not escritor.isOpened():
        raise RuntimeError(f"OpenCV no pudo abrir el escritor para {ruta_mp4}")
    try:
        for ruta in cuadros:
            imagen = cv2.imread(str(ruta))
            if imagen is None or imagen.shape[:2] != (alto, ancho):
                raise ValueError(f"Cuadro ilegible o de otro tamano: {ruta}")
            escritor.write(imagen)
    finally:
        escritor.release()
    return len(cuadros)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("secuencias", nargs="+", help="Nombres MVI_xxxxx a convertir")
    parser.add_argument("--origen", default=str(ORIGEN), help="Carpeta con <secuencia>/img*.jpg")
    parser.add_argument("--destino", default=str(DESTINO), help="Carpeta de salida de los MP4")
    parser.add_argument("--fps", type=float, default=FPS_UA_DETRAC, help="Tasa real de la secuencia")
    args = parser.parse_args(argv)
    for secuencia in args.secuencias:
        ruta_mp4 = Path(args.destino) / f"{secuencia}.mp4"
        try:
            n = convertir(Path(args.origen) / secuencia, ruta_mp4, args.fps)
        except (FileNotFoundError, ValueError, RuntimeError) as e:
            print(f"Error en {secuencia}: {e}", file=sys.stderr)
            return 1
        print(f"{secuencia}: {n} cuadros a {args.fps:g} FPS -> {ruta_mp4}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
