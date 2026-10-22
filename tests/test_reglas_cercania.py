from dataclasses import FrozenInstanceError, replace

import pytest

from roadguard.m3_geometria.relaciones import calcular_relaciones
from roadguard.m4_reglas import DetectorCercania
from roadguard.m6_evaluacion.emparejamiento import evaluar_eventos
from roadguard.m6_evaluacion.ngsim import CuadroReferencia
from roadguard.m6_evaluacion.referencia import eventos_referencia
from roadguard.tipos import EstadoCinematico, Relacion, Regla, Umbrales


def _datos_cuadro(n, t, *, thw=1.0, pred=2, calibrated=True, ttc=None):
    estado = EstadoCinematico(
        1, n, t, 0.0 if calibrated else None, 0.0 if calibrated else None,
        10.0 if calibrated else None, 0 if calibrated else None, 0.9, calibrated,
    )
    relacion = Relacion(
        1, pred, n, t, 0 if calibrated else None,
        10.0 if calibrated else None, thw if calibrated else None, ttc,
    )
    return [estado], [relacion]


def _actualizar(detector, n, t, **kwargs):
    return detector.actualizar(n, t, *_datos_cuadro(n, t, **kwargs))


def test_duracion_1_9_no_confirma_y_umbral_temporal_confirma():
    d = DetectorCercania()
    _actualizar(d, 0, 0)
    _actualizar(d, 1, 1)
    assert not _actualizar(d, 2, 1.9).activos
    assert _actualizar(d, 3, 2.0).activos[0].variables["t_confirmacion"] == 2.0


def test_activo_cierra_sin_duplicar_y_termina_en_ultima_observacion():
    d = DetectorCercania()
    _actualizar(d, 0, 0)
    _actualizar(d, 1, 1)
    live = _actualizar(d, 2, 2)
    assert len(live.activos) == 1 and not live.cerrados
    ended = _actualizar(d, 3, 3, thw=2.0)
    assert not ended.activos and len(ended.cerrados) == 1
    assert ended.cerrados[0].t_fin == 2


def test_cambio_predecesor_cierra_tramo():
    d = DetectorCercania()
    _actualizar(d, 0, 0)
    _actualizar(d, 1, 1)
    _actualizar(d, 2, 2)
    out = _actualizar(d, 3, 3, pred=4)
    assert out.cerrados[0].id_relacionado == 2
    assert not out.activos


def test_finalizar_idempotente_y_rechaza_actualizar():
    d = DetectorCercania()
    _actualizar(d, 0, 0)
    _actualizar(d, 1, 1)
    _actualizar(d, 2, 2)
    assert len(d.finalizar()) == 1
    assert d.finalizar() == []
    with pytest.raises(ValueError):
        _actualizar(d, 3, 3)


def test_calibracion_ausente_y_thw_none_no_generan_evento():
    d = DetectorCercania()
    out = _actualizar(d, 0, 0, calibrated=False)
    assert out.advertencias and not out.activos
    out = _actualizar(d, 1, 1, thw=None)
    assert out.advertencias and not out.activos


def test_resultado_frozen_e_eventos_snapshot_isolados():
    d = DetectorCercania()
    _actualizar(d, 0, 0)
    _actualizar(d, 1, 1)
    one = _actualizar(d, 2, 2)
    with pytest.raises(FrozenInstanceError):
        one.activos = ()
    one.activos[0].variables["thw"] = 99
    two = _actualizar(d, 3, 3)
    assert two.activos[0].variables["thw"] == 1.0


def test_umbral_personalizado():
    d = DetectorCercania(
        Umbrales(cercania_velocidad_min=9, cercania_thw_max=0.8, cercania_persistencia=0.5)
    )
    assert not _actualizar(d, 0, 0, thw=1.0).activos
    assert not _actualizar(d, 1, 1, thw=0.7).activos
    assert _actualizar(d, 2, 1.5, thw=0.7).activos


def test_metadata_timestamps_rechazan_relativa_y_none_atomicamente():
    detector = DetectorCercania()
    estados, relaciones = _datos_cuadro(0, 1e9)
    estados[0] = EstadoCinematico(1, 0, 1e9 + 0.1, 0, 0, 10, 0, 0.9, True)
    with pytest.raises(ValueError):
        detector.actualizar(0, 1e9, estados, relaciones)
    estados[0] = EstadoCinematico(1, 0, None, 0, 0, 10, 0, 0.9, True)
    with pytest.raises(ValueError):
        detector.actualizar(0, 1e9, estados, relaciones)
    assert _actualizar(detector, 0, 1e9).activos == ()


