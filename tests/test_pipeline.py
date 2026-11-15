"""Integracion end-to-end (pipeline y CLI) con video sintetico y detector falso.

Casos minimos a cubrir:
  - Con calibracion, dos rectangulos en el mismo carril a THW < 1,5 s durante
    mas de 2 s producen un evento de cercania, el puntaje sube y se escriben
    anotado.mp4, eventos.csv y resumen.json con la forma esperada.
  - Sin calibracion el pipeline sigue: cajas e ID, advertencia visible, cero
    eventos y metricas de distancia no disponibles (Paso 5).
  - --max-cuadros y --sin-video se respetan desde la CLI.
  - El motor inyectado recibe la firma acordada con M4.

No se carga YOLO: el detector falso segmenta los rectangulos claros.
"""

import csv
import json
import os

import cv2
import numpy as np
import pytest

from roadguard import cli
from roadguard.m1_ingesta.config import configuracion_desde_dict
from roadguard.m1_ingesta.video import iterar_cuadros, leer_metadatos
from roadguard.m5_salidas.exportar import COLUMNAS_FIJAS
from roadguard.pipeline import MotorCercania, Pipeline, nivel_por_puntaje
from roadguard.tipos import Caja, Deteccion, NivelRiesgo, Umbrales

ANCHO, ALTO, FPS, N_CUADROS = 320, 320, 25.0, 75
# Escala de la calibracion sintetica: 0,2 m por pixel, x_camino = y_px * 0,2.
ESCALA = 0.2


class DetectorFalso:
    """Detecta rectangulos claros sobre fondo negro como automoviles."""

    version_modelo = "detector falso (umbral + contornos)"

    def __init__(self) -> None:
        self.llamadas = 0

    def detectar(self, imagen) -> list[Deteccion]:
        self.llamadas += 1
        gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
        _, mascara = cv2.threshold(gris, 128, 255, cv2.THRESH_BINARY)
        contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        dets = []
        for c in contornos:
            x, y, w, h = cv2.boundingRect(c)
            if w * h < 100:
                continue
            dets.append(Deteccion("automovil", 0.9, Caja(x, y, x + w, y + h)))
        return dets


def _config(calibrada: bool) -> dict:
    datos = {
        "region_interes": [[0, 0], [ANCHO, 0], [ANCHO, ALTO], [0, ALTO]],
        "carriles": [
            {"indice": 0, "poligono": [[0, 0], [160, 0], [160, ALTO], [0, ALTO]]},
            {"indice": 1, "poligono": [[160, 0], [ANCHO, 0], [ANCHO, ALTO], [160, ALTO]]},
        ],
        "clases": ["automovil"],
    }
    if calibrada:
        datos["homografia"] = {
            "puntos_imagen": [[0, 0], [ANCHO, 0], [ANCHO, ALTO], [0, ALTO]],
            "puntos_camino": [
                [0, 0], [0, ANCHO * ESCALA], [ALTO * ESCALA, ANCHO * ESCALA], [ALTO * ESCALA, 0],
            ],
        }
    return datos


def _video(tmp_path, n_cuadros=N_CUADROS) -> str:
    """Dos autos en el carril 0 avanzando hacia abajo a 2 px/cuadro (10 m/s).

    Sus puntos de calzada van 50 px (10 m) separados: THW = 1,0 s < 1,5 s.
    """
    ruta = str(tmp_path / "sintetico.mp4")
    escritor = cv2.VideoWriter(ruta, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (ANCHO, ALTO))
    for i in range(n_cuadros):
        cuadro = np.zeros((ALTO, ANCHO, 3), np.uint8)
        y = 10 + 2 * i
        cv2.rectangle(cuadro, (60, y), (100, y + 30), (255, 255, 255), -1)
        cv2.rectangle(cuadro, (60, y + 50), (100, y + 80), (255, 255, 255), -1)
        escritor.write(cuadro)
    escritor.release()
    return ruta


def _escribir_yaml(tmp_path, datos) -> str:
    import yaml

    ruta = str(tmp_path / "camara.yaml")
    with open(ruta, "w", encoding="utf-8") as f:
        yaml.safe_dump(datos, f)
    return ruta


