"""M6: carga NGSIM, eventos de referencia y F1 de eventos (seccion 2.5)."""

from pathlib import Path

import pytest

from roadguard.m6_evaluacion.emparejamiento import (
    ResultadoEventos,
    evaluar_eventos,
    resultado_global,
)
from roadguard.m6_evaluacion.ngsim import (
    PIE_A_METRO,
    CuadroReferencia,
    cargar_ngsim,
    consulta_muestra,
)
from roadguard.m6_evaluacion.referencia import (
    EventoReferencia,
    cambios_de_carril,
    eventos_referencia,
)
from roadguard.tipos import EstadoCinematico, Regla

FPS = 10.0
ENCABEZADO = (
    "vehicle_id,frame_id,global_time,local_x,local_y,v_length,v_width,v_class,"
    "v_vel,v_acc,lane_id,preceding,following,space_headway,time_headway,location\n"
)


def _fila(vid, gt, y, v, carril, pred=0, sh=0.0):
    return f"{vid},1,{gt},6.0,{y},15,6,2,{v},0,{carril},{pred},0,{sh},0,us-101\n"


@pytest.fixture
def csv_ngsim(tmp_path: Path) -> Path:
    ruta = tmp_path / "ngsim.csv"
    ruta.write_text(
        ENCABEZADO
        + _fila(1, 1000, 100.0, 50.0, 2, pred=2, sh=40.0)
        + _fila(2, 1000, 140.0, 40.0, 2)
        + _fila(1, 1100, 105.0, 50.0, 2, pred=2, sh=39.0)
        + _fila(2, 1100, 144.0, 60.0, 2)
    )
    return ruta


# ---------------------------------------------------------------------------
# Carga NGSIM
# ---------------------------------------------------------------------------

def test_carga_convierte_unidades_y_tiempo(csv_ngsim):
    cuadros = cargar_ngsim(csv_ngsim)
    assert [c.cuadro for c in cuadros] == [0, 1]
    assert cuadros[1].t == pytest.approx(0.1)
    e = {e.id_vehiculo: e for e in cuadros[0].estados}[1]
    assert e.x_camino == pytest.approx(100.0 * PIE_A_METRO)
    assert e.velocidad == pytest.approx(50.0 * PIE_A_METRO)
    assert e.carril == 2 and e.calibrado


def test_carga_calcula_thw_y_ttc_con_las_funciones_de_m3(csv_ngsim):
    cuadros = cargar_ngsim(csv_ngsim)
    r = {r.id_seguidor: r for r in cuadros[0].relaciones}
    assert r[1].id_predecesor == 2
    assert r[1].distancia == pytest.approx(40.0 * PIE_A_METRO)
    assert r[1].thw == pytest.approx(40.0 / 50.0)
    assert r[1].ttc == pytest.approx(40.0 / 10.0)


def test_sin_predecesor_y_sin_cierre_quedan_no_disponibles(csv_ngsim):
    cuadros = cargar_ngsim(csv_ngsim)
    r0 = {r.id_seguidor: r for r in cuadros[0].relaciones}
    assert r0[2].id_predecesor is None
    assert r0[2].distancia is None and r0[2].thw is None and r0[2].ttc is None
    r1 = {r.id_seguidor: r for r in cuadros[1].relaciones}
    assert r1[1].thw is not None
    assert r1[1].ttc is None  # el predecesor va mas rapido


def test_archivo_vacio_falla(tmp_path):
    ruta = tmp_path / "vacio.csv"
    ruta.write_text(ENCABEZADO)
    with pytest.raises(ValueError):
        cargar_ngsim(ruta)


def test_consulta_filtra_ubicacion_y_ventana():
    q = consulta_muestra("us-101", 1000, 2000)
    assert "location='us-101'" in q["$where"]
    assert "global_time >= 1000" in q["$where"] and "global_time < 2000" in q["$where"]


# ---------------------------------------------------------------------------
# Escenas sinteticas para la referencia
# ---------------------------------------------------------------------------

