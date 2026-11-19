import numpy as np
import pytest

from roadguard.m1_ingesta.config import configuracion_desde_dict
from roadguard.m2_deteccion.detector import detecciones_desde_arrays
from roadguard.m3_geometria import procesador
from roadguard.m3_geometria.movimiento import MovimientoCamara
from roadguard.m3_geometria.procesador import ProcesadorGeometria
from roadguard.tipos import Caja, Deteccion, Track


def _cfg(*, size=100, lane_split=None, calibrated=True, compensate=False, support="longitudinal"):
    split = size if lane_split is None else lane_split
    data = {
        "region_interes": [[0, 0], [size, 0], [size, size], [0, size]],
        "carriles": [
            {"indice": 0, "poligono": [[0, 0], [split, 0], [split, size], [0, size]]},
            {"indice": 1, "poligono": [[split, 0], [size, 0], [size, size], [split, size]]},
        ] if split < size else [
            {"indice": 0, "poligono": [[0, 0], [size, 0], [size, size], [0, size]]},
        ],
        "clases": ["automovil"],
        "procesamiento_geometria": {
            "metodo_apoyo": support, "compensar_camara": compensate,
        },
    }
    if calibrated:
        data["homografia"] = {
            "puntos_imagen": [[0, 0], [size, 0], [size, size], [0, size]],
            "puntos_camino": [[0, 0], [100, 0], [100, 100], [0, 100]],
        }
    return configuracion_desde_dict(data)


def _track(ident, frame, t, bbox, point):
    return Track(ident, frame, t, "automovil", 0.9, Caja(*bbox), point)


def test_configuracion_geometria_es_default_y_overrides_opcionales():
    cfg = _cfg(compensate=True)
    m3 = ProcesadorGeometria(cfg, 25.0)
    assert m3.compensador is not None
    assert m3.metodo_apoyo == "longitudinal"
    override = ProcesadorGeometria(cfg, 25.0, compensar_camara=False, metodo_apoyo="centro_inferior")
    assert override.compensador is None
    assert override.metodo_apoyo == "centro_inferior"


def test_roi_longitudinal_opuesto_a_centro_inferior(monkeypatch):
    cfg = _cfg()
    m3 = ProcesadorGeometria(cfg, 25.0)
    # Centro inferior fuera; el bbox cruza la envolvente ROI y el apoyo queda
    # dentro tanto de la caja como de la ROI.
    det = Deteccion("automovil", 0.9, Caja(80, 20, 120, 120))
    assert m3.filtrar_detecciones([det]) == [det]
    monkeypatch.setattr(procesador, "estimar_apoyo_longitudinal", lambda *_: (99.0, 80.0))
    track = _track(5, 0, 0.0, (80, 20, 120, 120), (100, 120))
    result = m3.procesar_tracks([track], 0, 0.0, np.zeros((140, 140, 3), dtype=np.uint8))
    assert result.estados[0].calibrado
    assert result.tracks[0].punto_calzada_px == (99.0, 80.0)

    # Centro inferior dentro, apoyo calculado fuera: no participa en métricas.
    otro = ProcesadorGeometria(cfg, 25.0)
    monkeypatch.setattr(procesador, "estimar_apoyo_longitudinal", lambda *_: (120.0, 70.0))
    track_fuera = _track(6, 0, 0.0, (80, 20, 120, 80), (100, 80))
    result_fuera = otro.procesar_tracks(
        [track_fuera], 0, 0.0, np.zeros((100, 140, 3), dtype=np.uint8)
    )
    assert result_fuera.estados[0].x_camino is None
    assert result_fuera.estados[0].carril is None


def test_detecciones_desde_arrays_retrocompatible_y_raw_opt_in():
    cfg = _cfg()
    args = ([(150, 20, 180, 60)], [0.9], [2], cfg)
    assert detecciones_desde_arrays(*args) == []
    assert len(detecciones_desde_arrays(*args, aplicar_roi=False)) == 1


