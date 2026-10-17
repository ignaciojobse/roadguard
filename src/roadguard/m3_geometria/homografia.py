"""M3 - Rectificacion de perspectiva a vista de pajaro (RF4)."""

from __future__ import annotations

from typing import Optional

from roadguard.tipos import Homografia


class ProyectorCamino:
    """Proyecta el punto de contacto con la calzada al plano del camino.

    Si la homografia no esta disponible, `proyectar` devuelve None y el
    pipeline debe degradar las metricas basadas en distancia manteniendo
    deteccion, seguimiento y una advertencia visible (Paso 5).
    """

    def __init__(self, homografia: Homografia) -> None:
        raise NotImplementedError("RF4: calcular matriz de homografia")

    @property
    def disponible(self) -> bool:
        raise NotImplementedError("RF4: estado de calibracion")

    def proyectar(
        self, punto_px: tuple[float, float]
    ) -> Optional[tuple[float, float]]:
        """Devuelve (x_camino, y_camino) en metros, o None sin calibracion."""
        raise NotImplementedError("RF4: proyeccion imagen -> camino")
