"""M3 - Asignacion de carril mediante poligonos (RF4)."""

from __future__ import annotations

from typing import Optional

from roadguard.tipos import CambioCarril, Carril


def asignar_carril(
    punto_px: tuple[float, float], carriles: list[Carril]
) -> tuple[Optional[int], float]:
    """Devuelve (indice_carril, confianza) para un punto de calzada (RF4)."""
    raise NotImplementedError("RF4: asignacion por poligono con confianza")


class DetectorCambioCarril:
    """Confirma cambios de carril COMPLETOS (Paso 4).

    Un cambio solo se confirma tras permanencia estable en el nuevo carril.
    Las oscilaciones sobre la linea no cuentan como cambio completo y deben
    descartarse (Paso 4, M4).
    """

    def __init__(self, confianza_min: float) -> None:
        raise NotImplementedError("Paso 4: inicializar maquina de estados")

    def actualizar(
        self, id_vehiculo: int, carril: Optional[int], t: float
    ) -> Optional[CambioCarril]:
        """Devuelve un CambioCarril cuando se confirma, si no None."""
        raise NotImplementedError("Paso 4: confirmacion de cambio completo")
