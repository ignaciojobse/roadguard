"""Scripts de apoyo para la demo y el perfil de FPS: jpg_a_mp4 y perfilar_fps."""

import importlib.util
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

from roadguard.m1_ingesta.config import configuracion_desde_dict
from roadguard.m1_ingesta.video import leer_metadatos

RAIZ = Path(__file__).resolve().parents[1]


def _cargar(nombre: str):
    spec = importlib.util.spec_from_file_location(nombre, RAIZ / "scripts" / f"{nombre}.py")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = modulo
    spec.loader.exec_module(modulo)
    return modulo


jpg_a_mp4 = _cargar("jpg_a_mp4")
perfilar_fps = _cargar("perfilar_fps")


def _cuadros(directorio: Path, n: int, ancho: int = 96, alto: int = 54) -> None:
    directorio.mkdir(parents=True)
    for i in range(n):
        imagen = np.full((alto, ancho, 3), i * 10, np.uint8)
        cv2.imwrite(str(directorio / f"img{i + 1:05d}.jpg"), imagen)


def test_jpg_a_mp4_conserva_cuadros_tamano_y_fps(tmp_path) -> None:
    _cuadros(tmp_path / "MVI_X", 12)
    ruta = tmp_path / "videos" / "MVI_X.mp4"
    n = jpg_a_mp4.convertir(tmp_path / "MVI_X", ruta, fps=25.0)
    meta = leer_metadatos(str(ruta))
    assert n == 12
    assert (meta.ancho, meta.alto) == (96, 54)
    assert meta.fps == pytest.approx(25.0)
    assert meta.n_cuadros == 12


def test_jpg_a_mp4_falla_sin_cuadros(tmp_path) -> None:
    (tmp_path / "vacia").mkdir()
    with pytest.raises(FileNotFoundError):
        jpg_a_mp4.convertir(tmp_path / "vacia", tmp_path / "x.mp4")


def test_escalar_config_escala_pixeles_y_conserva_metros() -> None:
    datos = {
        "region_interes": [[0, 0], [960, 0], [960, 540], [0, 540]],
        "carriles": [{"indice": 0, "poligono": [[0, 0], [960, 0], [960, 540], [0, 540]]}],
        "homografia": {
            "puntos_imagen": [[0, 0], [960, 0], [960, 540], [0, 540]],
            "puntos_camino": [[0, 0], [0, 10], [30, 10], [30, 0]],
        },
        "clases": ["automovil"],
    }
    escalada = perfilar_fps.escalar_config(datos, 720 / 540)

    assert escalada["region_interes"][2] == [1280.0, 720.0]
    assert escalada["carriles"][0]["poligono"][1] == [1280.0, 0.0]
    assert escalada["homografia"]["puntos_imagen"][2] == [1280.0, 720.0]
    assert escalada["homografia"]["puntos_camino"] == datos["homografia"]["puntos_camino"]
    assert datos["region_interes"][2] == [960, 540], "no modifica el original"
    configuracion_desde_dict(escalada)  # sigue siendo una configuracion valida


def test_escalar_config_sin_homografia() -> None:
    datos = {
        "region_interes": [[0, 0], [10, 0], [10, 10]],
        "carriles": [{"indice": 0, "poligono": [[0, 0], [10, 0], [10, 10]]}],
        "clases": ["automovil"],
    }
    assert perfilar_fps.escalar_config(datos, 2.0)["region_interes"][1] == [20.0, 0.0]