def test_resultado_toma_snapshot_de_diagnosticos():
    cfg = _cfg(compensate=True)
    m3 = ProcesadorGeometria(cfg, 25.0)
    ident = np.eye(3)

    class Compensador:
        def __init__(self, _): pass
        def actualizar(self, _):
            return MovimientoCamara(ident, ident, True, residuo_mediano=1.0)

    original = procesador.CompensadorCamara
    procesador.CompensadorCamara = Compensador
    try:
        m3 = ProcesadorGeometria(cfg, 25.0)
    finally:
        procesador.CompensadorCamara = original
    m3.preparar_cuadro(np.zeros((100, 100, 3), dtype=np.uint8))
    result = m3.procesar_tracks([], 0, 0.0, np.zeros((100, 100, 3), dtype=np.uint8))
    m3.preparar_cuadro(np.zeros((100, 100, 3), dtype=np.uint8))
    assert result.diagnosticos.validos == 1
    assert m3.diagnosticos.validos == 2
    assert result.diagnosticos is not m3.diagnosticos


def test_perfiles_distintos_intercalados_no_comparten_estado():
    cfg_a = _cfg(size=100, support="centro_inferior")
    cfg_b = _cfg(size=200, lane_split=100, support="centro_inferior")
    a, b = ProcesadorGeometria(cfg_a, 10.0), ProcesadorGeometria(cfg_b, 10.0)
    def paso(m3, ident, frame, t, size, x, y):
        track = _track(ident, frame, t, (x - 2, y - 5, x + 2, y), (x, y))
        return m3.procesar_tracks([track], frame, t, np.zeros((size, size, 3), dtype=np.uint8)).estados[0]

    estados_a, estados_b = [], []
    for frame in range(4):
        estados_a.append(paso(a, 1, frame, frame * 0.1, 100, 20 + frame, 25))
        estados_b.append(paso(b, 2, frame, frame * 0.1, 200, 40 + 2 * frame, 50))
    assert [(e.x_camino, e.y_camino, e.carril) for e in estados_a] == [
        (e.x_camino, e.y_camino, e.carril) for e in estados_b
    ]
    assert estados_a[-1].velocidad == pytest.approx(10.0, abs=0.1)
    assert estados_b[-1].velocidad == pytest.approx(10.0, abs=0.1)
    b_last = estados_b[-1]
    for frame in range(4, 10):
        paso(a, 1, frame, frame * 0.1, 100, 20 + frame, 25)
    assert b.historial._t_ultimo[2] == pytest.approx(0.3)
    assert b_last.x_camino == estados_b[-1].x_camino


def test_compensacion_traslada_roi_preliminar_y_apoyo_referencia(monkeypatch):
    cfg = _cfg(compensate=True)
    translate = np.array([[1., 0., 10.], [0., 1., 5.], [0., 0., 1.]])
    inverse = np.linalg.inv(translate)

    class Compensador:
        def __init__(self, _): pass
        def actualizar(self, _):
            return MovimientoCamara(translate, inverse, True)

    monkeypatch.setattr(procesador, "CompensadorCamara", Compensador)
    monkeypatch.setattr(procesador, "estimar_apoyo_longitudinal", lambda caja, *_: (95.0, 80.0))
    m3 = ProcesadorGeometria(cfg, 25.0)
    m3.preparar_cuadro(np.zeros((150, 150, 3), dtype=np.uint8))
    det = Deteccion("automovil", 0.9, Caja(105, 75, 125, 100))
    assert m3.filtrar_detecciones([det]) == [det]  # intersección con ROI actual trasladada
    track = _track(1, 0, 0.0, (105, 75, 125, 100), (115, 100))
    result = m3.procesar_tracks([track], 0, 0.0, np.zeros((150, 150, 3), dtype=np.uint8))
    assert result.estados[0].calibrado
    assert result.estados[0].x_camino == 95.0
    assert result.tracks[0].punto_calzada_px == (105.0, 85.0)


def test_sin_homografia_conserva_percepcion_y_cambio_completo():
    cfg = _cfg(calibrated=False, lane_split=50, support="centro_inferior")
    m3 = ProcesadorGeometria(cfg, 10.0)
    cambios = []
    for frame in range(23):
        x = 25 if frame < 12 else 75
        track = _track(3, frame, frame * 0.1, (x - 3, 20, x + 3, 30), (x, 30))
        result = m3.procesar_tracks([track], frame, frame * 0.1, np.zeros((100, 100, 3), dtype=np.uint8))
        cambios.extend(result.cambios)
        assert len(result.tracks) == 1
        assert result.estados[0].x_camino is None
    assert len(cambios) == 1
    assert (cambios[0].carril_origen, cambios[0].carril_destino) == (0, 1)
