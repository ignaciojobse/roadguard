import pytest

from roadguard.m4_reglas.puntaje import CalculadorPuntaje, nivel_de
from roadguard.tipos import Evento, NivelRiesgo, Regla, Umbrales


def _ev(regla, ident=1, t_inicio=0.0, t_fin=1.0, aporte=None, rel=None):
    u = Umbrales()
    if aporte is None:
        aporte = {
            Regla.CERCANIA: u.aporte_cercania,
            Regla.ZIGZAG: u.aporte_zigzag,
            Regla.CORTE: u.aporte_corte,
        }[regla]
    return Evento(ident, regla, t_inicio, t_fin, {}, {}, aporte, rel)


def test_sin_eventos_puntaje_cero_verde():
    c = CalculadorPuntaje()
    out = c.actualizar(0.0, [1, 2])
    assert set(out) == {1, 2}
    assert out[1].puntaje == 0 and out[1].nivel is NivelRiesgo.VERDE and out[1].t == 0.0


def test_cercania_activa_suma_y_caduca_tras_vigencia():
    c = CalculadorPuntaje()
    assert c.actualizar(0.0, [1], cercania_activa=[_ev(Regla.CERCANIA)])[1].puntaje == 40
    assert c.actualizar(1.0, [1], cercania_activa=[_ev(Regla.CERCANIA)])[1].puntaje == 40
    # se deja de observar en t=1: sigue vigente hasta t=6 inclusive
    assert c.actualizar(6.0, [1])[1].puntaje == 40
    assert c.actualizar(6.1, [1])[1].puntaje == 0


def test_eventos_se_suman_con_tope_y_nivel_rojo():
    c = CalculadorPuntaje()
    out = c.actualizar(
        0.0, [1],
        cercania_activa=[_ev(Regla.CERCANIA)],
        eventos_nuevos=[_ev(Regla.ZIGZAG), _ev(Regla.CORTE, rel=2)],
    )
    assert out[1].puntaje == 100 and out[1].nivel is NivelRiesgo.ROJO


def test_mismo_evento_repetido_no_duplica():
    c = CalculadorPuntaje()
    ev = _ev(Regla.ZIGZAG)
    c.actualizar(0.0, [1], eventos_nuevos=[ev])
    assert c.actualizar(1.0, [1], eventos_nuevos=[ev])[1].puntaje == 35


def test_dos_cortes_distintos_suman():
    c = CalculadorPuntaje()
    out = c.actualizar(0.0, [1], eventos_nuevos=[_ev(Regla.CORTE, rel=2), _ev(Regla.CORTE, t_inicio=3.0, rel=5)])
    assert out[1].puntaje == 100


def test_bandas():
    u = Umbrales()
    assert nivel_de(0, u) is NivelRiesgo.VERDE
    assert nivel_de(29, u) is NivelRiesgo.VERDE
    assert nivel_de(30, u) is NivelRiesgo.AMARILLO
    assert nivel_de(59, u) is NivelRiesgo.AMARILLO
    assert nivel_de(60, u) is NivelRiesgo.ROJO
    c = CalculadorPuntaje()
    assert c.actualizar(0.0, [1], eventos_nuevos=[_ev(Regla.ZIGZAG)])[1].nivel is NivelRiesgo.AMARILLO


def test_vehiculo_ausente_conserva_aporte_hasta_que_vuelve():
    c = CalculadorPuntaje()
    c.actualizar(0.0, [1], eventos_nuevos=[_ev(Regla.CORTE, rel=2)])
    assert 1 not in c.actualizar(2.0, [3])
    assert c.actualizar(4.0, [1])[1].puntaje == 50
    assert c.actualizar(9.0, [1])[1].puntaje == 0


def test_vigencia_personalizada_y_tope():
    c = CalculadorPuntaje(Umbrales(vigencia_aporte=1.0, puntaje_maximo=60, banda_verde_max=10, banda_amarillo_max=30))
    assert c.actualizar(0.0, [1], eventos_nuevos=[_ev(Regla.CORTE, rel=2), _ev(Regla.ZIGZAG)])[1].puntaje == 60
    assert c.actualizar(1.5, [1])[1].puntaje == 0


def test_aporte_viene_del_evento():
    c = CalculadorPuntaje()
    assert c.actualizar(0.0, [1], eventos_nuevos=[_ev(Regla.ZIGZAG, aporte=7)])[1].puntaje == 7


def test_rechazos():
    c = CalculadorPuntaje()
    c.actualizar(1.0, [1])
    with pytest.raises(ValueError):
        c.actualizar(0.5, [1])
    with pytest.raises(ValueError):
        c.actualizar(2.0, [1], eventos_nuevos=[_ev(Regla.ZIGZAG, aporte=-1)])


@pytest.mark.parametrize(
    "kw",
    [{"puntaje_maximo": 0}, {"vigencia_aporte": 0.0}, {"banda_verde_max": 70}, {"banda_amarillo_max": 100}],
)
def test_umbrales_invalidos(kw):
    with pytest.raises(ValueError):
        CalculadorPuntaje(Umbrales(**kw))
