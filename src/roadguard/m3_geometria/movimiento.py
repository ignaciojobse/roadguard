"""Compensacion causal de movimiento leve de camara en coordenadas de imagen."""

from __future__ import annotations

from dataclasses import dataclass
import math
import numbers
from typing import Optional

import cv2
import numpy as np


@dataclass
class MovimientoCamara:
    """Estimacion relativa al primer cuadro; nunca modifica imagen ni detecciones."""

    referencia_a_actual: Optional[np.ndarray]
    actual_a_referencia: Optional[np.ndarray]
    valido: bool
    motivo: Optional[str] = None
    inliers: int = 0
    correspondencias: int = 0
    residuo_mediano: Optional[float] = None

    def transformar_punto_actual_a_referencia(
        self, punto: tuple[float, float]
    ) -> Optional[tuple[float, float]]:
        if not self.valido or self.actual_a_referencia is None:
            return None
        return _transformar(punto, self.actual_a_referencia)

    def transformar_puntos_referencia_a_actual(
        self, puntos: list[tuple[float, float]]
    ) -> Optional[list[tuple[float, float]]]:
        if not self.valido or self.referencia_a_actual is None:
            return None
        return [_transformar(punto, self.referencia_a_actual) for punto in puntos]


def _transformar(punto: tuple[float, float], matriz: np.ndarray) -> tuple[float, float]:
    x, y = np.asarray(matriz)[:2] @ np.array([punto[0], punto[1], 1.0])
    return float(x), float(y)


