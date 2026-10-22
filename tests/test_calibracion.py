"""RF4. Calibracion de la homografia desde lineas discontinuas (m3_geometria).

Casos minimos a cubrir:
  - Las posiciones de los trazos siguen trazo y hueco de la norma.
  - Con puntos generados por una camara conocida, la calibracion recupera
    el desfase entre lineas, la homografia y la focal.
  - Sin la condicion de camara fisica el desfase no se puede recuperar:
    cualquier desfase da error de reproyeccion ~0 (cizalle).
  - proyectar_a_imagen es la inversa de ProyectorCamino.
  - Los poligonos de carril construidos en metros asignan el carril
    correcto al centro de cada carril.
  - Una sola linea o puntos sin posicion se rechazan.
"""

import math

import numpy as np
import pytest

from roadguard.m3_geometria.calibracion import (
    LineaDiscontinua,
    calibrar_lineas,
    carriles_desde_metros,
    posiciones_trazos,
    proyectar_a_imagen,
)
from roadguard.m3_geometria.carriles import asignar_carril
from roadguard.m3_geometria.homografia import ProyectorCamino

# Camara sintetica: focal 800 px, imagen de 960x540, a 8 m de altura,
# inclinada 20 grados hacia abajo y girada 10 grados respecto del camino.
FOCAL, ANCHO, ALTO = 800.0, 960, 540
DESFASE = 4.2  # metros entre los trazos de la segunda linea y los de la primera


def _camara() -> np.ndarray:
    p, g = math.radians(20), math.radians(10)
    adelante = np.array([math.cos(p) * math.cos(g), math.cos(p) * math.sin(g), -math.sin(p)])
    derecha = np.cross(adelante, [0.0, 0.0, 1.0])
    derecha /= np.linalg.norm(derecha)
    abajo = np.cross(adelante, derecha)
    rotacion = np.array([derecha, abajo, adelante])
    t = -rotacion @ np.array([-20.0, -6.0, 8.0])
    k = np.array([[FOCAL, 0, ANCHO / 2], [0, FOCAL, ALTO / 2], [0, 0, 1]])
    return k @ np.c_[rotacion[:, 0], rotacion[:, 1], t]


CAMINO_A_IMAGEN = _camara()


def _a_imagen(x: float, y: float) -> tuple[float, float]:
    u, v, w = CAMINO_A_IMAGEN @ np.array([x, y, 1.0])
    return (u / w, v / w)


def _linea(lateral: float, desfase: float) -> LineaDiscontinua:
    pos = posiciones_trazos(2, 6.0, 9.0)
    return LineaDiscontinua([_a_imagen(x + desfase, lateral) for x in pos], pos, lateral)


def test_posiciones_de_los_trazos() -> None:
    assert posiciones_trazos(2, 6.0, 9.0) == [0.0, 6.0, 15.0, 21.0]
    assert posiciones_trazos(1, 2.0, 4.0) == [0.0, 2.0]
    with pytest.raises(ValueError):
        posiciones_trazos(0, 6.0, 9.0)


def test_recupera_desfase_y_homografia() -> None:
    r = calibrar_lineas([_linea(0.0, 0.0), _linea(3.5, DESFASE)], (ANCHO, ALTO))
    assert r.desfases[0] == 0.0
    assert r.desfases[1] == pytest.approx(DESFASE, abs=0.02)
    assert r.rmse < 0.01
    assert r.focal_px == pytest.approx(FOCAL, rel=0.01)
    assert abs(r.inconsistencia) < 0.01
    proyector = ProyectorCamino(r.homografia)
    x, y = proyector.proyectar(_a_imagen(30.0, 1.75))
    assert (x, y) == (pytest.approx(30.0, abs=0.05), pytest.approx(1.75, abs=0.05))


def test_proyectar_a_imagen_es_la_inversa() -> None:
    r = calibrar_lineas([_linea(0.0, 0.0), _linea(3.5, DESFASE)], (ANCHO, ALTO))
    proyector = ProyectorCamino(r.homografia)
    for p in [(-10.0, 0.5), (12.0, 3.0), (25.0, -2.0)]:
        (u, v), = proyectar_a_imagen(r.homografia, [p])
        assert math.dist(proyector.proyectar((u, v)), p) < 1e-6


def test_carriles_en_metros_asignan_el_centro() -> None:
    r = calibrar_lineas([_linea(0.0, 0.0), _linea(3.5, DESFASE)], (ANCHO, ALTO))
    carriles = carriles_desde_metros(r.homografia, -5.0, 30.0, [-3.5, 0.0, 3.5, 7.0])
    assert [c.indice for c in carriles] == [0, 1, 2]
    for indice, y in [(0, -1.75), (1, 1.75), (2, 5.25)]:
        (u, v), = proyectar_a_imagen(r.homografia, [(10.0, y)])
        carril, confianza = asignar_carril((u, v), carriles)
        assert carril == indice
        assert confianza > 0.8


def test_rechaza_entradas_insuficientes() -> None:
    with pytest.raises(ValueError):
        calibrar_lineas([_linea(0.0, 0.0)], (ANCHO, ALTO))
    corta = LineaDiscontinua([(10.0, 10.0)], [0.0], 3.5)
    with pytest.raises(ValueError):
        calibrar_lineas([_linea(0.0, 0.0), corta], (ANCHO, ALTO))


def test_el_error_de_reproyeccion_no_fija_el_desfase() -> None:
    """Motivo del criterio de camara: con otro desfase el ajuste es igual de bueno."""
    from roadguard.m3_geometria.calibracion import _ajustar

    for otro in (0.0, DESFASE + 5.0):
        assert _ajustar([_linea(0.0, 0.0), _linea(3.5, DESFASE)], [0.0, otro])[1] < 1e-4


def test_coincide_con_la_camara() -> None:
    """Fuera de los puntos de calibracion, proyecta igual que la camara sintetica.

    Los puntos de imagen se guardan redondeados a 0,1 px, asi que la
    tolerancia es de unos centimetros.
    """
    r = calibrar_lineas([_linea(0.0, 0.0), _linea(3.5, DESFASE)], (ANCHO, ALTO))
    proyector = ProyectorCamino(r.homografia)
    for p in [(-8.0, -3.0), (5.0, 6.0), (30.0, 1.75), (40.0, 7.0)]:
        assert math.dist(proyector.proyectar(_a_imagen(*p)), p) < 0.1
