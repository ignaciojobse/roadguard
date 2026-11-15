import pytest

from roadguard.m4_reglas import MotorReglas
from roadguard.tipos import CambioCarril, EstadoCinematico, NivelRiesgo, Regla, Relacion, Umbrales


def _estado(ident, n, t, carril=0, v=10.0, x=0.0, calibrado=True):
    return EstadoCinematico(
        ident, n, t, x if calibrado else None, 0.0 if calibrado else None,
        v if calibrado else None, carril, 0.9, calibrado,
    )


def _rel(seguidor, pred, n, t, carril=0, thw=2.0, ttc=None, calibrado=True):
    return Relacion(
        seguidor, pred, n, t, carril,
        10.0 if calibrado else None, thw if calibrado else None, ttc,
    )


def test_cercania_puntua_mientras_esta_activa_y_el_evento_llega_al_cerrar():
    m = MotorReglas()
    for n, t in enumerate([0.0, 1.0, 2.0]):
        estados = {1: _estado(1, n, t), 2: _estado(2, n, t, x=10.0)}
        rels = [_rel(1, 2, n, t, thw=1.0), _rel(2, None, n, t, thw=None)]
        eventos, puntajes = m.actualizar(t, estados, rels, [])
        assert eventos == []
    assert puntajes[1].puntaje == 40 and puntajes[1].nivel is NivelRiesgo.AMARILLO
    assert puntajes[2].puntaje == 0
    estados = {1: _estado(1, 3, 3.0), 2: _estado(2, 3, 3.0, x=30.0)}
    eventos, puntajes = m.actualizar(3.0, estados, [_rel(1, 2, 3, 3.0, thw=3.0), _rel(2, None, 3, 3.0, thw=None)], [])
    assert len(eventos) == 1 and eventos[0].regla is Regla.CERCANIA and eventos[0].t_fin == 2.0
    assert puntajes[1].puntaje == 40  # aun vigente
    assert m.finalizar() == []


def test_zigzag_y_corte_con_puntaje_acumulado_y_tope():
    m = MotorReglas()
    estados = {1: _estado(1, 0, 5.0, carril=1), 3: _estado(3, 0, 5.0, carril=1, x=-5.0)}
    rels = [_rel(1, None, 0, 5.0, carril=1, thw=None), _rel(3, 1, 0, 5.0, carril=1, thw=0.5)]
    cambios = [CambioCarril(1, 0, 1, 0.0, 1.0), CambioCarril(1, 1, 0, 2.0, 3.0), CambioCarril(1, 0, 1, 4.0, 5.0)]
    eventos, puntajes = m.actualizar(5.0, estados, rels, cambios)
    reglas = sorted(e.regla for e in eventos)
    assert reglas == [Regla.CORTE, Regla.ZIGZAG]
    corte = next(e for e in eventos if e.regla is Regla.CORTE)
    assert corte.id_vehiculo == 1 and corte.id_relacionado == 3
    assert puntajes[1].puntaje == 85 and puntajes[1].nivel is NivelRiesgo.ROJO
    assert puntajes[3].puntaje == 0


def test_sin_calibracion_no_rompe_y_deja_advertencia():
    m = MotorReglas()
    estados = {1: _estado(1, 0, 0.0, calibrado=False)}
    eventos, puntajes = m.actualizar(0.0, estados, [_rel(1, 2, 0, 0.0, calibrado=False)], [CambioCarril(1, 0, 1, -1.0, 0.0)])
    assert eventos == [] and puntajes[1].puntaje == 0
    assert m.advertencias


def test_cuadro_vacio_usa_siguiente_cuadro():
    m = MotorReglas()
    m.actualizar(0.0, {1: _estado(1, 0, 0.0)}, [_rel(1, None, 0, 0.0, thw=None)], [])
    eventos, puntajes = m.actualizar(1.0, {}, [], [])
    assert eventos == [] and puntajes == {}
    m.actualizar(2.0, {1: _estado(1, 2, 2.0)}, [_rel(1, None, 2, 2.0, thw=None)], [])


def test_estados_de_cuadros_distintos_se_rechazan():
    m = MotorReglas()
    with pytest.raises(ValueError):
        m.actualizar(0.0, {1: _estado(1, 0, 0.0), 2: _estado(2, 1, 0.0)}, [], [])


def test_finalizar_entrega_cercania_abierta_y_umbrales_se_propagan():
    m = MotorReglas(Umbrales(cercania_persistencia=0.5, aporte_cercania=10))
    for n, t in enumerate([0.0, 0.5]):
        _, puntajes = m.actualizar(t, {1: _estado(1, n, t)}, [_rel(1, 2, n, t, thw=1.0)], [])
    assert puntajes[1].puntaje == 10
    fin = m.finalizar()
    assert len(fin) == 1 and fin[0].aporte_puntaje == 10
    assert m.finalizar() == []
