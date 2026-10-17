"""M4 - RF7: cercania peligrosa.

Activar una alerta si el seguidor supera 5 m/s y mantiene THW < 1,5 s
durante al menos 2 s. Implementado con ventana deslizante y evaluacion de
persistencia; debe evitar eventos duplicados (M4).
"""

from __future__ import annotations

from typing import Optional

from roadguard.tipos import Evento, Relacion, Umbrales


class ReglaCercania:
    def __init__(self, umbrales: Umbrales) -> None:
        raise NotImplementedError("RF7: inicializar ventana de persistencia")

    def evaluar(
        self, relacion: Relacion, velocidad: Optional[float], t: float
    ) -> Optional[Evento]:
        """Devuelve un Evento cuando se cumple la persistencia de 2 s."""
        raise NotImplementedError("RF7: v > 5 m/s y THW < 1,5 s por >= 2 s")
