"""M6 - mAP@0.5 sobre secuencias seleccionadas de UA-DETRAC.

Criterio de aceptacion (seccion 2.5): mAP@0.5 >= 0,60.
"""

from __future__ import annotations


def evaluar_deteccion(ruta_anotaciones: str, ruta_predicciones: str) -> dict[str, float]:
    """Devuelve mAP@0.5 y metricas por clase."""
    raise NotImplementedError("2.5: mAP@0.5 >= 0,60 sobre UA-DETRAC")
