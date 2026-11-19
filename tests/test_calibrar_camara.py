import importlib.util
import sys
from dataclasses import fields
from pathlib import Path

import pytest
import yaml

from roadguard.m1_ingesta.config import cargar_configuracion
from roadguard.tipos import Umbrales

RAIZ = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("calibrar_camara", RAIZ / "scripts" / "calibrar_camara.py")
calibrar_camara = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = calibrar_camara
spec.loader.exec_module(calibrar_camara)


def test_definicion_mvi_genera_perfil_completo_y_cargable(tmp_path):
    salida = tmp_path / "perfil.yaml"
    calibrar_camara.calibrar(RAIZ / "configs/calibraciones/MVI_39271_lineas.yaml", salida)
    perfil = yaml.safe_load(salida.read_text())
    cfg = cargar_configuracion(str(salida))
    assert cfg.homografia.disponible
    assert len(cfg.carriles) == 4
    assert "umbrales" not in perfil
    assert perfil["camara"]["resolucion_referencia"] == [960, 540]


@pytest.mark.parametrize("mutacion", [
    pytest.param(lambda d: d.update({"sorpresa": True}), id="clave-desconocida"),
    pytest.param(lambda d: d.update({7: True}), id="claves-de-tipos-mixtos"),
    pytest.param(lambda d: d["camara"].update({"nombre": []}), id="tipo-de-camara"),
    pytest.param(lambda d: d["camara"].update({"resolucion_referencia": [960, 0]}), id="resolucion-no-positiva"),
    pytest.param(lambda d: d["calibracion"]["lineas"][0]["puntos_imagen"][0].__setitem__(0, float("nan")), id="medida-no-finita"),
    pytest.param(lambda d: d["calibracion"]["lineas"][0].update({"posiciones": [0, 6, 5, 21]}), id="posiciones-desordenadas"),
    pytest.param(lambda d: d["calibracion"]["lineas"][0].update({"posiciones": [0, 6]}), id="longitudes-distintas"),
    pytest.param(lambda d: d["calibracion"].update({"tramo_longitudinal": [10, 10]}), id="rango-degenerado"),
    pytest.param(lambda d: d["procesamiento_geometria"].update({"metodo_apoyo": "desconocido"}), id="metodo-apoyo-invalido"),
    pytest.param(lambda d: d["calibracion"].update({"bordes_carriles": [0, 0, 4]}), id="bordes-no-crecientes"),
    pytest.param(lambda d: d["calibracion"].update({"lineas": d["calibracion"]["lineas"][:1]}), id="lineas-insuficientes"),
])
def test_entrada_malformada_no_escribe_salida(tmp_path, mutacion):
    datos = yaml.safe_load((RAIZ / "configs/calibraciones/MVI_39271_lineas.yaml").read_text())
    mutacion(datos)
    entrada, salida = tmp_path / "entrada.yaml", tmp_path / "salida.yaml"
    entrada.write_text(yaml.safe_dump(datos))
    with pytest.raises(ValueError):
        calibrar_camara.calibrar(entrada, salida)
    assert not salida.exists()


def test_no_sobrescribe_sin_indicacion(tmp_path):
    origen = RAIZ / "configs/calibraciones/MVI_39271_lineas.yaml"
    salida = tmp_path / "perfil.yaml"
    salida.write_text("conservar")
    with pytest.raises(FileExistsError):
        calibrar_camara.calibrar(origen, salida)
    assert salida.read_text() == "conservar"


def test_flag_sobrescribir_reemplaza_salida_existente(tmp_path, monkeypatch):
    origen = RAIZ / "configs/calibraciones/MVI_39271_lineas.yaml"
    salida = tmp_path / "perfil.yaml"
    salida.write_text("reemplazar")
    monkeypatch.setattr(sys, "argv", [
        "calibrar_camara", "--entrada", str(origen), "--salida", str(salida), "--sobrescribir"
    ])
    assert calibrar_camara.main() == 0
    assert cargar_configuracion(str(salida)).homografia.disponible


def test_politica_propuesta_equivale_a_defaults():
    politica = yaml.safe_load((RAIZ / "configs/politicas/propuesta.yaml").read_text())
    assert politica["umbrales"] == {
        campo.name: getattr(Umbrales(), campo.name) for campo in fields(Umbrales)
    }
