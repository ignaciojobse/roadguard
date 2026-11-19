"""M6: degradacion de trayectorias y F1 de reglas de punta a punta."""

import numpy as np
import pytest

from roadguard.m3_geometria.relaciones import calcular_relaciones
from roadguard.m6_evaluacion.degradacion import (
    AsignadorCarrilNGSIM,
    ParametrosDegradacion,
    degradar,
    evaluar_degradacion,
    eventos_m4_limpio,
    fraccion_con_respaldo,
    remuestrear,
    simular_sistema,
)
from roadguard.m6_evaluacion.emparejamiento import evaluar_eventos
from roadguard.m6_evaluacion.ngsim import CuadroReferencia
from roadguard.m6_evaluacion.referencia import EventoReferencia, eventos_referencia
from roadguard.tipos import EstadoCinematico, Regla, Umbrales

CENTROS = {1: 2.0, 2: 5.5}


def _cuadros(trayectorias, duracion=6.0, fps=10.0):
    """trayectorias: id -> (x0, v, carril). Movimiento uniforme en su carril."""
    cuadros = []
    for k in range(int(round(duracion * fps)) + 1):
        t = k / fps
        estados = [
            EstadoCinematico(vid, k, t, x0 + v * t, CENTROS[carril], v, carril, 1.0, True)
            for vid, (x0, v, carril) in trayectorias.items()
        ]
        cuadros.append(CuadroReferencia(k, t, estados, calcular_relaciones(estados, k, t)))
    return cuadros


def _seguidor_pegado():
    # El 2 va 10 m detras del 1 a 10 m/s: THW 1,0 s durante 6 s. El 3 va solo.
    return _cuadros({1: (30.0, 10.0, 1), 2: (20.0, 10.0, 1), 3: (0.0, 12.0, 2)})


def test_remuestrear_interpola_a_25_hz():
    serie = remuestrear([(0.0, 0.0, 1.0), (0.1, 1.0, 1.0), (0.2, 2.0, 1.0)], 25.0)
    assert [i for i, _, _ in serie] == [0, 1, 2, 3, 4, 5]
    assert [round(x, 6) for _, x, _ in serie] == [0.0, 0.4, 0.8, 1.2, 1.6, 2.0]


def test_remuestrear_respeta_huecos_del_origen():
    serie = remuestrear(
        [(0.0, 0.0, 0.0), (0.1, 1.0, 0.0), (0.5, 5.0, 0.0), (0.6, 6.0, 0.0)], 25.0
    )
    indices = [i for i, _, _ in serie]
    # 0,1 s y 0,5 s caen en los indices 2,5 y 12,5: entre 2 y 13 no hay muestras
    assert indices == [0, 1, 2, 13, 14, 15]


def test_asignador_carril_confianza_y_zona_auxiliar():
    a = AsignadorCarrilNGSIM([2.0, 5.5, 9.0, 12.5, 16.0, 20.0], {7: (0.0, 50.0), 6: (50.0, 120.0)})
    assert a.asignar(10.0, 2.0) == (1, 1.0)
    carril, confianza = a.asignar(10.0, 3.75)
    assert carril == 2 and confianza == pytest.approx(0.0)
    carril, confianza = a.asignar(10.0, 4.625)
    assert carril == 2 and confianza == pytest.approx(0.5)
    assert a.asignar(10.0, -5.0) == (None, 0.0)
    assert a.asignar(10.0, 20.0)[0] == 7
    assert a.asignar(80.0, 20.0)[0] == 6
    assert a.asignar(200.0, 20.0)[0] == 6  # fuera de tramo: el mas cercano


def test_asignador_desde_cuadros_usa_la_mediana_por_carril():
    a = AsignadorCarrilNGSIM.desde_cuadros(_seguidor_pegado())
    assert a.centros == [2.0, 5.5]


def test_degradar_sin_defectos_conserva_posiciones_e_ids():
    cuadros = _seguidor_pegado()
    deg = degradar(cuadros, ParametrosDegradacion())
    assert len(deg) == 151  # 6 s a 25 Hz, extremos incluidos
    obs = {o.id_degradado: o for o in deg[50].observaciones}  # t = 2,0 s
    assert deg[50].t == pytest.approx(2.0)
    assert obs[2].x == pytest.approx(40.0) and obs[2].y == pytest.approx(2.0)
    assert all(o.id_degradado == o.id_original for c in deg for o in c.observaciones)