def _escena(n_cuadros, vehiculos):
    """vehiculos: id -> funcion(t) -> (x, v, carril) o None si no se observa."""
    cuadros = []
    for k in range(n_cuadros):
        t = k / FPS
        estados = []
        for vid, f in vehiculos.items():
            obs = f(t)
            if obs is None:
                continue
            x, v, carril = obs
            estados.append(EstadoCinematico(vid, k, t, x, 0.0, v, carril, 1.0, True))
        relaciones = _relaciones(estados, k, t)
        cuadros.append(CuadroReferencia(k, t, estados, relaciones))
    return cuadros


def _relaciones(estados, k, t):
    from roadguard.m3_geometria.relaciones import calcular_relaciones

    return calcular_relaciones(estados, k, t)


def _de(eventos, regla):
    return [e for e in eventos if e.regla == regla]


# ---------------------------------------------------------------------------
# RF7 - Cercania
# ---------------------------------------------------------------------------

def _seguimiento(duracion, separacion, v=20.0):
    n = int(round(duracion * FPS)) + 1
    return _escena(
        n,
        {
            1: lambda t: (v * t, v, 1),
            2: lambda t: (v * t + separacion, v, 1),
        },
    )


def test_cercania_sostenida_dos_segundos_genera_evento(umbrales):
    eventos = _de(eventos_referencia(_seguimiento(2.0, 20.0), umbrales), Regla.CERCANIA)
    assert len(eventos) == 1
    e = eventos[0]
    assert (e.id_vehiculo, e.id_relacionado) == (1, 2)
    assert e.t_inicio == pytest.approx(0.0) and e.t_fin == pytest.approx(2.0)


def test_cercania_menor_a_la_persistencia_no_genera_evento(umbrales):
    eventos = eventos_referencia(_seguimiento(1.9, 20.0), umbrales)
    assert _de(eventos, Regla.CERCANIA) == []


def test_cercania_con_thw_holgado_no_genera_evento(umbrales):
    eventos = eventos_referencia(_seguimiento(3.0, 40.0), umbrales)
    assert _de(eventos, Regla.CERCANIA) == []


def test_cercania_a_baja_velocidad_no_genera_evento(umbrales):
    eventos = eventos_referencia(_seguimiento(3.0, 2.0, v=4.0), umbrales)
    assert _de(eventos, Regla.CERCANIA) == []


def test_cercania_se_corta_si_falta_un_cuadro(umbrales):
    cuadros = _escena(
        31,
        {
            1: lambda t: None if abs(t - 1.5) < 0.05 else (20 * t, 20.0, 1),
            2: lambda t: (20 * t + 20.0, 20.0, 1),
        },
    )
    eventos = _de(eventos_referencia(cuadros, umbrales), Regla.CERCANIA)
    assert eventos == []  # dos tramos de 1,4 s


# ---------------------------------------------------------------------------
# RF8 - Zigzag
# ---------------------------------------------------------------------------

def _carril_por_tramos(tramos):
    """tramos: lista de (t_desde, carril)."""
    def carril(t):
        actual = tramos[0][1]
        for desde, c in tramos:
            if t >= desde - 1e-9:
                actual = c
        return actual
    return carril


def _un_vehiculo(n_cuadros, carril):
    return _escena(n_cuadros, {7: lambda t: (25 * t, 25.0, carril(t))})


def test_dos_cambios_en_diez_segundos_es_zigzag(umbrales):
    cuadros = _un_vehiculo(150, _carril_por_tramos([(0, 1), (3.0, 2), (7.0, 1)]))
    assert len(cambios_de_carril(cuadros)) == 2
    eventos = _de(eventos_referencia(cuadros, umbrales), Regla.ZIGZAG)
    assert len(eventos) == 1
    assert eventos[0].t_inicio == pytest.approx(3.0)
    assert eventos[0].t_fin == pytest.approx(8.0)


def test_cambios_separados_no_son_zigzag(umbrales):
    cuadros = _un_vehiculo(200, _carril_por_tramos([(0, 1), (2.0, 2), (14.0, 1)]))
    assert len(cambios_de_carril(cuadros)) == 2
    assert _de(eventos_referencia(cuadros, umbrales), Regla.ZIGZAG) == []


