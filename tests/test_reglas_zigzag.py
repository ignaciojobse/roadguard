import pytest

from roadguard.m4_reglas.zigzag import DetectorZigzag
from roadguard.tipos import CambioCarril, Regla, Umbrales


def _cambio(t_cruce, origen=0, destino=1, ident=1, latencia=1.0):
    return CambioCarril(ident, origen, destino, t_cruce, t_cruce + latencia)


def test_un_cambio_no_basta_y_el_segundo_en_ventana_emite():
    d = DetectorZigzag()
    assert d.actualizar(1.0, [_cambio(0.0)]) == []
    assert d.actualizar(2.0, []) == []
    out = d.actualizar(5.0, [_cambio(4.0, 1, 0)])
    assert len(out) == 1
    ev = out[0]
    assert ev.regla is Regla.ZIGZAG and ev.id_vehiculo == 1
    assert ev.t_inicio == 0.0 and ev.t_fin == 5.0
    assert ev.variables["n_cambios"] == 2
    assert ev.umbrales == {"zigzag_cambios_min": 2.0, "zigzag_ventana": 10.0}
    assert ev.aporte_puntaje == Umbrales().aporte_zigzag


def test_cambios_separados_mas_de_la_ventana_no_cuentan():
    d = DetectorZigzag()
    d.actualizar(1.0, [_cambio(0.0)])
    assert d.actualizar(12.0, [_cambio(11.0, 1, 0)]) == []
    # el tercero si forma racha con el segundo
    assert len(d.actualizar(16.0, [_cambio(15.0)])) == 1


def test_racha_prolongada_no_duplica_evento():
    d = DetectorZigzag()
    d.actualizar(1.0, [_cambio(0.0)])
    assert len(d.actualizar(4.0, [_cambio(3.0, 1, 0)])) == 1
    assert d.actualizar(7.0, [_cambio(6.0)]) == []
    assert d.actualizar(10.0, [_cambio(9.0, 1, 0)]) == []
    assert d.actualizar(11.0, []) == []


def test_ventana_borde_y_cruces_demora_variable_con_intermedios_vacios():
    d = DetectorZigzag()
    d.actualizar(1.0, [_cambio(0.0)])
    assert d.actualizar(10.2, []) == []
    assert len(d.actualizar(10.5, [_cambio(10.0, 1, 0, latencia=0.5)])) == 1


def test_ventana_excluye_cruce_ligeramente_fuera_del_borde():
    d = DetectorZigzag()
    d.actualizar(1.0, [_cambio(0.0)])
    d.actualizar(10.2, [])
    assert d.actualizar(10.5, [_cambio(10.00001, 1, 0, latencia=0.49)]) == []


def test_confirmacion_tardia_no_purga_cruces_por_reloj_actual():
    d = DetectorZigzag()
    d.actualizar(1.0, [_cambio(0.0)])
    d.actualizar(10.2, [])
    d.actualizar(11.0, [])
    assert len(d.actualizar(12.5, [_cambio(9.5, 1, 0, latencia=3.0)])) == 1


def test_historial_racha_acotado_sin_duplicar_evento_ni_alterar_variables():
    d = DetectorZigzag()
    evento = None
    for i in range(25):
        cruza = float(i) * 0.5
        out = d.actualizar(
            cruza + 0.1,
            [_cambio(cruza, i % 2, (i + 1) % 2, latencia=0.1)],
        )
        if out:
            evento = out[0]
        assert len(d._rachas[1].cruces) <= d.umbrales.zigzag_cambios_min
    assert evento is not None
    assert evento.variables["n_cambios"] == 2
    assert all(d.actualizar(12.6 + i * 0.1, []) == [] for i in range(3))


def test_racha_nueva_tras_cerrar_la_anterior():
    d = DetectorZigzag()
    d.actualizar(1.0, [_cambio(0.0)])
    assert len(d.actualizar(4.0, [_cambio(3.0, 1, 0)])) == 1
    assert d.actualizar(20.0, []) == []
    d.actualizar(31.0, [_cambio(30.0)])
    assert len(d.actualizar(34.0, [_cambio(33.0, 1, 0)])) == 1


def test_vehiculos_independientes_y_mismo_cuadro():
    d = DetectorZigzag()
    out = d.actualizar(5.0, [_cambio(0.0, ident=1), _cambio(4.0, 1, 0, ident=1), _cambio(4.0, ident=2)])
    assert [e.id_vehiculo for e in out] == [1]


def test_umbral_personalizado_tres_cambios():
    d = DetectorZigzag(Umbrales(zigzag_cambios_min=3, zigzag_ventana=5.0))
    d.actualizar(1.0, [_cambio(0.0)])
    assert d.actualizar(3.0, [_cambio(2.0, 1, 0)]) == []
    assert len(d.actualizar(5.0, [_cambio(4.0)])) == 1


def test_cambio_futuro_y_tiempo_no_creciente_se_rechazan():
    d = DetectorZigzag()
    with pytest.raises(ValueError):
        d.actualizar(0.5, [_cambio(0.0)])
    d.actualizar(1.0, [_cambio(0.0)])
    with pytest.raises(ValueError):
        d.actualizar(1.0, [])


def test_finalizar_vacio_idempotente_y_bloquea():
    d = DetectorZigzag()
    d.actualizar(1.0, [_cambio(0.0)])
    assert d.finalizar() == []
    assert d.finalizar() == []
    with pytest.raises(ValueError):
        d.actualizar(2.0, [])


@pytest.mark.parametrize("kw", [{"zigzag_cambios_min": 0}, {"zigzag_ventana": 0.0}, {"aporte_zigzag": -1}])
def test_umbrales_invalidos(kw):
    with pytest.raises(ValueError):
        DetectorZigzag(Umbrales(**kw))