def test_ruido_ar1_tiene_la_desviacion_y_autocorrelacion_pedidas():
    cuadros = _cuadros({1: (0.0, 10.0, 1)}, duracion=400.0)
    p = ParametrosDegradacion(sigma_x=0.4, autocorrelacion_x=0.9, semilla=3)
    deg = degradar(cuadros, p)
    error = np.array([c.observaciones[0].x - 10.0 * c.t for c in deg])
    assert error.std() == pytest.approx(0.4, rel=0.15)
    assert np.corrcoef(error[:-1], error[1:])[0, 1] == pytest.approx(0.9, abs=0.03)


def test_perdidas_respetan_la_fraccion_y_el_hueco_medio():
    cuadros = _cuadros({i: (10.0 * i, 10.0, 1) for i in range(1, 6)}, duracion=200.0)
    p = ParametrosDegradacion(fraccion_perdida=0.3, duracion_hueco=1.0, semilla=1)
    deg = degradar(cuadros, p)
    vistas = sum(len(c.observaciones) for c in deg)
    total = 5 * (200 * 25 + 1)
    assert 1 - vistas / total == pytest.approx(0.3, abs=0.05)


def test_degradar_es_reproducible_con_la_misma_semilla():
    cuadros = _seguidor_pegado()
    p = ParametrosDegradacion(sigma_x=0.3, fraccion_perdida=0.2, cambios_id_por_s=0.5, semilla=7)
    a, b = degradar(cuadros, p), degradar(cuadros, p)
    assert [(o.id_degradado, o.x) for c in a for o in c.observaciones] == [
        (o.id_degradado, o.x) for c in b for o in c.observaciones
    ]


def test_cambios_de_id_fragmentan_pero_los_eventos_vuelven_al_id_original():
    cuadros = _seguidor_pegado()
    p = ParametrosDegradacion(cambios_id_por_s=0.3, semilla=2)
    deg = degradar(cuadros, p)
    assert any(o.id_degradado != o.id_original for c in deg for o in c.observaciones)
    a = AsignadorCarrilNGSIM.desde_cuadros(cuadros)
    eventos = simular_sistema(deg, Umbrales(), a, p.fps)
    assert eventos and all(e.id_vehiculo in (1, 2, 3) for e in eventos)
    assert all(e.id_relacionado in (None, 1, 2, 3) for e in eventos)


def test_sistema_sin_ruido_detecta_la_cercania_de_referencia():
    cuadros = _seguidor_pegado()
    r = evaluar_degradacion(cuadros, ParametrosDegradacion())
    assert r.referencia == 1
    assert r.por_regla[Regla.CERCANIA].f1 == pytest.approx(1.0)
    assert r.con_respaldo[Regla.CERCANIA] == pytest.approx(1.0)
    assert r.por_regla[Regla.ZIGZAG].f1 is None  # sin eventos en ningun lado (Paso 3)


def test_m4_limpio_coincide_con_la_referencia():
    cuadros = _seguidor_pegado()
    u = Umbrales()
    resultado = evaluar_eventos(eventos_m4_limpio(cuadros, u), eventos_referencia(cuadros, u))
    assert resultado[Regla.CERCANIA].f1 == pytest.approx(1.0)


def test_fraccion_con_respaldo_cuenta_fragmentos_como_respaldados():
    ref = [EventoReferencia(1, Regla.CERCANIA, 0.0, 10.0)]
    fragmentos = [
        EventoReferencia(1, Regla.CERCANIA, 0.0, 4.0),
        EventoReferencia(1, Regla.CERCANIA, 5.0, 10.0),
    ]
    assert fraccion_con_respaldo(fragmentos, ref) == 1.0
    espurio = fragmentos + [EventoReferencia(2, Regla.CERCANIA, 0.0, 3.0)]
    assert fraccion_con_respaldo(espurio, ref) == pytest.approx(2 / 3)
    assert fraccion_con_respaldo([], ref) is None
    # F1 uno a uno: el segundo fragmento es falso positivo
    r = evaluar_eventos(fragmentos, ref)[Regla.CERCANIA]
    assert (r.verdaderos_positivos, r.falsos_positivos) == (1, 1)


def test_escalado_multiplica_solo_la_posicion():
    p = ParametrosDegradacion(sigma_x=0.3, sigma_y=0.1, fraccion_perdida=0.2)
    q = p.escalado(2.0)
    assert (q.sigma_x, q.sigma_y, q.fraccion_perdida) == (0.6, 0.2, 0.2)
