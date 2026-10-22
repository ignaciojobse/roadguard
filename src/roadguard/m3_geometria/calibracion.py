"""M3 - Calibracion de la homografia desde lineas discontinuas (RF4).

La calibracion es la parte de M3 que el codigo no puede adivinar: hay que
marcar en la imagen puntos cuya posicion real se conoce. En vias con linea
discontinua, los extremos de los trazos dan esas medidas: dentro de una
misma linea, la distancia entre trazos es fija por norma (trazo y hueco), y
entre lineas vecinas la separacion es el ancho de carril.

Lo que no se conoce es el desfase longitudinal entre los trazos de dos
lineas distintas (no tienen por que estar alineados). El error de
reproyeccion no sirve para estimarlo: con lineas paralelas, cualquier
desfase se ajusta igual de bien con una homografia que inclina el eje
lateral (un cizalle). Por eso se elige el desfase con el que la homografia
corresponde a una camara fisica: pixeles cuadrados, sin sesgo y punto
principal en el centro de la imagen. Con eso los ejes `x` e `y` quedan
perpendiculares y con la misma escala, y de paso se obtiene la focal, que
sirve como control de plausibilidad.

Convencion (la misma de ProyectorCamino): `x` longitudinal en el sentido de
avance del trafico y `y` lateral, en metros.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from roadguard.m3_geometria.homografia import ProyectorCamino
from roadguard.tipos import Carril, Homografia


@dataclass(frozen=True)
class LineaDiscontinua:
    """Extremos de trazos de una linea de carril, medidos en la imagen.

    `puntos_imagen[i]` esta a `posiciones[i]` metros en el sentido de avance
    desde el primer punto de la linea, y la linea esta a `lateral` metros del
    eje y = 0. Ver `posiciones_trazos`.
    """

    puntos_imagen: list[tuple[float, float]]
    posiciones: list[float]
    lateral: float


@dataclass(frozen=True)
class ResultadoCalibracion:
    homografia: Homografia
    desfases: list[float]  # desfase longitudinal de cada linea (la primera es 0)
    rmse: float  # error de reproyeccion en metros
    error_maximo: float
    focal_px: Optional[float]  # focal de la camara implicita, en pixeles
    inconsistencia: Optional[float]  # 0 = camara fisica exacta (ver _camara_implicita)


def posiciones_trazos(n_trazos: int, trazo: float, hueco: float) -> list[float]:
    """Posiciones de los extremos de `n_trazos` trazos consecutivos.

    Con trazo de 6 m y hueco de 9 m (GB 5768.3-2009, vias de 60 km/h o
    mas), dos trazos dan [0, 6, 15, 21]: inicio y fin de cada trazo, en el
    sentido de avance.
    """
    if n_trazos < 1 or trazo <= 0 or hueco <= 0:
        raise ValueError("Se requiere al menos un trazo y medidas positivas")
    posiciones: list[float] = []
    for i in range(n_trazos):
        inicio = i * (trazo + hueco)
        posiciones += [inicio, inicio + trazo]
    return posiciones


def calibrar_lineas(
    lineas: list[LineaDiscontinua],
    tamano_imagen: tuple[int, int],
    rango_desfase: tuple[float, float] = (-30.0, 30.0),
    paso: float = 0.05,
) -> ResultadoCalibracion:
    """Estima la homografia y los desfases entre lineas.

    `tamano_imagen` es (ancho, alto) en pixeles; su centro se toma como
    punto principal. La primera linea fija el origen longitudinal. Para cada
    linea siguiente se recorre su desfase en `rango_desfase` (barrido grueso
    y luego fino) y se queda el de menor inconsistencia con una camara
    fisica. Si ningun desfase da una camara valida, se rechaza: los puntos
    marcados no son coherentes entre si.
    """
    if len(lineas) < 2:
        raise ValueError("Se necesitan al menos dos lineas para fijar la escala lateral")
    for i, linea in enumerate(lineas):
        if len(linea.puntos_imagen) != len(linea.posiciones) or len(linea.posiciones) < 2:
            raise ValueError(f"Linea {i}: se requieren 2 o mas puntos con su posicion")
    centro = (tamano_imagen[0] / 2.0, tamano_imagen[1] / 2.0)

    desfases = [0.0] * len(lineas)
    for i in range(1, len(lineas)):
        mejor: Optional[tuple[float, float]] = None
        lo, hi, paso_actual = rango_desfase[0], rango_desfase[1], paso
        for _ in range(2):  # barrido grueso y luego fino alrededor del minimo
            for d in np.arange(lo, hi + paso_actual / 2, paso_actual):
                prueba = desfases[: i + 1]
                prueba[i] = float(d)
                camara = _camara_implicita(_ajustar(lineas[: i + 1], prueba)[0], centro)
                if camara is not None and (mejor is None or abs(camara[1]) < mejor[0]):
                    mejor = (abs(camara[1]), float(d))
            if mejor is None:
                raise ValueError(
                    f"Ningun desfase de la linea {i} da una camara fisica: revisar los puntos"
                )
            desfases[i] = mejor[1]
            lo, hi, paso_actual = desfases[i] - paso_actual, desfases[i] + paso_actual, paso_actual / 10

    homografia, rmse, error_maximo = _ajustar(lineas, desfases)
    camara = _camara_implicita(homografia, centro)
    return ResultadoCalibracion(
        homografia,
        [round(d, 3) for d in desfases],
        rmse,
        error_maximo,
        None if camara is None else camara[0],
        None if camara is None else camara[1],
    )


def proyectar_a_imagen(
    homografia: Homografia, puntos_camino: list[tuple[float, float]]
) -> list[Optional[tuple[float, float]]]:
    """Inversa de ProyectorCamino: metros sobre el camino a pixeles."""
    proyector = ProyectorCamino(homografia)
    if not proyector.disponible:
        raise ValueError(f"Homografia no disponible: {proyector.motivo_no_disponible}")
    inversa = np.linalg.inv(proyector.matriz)
    salida: list[Optional[tuple[float, float]]] = []
    for x, y in puntos_camino:
        u, v, w = inversa @ np.array([x, y, 1.0])
        salida.append(None if abs(w) < 1e-12 else (float(u / w), float(v / w)))
    return salida


def carriles_desde_metros(
    homografia: Homografia,
    x_inicio: float,
    x_fin: float,
    bordes_laterales: list[float],
) -> list[Carril]:
    """Poligonos de carril en pixeles a partir de sus bordes en metros.

    `bordes_laterales` son las `y` de las lineas que separan carriles, en
    orden; n bordes dan n - 1 carriles, con indices 0, 1, ... Asi los
    poligonos quedan coherentes con la homografia por construccion.
    """
    if len(bordes_laterales) < 2:
        raise ValueError("Se necesitan al menos dos bordes para un carril")
    carriles = []
    for i, (y0, y1) in enumerate(zip(bordes_laterales, bordes_laterales[1:])):
        esquinas = proyectar_a_imagen(
            homografia, [(x_inicio, y0), (x_fin, y0), (x_fin, y1), (x_inicio, y1)]
        )
        if any(p is None for p in esquinas):
            raise ValueError(f"El carril {i} cruza el horizonte de la imagen")
        carriles.append(Carril(indice=i, poligono=[_redondear(p) for p in esquinas]))
    return carriles


def _camara_implicita(
    homografia: Homografia, centro: tuple[float, float]
) -> Optional[tuple[float, float]]:
    """(focal, inconsistencia) de la camara que produciria esta homografia.

    Camino -> imagen es G = K [r1 r2 t], con K = [[f, 0, cx], [0, f, cy],
    [0, 0, 1]]. Para una camara fisica, K^-1 g1 y K^-1 g2 son perpendiculares
    y de igual norma. La perpendicularidad fija f; la inconsistencia es la
    diferencia relativa de normas que queda. None si ningun f la cumple.
    """
    proyector = ProyectorCamino(homografia)
    if not proyector.disponible:
        return None
    g = np.linalg.inv(proyector.matriz)
    g1, g2 = g[:, 0], g[:, 1]
    cx, cy = centro
    a = np.array([g1[0] - cx * g1[2], g1[1] - cy * g1[2]])
    b = np.array([g2[0] - cx * g2[2], g2[1] - cy * g2[2]])
    if abs(g1[2] * g2[2]) < 1e-15:
        return None
    f2 = -float(a @ b) / float(g1[2] * g2[2])
    if f2 <= 0:
        return None
    m1 = np.r_[a / math.sqrt(f2), g1[2]]
    m2 = np.r_[b / math.sqrt(f2), g2[2]]
    return math.sqrt(f2), float((m1 @ m1 - m2 @ m2) / (m1 @ m1 + m2 @ m2))


def _ajustar(
    lineas: list[LineaDiscontinua], desfases: list[float]
) -> tuple[Homografia, float, float]:
    img, cam = [], []
    for linea, desfase in zip(lineas, desfases):
        for p, x in zip(linea.puntos_imagen, linea.posiciones):
            img.append(p)
            cam.append((x + desfase, linea.lateral))
    matriz, _ = cv2.findHomography(np.asarray(img, float), np.asarray(cam, float), 0)
    if matriz is None:
        return Homografia(), math.inf, math.inf
    proyectados = cv2.perspectiveTransform(np.asarray(img, float).reshape(-1, 1, 2), matriz)
    errores = np.linalg.norm(proyectados.reshape(-1, 2) - np.asarray(cam, float), axis=1)
    homografia = Homografia(
        puntos_imagen=[_redondear(p) for p in img],
        puntos_camino=[(round(x, 3), round(y, 3)) for x, y in cam],
    )
    return homografia, float(np.sqrt(np.mean(errores**2))), float(errores.max())


def _redondear(p: tuple[float, float]) -> tuple[float, float]:
    return (round(float(p[0]), 1), round(float(p[1]), 1))
