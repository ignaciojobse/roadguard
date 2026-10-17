"""M6 - Rendimiento del pipeline.

Criterio de aceptacion (seccion 2.5): al menos 15 FPS a 720p en GPU Colab
T4. 25 FPS se trata como extension.
"""

from __future__ import annotations

FPS_OBJETIVO = 15.0
FPS_EXTENSION = 25.0


def medir_fps(tiempos_por_etapa: dict[str, list[float]]) -> dict[str, float]:
    """FPS global y desglose por etapa, para perfilar antes de tocar umbrales.

    `tiempos_por_etapa` mapea cada etapa a sus duraciones por cuadro, en
    segundos. Devuelve `fps_global` (cuadros / suma de todas las etapas) y,
    por etapa, `ms_<etapa>` (media por cuadro), `fps_<etapa>` (si fuera la
    unica etapa) y `fraccion_<etapa>` (proporcion del tiempo total). Ante
    rendimiento insuficiente, la propuesta indica reducir region o
    frecuencia de deteccion antes de modificar umbrales (riesgos 4.4).
    """
    n = max((len(v) for v in tiempos_por_etapa.values()), default=0)
    total = sum(sum(v) for v in tiempos_por_etapa.values())
    salida: dict[str, float] = {
        "n_cuadros": float(n),
        "segundos_total": total,
        "fps_global": n / total if total > 0 else 0.0,
    }
    for etapa, tiempos in tiempos_por_etapa.items():
        suma = sum(tiempos)
        salida[f"ms_{etapa}"] = 1000.0 * suma / len(tiempos) if tiempos else 0.0
        salida[f"fps_{etapa}"] = len(tiempos) / suma if suma > 0 else 0.0
        salida[f"fraccion_{etapa}"] = suma / total if total > 0 else 0.0
    salida["cumple_15_fps"] = float(salida["fps_global"] >= FPS_OBJETIVO)
    salida["cumple_25_fps"] = float(salida["fps_global"] >= FPS_EXTENSION)
    return salida