def test_oscilacion_sobre_la_linea_no_es_cambio(umbrales):
    cuadros = _un_vehiculo(100, _carril_por_tramos([(0, 1), (3.0, 2), (3.4, 1), (5.0, 2), (5.3, 1)]))
    assert cambios_de_carril(cuadros) == []
    assert _de(eventos_referencia(cuadros, umbrales), Regla.ZIGZAG) == []


def test_tres_cambios_seguidos_son_un_solo_evento(umbrales):
    cuadros = _un_vehiculo(150, _carril_por_tramos([(0, 1), (2.0, 2), (5.0, 3), (8.0, 2)]))
    assert len(cambios_de_carril(cuadros)) == 3
    assert len(_de(eventos_referencia(cuadros, umbrales), Regla.ZIGZAG)) == 1


# ---------------------------------------------------------------------------
# RF9 - Corte de carril
# ---------------------------------------------------------------------------

def _corte(separacion):
    return _escena(
        60,
        {
            1: lambda t: (25 * t + 50.0, 25.0, _carril_por_tramos([(0, 1), (2.0, 2)])(t)),
            2: lambda t: (25 * t + 50.0 - separacion, 25.0, 2),
        },
    )


def test_corte_cerrado_genera_evento_para_el_que_cambia(umbrales):
    eventos = _de(eventos_referencia(_corte(20.0), umbrales), Regla.CORTE)
    assert len(eventos) == 1
    e = eventos[0]
    assert (e.id_vehiculo, e.id_relacionado) == (1, 2)
    assert e.t_inicio == pytest.approx(2.0)


def test_corte_con_distancia_holgada_no_genera_evento(umbrales):
    assert _de(eventos_referencia(_corte(60.0), umbrales), Regla.CORTE) == []


# ---------------------------------------------------------------------------
# Emparejamiento y F1
# ---------------------------------------------------------------------------

def _ev(vid, regla, t0, t1):
    return EventoReferencia(vid, regla, t0, t1)


def test_evento_desplazado_dentro_de_la_tolerancia_acierta():
    ref = [_ev(1, Regla.CERCANIA, 10.0, 12.0)]
    det = [_ev(1, Regla.CERCANIA, 12.8, 14.0)]
    r = evaluar_eventos(det, ref, tolerancia=1.0)[Regla.CERCANIA]
    assert (r.verdaderos_positivos, r.falsos_positivos, r.falsos_negativos) == (1, 0, 0)
    assert r.f1 == pytest.approx(1.0)


def test_otro_vehiculo_u_otra_regla_no_acierta():
    ref = [_ev(1, Regla.CERCANIA, 10.0, 12.0)]
    det = [_ev(2, Regla.CERCANIA, 10.0, 12.0), _ev(1, Regla.ZIGZAG, 10.0, 12.0)]
    r = evaluar_eventos(det, ref)
    assert r[Regla.CERCANIA].falsos_positivos == 1
    assert r[Regla.CERCANIA].falsos_negativos == 1
    assert r[Regla.ZIGZAG].falsos_positivos == 1


def test_emparejamiento_es_uno_a_uno():
    ref = [_ev(1, Regla.CORTE, 5.0, 6.0)]
    det = [_ev(1, Regla.CORTE, 5.0, 6.0), _ev(1, Regla.CORTE, 5.2, 6.2)]
    r = evaluar_eventos(det, ref)[Regla.CORTE]
    assert (r.verdaderos_positivos, r.falsos_positivos) == (1, 1)
    assert r.precision == pytest.approx(0.5) and r.recobrado == pytest.approx(1.0)


def test_sin_eventos_las_metricas_quedan_no_disponibles():
    r = ResultadoEventos(0, 0, 0)
    assert r.precision is None and r.recobrado is None and r.f1 is None
    assert evaluar_eventos([], []) == {}


def test_resultado_global_suma_conteos():
    ref = [_ev(1, Regla.CERCANIA, 0, 2), _ev(2, Regla.ZIGZAG, 0, 5)]
    det = [_ev(1, Regla.CERCANIA, 0, 2)]
    g = resultado_global(evaluar_eventos(det, ref))
    assert (g.verdaderos_positivos, g.falsos_positivos, g.falsos_negativos) == (1, 0, 1)
