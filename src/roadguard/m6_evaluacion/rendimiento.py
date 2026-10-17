"""M6 - Rendimiento del pipeline.

Criterio de aceptacion (seccion 2.5): al menos 15 FPS a 720p en GPU Colab
T4. 25 FPS se trata como extension.
"""

from __future__ import annotations


def medir_fps(tiempos_por_etapa: dict[str, list[float]]) -> dict[str, float]:
    """FPS global y desglose por etapa, para perfilar antes de tocar umbrales."""
    raise NotImplementedError("2.5: medicion de FPS por etapa")
