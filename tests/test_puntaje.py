"""RF10/RF11. Puntaje temporal y bandas (m4_reglas/puntaje.py).

Casos minimos a cubrir:
  - Aportes 40 / 35 / 50 segun regla.
  - El total se limita a 100.
  - Cada aporte se retira a los 5 s.
  - Bandas: 0-29 verde, 30-59 amarillo, 60-100 rojo.
"""

import pytest

from roadguard.m4_reglas.motor import MotorReglas
from roadguard.m4_reglas.puntaje import AcumuladorPuntaje, nivel_desde_puntaje
from roadguard.tipos import EstadoCinematico, Evento, NivelRiesgo, Regla, Relacion, Umbrales


def _evento(regla: Regla, t: float, aporte: int, id_v: int = 1) -> Evento:
    return Evento(id_v, regla, t_inicio=t - 1.0, t_fin=t, variables={"x": 1.0}, umbrales={"y": 1.0}, aporte_puntaje=aporte)


@pytest.mark.parametrize(
    "regla, aporte, nivel",
    [
        (Regla.CERCANIA, 40, NivelRiesgo.AMARILLO),
        (Regla.ZIGZAG, 35, NivelRiesgo.AMARILLO),
        (Regla.CORTE, 50, NivelRiesgo.AMARILLO),
    ],
)
def test_aporte_por_regla(umbrales: Umbrales, regla: Regla, aporte: int, nivel: NivelRiesgo) -> None:
    acc = AcumuladorPuntaje(umbrales)
    acc.registrar(_evento(regla, 1.0, aporte))
    p = acc.puntaje_en(1, 1.0)
    assert (p.puntaje, p.nivel) == (aporte, nivel)


def test_total_limitado_a_100(umbrales: Umbrales) -> None:
    acc = AcumuladorPuntaje(umbrales)
    acc.registrar(_evento(Regla.CERCANIA, 1.0, 40))
    acc.registrar(_evento(Regla.ZIGZAG, 1.5, 35))
    acc.registrar(_evento(Regla.CORTE, 2.0, 50))
    p = acc.puntaje_en(1, 2.0)
    assert p.puntaje == 100
    assert p.nivel is NivelRiesgo.ROJO


def test_cada_aporte_caduca_a_los_5s(umbrales: Umbrales) -> None:
    acc = AcumuladorPuntaje(umbrales)
    acc.registrar(_evento(Regla.CERCANIA, 1.0, 40))
    acc.registrar(_evento(Regla.CORTE, 3.0, 50))
    assert acc.puntaje_en(1, 5.9).puntaje == 90
    assert acc.puntaje_en(1, 6.0).puntaje == 50   # el aporte de t=1 ya caduco
    assert acc.puntaje_en(1, 7.99).puntaje == 50
    assert acc.puntaje_en(1, 8.0).puntaje == 0


def test_no_cuenta_aportes_registrados_despues_de_t(umbrales: Umbrales) -> None:
    acc = AcumuladorPuntaje(umbrales)
    acc.registrar(_evento(Regla.CORTE, 3.0, 50))
    assert acc.puntaje_en(1, 2.0).puntaje == 0


def test_puntaje_por_vehiculo(umbrales: Umbrales) -> None:
    acc = AcumuladorPuntaje(umbrales)
    acc.registrar(_evento(Regla.CORTE, 1.0, 50, id_v=1))
    assert acc.puntaje_en(2, 1.0).puntaje == 0
    assert acc.puntaje_en(2, 1.0).nivel is NivelRiesgo.VERDE


@pytest.mark.parametrize(
    "puntaje, nivel",
    [
        (0, NivelRiesgo.VERDE),
        (29, NivelRiesgo.VERDE),
        (30, NivelRiesgo.AMARILLO),
        (59, NivelRiesgo.AMARILLO),
        (60, NivelRiesgo.ROJO),
        (100, NivelRiesgo.ROJO),
    ],
)
def test_bandas(umbrales: Umbrales, puntaje: int, nivel: NivelRiesgo) -> None:
    assert nivel_desde_puntaje(puntaje, umbrales) is nivel


def test_motor_registra_aporte_de_cercania(umbrales: Umbrales) -> None:
    motor = MotorReglas(umbrales)
    eventos = []
    for i in range(0, 51):
        t = i / 25.0
        estado = EstadoCinematico(1, i, t, 10.0, 0.0, 20.0, 0, 1.0, True)
        rel = Relacion(1, 2, i, t, 0, 20.0, 1.0, None)
        eventos += motor.procesar_cuadro(t, [estado], [rel], [])
    assert [e.regla for e in eventos] == [Regla.CERCANIA]
    assert all(e.variables and e.umbrales for e in eventos)  # trazabilidad
    assert motor.puntajes([1], 2.0)[1].puntaje == 40
    assert motor.puntajes([1], 7.0)[1].puntaje == 0
