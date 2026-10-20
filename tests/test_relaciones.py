"""RF6 Relaciones viales (m3_geometria/relaciones.py).

Casos minimos a cubrir:
  - THW = distancia / velocidad del seguidor.
  - TTC solo se calcula con tasa de cierre positiva; si no, None.
  - Division invalida o ausencia de predecesor -> None (Paso 3).
  - Sin calibracion, distancia, THW y TTC quedan en None (Paso 5).
"""

from typing import Optional

import pytest

from roadguard.m3_geometria.relaciones import calcular_relaciones, calcular_thw, calcular_ttc
from roadguard.tipos import EstadoCinematico


def _estado(id_v: int, x: Optional[float], v: Optional[float], carril: Optional[int] = 0, calibrado: bool = True) -> EstadoCinematico:
    return EstadoCinematico(id_v, 0, 0.0, x, None if x is None else 1.0, v, carril, 0.9, calibrado)


def test_thw() -> None:
    assert calcular_thw(30.0, 20.0) == pytest.approx(1.5)
    assert calcular_thw(30.0, 0.0) is None
    assert calcular_thw(30.0, -3.0) is None
    assert calcular_thw(30.0, None) is None
    assert calcular_thw(None, 20.0) is None
    assert calcular_thw(float("nan"), 20.0) is None


def test_ttc() -> None:
    assert calcular_ttc(30.0, 10.0) == pytest.approx(3.0)
    assert calcular_ttc(30.0, 0.0) is None     # sin cierre
    assert calcular_ttc(30.0, -2.0) is None    # se alejan
    assert calcular_ttc(None, 5.0) is None
    assert calcular_ttc(30.0, None) is None


def test_relaciones_por_carril() -> None:
    estados = [
        _estado(1, 0.0, 25.0),          # ultimo del carril 0
        _estado(2, 30.0, 20.0),         # delante de 1
        _estado(3, 80.0, 30.0),         # lider del carril 0
        _estado(4, 10.0, 22.0, carril=1),
    ]
    rel = {r.id_seguidor: r for r in calcular_relaciones(estados, cuadro=5, t=0.2)}
    assert len(rel) == 4
    r1 = rel[1]
    assert r1.id_predecesor == 2 and r1.cuadro == 5 and r1.t == 0.2 and r1.carril == 0
    assert r1.distancia == pytest.approx(30.0)
    assert r1.thw == pytest.approx(30.0 / 25.0)
    assert r1.ttc == pytest.approx(30.0 / 5.0)
    r2 = rel[2]
    assert r2.id_predecesor == 3
    assert r2.ttc is None                       # el predecesor se aleja
    for lider in (3, 4):                         # ausencia de predecesor
        assert rel[lider].id_predecesor is None
        assert (rel[lider].distancia, rel[lider].thw, rel[lider].ttc) == (None, None, None)


def test_velocidad_no_disponible() -> None:
    rel = {r.id_seguidor: r for r in calcular_relaciones([_estado(1, 0.0, None), _estado(2, 20.0, 10.0)], 0, 0.0)}
    assert rel[1].distancia == pytest.approx(20.0)
    assert rel[1].thw is None and rel[1].ttc is None


def test_sin_carril_no_hay_predecesor() -> None:
    rel = {r.id_seguidor: r for r in calcular_relaciones([_estado(1, 0.0, 20.0, carril=None), _estado(2, 20.0, 10.0)], 0, 0.0)}
    assert rel[1].id_predecesor is None


def test_sin_calibracion_todo_none() -> None:
    estados = [_estado(1, None, None, calibrado=False), _estado(2, None, None, calibrado=False)]
    for r in calcular_relaciones(estados, 0, 0.0):
        assert (r.id_predecesor, r.distancia, r.thw, r.ttc) == (None, None, None, None)
