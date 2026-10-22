"""M5 - Anotacion de cuadros: cajas, ID, clase y carril."""

from __future__ import annotations

from typing import Iterable, Optional

import cv2
import numpy as np

from roadguard.tipos import Carril, EstadoCinematico, Track

# Colores en BGR (convencion de OpenCV).
# La caja usa un color neutro hasta que M4 entregue el nivel de riesgo (RF11).
COLOR_CAJA = (230, 180, 60)
COLOR_CARRIL = (0, 200, 200)
COLOR_TEXTO = (0, 0, 0)
COLOR_ADVERTENCIA = (0, 0, 200)
COLOR_TEXTO_ADVERTENCIA = (255, 255, 255)

_FUENTE = cv2.FONT_HERSHEY_SIMPLEX
_ESCALA = 0.45
_GROSOR = 1
_MARGEN = 3


def etiqueta_vehiculo(track: Track, estado: Optional[EstadoCinematico] = None) -> str:
    """Texto sobre la caja: ID, clase y carril.

    Sin estado de M3 no se informa carril. Con estado, un vehiculo fuera de
    todo carril se rotula explicitamente en vez de omitirlo. El texto va sin
    tildes porque las fuentes de OpenCV no las dibujan.
    """
    partes = [f"ID {track.id_vehiculo}", track.clase]
    if estado is not None:
        partes.append("sin carril" if estado.carril is None else f"carril {estado.carril}")
    return " ".join(partes)


def dibujar_carriles(imagen: np.ndarray, carriles: Iterable[Carril]) -> None:
    """Dibuja el contorno de cada poligono de carril y su indice (en el lugar)."""
    for carril in carriles:
        puntos = np.round(np.asarray(carril.poligono, dtype=np.float64)).astype(np.int32)
        cv2.polylines(imagen, [puntos], True, COLOR_CARRIL, 1, cv2.LINE_AA)
        cx, cy = puntos.mean(axis=0)
        cv2.putText(
            imagen, str(carril.indice), (int(cx), int(cy)),
            _FUENTE, _ESCALA, COLOR_CARRIL, _GROSOR, cv2.LINE_AA,
        )


def dibujar_vehiculo(
    imagen: np.ndarray,
    track: Track,
    estado: Optional[EstadoCinematico] = None,
    color: tuple[int, int, int] = COLOR_CAJA,
    y_min: int = 0,
) -> None:
    """Dibuja caja, punto de calzada y etiqueta de un vehiculo (en el lugar).

    Las coordenadas fuera de la imagen las recorta OpenCV; una caja que sale
    del cuadro no es un error (vehiculos que entran o salen). La etiqueta no
    se dibuja por encima de `y_min`, para que la franja de advertencia no la
    tape.
    """
    c = track.caja
    p1 = (int(round(c.x1)), int(round(c.y1)))
    p2 = (int(round(c.x2)), int(round(c.y2)))
    cv2.rectangle(imagen, p1, p2, color, 2)
    px, py = track.punto_calzada_px
    cv2.circle(imagen, (int(round(px)), int(round(py))), 3, color, -1)
    _rotulo(imagen, etiqueta_vehiculo(track, estado), p1, color, y_min)


def dibujar_advertencia(imagen: np.ndarray, texto: str) -> int:
    """Franja permanente en el borde superior (Paso 5), en el lugar.

    La escala del texto se reduce hasta que cabe en el ancho del cuadro.
    Devuelve el alto de la franja en pixeles.
    """
    alto, ancho = imagen.shape[:2]
    escala, th, alto_franja = _geometria_advertencia(texto, ancho, alto)
    cv2.rectangle(imagen, (0, 0), (ancho - 1, alto_franja - 1), COLOR_ADVERTENCIA, -1)
    cv2.putText(
        imagen, texto, (_MARGEN, _MARGEN + th),
        _FUENTE, escala, COLOR_TEXTO_ADVERTENCIA, _GROSOR, cv2.LINE_AA,
    )
    return alto_franja


def anotar_cuadro(
    imagen: np.ndarray,
    tracks: Iterable[Track],
    estados: Iterable[EstadoCinematico] = (),
    carriles: Iterable[Carril] = (),
    advertencia: Optional[str] = None,
) -> np.ndarray:
    """Devuelve una copia anotada del cuadro; no modifica `imagen`.

    `estados` se asocia a `tracks` por `id_vehiculo` y debe ser el del mismo
    cuadro. Un track sin estado se dibuja sin carril.
    """
    salida = imagen.copy()
    y_min = 0
    if advertencia:
        alto, ancho = salida.shape[:2]
        y_min = _geometria_advertencia(advertencia, ancho, alto)[2]
    dibujar_carriles(salida, carriles)
    por_id = {e.id_vehiculo: e for e in estados}
    for track in tracks:
        dibujar_vehiculo(salida, track, por_id.get(track.id_vehiculo), y_min=y_min)
    if advertencia:
        dibujar_advertencia(salida, advertencia)
    return salida


def _geometria_advertencia(texto: str, ancho: int, alto: int) -> tuple[float, int, int]:
    """(escala, alto del texto, alto de la franja) para que el texto quepa."""
    escala = 0.6
    (tw, th), base = cv2.getTextSize(texto, _FUENTE, escala, _GROSOR)
    while tw > ancho - 2 * _MARGEN and escala > 0.25:
        escala -= 0.05
        (tw, th), base = cv2.getTextSize(texto, _FUENTE, escala, _GROSOR)
    return escala, th, min(alto, th + base + 2 * _MARGEN)


def _rotulo(
    imagen: np.ndarray,
    texto: str,
    esquina: tuple[int, int],
    color: tuple[int, int, int],
    y_min: int = 0,
) -> None:
    """Texto sobre fondo de color, encima de la caja o dentro si no cabe."""
    (tw, th), base = cv2.getTextSize(texto, _FUENTE, _ESCALA, _GROSOR)
    x, y = esquina
    if y - th - base - _MARGEN >= y_min:
        y_base = y - _MARGEN
    else:
        y_base = max(y, y_min) + th + 2 * _MARGEN
    cv2.rectangle(
        imagen,
        (x, y_base - th - _MARGEN),
        (x + tw + 2 * _MARGEN, y_base + base),
        color,
        -1,
    )
    cv2.putText(
        imagen, texto, (x + _MARGEN, y_base),
        _FUENTE, _ESCALA, COLOR_TEXTO, _GROSOR, cv2.LINE_AA,
    )
