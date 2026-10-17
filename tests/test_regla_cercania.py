"""RF7. Cercania peligrosa (m4_reglas/cercania.py).

Casos minimos a cubrir:
  - Activa con v > 5 m/s y THW < 1,5 s sostenidos 2 s o mas.
  - No activa si la persistencia es menor a 2 s.
  - No activa si la velocidad del seguidor es <= 5 m/s.
  - No activa si THW es None (sin calibracion, Paso 5).
  - No duplica el evento mientras la condicion sigue activa (M4).
"""

from typing import Optional

import pytest

from roadguard.m4_reglas.cercania import ReglaCercania
from roadguard.tipos import Regla, Relacion, Umbrales


def _rel(t: float, thw: Optional[float], predecesor: Optional[int] = 2) -> Relacion:
    distancia = None if thw is None else thw * 20.0
    return Relacion(
        id_seguidor=1,
        id_predecesor=predecesor,
        cuadro=0,
        t=t,
        carril=0,
        distancia=distancia,
        thw=thw,
        ttc=None,
    )


def _correr(regla: ReglaCercania, fps: float, t_fin: float, thw, velocidad, t_ini: float = 0.0):
    eventos = []
    n0, n1 = round(t_ini * fps), round(t_fin * fps)
    for i in range(n0, n1 + 1):
        t = i / fps
        ev = regla.evaluar(_rel(t, thw), velocidad, t)
        if ev is not None:
            eventos.append(ev)
    return eventos


@pytest.mark.parametrize("fps", [10.0, 25.0, 30.0])
def test_activa_con_persistencia_de_2s(umbrales: Umbrales, fps: float) -> None:
    eventos = _correr(ReglaCercania(umbrales), fps, 2.0, thw=1.0, velocidad=20.0)
    assert len(eventos) == 1
    ev = eventos[0]
    assert ev.regla is Regla.CERCANIA
    assert ev.t_inicio == pytest.approx(0.0)
    assert ev.t_fin == pytest.approx(2.0)  # tiempo en segundos, no cuadros
    assert ev.id_relacionado == 2
    assert ev.aporte_puntaje == 40
    assert ev.variables["velocidad"] == 20.0
    assert ev.variables["thw"] == 1.0
    assert ev.umbrales == {"velocidad": 5.0, "thw": 1.5, "persistencia": 2.0}


def test_no_activa_con_persistencia_menor_a_2s(umbrales: Umbrales) -> None:
    regla = ReglaCercania(umbrales)
    assert _correr(regla, 25.0, 1.9, thw=1.0, velocidad=20.0) == []
    # se interrumpe la condicion y se reinicia la racha
    assert regla.evaluar(_rel(1.94, 2.0), 20.0, 1.94) is None
    assert _correr(regla, 25.0, 3.8, thw=1.0, velocidad=20.0, t_ini=1.96) == []


def test_no_activa_con_velocidad_no_mayor_a_5(umbrales: Umbrales) -> None:
    assert _correr(ReglaCercania(umbrales), 25.0, 4.0, thw=1.0, velocidad=5.0) == []
    assert _correr(ReglaCercania(umbrales), 25.0, 4.0, thw=1.0, velocidad=None) == []


def test_no_activa_con_thw_no_menor_a_1_5(umbrales: Umbrales) -> None:
    assert _correr(ReglaCercania(umbrales), 25.0, 4.0, thw=1.5, velocidad=20.0) == []


def test_no_activa_sin_thw(umbrales: Umbrales) -> None:
    assert _correr(ReglaCercania(umbrales), 25.0, 4.0, thw=None, velocidad=20.0) == []


def test_no_activa_sin_predecesor(umbrales: Umbrales) -> None:
    regla = ReglaCercania(umbrales)
    for i in range(101):
        t = i / 25.0
        assert regla.evaluar(_rel(t, 1.0, predecesor=None), 20.0, t) is None


def test_no_duplica_mientras_sigue_activa(umbrales: Umbrales) -> None:
    regla = ReglaCercania(umbrales)
    assert len(_correr(regla, 25.0, 6.0, thw=1.0, velocidad=20.0)) == 1
    # la condicion se rompe y vuelve: es una nueva activacion
    assert regla.evaluar(_rel(6.04, 3.0), 20.0, 6.04) is None
    eventos = _correr(regla, 25.0, 9.0, thw=1.0, velocidad=20.0, t_ini=6.08)
    assert len(eventos) == 1
    assert eventos[0].t_inicio == pytest.approx(6.08)


def test_cambio_de_predecesor_reinicia_la_persistencia(umbrales: Umbrales) -> None:
    regla = ReglaCercania(umbrales)
    for i in range(0, 26):
        t = i / 25.0
        assert regla.evaluar(_rel(t, 1.0, predecesor=2), 20.0, t) is None
    for i in range(26, 70):
        t = i / 25.0
        assert regla.evaluar(_rel(t, 1.0, predecesor=3), 20.0, t) is None