@pytest.mark.parametrize("tipo", ["estado", "relacion"])
@pytest.mark.parametrize("t_invalido", [-1e-10, float("nan"), float("inf"), True])
def test_tiempo_de_observacion_invalido_se_rechaza_sin_consumir_cuadro(tipo, t_invalido):
    detector = DetectorCercania()
    estados, relaciones = _datos_cuadro(0, 0.0)
    if tipo == "estado":
        estados[0] = replace(estados[0], t=t_invalido)
    else:
        relaciones[0] = replace(relaciones[0], t=t_invalido)
    with pytest.raises(ValueError):
        detector.actualizar(0, 0.0, estados, relaciones)
    assert not _actualizar(detector, 0, 0.0).activos


def test_duplicados_fallan_atomico_y_se_puede_reintentar():
    detector = DetectorCercania()
    estados, relaciones = _datos_cuadro(0, 0)
    with pytest.raises(ValueError):
        detector.actualizar(0, 0, estados * 2, relaciones)
    assert detector.actualizar(0, 0, estados, relaciones).activos == ()


def test_falta_contraparte_advierte_y_ttc_negativo_se_sanea():
    detector = DetectorCercania()
    estados, relaciones = _datos_cuadro(0, 0, ttc=-1.0)
    out = detector.actualizar(0, 0, estados, [])
    assert out.advertencias
    _, relaciones = _datos_cuadro(1, 1, ttc=-1.0)
    out = detector.actualizar(1, 1, [], relaciones)
    assert out.advertencias
    _actualizar(detector, 2, 2, ttc=-1.0)
    _actualizar(detector, 3, 3, ttc=-1.0)
    out = _actualizar(detector, 4, 4, ttc=-1.0)
    assert out.activos[0].variables["ttc"] is None


@pytest.mark.parametrize("velocidad,thw", [(5.0, 1.0), (10.0, 1.5)])
def test_limites_estrictos_no_califican(velocidad, thw):
    detector = DetectorCercania()
    for i in range(4):
        estados, relaciones = _datos_cuadro(i, i, thw=thw)
        estados[0] = replace(estados[0], velocidad=velocidad)
        out = detector.actualizar(i, i, estados, relaciones)
    assert not out.activos
    assert detector.finalizar() == []


@pytest.mark.parametrize("fps", [10, 25, 30])
def test_persistencia_depende_del_tiempo_y_limites_apenas_superados(fps):
    d = DetectorCercania()
    for i in range(2 * fps):
        assert not d.actualizar(i, i / fps, *_datos_cuadro(i, i / fps, thw=1.499)).activos
    out = d.actualizar(2 * fps, 2.0, *_datos_cuadro(2 * fps, 2.0, thw=1.499))
    assert len(out.activos) == 1
    # La primera observacion ocurre en t=0 y confirma exactamente en t=2.
    assert d.finalizar()[0].variables["t_confirmacion"] == 2.0


@pytest.mark.parametrize("field,value", [
    ("cercania_velocidad_min", float("nan")), ("cercania_thw_max", float("inf")),
    ("cercania_persistencia", -1), ("cercania_velocidad_min", True),
    ("cercania_thw_max", 0), ("aporte_cercania", True), ("aporte_cercania", -1),
    ("aporte_cercania", 2.5),
])
def test_umbrales_invalidos_se_rechazan(field, value):
    with pytest.raises(ValueError):
        DetectorCercania(replace(Umbrales(), **{field: value}))


@pytest.mark.parametrize("campo,valor", [("velocidad", None), ("velocidad", float("nan")),
                                            ("velocidad", float("inf")), ("velocidad", -1),
                                            ("thw", None), ("thw", float("nan")),
                                            ("thw", float("inf")), ("thw", -1),
                                            ("distancia", -1)])
def test_metricas_invalidas_suspenden_y_reinician_tramo(campo, valor):
    d = DetectorCercania()
    for i in range(2):
        _actualizar(d, i, i)
    estados, relaciones = _datos_cuadro(2, 2)
    if campo == "velocidad":
        estados[0] = replace(estados[0], velocidad=valor)
    else:
        relaciones[0] = replace(relaciones[0], **{campo: valor})
    out = d.actualizar(2, 2, estados, relaciones)
    assert out.advertencias and not out.activos


def test_cuadro_omitido_cierra_al_ultimo_bueno_y_reconfirma():
    d = DetectorCercania()
    for i in range(3):
        _actualizar(d, i, i)
    out = _actualizar(d, 4, 4)
    assert out.cerrados[0].t_fin == 2
    assert not out.activos
    for i in range(5, 8):
        out = _actualizar(d, i, i)
    assert out.activos[0].t_inicio == 4