class CompensadorCamara:
    """Estima cada cuadro respecto del primero usando ORB solo fuera de la ROI.

    La estimacion exige 12 inliers y al menos 50% de correspondencias inlier,
    cobertura espacial distribuida, residuo mediano <= 2 px, escala [0.9, 1.1],
    rotacion <= 5 grados y traslacion <= 20% de la diagonal de imagen.
    """

    def __init__(
        self,
        region_interes: list[tuple[float, float]],
        *,
        max_features: int = 1500,
        min_inliers: int = 12,
        umbral_ransac: float = 2.0,
    ) -> None:
        region = np.asarray(region_interes, dtype=np.float64)
        if (region.ndim != 2 or region.shape[1:] != (2,) or len(region) < 3
                or not np.isfinite(region).all()):
            raise ValueError("region_interes debe ser un poligono Nx2 finito con N>=3")
        if (not isinstance(max_features, numbers.Integral)
                or not isinstance(min_inliers, numbers.Integral)
                or isinstance(max_features, bool) or isinstance(min_inliers, bool)
                or min_inliers < 3 or max_features < min_inliers):
            raise ValueError("max_features y min_inliers deben cumplir max_features>=min_inliers>=3")
        if (not isinstance(umbral_ransac, numbers.Real)
                or not math.isfinite(umbral_ransac) or umbral_ransac <= 0):
            raise ValueError("umbral_ransac debe ser finito y mayor que cero")
        self.region_interes = region.astype(np.float32)
        self.max_features = max_features
        self.min_inliers = min_inliers
        self.umbral_ransac = umbral_ransac
        self._orb = cv2.ORB_create(nfeatures=max_features)
        self._bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        self._forma: Optional[tuple[int, int]] = None
        self._referencia_intentada = False
        self._referencia: Optional[np.ndarray] = None
        self._puntos_referencia: Optional[np.ndarray] = None
        self._descriptores_referencia: Optional[np.ndarray] = None

    def _mascara(self, alto: int, ancho: int) -> np.ndarray:
        mascara = np.full((alto, ancho), 255, dtype=np.uint8)
        roi = np.rint(self.region_interes).astype(np.int32)
        cv2.fillPoly(mascara, [roi], 0)
        return mascara

    def actualizar(self, imagen: np.ndarray) -> MovimientoCamara:
        if not isinstance(imagen, np.ndarray) or imagen.ndim not in (2, 3):
            raise ValueError("imagen debe ser un arreglo HxW o HxWxC")
        alto, ancho = imagen.shape[:2]
        if alto <= 0 or ancho <= 0:
            raise ValueError("imagen vacia")
        if self._forma is not None and (alto, ancho) != self._forma:
            return self._fallo("cambio de tamaño de imagen")
        gris = imagen if imagen.ndim == 2 else cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
        if self._referencia is None:
            if self._referencia_intentada:
                return self._fallo("referencia sin textura suficiente")
            self._referencia_intentada = True
            self._forma = (alto, ancho)
            puntos, descriptores = self._orb.detectAndCompute(gris, self._mascara(alto, ancho))
            if descriptores is None or len(puntos) < self.min_inliers:
                return self._fallo("textura insuficiente en el fondo de referencia")
            self._referencia = gris.copy()
            self._puntos_referencia = np.asarray([p.pt for p in puntos], dtype=np.float32)
            self._descriptores_referencia = descriptores
            identidad = np.eye(3, dtype=np.float64)
            return MovimientoCamara(identidad.copy(), identidad.copy(), True,
                                    inliers=len(puntos), correspondencias=len(puntos),
                                    residuo_mediano=0.0)

        puntos, descriptores = self._orb.detectAndCompute(gris, self._mascara(alto, ancho))
        if descriptores is None or len(puntos) < self.min_inliers:
            return self._fallo("textura insuficiente en el cuadro actual")
        parejas = self._bf.knnMatch(self._descriptores_referencia, descriptores, k=2)
        buenas = [m for m, n in parejas if m.distance < 0.7 * n.distance]
        if len(buenas) < self.min_inliers:
            return self._fallo("correspondencias insuficientes", correspondencias=len(buenas))
        origen = np.float32([self._puntos_referencia[m.queryIdx] for m in buenas])
        destino = np.float32([puntos[m.trainIdx].pt for m in buenas])
        affine, mascara_inliers = cv2.estimateAffinePartial2D(
            origen, destino, method=cv2.RANSAC, ransacReprojThreshold=self.umbral_ransac
        )
        if affine is None or mascara_inliers is None:
            return self._fallo("estimacion RANSAC fallida", correspondencias=len(buenas))
        seleccion = mascara_inliers.ravel().astype(bool)
        cantidad = int(seleccion.sum())
        if cantidad < self.min_inliers or cantidad / len(buenas) < 0.5:
            return self._fallo("inliers insuficientes", cantidad, len(buenas))
        predichos = origen[seleccion] @ affine[:, :2].T + affine[:, 2]
        residuo = float(np.median(np.linalg.norm(predichos - destino[seleccion], axis=1)))
        if residuo > self.umbral_ransac:
            return self._fallo("residuo mediano excesivo", cantidad, len(buenas), residuo)
        if (np.ptp(origen[seleccion, 0]) < ancho * 0.1
                or np.ptp(origen[seleccion, 1]) < alto * 0.1):
            return self._fallo("distribucion espacial degenerada", cantidad, len(buenas), residuo)
        a, b = affine[0, 0], affine[1, 0]
        escala = float(np.hypot(a, b))
        rotacion = abs(float(np.degrees(np.arctan2(b, a))))
        desplazamiento = float(np.hypot(affine[0, 2], affine[1, 2]))
        determinante = float(np.linalg.det(affine[:, :2]))
        if not np.isfinite(affine).all() or determinante <= 1e-8:
            return self._fallo("transformacion singular", cantidad, len(buenas), residuo)
        if not 0.9 <= escala <= 1.1 or rotacion > 5.0 or desplazamiento > 0.2 * np.hypot(ancho, alto):
            return self._fallo("transformacion fuera de limites", cantidad, len(buenas), residuo)
        referencia_a_actual = np.eye(3, dtype=np.float64)
        referencia_a_actual[:2] = affine
        actual_a_referencia = np.linalg.inv(referencia_a_actual)
        return MovimientoCamara(referencia_a_actual, actual_a_referencia, True,
                                inliers=cantidad, correspondencias=len(buenas),
                                residuo_mediano=residuo)

    @staticmethod
    def _fallo(
        motivo: str, inliers: int = 0, correspondencias: int = 0,
        residuo: Optional[float] = None,
    ) -> MovimientoCamara:
        return MovimientoCamara(None, None, False, motivo, inliers, correspondencias, residuo)
