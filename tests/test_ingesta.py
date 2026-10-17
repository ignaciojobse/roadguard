"""RF1, RF4. Carga y validacion de video y configuracion (M1).

Casos minimos a cubrir:
  - configs/camara_ejemplo.yaml carga sin error.
  - Homografia vacia carga, pero devuelve la advertencia de falta de
    calibracion (Paso 5).
  - Un carril de 2 puntos se rechaza (Paso 1).
  - Homografia desbalanceada o con menos de 4 pares se rechaza.
  - Clases vacias, umbrales no numericos y claves desconocidas se rechazan.
  - El video entrega t = cuadro / fps en orden estricto.
"""

from pathlib import Path

import pytest
import yaml

from roadguard.m1_ingesta.config import (
    ADVERTENCIA_SIN_CALIBRACION,
    ErrorConfiguracion,
    cargar_configuracion,
    validar_consistencia,
)
from roadguard.m1_ingesta.video import ErrorVideo, iterar_cuadros, leer_metadatos

RAIZ = Path(__file__).resolve().parents[1]
EJEMPLO = RAIZ / "configs" / "camara_ejemplo.yaml"


def _base() -> dict:
    return yaml.safe_load(EJEMPLO.read_text(encoding="utf-8"))


def _escribir(tmp_path: Path, datos: dict) -> str:
    ruta = tmp_path / "cfg.yaml"
    ruta.write_text(yaml.safe_dump(datos), encoding="utf-8")
    return str(ruta)


def test_carga_configuracion_de_ejemplo() -> None:
    cfg = cargar_configuracion(str(EJEMPLO))
    assert len(cfg.carriles) == 2
    assert cfg.clases == ["automovil", "bus", "camion", "motocicleta"]
    assert cfg.umbrales.cercania_thw_max == 1.5


def test_homografia_vacia_carga_con_advertencia(tmp_path: Path) -> None:
    cfg = cargar_configuracion(_escribir(tmp_path, _base()))
    assert not cfg.homografia.disponible
    assert ADVERTENCIA_SIN_CALIBRACION in validar_consistencia(cfg)


def test_homografia_valida_no_advierte_calibracion(tmp_path: Path) -> None:
    datos = _base()
    datos["homografia"] = {
        "puntos_imagen": [[0, 0], [100, 0], [100, 100], [0, 100]],
        "puntos_camino": [[0, 0], [10, 0], [10, 50], [0, 50]],
    }
    cfg = cargar_configuracion(_escribir(tmp_path, datos))
    assert cfg.homografia.disponible
    assert ADVERTENCIA_SIN_CALIBRACION not in validar_consistencia(cfg)


def test_carril_de_dos_puntos_falla(tmp_path: Path) -> None:
    datos = _base()
    datos["carriles"][0]["poligono"] = [[0, 0], [10, 10]]
    with pytest.raises(ErrorConfiguracion, match="al menos 3 puntos"):
        cargar_configuracion(_escribir(tmp_path, datos))


def test_region_de_dos_puntos_falla(tmp_path: Path) -> None:
    datos = _base()
    datos["region_interes"] = [[0, 0], [10, 10]]
    with pytest.raises(ErrorConfiguracion):
        cargar_configuracion(_escribir(tmp_path, datos))


@pytest.mark.parametrize(
    "homografia",
    [
        {"puntos_imagen": [[0, 0], [1, 0], [1, 1], [0, 1]], "puntos_camino": [[0, 0], [1, 0], [1, 1]]},
        {"puntos_imagen": [[0, 0], [1, 0], [1, 1]], "puntos_camino": [[0, 0], [1, 0], [1, 1]]},
        {"puntos_imagen": [[0, 0], [1, 0], [2, 0], [3, 0]], "puntos_camino": [[0, 0], [1, 0], [1, 1], [0, 1]]},
    ],
    ids=["desbalanceada", "menos_de_4", "colineal"],
)
def test_homografia_incoherente_falla(tmp_path: Path, homografia: dict) -> None:
    datos = _base()
    datos["homografia"] = homografia
    with pytest.raises(ErrorConfiguracion):
        cargar_configuracion(_escribir(tmp_path, datos))


def test_clases_vacias_fallan(tmp_path: Path) -> None:
    datos = _base()
    datos["clases"] = []
    with pytest.raises(ErrorConfiguracion):
        cargar_configuracion(_escribir(tmp_path, datos))


def test_umbral_no_numerico_falla(tmp_path: Path) -> None:
    datos = _base()
    datos["umbrales"]["cercania_thw_max"] = "rapido"
    with pytest.raises(ErrorConfiguracion, match="numerico"):
        cargar_configuracion(_escribir(tmp_path, datos))


def test_umbral_desconocido_falla(tmp_path: Path) -> None:
    datos = _base()
    datos["umbrales"]["thw_maximo"] = 1.0
    with pytest.raises(ErrorConfiguracion, match="desconocidos"):
        cargar_configuracion(_escribir(tmp_path, datos))


def test_bandas_incoherentes_fallan(tmp_path: Path) -> None:
    datos = _base()
    datos["umbrales"]["banda_verde_max"] = 70
    with pytest.raises(ErrorConfiguracion, match="Bandas"):
        cargar_configuracion(_escribir(tmp_path, datos))


def test_archivo_inexistente_falla() -> None:
    with pytest.raises(ErrorConfiguracion, match="No existe"):
        cargar_configuracion("no/existe.yaml")


def test_video_metadatos_e_iteracion(video_sintetico) -> None:
    ruta = video_sintetico(n_cuadros=12, fps=25.0)
    meta = leer_metadatos(ruta)
    assert (meta.ancho, meta.alto, meta.fps) == (320, 240, 25.0)
    cuadros = list(iterar_cuadros(ruta))
    assert [c for c, _, _ in cuadros] == list(range(12))
    assert all(t == pytest.approx(c / 25.0) for c, t, _ in cuadros)


def test_video_inexistente_o_no_mp4_falla(tmp_path: Path) -> None:
    with pytest.raises(ErrorVideo):
        leer_metadatos(str(tmp_path / "nada.mp4"))
    otro = tmp_path / "video.avi"
    otro.write_bytes(b"x")
    with pytest.raises(ErrorVideo, match="MP4"):
        leer_metadatos(str(otro))


def test_video_corrupto_falla(tmp_path: Path) -> None:
    ruta = tmp_path / "roto.mp4"
    ruta.write_bytes(b"esto no es un video")
    with pytest.raises(ErrorVideo):
        leer_metadatos(str(ruta))