def test_cambio_de_predecesor_reconfirma_en_intervalo_distinto():
    d = DetectorCercania()
    for i in range(3):
        _actualizar(d, i, i)
    out = _actualizar(d, 3, 3, pred=4)
    assert out.cerrados[0].id_relacionado == 2
    assert not out.activos
    _actualizar(d, 4, 4, pred=4)
    _actualizar(d, 5, 5, pred=4)
    out = _actualizar(d, 6, 6, pred=4)
    assert (out.activos[0].t_inicio, out.activos[0].id_relacionado) == (3, 4)


def test_iterables_generadores_y_finalizacion_de_candidato():
    d = DetectorCercania()
    es, rs = _datos_cuadro(0, 0)
    out = d.actualizar(0, 0, (e for e in es), (r for r in rs))
    assert not out.activos and d.finalizar() == [] and d.finalizar() == []


def test_snapshot_guarda_variables_del_mismo_frame_y_copia_umbrales():
    d = DetectorCercania()
    for i in range(3):
        out = _actualizar(d, i, i, thw=0.8 + i / 10)
    ev = out.activos[0]
    assert ev.variables["t_observacion"] == 2
    assert ev.variables["thw"] == pytest.approx(1.0)
    assert ev.variables["t_confirmacion"] == 2
    ev.umbrales["cercania_thw_max"] = -1
    assert _actualizar(d, 3, 3).activos[0].umbrales["cercania_thw_max"] == 1.5


def test_ttc_invalido_no_impide_confirmacion_y_distancia_none_es_valida():
    d = DetectorCercania()
    for i in range(3):
        es, rs = _datos_cuadro(i, i, ttc=float("nan"))
        rs[0] = replace(rs[0], distancia=None)
        out = d.actualizar(i, i, es, rs)
    assert out.activos[0].variables["ttc"] is None


def test_thw_cero_es_valido():
    detector = DetectorCercania()
    for i in range(3):
        out = _actualizar(detector, i, i, thw=0.0)
    assert out.activos[0].variables["thw"] == 0.0


def _escena_referencia_cercania():
    cuadros = []
    for n in range(81):
        t = n / 10
        separation = 10.0 if t <= 2.5 or 4.0 <= t <= 7.0 else 40.0
        estados = [
            EstadoCinematico(1, n, t, 20 * t, 0.0, 20.0, 1, 1.0, True),
            EstadoCinematico(2, n, t, 20 * t + separation, 0.0, 20.0, 1, 1.0, True),
        ]
        relaciones = calcular_relaciones(estados, n, t)
        cuadros.append(CuadroReferencia(n, t, estados, relaciones))
    return cuadros


def test_detector_coincide_con_referencia_publica_en_tramos_sinteticos():
    cuadros = _escena_referencia_cercania()
    umbrales = Umbrales()
    detector = DetectorCercania(umbrales)
    cerrados = []
    for cuadro in cuadros:
        out = detector.actualizar(cuadro.cuadro, cuadro.t, cuadro.estados, cuadro.relaciones)
        cerrados.extend(out.cerrados)
    cerrados.extend(detector.finalizar())
    referencia = [
        e for e in eventos_referencia(cuadros, umbrales)
        if e.regla == Regla.CERCANIA
    ]
    observado = [e for e in cerrados if e.regla == Regla.CERCANIA]
    identidad = lambda e: (e.id_vehiculo, e.id_relacionado, e.t_inicio, e.t_fin)
    assert [identidad(e) for e in observado] == [identidad(e) for e in referencia]
    assert evaluar_eventos(observado, referencia, tolerancia=0)[Regla.CERCANIA].verdaderos_positivos == 2


def _marco_activo(detector):
    for i in range(3):
        _actualizar(detector, i, i)


@pytest.mark.parametrize("malformacion", [
    "estados_duplicados", "relaciones_duplicadas", "estado_cuadro", "estado_t",
    "relacion_cuadro", "relacion_t", "auto_predecesor", "carriles_conflictivos",
])
def test_marco_malformado_es_atomico_con_tramo_activo(malformacion):
    detector = DetectorCercania()
    _marco_activo(detector)
    estados, relaciones = _datos_cuadro(3, 3)
    if malformacion == "estados_duplicados":
        estados *= 2
    elif malformacion == "relaciones_duplicadas":
        relaciones *= 2
    elif malformacion == "estado_cuadro":
        estados[0] = replace(estados[0], cuadro=4)
    elif malformacion == "estado_t":
        estados[0] = replace(estados[0], t=3.1)
    elif malformacion == "relacion_cuadro":
        relaciones[0] = replace(relaciones[0], cuadro=4)
    elif malformacion == "relacion_t":
        relaciones[0] = replace(relaciones[0], t=3.1)
    elif malformacion == "auto_predecesor":
        relaciones[0] = replace(relaciones[0], id_predecesor=1)
    else:
        estados.append(EstadoCinematico(2, 3, 3, 0, 0, 10, 1, 0.9, True))
    if malformacion == "carriles_conflictivos":
        relaciones[0] = replace(relaciones[0], carril=1)
    with pytest.raises(ValueError):
        detector.actualizar(3, 3, estados, relaciones)
    out = detector.actualizar(3, 3, *_datos_cuadro(3, 3))
    assert out.activos[0].t_inicio == 0
    assert not out.cerrados


