"""T7/T8. Salidas (M5) y pipeline de extremo a extremo (seccion 4.3).

Casos minimos a cubrir:
  - Se generan MP4 anotado, CSV de eventos y JSON de resumen.
  - El JSON permite reconstruir configuracion y modelo de la corrida.
  - Con calibracion, un seguimiento cercano sostenido produce un evento de
    cercania trazable (variables y umbrales poblados).
  - Sin calibracion: sin eventos dependientes de distancia, calibrado False
    y advertencia presente (Paso 5).
  - Una falla a mitad de camino cierra los archivos y deja salidas parciales
    marcadas como no completadas (Paso 6).
  - Configuracion incoherente: no se crea el directorio de salida (Paso 1).
  - Ningun texto de salida afirma conducta temeraria, culpabilidad ni
    infraccion (secciones 1.1 y 1.2).
"""

import csv
import json
from pathlib import Path

import cv2
import pytest
import yaml

from roadguard.cli import main
from roadguard.m1_ingesta.config import ADVERTENCIA_SIN_CALIBRACION, ErrorConfiguracion
from roadguard.m2_deteccion.detector import detecciones_desde_arrays
from roadguard.m5_salidas.registros import COLUMNAS_EVENTOS
from roadguard.pipeline import ejecutar
from roadguard.tipos import Configuracion

FPS = 25.0
ESCALA = 0.125  # metros por pixel en el eje longitudinal (60 m en 480 px)

CONFIG = {
    "camara": {"nombre": "sintetica"},
    "region_interes": [[0, 0], [640, 0], [640, 480], [0, 480]],
    "carriles": [
        {"indice": 0, "poligono": [[0, 0], [320, 0], [320, 480], [0, 480]]},
        {"indice": 1, "poligono": [[320, 0], [640, 0], [640, 480], [320, 480]]},
    ],
    "homografia": {
        "puntos_imagen": [[0, 480], [640, 480], [640, 0], [0, 0]],
        "puntos_camino": [[0, 0], [0, 7], [60, 7], [60, 0]],
    },
    "clases": ["automovil", "bus", "camion", "motocicleta"],
}


class DetectorGuionado:
    """Detector falso: dos autos en el carril 0 a 8 m/s separados 9 m
    (THW 1,125 s). Usa el mismo filtrado que YOLOv8n."""

    version_modelo = "detector-guionado-prueba"

    def __init__(self, cfg: Configuracion, falla_en: int | None = None) -> None:
        self.cfg = cfg
        self.cuadro = 0
        self.falla_en = falla_en

    def detectar(self, imagen):
        if self.falla_en is not None and self.cuadro == self.falla_en:
            raise RuntimeError("falla simulada")
        t = self.cuadro / FPS
        self.cuadro += 1
        cajas = []
        for x0 in (16.0, 25.0):  # seguidor, predecesor
            y_px = 480 - (x0 + 8.0 * t) / ESCALA
            cajas.append((140, y_px - 30, 180, y_px))
        return detecciones_desde_arrays(cajas, [0.9, 0.9], [2, 2], self.cfg)


def _preparar(tmp_path: Path, video_sintetico, calibrado: bool = True):
    datos = dict(CONFIG)
    if not calibrado:
        datos["homografia"] = {"puntos_imagen": [], "puntos_camino": []}
    ruta_cfg = tmp_path / "cfg.yaml"
    ruta_cfg.write_text(yaml.safe_dump(datos), encoding="utf-8")
    from roadguard.m1_ingesta.config import cargar_configuracion

    cfg = cargar_configuracion(str(ruta_cfg))
    ruta_video = video_sintetico(n_cuadros=100, fps=FPS, ancho=640, alto=480)
    return str(ruta_cfg), ruta_video, cfg