def _leer_salidas(dir_salida):
    with open(os.path.join(dir_salida, "eventos.csv"), encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f)
        filas = list(lector)
        columnas = lector.fieldnames
    with open(os.path.join(dir_salida, "resumen.json"), encoding="utf-8") as f:
        resumen = json.load(f)
    return columnas, filas, resumen


def test_pipeline_calibrado_detecta_cercania_y_escribe_salidas(tmp_path) -> None:
    video = _video(tmp_path)
    cfg = configuracion_desde_dict(_config(calibrada=True))
    ruta_cfg = _escribir_yaml(tmp_path, _config(calibrada=True))
    salida = str(tmp_path / "salida")
    detector = DetectorFalso()

    resultado = Pipeline(cfg, detector, ruta_config=ruta_cfg).ejecutar(video, salida)

    assert detector.llamadas == N_CUADROS
    for nombre in ("anotado.mp4", "eventos.csv", "resumen.json"):
        assert os.path.isfile(os.path.join(salida, nombre))
    meta = leer_metadatos(os.path.join(salida, "anotado.mp4"))
    assert (meta.ancho, meta.alto) == (ANCHO, ALTO)
    assert meta.fps == pytest.approx(FPS)
    assert sum(1 for _ in iterar_cuadros(os.path.join(salida, "anotado.mp4"))) == N_CUADROS

    columnas, filas, resumen = _leer_salidas(salida)
    assert columnas[: len(COLUMNAS_FIJAS)] == list(COLUMNAS_FIJAS)
    assert "variable_thw" in columnas and "umbral_cercania_thw_max" in columnas
    assert len(filas) == 1
    fila = filas[0]
    assert fila["regla"] == "cercania_peligrosa"
    assert fila["id_vehiculo"] != fila["id_relacionado"]
    assert 0.5 < float(fila["variable_thw"]) < 1.5
    assert float(fila["variable_velocidad"]) == pytest.approx(10.0, rel=0.2)
    assert float(fila["t_fin"]) - float(fila["t_inicio"]) >= 2.0

    ejecucion = resumen["ejecucion"]
    assert ejecucion["n_cuadros_procesados"] == N_CUADROS
    assert ejecucion["calibrado"] is True
    assert ejecucion["completada"] is True
    assert ejecucion["fps_procesamiento"] > 0
    assert ejecucion["n_eventos"] == {"cercania_peligrosa": 1, "zigzag": 0, "corte_de_carril": 0}
    assert ejecucion["version_modelo"] == DetectorFalso.version_modelo
    assert len(ejecucion["configuracion_sha256"]) == 64
    assert ejecucion["parametros"]["umbrales"]["aporte_cercania"] == 40
    assert set(ejecucion["fps_por_etapa"]) == {"deteccion", "seguimiento", "geometria", "reglas", "salidas"}

    vehiculos = {v["id_vehiculo"]: v for v in resumen["vehiculos"]}
    assert set(vehiculos) == {1, 2}
    seguidor = vehiculos[int(fila["id_vehiculo"])]
    assert seguidor["n_eventos"] == {"cercania_peligrosa": 1}
    assert seguidor["puntaje_maximo"] == 40
    assert seguidor["nivel_maximo"] == "amarillo"
    assert all(v["clase"] == "automovil" for v in vehiculos.values())
    assert resultado.resumen.n_eventos["cercania_peligrosa"] == 1


def test_pipeline_sin_calibracion_sigue_sin_eventos(tmp_path) -> None:
    video = _video(tmp_path, n_cuadros=30)
    cfg = configuracion_desde_dict(_config(calibrada=False))
    salida = str(tmp_path / "salida")

    resultado = Pipeline(cfg, DetectorFalso()).ejecutar(video, salida)

    _, filas, resumen = _leer_salidas(salida)
    assert filas == []
    assert resumen["ejecucion"]["calibrado"] is False
    assert resumen["ejecucion"]["n_cuadros_procesados"] == 30
    assert any("SIN CALIBRACION" in a for a in resumen["ejecucion"]["advertencias"])
    assert resumen["ejecucion"]["configuracion_sha256"] == ""
    assert {v["id_vehiculo"] for v in resumen["vehiculos"]} == {1, 2}
    assert all(v["puntaje_maximo"] == 0 and v["nivel_maximo"] == "verde" for v in resumen["vehiculos"])
    # La franja de advertencia ocupa el borde superior del video anotado.
    _, _, primero = next(iterar_cuadros(resultado.ruta_video))
    assert primero[1, :].any(axis=-1).all()


