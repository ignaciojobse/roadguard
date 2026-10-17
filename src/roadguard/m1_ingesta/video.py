"""M1 - Lectura de video y metadatos con OpenCV (RF1)."""

from __future__ import annotations

from typing import Iterator

from roadguard.tipos import MetadatosVideo


def leer_metadatos(ruta_video: str) -> MetadatosVideo:
    """Valida codec, resolucion y FPS del MP4 de entrada (RF1, Paso 1)."""
    raise NotImplementedError("RF1: validar codec, resolucion y FPS")


def iterar_cuadros(ruta_video: str) -> Iterator[tuple[int, float, "object"]]:
    """Itera (indice_cuadro, t_segundos, imagen) en orden temporal estricto.

    `t` se deriva de los FPS reales del archivo. El orden causal del Paso 2
    depende de que este iterador no adelante cuadros.
    """
    raise NotImplementedError("RF1: iteracion causal de cuadros")