def _leer(salida: Path):
    with open(salida / "eventos.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    resumen = json.loads((salida / "resumen.json").read_text(encoding="utf-8"))
    return filas, resumen


def test_end_to_end_con_calibracion(tmp_path: Path, video_sintetico) -> None:
    ruta_cfg, ruta_video, cfg = _preparar(tmp_path, video_sintetico)
    salida = tmp_path / "salida"
    resumen = ejecutar(ruta_video, ruta_cfg, str(salida), detector=DetectorGuionado(cfg))

    assert resumen.completada and resumen.calibrado
    assert resumen.n_cuadros_procesados == 100
    assert (salida / "video_anotado.mp4").stat().st_size > 0
    captura = cv2.VideoCapture(str(salida / "video_anotado.mp4"))
    assert int(captura.get(cv2.CAP_PROP_FRAME_COUNT)) == 100
    captura.release()

    filas, doc = _leer(salida)
    assert list(filas[0].keys()) == list(COLUMNAS_EVENTOS)
    cercania = [f for f in filas if f["regla"] == "cercania_peligrosa"]
    assert len(cercania) == 1
    ev = cercania[0]
    assert ev["id_vehiculo"] == "1" and ev["id_relacionado"] == "2"
    assert float(ev["thw"]) == pytest.approx(9 / 8, rel=0.05)
    assert float(ev["velocidad"]) == pytest.approx(8.0, rel=0.05)
    assert float(ev["umbral_thw"]) == 1.5 and float(ev["umbral_velocidad"]) == 5.0
    assert float(ev["t_fin"]) - float(ev["t_inicio"]) >= 2.0
    assert ev["aporte_puntaje"] == "40"

    # reproducibilidad (Paso 6)
    ejec = doc["ejecucion"]
    assert ejec["version_modelo"] == "detector-guionado-prueba"
    assert ejec["fps_video"] == FPS
    assert len(ejec["configuracion_sha256"]) == 64
    assert ejec["parametros"]["umbrales"]["cercania_thw_max"] == 1.5
    assert ejec["parametros"]["homografia"]["puntos_camino"][2] == [60.0, 7.0]
    assert ejec["fps_por_etapa"]["n_cuadros"] == 100
    assert doc["resumen_eventos"]["cercania_peligrosa"] == 1
    vehiculos = {v["id_vehiculo"]: v for v in doc["vehiculos"]}
    assert vehiculos[1]["puntaje_maximo"] == 40 and vehiculos[1]["nivel_maximo"] == "amarillo"
    assert vehiculos[1]["n_eventos"]["cercania_peligrosa"] == 1
    assert vehiculos[2]["puntaje_maximo"] == 0


def test_end_to_end_sin_calibracion(tmp_path: Path, video_sintetico) -> None:
    ruta_cfg, ruta_video, cfg = _preparar(tmp_path, video_sintetico, calibrado=False)
    salida = tmp_path / "salida"
    resumen = ejecutar(ruta_video, ruta_cfg, str(salida), detector=DetectorGuionado(cfg))
    assert resumen.completada and not resumen.calibrado
    assert ADVERTENCIA_SIN_CALIBRACION in resumen.advertencias
    filas, doc = _leer(salida)
    assert filas == []
    assert doc["ejecucion"]["calibrado"] is False
    assert len(doc["vehiculos"]) == 2  # deteccion y seguimiento se mantienen


def test_falla_a_mitad_deja_salidas_parciales(tmp_path: Path, video_sintetico) -> None:
    ruta_cfg, ruta_video, cfg = _preparar(tmp_path, video_sintetico)
    salida = tmp_path / "salida"
    with pytest.raises(RuntimeError, match="falla simulada"):
        ejecutar(ruta_video, ruta_cfg, str(salida), detector=DetectorGuionado(cfg, falla_en=30))
    _, doc = _leer(salida)
    assert doc["ejecucion"]["completada"] is False
    assert doc["ejecucion"]["n_cuadros_procesados"] == 30
    captura = cv2.VideoCapture(str(salida / "video_anotado.mp4"))
    assert captura.isOpened() and int(captura.get(cv2.CAP_PROP_FRAME_COUNT)) == 30
    captura.release()


def test_configuracion_incoherente_no_crea_salidas(tmp_path: Path, video_sintetico) -> None:
    ruta_cfg, ruta_video, cfg = _preparar(tmp_path, video_sintetico)
    datos = yaml.safe_load(Path(ruta_cfg).read_text())
    datos["carriles"][0]["poligono"] = [[0, 0], [1, 1]]
    Path(ruta_cfg).write_text(yaml.safe_dump(datos))
    salida = tmp_path / "no_debe_existir"
    with pytest.raises(ErrorConfiguracion):
        ejecutar(ruta_video, ruta_cfg, str(salida), detector=DetectorGuionado(cfg))
    assert not salida.exists()
    assert main(["--video", ruta_video, "--config", ruta_cfg, "--salida", str(salida)]) == 2
    assert not salida.exists()


def test_lenguaje_de_las_salidas(tmp_path: Path, video_sintetico) -> None:
    from roadguard.m5_salidas import anotacion, registros
    from roadguard.m1_ingesta import config

    ruta_cfg, ruta_video, cfg = _preparar(tmp_path, video_sintetico)
    salida = tmp_path / "salida"
    ejecutar(ruta_video, ruta_cfg, str(salida), detector=DetectorGuionado(cfg))
    textos = [
        (salida / "eventos.csv").read_text(encoding="utf-8"),
        (salida / "resumen.json").read_text(encoding="utf-8"),
        anotacion.ENCABEZADO,
        " ".join(anotacion.ROTULO_REGLA.values()),
        registros.AVISO,
        config.ADVERTENCIA_SIN_CALIBRACION,
        config.ADVERTENCIA_SIN_CALIBRACION_CORTA,
    ]
    for texto in textos:
        bajo = texto.lower()
        for prohibida in ("temerari", "culpa", "infracc", "sancion", "multa", "ilegal"):
            assert prohibida not in bajo, (prohibida, texto[:80])
    assert "experimental" in registros.AVISO.lower()
    assert "EXPERIMENTAL" in anotacion.ENCABEZADO
