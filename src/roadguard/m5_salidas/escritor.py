"""M5 - Escritura del MP4 anotado (RF12)."""

from __future__ import annotations

import math
import os
from typing import Optional

import cv2
import numpy as np

from roadguard.tipos import MetadatosVideo


class ErrorSalida(ValueError):
    """La salida pedida es incoherente: se rechaza antes de escribir."""


class EscritorVideo:
    """Escribe cuadros anotados en un MP4 con los FPS y tamano de la entrada.

    Mantener los FPS de la entrada conserva la escala de tiempo: el cuadro n
    del video anotado ocurre en el mismo `t` que el cuadro n de la entrada.

    Uso:
        with EscritorVideo.desde_metadatos("salida.mp4", meta) as escritor:
            escritor.escribir(cuadro_anotado)
    """

    def __init__(
        self, ruta: str, fps: float, ancho: int, alto: int, fourcc: str = "mp4v"
    ) -> None:
        if not ruta.lower().endswith(".mp4"):
            raise ErrorSalida(f"La salida debe ser un archivo MP4: {ruta}")
        if not math.isfinite(fps) or fps <= 0:
            raise ErrorSalida(f"FPS invalidos para la salida: {fps}")
        if ancho <= 0 or alto <= 0:
            raise ErrorSalida(f"Resolucion invalida para la salida: {ancho}x{alto}")
        directorio = os.path.dirname(ruta)
        if directorio:
            os.makedirs(directorio, exist_ok=True)

        self.ruta = ruta
        self.fps = fps
        self.ancho = ancho
        self.alto = alto
        self.n_cuadros = 0
        self._escritor: Optional[cv2.VideoWriter] = cv2.VideoWriter(
            ruta, cv2.VideoWriter_fourcc(*fourcc), fps, (ancho, alto)
        )
        if not self._escritor.isOpened():
            self._escritor = None
            raise ErrorSalida(f"OpenCV no pudo crear el video de salida: {ruta}")

    @classmethod
    def desde_metadatos(cls, ruta: str, metadatos: MetadatosVideo) -> "EscritorVideo":
        """Escritor con los FPS y la resolucion del video de entrada."""
        if os.path.abspath(ruta) == os.path.abspath(metadatos.ruta):
            raise ErrorSalida(f"La salida no puede sobrescribir el video de entrada: {ruta}")
        return cls(ruta, metadatos.fps, metadatos.ancho, metadatos.alto)

    def escribir(self, imagen: np.ndarray) -> None:
        if self._escritor is None:
            raise ErrorSalida("El escritor ya fue cerrado")
        if imagen.shape != (self.alto, self.ancho, 3):
            raise ErrorSalida(
                f"Cuadro de forma {imagen.shape}; se espera ({self.alto}, {self.ancho}, 3)"
            )
        self._escritor.write(imagen)
        self.n_cuadros += 1

    def cerrar(self) -> None:
        if self._escritor is not None:
            self._escritor.release()
            self._escritor = None

    def __enter__(self) -> "EscritorVideo":
        return self

    def __exit__(self, *_exc) -> None:
        self.cerrar()
