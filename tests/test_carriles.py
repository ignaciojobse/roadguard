"""RF4, Paso 4. Asignacion de carril y confirmacion de cambios completos.

Casos minimos a cubrir:
  - Un punto dentro de un carril recibe su indice y una confianza que cae
    hacia la linea divisoria; fuera de todo carril -> (None, 0.0).
  - Un cambio se confirma solo tras permanencia estable en el nuevo carril,
    registrando t_cruce y t_confirmacion.
  - Las oscilaciones sobre la linea y los cruces breves no generan cambio,
    y por lo tanto no activan zigzag (RF8).
"""

import pytest

from roadguard.m3_geometria.carriles import DetectorCambioCarril, asignar_carril
from roadguard.m4_reglas.zigzag import ReglaZigzag
from roadguard.tipos import Carril, Umbrales

# Dos carriles verticales en perspectiva: 0 a la izquierda, 1 a la derecha.
CARRILES = [
    Carril(0, [(100, 0), (150, 0), (150, 400), (0, 400)]),
    Carril(1, [(150, 0), (200, 0), (300, 400), (150, 400)]),
]


def test_asignacion_y_confianza() -> None:
    carril, conf = asignar_carril((75, 400 - 1e-6), CARRILES)
    assert carril == 0 and conf == pytest.approx(1.0, abs=1e-3)
    carril, conf = asignar_carril((140, 200), CARRILES)
    assert carril == 0 and 0 < conf < 0.5
    carril, conf = asignar_carril((225, 300), CARRILES)
    assert carril == 1 and conf > 0.6


def test_fuera_de_todo_carril() -> None:
    assert asignar_carril((500, 500), CARRILES) == (None, 0.0)


def test_carriles_horizontales_usan_la_seccion_vertical() -> None:
    horizontal = [Carril(0, [(0, 0), (1000, 0), (1000, 40), (0, 40)])]
    carril, conf = asignar_carril((10, 20), horizontal)
    assert carril == 0 and conf == pytest.approx(1.0)
    assert asignar_carril((500, 38), horizontal)[1] == pytest.approx(0.1)


def _secuencia(det: DetectorCambioCarril, obs, fps: float = 25.0):
    cambios = []
    for i, (carril, conf) in enumerate(obs):
        c = det.actualizar(1, carril, i / fps, conf)
        if c is not None:
            cambios.append(c)
    return cambios


def test_confirma_cambio_completo_con_latencia() -> None:
    det = DetectorCambioCarril(confianza_min=0.6, permanencia=1.0)
    obs = [(0, 0.9)] * 50 + [(1, 0.3)] * 5 + [(1, 0.9)] * 40
    cambios = _secuencia(det, obs)
    assert len(cambios) == 1
    c = cambios[0]
    assert (c.carril_origen, c.carril_destino) == (0, 1)
    assert c.t_cruce == pytest.approx(50 / 25)
    assert c.t_confirmacion == pytest.approx(80 / 25)  # 1 s de permanencia confiable
    assert c.t_confirmacion - c.t_cruce == pytest.approx(1.2)


def test_carril_inicial_no_es_cambio() -> None:
    det = DetectorCambioCarril(0.6, 1.0)
    assert _secuencia(det, [(1, 0.9)] * 60) == []
    assert det.carril_estable(1) == 1


def test_oscilacion_sobre_la_linea_no_confirma() -> None:
    det = DetectorCambioCarril(0.6, 1.0)
    obs = [(0, 0.9)] * 30
    # zigzaguea sobre la linea: alterna carril con baja confianza
    for _ in range(10):
        obs += [(1, 0.2)] * 4 + [(0, 0.2)] * 4
    obs += [(0, 0.9)] * 30
    assert _secuencia(det, obs) == []


def test_cruce_breve_no_confirma() -> None:
    det = DetectorCambioCarril(0.6, 1.0)
    obs = [(0, 0.9)] * 30 + [(1, 0.9)] * 15 + [(0, 0.9)] * 30
    assert _secuencia(det, obs) == []


def test_oscilaciones_no_activan_zigzag(umbrales: Umbrales) -> None:
    det = DetectorCambioCarril(0.6, 1.0)
    zigzag = ReglaZigzag(umbrales)
    obs = [(0, 0.9)] * 30
    for _ in range(6):
        obs += [(1, 0.9)] * 10 + [(0, 0.9)] * 10   # cruces de 0,4 s
    eventos = [zigzag.evaluar(c, c.t_confirmacion) for c in _secuencia(det, obs)]
    assert [e for e in eventos if e is not None] == []


def test_dos_cambios_completos_activan_zigzag(umbrales: Umbrales) -> None:
    det = DetectorCambioCarril(0.6, 1.0)
    zigzag = ReglaZigzag(umbrales)
    obs = [(0, 0.9)] * 30 + [(1, 0.9)] * 40 + [(0, 0.9)] * 40
    cambios = _secuencia(det, obs)
    assert len(cambios) == 2
    eventos = [zigzag.evaluar(c, c.t_confirmacion) for c in cambios]
    assert eventos[0] is None and eventos[1] is not None