@pytest.mark.parametrize("cuadro,t", [(2, 2), (3, 2), (1, 1), (3, 1)])
def test_tiempo_global_invalido_no_mutate_y_permite_reintento(cuadro, t):
    detector = DetectorCercania()
    _marco_activo(detector)
    with pytest.raises(ValueError):
        detector.actualizar(cuadro, t, *_datos_cuadro(cuadro, t))
    out = _actualizar(detector, 3, 3)
    assert out.activos[0].t_inicio == 0
    assert not out.cerrados


def _datos_dos_autos(n, t, thw=1.0):
    estados = [
        EstadoCinematico(i, n, t, float(i), 0.0, 10.0, 0, 1.0, True)
        for i in (5, 1)
    ]
    relaciones = [
        Relacion(i, pred, n, t, 0, 0.0, thw, None)
        for i, pred in ((5, 6), (1, 2))
    ]
    return estados, relaciones


def test_dos_vehiculos_son_independientes_y_salen_ordenados():
    detector = DetectorCercania()
    for i in range(3):
        out = detector.actualizar(i, i, *_datos_dos_autos(i, i))
    assert [e.id_vehiculo for e in out.activos] == [1, 5]
    estados, relaciones = _datos_dos_autos(3, 3)
    relaciones[0] = replace(relaciones[0], thw=2.0)
    out = detector.actualizar(3, 3, estados, relaciones)
    assert [e.id_vehiculo for e in out.cerrados] == [5]
    assert [e.id_vehiculo for e in out.activos] == [1]
    out = detector.actualizar(4, 4, *_datos_dos_autos(4, 4))
    assert not out.cerrados
    assert [e.id_vehiculo for e in out.activos] == [1]
    assert [e.id_vehiculo for e in detector.finalizar()] == [1]
    assert detector.finalizar() == []


@pytest.mark.parametrize("caso,advierte", [
    ("estado_ausente", True), ("relacion_ausente", True), ("carril_desconocido", True),
    ("sin_calibrar", True), ("cuadro_vacio", False),
])
def test_datos_ausentes_o_no_validos_cierran_y_exigen_reconfirmar(caso, advierte):
    detector = DetectorCercania()
    _marco_activo(detector)
    estados, relaciones = _datos_cuadro(3, 3)
    if caso == "estado_ausente":
        estados = []
    elif caso == "relacion_ausente":
        relaciones = []
    elif caso == "carril_desconocido":
        estados[0] = replace(estados[0], carril=None)
    elif caso == "sin_calibrar":
        estados[0] = replace(estados[0], calibrado=False)
    else:
        estados = []
        relaciones = []
    out = detector.actualizar(3, 3, estados, relaciones)
    assert bool(out.advertencias) is advierte
    assert len(out.cerrados) == 1
    assert out.cerrados[0].t_fin == 2
    assert not out.activos
    for i in (4, 5):
        out = _actualizar(detector, i, i)
        assert not out.activos
    out = _actualizar(detector, 6, 6)
    assert out.activos[0].t_inicio == 4


def test_prefijo_causal_es_invariante_y_snapshots_previos_no_cambian():
    completo = DetectorCercania()
    solo_prefijo = DetectorCercania()
    resultados_completos = []
    resultados_prefijo = []
    for i in range(4):
        resultados_completos.append(_actualizar(completo, i, i))
        resultados_prefijo.append(_actualizar(solo_prefijo, i, i))
    snapshots = [
        [(e.id_vehiculo, e.t_inicio, e.t_fin, dict(e.variables)) for e in out.activos]
        for out in resultados_completos
    ]
    for i in range(4, 8):
        _actualizar(completo, i, i, thw=2.0)
    snapshots_despues = [
        [(e.id_vehiculo, e.t_inicio, e.t_fin, dict(e.variables)) for e in out.activos]
        for out in resultados_completos
    ]
    assert snapshots_despues == snapshots
    assert resultados_completos == resultados_prefijo
