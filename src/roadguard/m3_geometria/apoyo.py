"""Estimacion aproximada del apoyo longitudinal de una caja delimitadora.

El ajuste alinea el punto inferior con la direccion vial proyectada. En vistas
oblicuas es solo un modelo de silueta: no es una medicion 3D ni una correccion
por ID o clase. La oclusion y una silueta truncada pueden sesgar el resultado;
su uso debe ser opt-in. No permite inferir velocidad verificada.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from roadguard.m3_geometria.homografia import ProyectorCamino
from roadguard.tipos import Caja


def _aplicar(matriz: np.ndarray, punto: tuple[float, float]) -> Optional[tuple[float, float]]:
    vector = matriz @ np.array([punto[0], punto[1], 1.0], dtype=np.float64)
    escala = max(1.0, float(np.max(np.abs(vector))))
    if not np.all(np.isfinite(vector)) or abs(vector[2]) <= np.finfo(float).eps * escala:
        return None
    resultado = vector[:2] / vector[2]
    if not np.all(np.isfinite(resultado)):
        return None
    return float(resultado[0]), float(resultado[1])


def estimar_apoyo_longitudinal(
    caja: Caja,
    proyector: ProyectorCamino,
    actual_a_referencia: Optional[np.ndarray] = None,
) -> Optional[tuple[float, float]]:
    """Devuelve el apoyo estimado en referencia, o ``None`` si no es fiable.

    ``actual_a_referencia`` es una transformacion homogenea de la imagen
    actual a la referencia. Si se omite, ambas coordenadas son la misma.
    """
    valores = (caja.x1, caja.y1, caja.x2, caja.y2)
    if not all(math.isfinite(v) for v in valores) or caja.x1 >= caja.x2 or caja.y1 >= caja.y2:
        return None
    if not proyector.disponible or proyector.matriz is None:
        return None
    actual = np.eye(3, dtype=np.float64) if actual_a_referencia is None else np.asarray(actual_a_referencia)
    if actual.shape != (3, 3) or not np.all(np.isfinite(actual)):
        return None
    try:
        actual = np.array(actual, dtype=np.float64, copy=True)
        referencia_a_actual = np.linalg.inv(actual)
        camino_a_imagen = np.linalg.inv(proyector.matriz)
    except (ValueError, np.linalg.LinAlgError):
        return None
    if not np.all(np.isfinite(referencia_a_actual)) or not np.all(np.isfinite(camino_a_imagen)):
        return None

    centro = ((caja.x1 + caja.x2) / 2.0, caja.y2)
    izquierdo, derecho = (caja.x1, caja.y2), (caja.x2, caja.y2)
    puntos_ref = [_aplicar(actual, p) for p in (centro, izquierdo, derecho)]
    if any(p is None for p in puntos_ref):
        return None
    centro_camino = proyector.proyectar(puntos_ref[0])
    if centro_camino is None:
        return None

    centro_img_vial = _aplicar(camino_a_imagen, (centro_camino[0] + 1.0, centro_camino[1]))
    if centro_img_vial is None:
        return None
    dx = centro_img_vial[0] - puntos_ref[0][0]
    dy = centro_img_vial[1] - puntos_ref[0][1]
    eps = np.finfo(float).eps * max(1.0, abs(centro_img_vial[0]), abs(puntos_ref[0][0]))
    if abs(dx) <= eps:
        punto_ref = puntos_ref[0]  # direccion vial frontal/vertical
    else:
        pendiente = dy / dx
        extremo = puntos_ref[1] if pendiente < 0 else puntos_ref[2]
        punto_ref = (
            puntos_ref[0][0],
            extremo[1] + pendiente * (puntos_ref[0][0] - extremo[0]),
        )
        if not all(math.isfinite(v) for v in punto_ref):
            return None
    punto_actual = _aplicar(referencia_a_actual, punto_ref)
    if punto_actual is None or not (caja.x1 <= punto_actual[0] <= caja.x2 and caja.y1 <= punto_actual[1] <= caja.y2):
        return None
    return punto_ref
