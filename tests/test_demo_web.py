"""M5: datos de la demo interactiva (`construir_demo`) desde una corrida real."""

import json

import pytest

from roadguard.m1_ingesta.config import configuracion_desde_dict
from roadguard.m5_salidas.demo import CAMPOS_VEHICULO, construir_demo, geometria
from roadguard.pipeline import Pipeline
from test_pipeline import N_CUADROS, DetectorFalso, _config, _video

PATRON = "../datos/ua-detrac/X/img{:05d}.jpg"


def _corrida(tmp_path, calibrada):
    cfg = configuracion_desde_dict(_config(calibrada=calibrada))
    salida = tmp_path / ("cal" if calibrada else "sin")
    Pipeline(cfg, DetectorFalso()).ejecutar(
        _video(tmp_path), str(salida), escribir_video=False, escribir_tracks=True, escribir_estados=True
    )
    return cfg, salida


def test_demo_calibrada_trae_cuadros_metros_y_eventos(tmp_path) -> None:
    cfg, salida = _corrida(tmp_path, calibrada=True)
    doc = construir_demo("X", cfg, salida, PATRON)

    assert doc["n_cuadros"] == N_CUADROS and len(doc["cuadros"]) == N_CUADROS
    assert doc["campos_vehiculo"] == list(CAMPOS_VEHICULO)
    i = {n: k for k, n in enumerate(CAMPOS_VEHICULO)}
    vehiculos = [veh for cuadro in doc["cuadros"] for veh in cuadro]
    assert vehiculos and all(len(veh) == len(CAMPOS_VEHICULO) for veh in vehiculos)
    assert all(veh[i["x_m"]] is not None for veh in vehiculos)
    assert any(veh[i["thw"]] is not None for veh in vehiculos)
    assert max(veh[i["puntaje"]] for veh in vehiculos) == 40
    assert [e["regla"] for e in doc["eventos"]] == ["cercania_peligrosa"]
    assert doc["eventos"][0]["variables"]["thw"] < 1.5
    g = doc["geometria"]
    assert g["calibrado"] and g["carriles_m"] and g["region_m"]
    assert doc["patron_cuadros"] == PATRON
    json.dumps(doc)  # serializable tal cual


def test_demo_sin_calibracion_no_inventa_metros(tmp_path) -> None:
    cfg, salida = _corrida(tmp_path, calibrada=False)
    doc = construir_demo("X", cfg, salida, PATRON)
    i = {n: k for k, n in enumerate(CAMPOS_VEHICULO)}
    vehiculos = [veh for cuadro in doc["cuadros"] for veh in cuadro]
    assert vehiculos and all(veh[i["x_m"]] is None and veh[i["thw"]] is None for veh in vehiculos)
    assert doc["geometria"]["calibrado"] is False
    assert "carriles_m" not in doc["geometria"]
    assert doc["eventos"] == []


def test_geometria_rejilla_vuelve_a_los_metros_de_partida(tmp_path) -> None:
    from roadguard.m3_geometria.homografia import ProyectorCamino

    cfg = configuracion_desde_dict(_config(calibrada=True))
    g = geometria(cfg, paso_m=5.0)
    assert g["rejilla_px"], "con calibracion hay lineas de la rejilla"
    proyector = ProyectorCamino(cfg.homografia)
    xs = set()
    for linea in g["rejilla_px"]:
        assert len(linea) == 2
        ida = [proyector.proyectar(tuple(p)) for p in linea]
        assert ida[0][0] == pytest.approx(ida[1][0], abs=0.05)  # cada linea es un x constante
        xs.add(round(ida[0][0]))
    assert all(x % 5 == 0 for x in xs)
