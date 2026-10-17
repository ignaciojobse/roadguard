"""M6 - Precision, recobrado y F1 de los eventos de reglas.

Criterio de aceptacion (seccion 2.5): F1 >= 0,75 al comparar alertas desde
trayectorias degradadas con eventos de referencia calculados desde highD o
NGSIM.
"""

from __future__ import annotations

from roadguard.tipos import Evento


def evaluar_reglas(
    eventos_referencia: list[Evento],
    eventos_obtenidos: list[Evento],
    tolerancia_temporal: float,
) -> dict[str, float]:
    """Devuelve precision, recobrado y F1 por regla y global."""
    raise NotImplementedError("2.5: F1 >= 0,75 sobre trayectorias degradadas")
