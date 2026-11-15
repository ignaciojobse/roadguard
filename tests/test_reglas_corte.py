import pytest

from roadguard.m4_reglas.corte import DetectorCorte
from roadguard.tipos import CambioCarril, Regla, Relacion, Umbrales


def _rel(seguidor, pred, t, carril=1, thw=2.0, ttc=None, distancia=20.0, cuadro=0):
    return Relacion(seguidor, pred, cuadro, t, carril, distancia, thw, ttc)


def _cambio(t_cruce=1.0, latencia=1.0, ident=1, origen=0, destino=1):
    return CambioCarril(ident, origen, destino, t_cruce, t_cruce + latencia)


def _correr(d, frames, cambios_en):
    """frames: lista de (t, relaciones). cambios_en: {t: [cambios]}."""
    salida = []
    for t, rels in frames:
        salida.extend(d.actualizar(t, rels, cambios_en.get(t, [])))
    return salida


def test_thw_bajo_tras_cambio_emite_corte_para_el_que_cambio():
    d = DetectorCorte()
    c = _cambio(1.0)
    out = _correr(
        d,
        [(0.0, []), (1.0, [_rel(2, 1, 1.0, thw=2.0)]), (2.0, [_rel(2, 1, 2.0, thw=2.0)]),
         (2.5, [_rel(2, 1, 2.5, thw=1.0)])],
        {2.0: [c]},
    )
    assert len(out) == 1
    ev = out[0]
    assert ev.regla is Regla.CORTE
    assert ev.id_vehiculo == 1 and ev.id_relacionado == 2
    assert ev.t_inicio == 1.0 and ev.t_fin == 2.5
    assert ev.variables["thw"] == 1.0 and ev.variables["ttc"] is None
    assert ev.umbrales["corte_ttc_max"] == 3.0
    assert ev.aporte_puntaje == Umbrales().aporte_corte


def test_observacion_entre_cruce_y_confirmacion_se_recupera_del_historial():
    d = DetectorCorte()
    c = _cambio(1.0, latencia=1.0)
    out = _correr(
        d,
        [(0.5, []), (1.2, [_rel(2, 1, 1.2, thw=0.8)]), (1.6, [_rel(2, 1, 1.6, thw=2.5)]),
         (2.0, [_rel(2, 1, 2.0, thw=2.5)])],
        {2.0: [c]},
    )
    assert len(out) == 1 and out[0].t_fin == 1.2


def test_ttc_bajo_basta_aunque_thw_sea_alto():
    d = DetectorCorte()
    out = _correr(
        d,
        [(2.0, [_rel(2, 1, 2.0, thw=2.0, ttc=2.0)])],
        {2.0: [_cambio(1.0)]},
    )
    assert len(out) == 1 and out[0].variables["ttc"] == 2.0


def test_fuera_de_ventana_no_emite():
    d = DetectorCorte()
    out = _correr(
        d,
        [(2.0, [_rel(2, 1, 2.0, thw=2.0)]), (3.0, [_rel(2, 1, 3.0, thw=2.0)]),
         (3.5, [_rel(2, 1, 3.5, thw=0.5)])],
        {2.0: [_cambio(1.0)]},
    )
    assert out == []


def test_un_solo_evento_por_cambio():
    d = DetectorCorte()
    out = _correr(
        d,
        [(2.0, [_rel(2, 1, 2.0, thw=1.0)]), (2.4, [_rel(2, 1, 2.4, thw=0.9)]),
         (2.8, [_rel(2, 1, 2.8, thw=0.8)])],
        {2.0: [_cambio(1.0)]},
    )
    assert len(out) == 1


def test_seguidor_queda_fijo_en_el_primero_observado():
    d = DetectorCorte()
    out = _correr(
        d,
        [(2.0, [_rel(2, 1, 2.0, thw=2.0)]), (2.5, [_rel(3, 1, 2.5, thw=0.5)])],
        {2.0: [_cambio(1.0)]},
    )
    assert out == []


def test_relacion_en_otro_carril_no_cuenta():
    d = DetectorCorte()
    out = _correr(d, [(2.0, [_rel(2, 1, 2.0, carril=0, thw=0.5)])], {2.0: [_cambio(1.0)]})
    assert out == []


def test_sin_calibracion_se_suspende_sin_romper():
    d = DetectorCorte()
    out = _correr(
        d,
        [(2.0, [_rel(2, 1, 2.0, thw=None, ttc=None, distancia=None)]),
         (2.5, [_rel(2, 1, 2.5, thw=None, ttc=None, distancia=None)])],
        {2.0: [_cambio(1.0)]},
    )
    assert out == []


def test_cambios_de_dos_vehiculos_en_el_mismo_cuadro():
    d = DetectorCorte()
    out = d.actualizar(
        2.0,
        [_rel(2, 1, 2.0, thw=1.0), _rel(4, 3, 2.0, thw=1.0, carril=2)],
        [_cambio(1.0, ident=1), _cambio(1.5, latencia=0.5, ident=3, origen=1, destino=2)],
    )
    assert [(e.id_vehiculo, e.id_relacionado) for e in out] == [(1, 2), (3, 4)]


def test_umbrales_personalizados():
    d = DetectorCorte(Umbrales(corte_thw_max=0.5, corte_ventana_post_cambio=5.0))
    out = _correr(
        d,
        [(2.0, [_rel(2, 1, 2.0, thw=1.0)]), (5.5, [_rel(2, 1, 5.5, thw=0.4)])],
        {2.0: [_cambio(1.0)]},
    )
    assert len(out) == 1 and out[0].t_fin == 5.5


def test_rechazos_y_finalizar():
    d = DetectorCorte()
    with pytest.raises(ValueError):
        d.actualizar(1.5, [], [_cambio(1.0)])
    d.actualizar(2.0, [], [])
    with pytest.raises(ValueError):
        d.actualizar(2.0, [], [])
    assert d.finalizar() == []
    assert d.finalizar() == []
    with pytest.raises(ValueError):
        d.actualizar(3.0, [], [])


@pytest.mark.parametrize("kw", [{"corte_thw_max": 0}, {"corte_ttc_max": -1}, {"corte_ventana_post_cambio": 0}, {"aporte_corte": -5}])
def test_umbrales_invalidos(kw):
    with pytest.raises(ValueError):
        DetectorCorte(Umbrales(**kw))
