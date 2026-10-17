"""Fixtures compartidas de las pruebas unitarias."""

from pathlib import Path
from typing import Callable

import pytest

from roadguard.tipos import Umbrales


@pytest.fixture
def umbrales() -> Umbrales:
    """Umbrales por defecto declarados en la propuesta (contrato de datos)."""
    return Umbrales()


@pytest.fixture
def video_sintetico(tmp_path: Path) -> Callable[..., str]:
    """Fabrica un MP4 corto de prueba y devuelve su ruta."""
    import cv2
    import numpy as np

    def fabricar(n_cuadros: int = 10, fps: float = 25.0, ancho: int = 320, alto: int = 240) -> str:
        ruta = tmp_path / f"sintetico_{n_cuadros}_{fps:g}.mp4"
        escritor = cv2.VideoWriter(
            str(ruta), cv2.VideoWriter_fourcc(*"mp4v"), fps, (ancho, alto)
        )
        for i in range(n_cuadros):
            escritor.write(np.full((alto, ancho, 3), (i * 7) % 255, np.uint8))
        escritor.release()
        return str(ruta)

    return fabricar
