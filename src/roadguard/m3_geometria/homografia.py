"""M3 - Rectificacion de perspectiva a vista de pajaro (RF4)."""

from __future__ import annotations

import math
from typing import Optional

import cv2
import numpy as np

from roadguard.tipos import Homografia


class ProyectorCamino:
    """Proyecta el punto de contacto con la calzada al plano del camino.

    Si la homografia no esta disponible, `proyectar` devuelve None y el
    consumidor debe degradar las metricas basadas en distancia manteniendo
    deteccion, seguimiento y una advertencia visible (Paso 5).

    Convencion: `puntos_camino` se entregan en metros con el eje x en el
    sentido de avance del trafico y el eje y lateral. Las relaciones
    predecesor/seguidor (RF6) suponen esa orientacion.
    """

    def __init__(self, homografia: Homografia) -> None:
        self.matriz: Optional[np.ndarray] = None
        self.error_reproyeccion: Optional[float] = None  # RMSE en metros
        self.motivo_no_disponible: Optional[str] = None
        self._signo_w = 1.0
        if not homografia.disponible:
            self.motivo_no_disponible = "sin correspondencias de calibracion"
            return
        img = np.asarray(homografia.puntos_imagen, dtype=np.float64)
        cam = np.asarray(homografia.puntos_camino, dtype=np.float64)
        matriz, _ = cv2.findHomography(img, cam, 0)
        if matriz is None or not np.all(np.isfinite(matriz)) or abs(np.linalg.det(matriz)) < 1e-12:
            self.motivo_no_disponible = "homografia degenerada"
            return
        self.matriz = matriz
        ws = img @ matriz[2, :2] + matriz[2, 2]
        if not (np.all(ws > 0) or np.all(ws < 0)):
            self.matriz = None
            self.motivo_no_disponible = "puntos de calibracion a ambos lados del horizonte"
            return
        self._signo_w = 1.0 if ws[0] > 0 else -1.0
        proyectados = [self._aplicar(tuple(p)) for p in img]
        errores = [math.dist(p, tuple(c)) for p, c in zip(proyectados, cam)]
        self.error_reproyeccion = math.sqrt(sum(e * e for e in errores) / len(errores))

    @property
    def disponible(self) -> bool:
        return self.matriz is not None

    def proyectar(
        self, punto_px: tuple[float, float]
    ) -> Optional[tuple[float, float]]:
        """Devuelve (x_camino, y_camino) en metros, o None sin calibracion."""
        if self.matriz is None:
            return None
        return self._aplicar(punto_px)

    def _aplicar(self, punto_px: tuple[float, float]) -> Optional[tuple[float, float]]:
        h = self.matriz
        x, y = punto_px
        w = h[2, 0] * x + h[2, 1] * y + h[2, 2]
        if w * self._signo_w < 1e-12:
            return None  # punto en o detras del horizonte: no disponible
        xc = (h[0, 0] * x + h[0, 1] * y + h[0, 2]) / w
        yc = (h[1, 0] * x + h[1, 1] * y + h[1, 2]) / w
        if not (math.isfinite(xc) and math.isfinite(yc)):
            return None
        return (float(xc), float(yc))
