"""M5 - RF12: exportacion de eventos CSV y resumen JSON.

Esquema estable y marcas temporales basadas en FPS (M5). Cada evento debe
incluir vehiculo, intervalo, regla, variables medidas, umbrales y puntaje
(seccion 2.5, trazabilidad).
"""

from __future__ import annotations

from roadguard.tipos import Evento, ResumenEjecucion, ResumenVehiculo

COLUMNAS_EVENTOS: tuple[str, ...] = (
    "id_vehiculo",
    "regla",
    "t_inicio",
    "t_fin",
    "id_relacionado",
    "velocidad",
    "distancia",
    "thw",
    "ttc",
    "umbral_velocidad",
    "umbral_thw",
    "umbral_ttc",
    "aporte_puntaje",
)


def exportar_eventos_csv(eventos: list[Evento], ruta: str) -> None:
    """Escribe un evento por activacion, con metricas y umbrales (RF12)."""
    raise NotImplementedError("RF12: CSV de eventos")


def exportar_resumen_json(
    resumenes: list[ResumenVehiculo], ejecucion: ResumenEjecucion, ruta: str
) -> None:
    """Resumen jerarquico por vehiculo mas evidencia de reproducibilidad.

    Debe incluir configuracion, version del modelo, FPS y resumen de eventos
    (Paso 6, RF12).
    """
    raise NotImplementedError("RF12: JSON por vehiculo y resumen de ejecucion")