def test_motor_inyectado_recibe_la_firma_acordada(tmp_path) -> None:
    video = _video(tmp_path, n_cuadros=12)
    cfg = configuracion_desde_dict(_config(calibrada=True))
    llamadas = []

    class MotorEspia:
        def actualizar(self, t, estados, relaciones, cambios):
            llamadas.append((t, estados, relaciones, cambios))
            return [], {}

        def finalizar(self):
            return []

    Pipeline(cfg, DetectorFalso(), motor=MotorEspia()).ejecutar(
        video, str(tmp_path / "s"), escribir_video=False
    )
    assert len(llamadas) == 12
    t, estados, relaciones, cambios = llamadas[-1]
    assert t == pytest.approx(11 / FPS)
    assert isinstance(estados, dict) and set(estados) == {1, 2}
    assert all(e.id_vehiculo == k for k, e in estados.items())
    assert {r.id_seguidor for r in relaciones} == {1, 2}
    assert cambios == []
    assert not os.path.exists(tmp_path / "s" / "anotado.mp4")


def test_motor_cercania_puntaje_caduca() -> None:
    u = Umbrales()
    assert nivel_por_puntaje(0, u) == NivelRiesgo.VERDE
    assert nivel_por_puntaje(40, u) == NivelRiesgo.AMARILLO
    assert nivel_por_puntaje(60, u) == NivelRiesgo.ROJO
    from roadguard.tipos import EstadoCinematico, Relacion

    motor = MotorCercania(u)
    ultimo = {}
    for n in range(25):
        t = n / 10
        e = EstadoCinematico(1, n, t, 0.0, 0.0, 10.0, 0, 1.0, True)
        r = Relacion(1, 2, n, t, 0, 10.0, 1.0, None)
        _, ultimo = motor.actualizar(t, {1: e}, [r], [])
    assert ultimo[1].puntaje == 40 and ultimo[1].nivel == NivelRiesgo.AMARILLO
    # Sin predecesor el tramo se cierra; el aporte sigue vigente 5 s y luego caduca.
    cerrados, puntajes = motor.actualizar(2.5, {1: EstadoCinematico(1, 25, 2.5, 0.0, 0.0, 10.0, 0, 1.0, True)},
                                           [Relacion(1, None, 25, 2.5, 0, None, None, None)], [])
    assert len(cerrados) == 1 and puntajes[1].puntaje == 40
    _, puntajes = motor.actualizar(8.0, {1: EstadoCinematico(1, 26, 8.0, 0.0, 0.0, 10.0, 0, 1.0, True)},
                                   [Relacion(1, None, 26, 8.0, 0, None, None, None)], [])
    assert puntajes[1].puntaje == 0
    assert motor.finalizar() == []


def test_cli_max_cuadros_y_sin_video(tmp_path, capsys) -> None:
    video = _video(tmp_path, n_cuadros=40)
    ruta_cfg = _escribir_yaml(tmp_path, _config(calibrada=True))
    salida = str(tmp_path / "cli")
    codigo = cli.main(
        ["procesar", "--video", video, "--config", ruta_cfg, "--salida", salida,
         "--max-cuadros", "20", "--sin-video"],
        fabrica_detector=lambda cfg, args: DetectorFalso(),
    )
    assert codigo == 0
    assert not os.path.exists(os.path.join(salida, "anotado.mp4"))
    _, _, resumen = _leer_salidas(salida)
    assert resumen["ejecucion"]["n_cuadros_procesados"] == 20
    texto = capsys.readouterr().out
    assert "Cuadros procesados: 20" in texto
    assert "FPS de procesamiento" in texto
    assert "cercania_peligrosa: 0" in texto


def test_cli_rechaza_config_inexistente(tmp_path, capsys) -> None:
    video = _video(tmp_path, n_cuadros=3)
    codigo = cli.main(
        ["procesar", "--video", video, "--config", str(tmp_path / "no.yaml"), "--salida", str(tmp_path / "x")],
        fabrica_detector=lambda cfg, args: DetectorFalso(),
    )
    assert codigo == 1
    assert "Error" in capsys.readouterr().err
