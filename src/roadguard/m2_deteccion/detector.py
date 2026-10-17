"""M2 - Deteccion vehicular con YOLOv8n preentrenado (RF2)."""

from __future__ import annotations

from typing import Any, Optional, Sequence

from roadguard.m1_ingesta.config import CLASES_VEHICULARES
from roadguard.poligonos import punto_en_poligono
from roadguard.tipos import Caja, Configuracion, Deteccion

# Decision documentada (T2, usada por el protocolo de evaluacion T9):
# mapeo explicito entre los indices COCO del YOLOv8n preentrenado y las
# clases vehiculares de la configuracion. Cualquier otra clase COCO
# (personas, bicicletas, etc.) se descarta.
MAPEO_COCO: dict[int, str] = {
    2: "automovil",    # car
    3: "motocicleta",  # motorcycle
    5: "bus",          # bus
    7: "camion",       # truck
}
assert set(MAPEO_COCO.values()) == set(CLASES_VEHICULARES)


class DetectorVehiculos:
    """Detecta automoviles, buses, camiones y motocicletas (RF2).

    Filtra por clases configuradas y por region de interes antes de entregar
    resultados (M2).

    `confianza_min_deteccion` de la configuracion es el piso de confianza.
    ByteTrack aprovecha las detecciones entre ese piso y su umbral alto en
    la segunda asociacion, por lo que no conviene subir este valor por
    encima del umbral bajo del seguidor sin medir IDF1 (T9).
    """

    def __init__(
        self,
        cfg: Configuracion,
        pesos: str = "yolov8n.pt",
        dispositivo: Optional[str] = None,
        tam_imagen: int = 640,
    ) -> None:
        try:
            import ultralytics
            from ultralytics import YOLO
        except ImportError as e:  # pragma: no cover - depende del entorno
            raise ImportError(
                "RF2 requiere Ultralytics: pip install -r requirements.txt"
            ) from e
        self.cfg = cfg
        self.modelo = YOLO(pesos)
        self.dispositivo = dispositivo
        self.tam_imagen = tam_imagen
        self.version_modelo = f"ultralytics {ultralytics.__version__} / {pesos}"
        self._ids_coco = [i for i, c in MAPEO_COCO.items() if c in cfg.clases]

    def detectar(self, imagen: "object") -> list[Deteccion]:
        """Devuelve detecciones con clase, caja y confianza (RF2)."""
        resultado = self.modelo.predict(
            imagen,
            conf=self.cfg.confianza_min_deteccion,
            classes=self._ids_coco,
            imgsz=self.tam_imagen,
            device=self.dispositivo,
            verbose=False,
        )[0]
        cajas = resultado.boxes
        return detecciones_desde_arrays(
            cajas.xyxy.cpu().numpy(),
            cajas.conf.cpu().numpy(),
            cajas.cls.cpu().numpy(),
            self.cfg,
        )


def detecciones_desde_arrays(
    xyxy: Sequence[Sequence[float]],
    confianzas: Sequence[float],
    clases_coco: Sequence[Any],
    cfg: Configuracion,
) -> list[Deteccion]:
    """Aplica mapeo de clases, clases configuradas, confianza minima y
    region de interes a la salida cruda del modelo (RF2)."""
    detecciones: list[Deteccion] = []
    for (x1, y1, x2, y2), conf, cls in zip(xyxy, confianzas, clases_coco):
        clase = MAPEO_COCO.get(int(cls))
        if clase is None or clase not in cfg.clases:
            continue
        if float(conf) < cfg.confianza_min_deteccion:
            continue
        caja = Caja(float(x1), float(y1), float(x2), float(y2))
        detecciones.append(Deteccion(clase=clase, confianza=float(conf), caja=caja))
    return filtrar_region_interes(detecciones, cfg.region_interes)


def filtrar_region_interes(
    detecciones: list[Deteccion], region: list[tuple[float, float]]
) -> list[Deteccion]:
    """Descarta detecciones fuera de la region configurada (RF2).

    El criterio es el punto de contacto con la calzada (centro del borde
    inferior de la caja), el mismo que M3 proyecta al plano del camino.
    """
    return [d for d in detecciones if punto_en_poligono(d.caja.punto_calzada, region)]
