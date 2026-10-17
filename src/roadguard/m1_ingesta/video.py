"""M1 - Lectura de video y metadatos con OpenCV (RF1)."""

from __future__ import annotations

import math
import os
from typing import Iterator

import cv2

from roadguard.tipos import MetadatosVideo


class ErrorVideo(ValueError):
    """El video de entrada no cumple RF1: se rechaza antes de crear salidas."""


def _fourcc_a_texto(valor: float) -> str:
    codigo = int(valor)
    texto = "".join(chr((codigo >> (8 * i)) & 0xFF) for i in range(4))
    return texto.strip("\x00 ") or "desconocido"


def leer_metadatos(ruta_video: str) -> MetadatosVideo:
    """Valida codec, resolucion y FPS del MP4 de entrada (RF1, Paso 1)."""
    if not os.path.isfile(ruta_video):
        raise ErrorVideo(f"No existe el video: {ruta_video}")
    if not ruta_video.lower().endswith(".mp4"):
        raise ErrorVideo(f"Se espera un archivo MP4 (RF1): {ruta_video}")

    captura = cv2.VideoCapture(ruta_video)
    try:
        if not captura.isOpened():
            raise ErrorVideo(f"OpenCV no pudo abrir el video: {ruta_video}")
        ancho = int(captura.get(cv2.CAP_PROP_FRAME_WIDTH))
        alto = int(captura.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(captura.get(cv2.CAP_PROP_FPS))
        n_cuadros = int(captura.get(cv2.CAP_PROP_FRAME_COUNT))
        codec = _fourcc_a_texto(captura.get(cv2.CAP_PROP_FOURCC))

        if ancho <= 0 or alto <= 0:
            raise ErrorVideo(f"Resolucion invalida ({ancho}x{alto}): {ruta_video}")
        if not math.isfinite(fps) or fps <= 0:
            raise ErrorVideo(
                f"FPS invalidos ({fps}): no se puede derivar t en segundos: {ruta_video}"
            )
        ok, _ = captura.read()
        if not ok:
            raise ErrorVideo(
                f"No se pudo decodificar el primer cuadro (codec {codec}): {ruta_video}"
            )
    finally:
        captura.release()

    return MetadatosVideo(
        ruta=ruta_video,
        ancho=ancho,
        alto=alto,
        fps=fps,
        n_cuadros=max(n_cuadros, 0),
        codec=codec,
    )


def iterar_cuadros(ruta_video: str) -> Iterator[tuple[int, float, "object"]]:
    """Itera (indice_cuadro, t_segundos, imagen) en orden temporal estricto.

    `t` se deriva de los FPS reales del archivo. El orden causal del Paso 2
    depende de que este iterador no adelante cuadros.
    """
    fps = leer_metadatos(ruta_video).fps
    captura = cv2.VideoCapture(ruta_video)
    try:
        cuadro = 0
        while True:
            ok, imagen = captura.read()
            if not ok:
                break
            yield cuadro, cuadro / fps, imagen
            cuadro += 1
    finally:
        captura.release()
