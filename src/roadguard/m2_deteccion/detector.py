"""M2 - Deteccion vehicular con YOLOv8n preentrenado (RF2)."""

from __future__ import annotations

from roadguard.tipos import Caja, Configuracion, Deteccion


class DetectorVehiculos:
    """Detecta automoviles, buses, camiones y motocicletas (RF2).

    Filtra por clases configuradas y por region de interes antes de entregar
    resultados (M2).
    """

    def __init__(self, cfg: Configuracion, pesos: str = "yolov8n.pt") -> None:
        raise NotImplementedError("RF2: inicializar YOLOv8n")

    def detectar(self, imagen: "object") -> list[Deteccion]:
        """Devuelve detecciones con clase, caja y confianza (RF2)."""
        raise NotImplementedError("RF2: inferencia por cuadro")


def filtrar_region_interes(
    detecciones: list[Deteccion], region: list[tuple[float, float]]
) -> list[Deteccion]:
    """Descarta detecciones fuera de la region configurada (RF2)."""
    raise NotImplementedError("RF2: filtro por region de interes")
