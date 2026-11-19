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
from roadguard.m5_salidas.exportar import COLUMNAS_FIJAS, COLUMNAS_TRACKS
from roadguard.pipeline import MotorCercania, Pipeline, nivel_por_puntaje
from roadguard.m3_geometria.movimiento import MovimientoCamara
from roadguard.tipos import Caja, Deteccion, NivelRiesgo, Track, Umbrales
from dataclasses import replace

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


class DetectorGeometriaNoConfiable(DetectorFalso):
    def __init__(self, recortadas: bool) -> None:
        super().__init__()
        self.recortadas = recortadas

    def detectar(self, imagen) -> list[Deteccion]:
        detecciones = super().detectar(imagen)
        resultado = []
        for d in detecciones:
            if self.recortadas:
                caja = Caja(-20, d.caja.y1, 180, d.caja.y2)
                confianza = 0.9
            else:
                caja = Caja(d.caja.x1 + 40, d.caja.y1, d.caja.x2 + 40, d.caja.y2)
                confianza = 0.9
            resultado.append(Deteccion(d.clase, confianza, caja))
        return resultado


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


def test_pipeline_centralidad_baja_conserva_carril_y_habilita_rf7(tmp_path) -> None:
    video = _video(tmp_path)
    cfg = configuracion_desde_dict(_config(calibrada=True))
    salida = str(tmp_path / "lowconf")
    resultado = Pipeline(cfg, DetectorGeometriaNoConfiable(False)).ejecutar(
        video, salida, escribir_video=False, escribir_tracks=True
    )
    _, filas, _ = _leer_salidas(salida)
    assert resultado.resumen.calibrado is True
    assert len(filas) == 1 and filas[0]["regla"] == "cercania_peligrosa"
    assert any("centralidad de carril baja (diagnostica; no excluidas" in a
               for a in resultado.resumen.advertencias)
    with open(os.path.join(salida, "tracks.csv"), encoding="utf-8", newline="") as f:
        tracks = list(csv.DictReader(f))
    assert tracks and {r["carril"] for r in tracks} == {"0"}
    assert all(0.0 <= float(r["centralidad_carril"]) < 0.6 for r in tracks)


def test_pipeline_entrega_cambio_geometrico_bajo_centralidad_a_motor(tmp_path) -> None:
    """M3 confirma por pertenencia persistente; no filtra por centralidad."""
    from roadguard.tipos import Deteccion

    class DetectorCambio:
        version_modelo = "secuencia geometrica sintetica"

        def __init__(self):
            self.i = 0

        def detectar(self, imagen):
            centro = 139 if self.i < 30 else 141
            self.i += 1
            return [Deteccion("automovil", 0.9, Caja(centro - 10, 90, centro + 10, 120))]

    class MotorCaptura:
        def __init__(self):
            self.cambios = []

        def actualizar(self, t, estados, relaciones, cambios):
            self.cambios.extend(cambios)
            return [], {}

        def finalizar(self):
            return []

    datos = _config(calibrada=True)
    datos["carriles"][0]["poligono"] = [[0, 0], [140, 0], [140, ALTO], [0, ALTO]]
    datos["carriles"][1]["poligono"] = [[140, 0], [ANCHO, 0], [ANCHO, ALTO], [140, ALTO]]
    datos["confianza_min_carril"] = 0.6
    cfg = configuracion_desde_dict(datos)
    motor = MotorCaptura()
    Pipeline(cfg, DetectorCambio(), motor=motor).ejecutar(
        _video(tmp_path, 60), str(tmp_path / "cambio-geometrico"),
        escribir_video=False,
    )
    assert len(motor.cambios) == 1
    cambio = motor.cambios[0]
    assert (cambio.carril_origen, cambio.carril_destino) == (0, 1)
    assert cambio.t_confirmacion - cambio.t_cruce >= 1.0


def test_pipeline_descarta_cajas_recortadas_y_conserva_tracks(tmp_path) -> None:
    # La escena dura mas que los 2 s de persistencia: sin el gate produciria RF7.
    video = _video(tmp_path)
    cfg = configuracion_desde_dict(_config(calibrada=True))
    salida = str(tmp_path / "recortadas")
    resultado = Pipeline(cfg, DetectorGeometriaNoConfiable(True)).ejecutar(
        video, salida, escribir_video=False, escribir_tracks=True
    )
    _, filas, resumen = _leer_salidas(salida)
    assert resultado.resumen.calibrado is True
    assert filas == []
    assert any("cajas recortadas excluidas" in a for a in resultado.resumen.advertencias)
    assert resumen["ejecucion"]["n_eventos"]["cercania_peligrosa"] == 0
    with open(os.path.join(salida, "tracks.csv"), encoding="utf-8", newline="") as f:
        tracks = list(csv.DictReader(f))
    assert tracks
    assert {r["carril"] for r in tracks} == {""}


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


def test_cli_flags_nuevos_y_longitudinal_sin_homografia(tmp_path, capsys) -> None:
    parser = cli.construir_parser()
    base = ["procesar", "--video", "v.mp4", "--config", "c.yaml", "--salida", "s"]
    defaults = parser.parse_args(base)
    assert defaults.compensar_camara is None
    assert defaults.punto_apoyo is None
    explicitos = parser.parse_args(base + ["--compensar-camara", "--punto-apoyo", "longitudinal"])
    assert explicitos.compensar_camara is True and explicitos.punto_apoyo == "longitudinal"
    inversos = parser.parse_args(base + ["--sin-compensar-camara", "--punto-apoyo", "centro_inferior"])
    assert inversos.compensar_camara is False and inversos.punto_apoyo == "centro_inferior"
    ruta_cfg = _escribir_yaml(tmp_path, _config(calibrada=False))
    salida = tmp_path / "no-salida"
    codigo = cli.main(
        ["procesar", "--video", _video(tmp_path, 1), "--config", ruta_cfg,
         "--salida", str(salida), "--punto-apoyo", "longitudinal"],
        fabrica_detector=lambda cfg, args: pytest.fail("No debe construirse detector sin homografia"),
    )
    assert codigo == 1
    assert not salida.exists()
    assert "requiere una homografia" in capsys.readouterr().err
    ruta_cfg_valida = _escribir_yaml(tmp_path, _config(calibrada=True))
    salida_valida = tmp_path / "salida-valida"
    codigo = cli.main(
        ["procesar", "--video", _video(tmp_path, 1), "--config", ruta_cfg_valida,
         "--salida", str(salida_valida), "--sin-video", "--compensar-camara",
         "--punto-apoyo", "longitudinal"],
        fabrica_detector=lambda cfg, args: DetectorFalso(),
    )
    assert codigo == 0
    with open(salida_valida / "resumen.json", encoding="utf-8") as f:
        geo = json.load(f)["ejecucion"]["parametros"]["procesamiento_geometria"]
    assert geo["compensar_camara"] is True and geo["metodo_apoyo"] == "longitudinal"


def test_cli_validar_no_crea_detector_ni_salidas(tmp_path, capsys) -> None:
    ruta_cfg = _escribir_yaml(tmp_path, _config(calibrada=False))
    video = _video(tmp_path, 1)
    assert cli.main(["validar", "--video", video, "--config", ruta_cfg],
                    fabrica_detector=lambda *_: pytest.fail("no debe crear detector")) == 0
    assert "RF9" in capsys.readouterr().out
    assert set(tmp_path.iterdir()) == {tmp_path / "camara.yaml", tmp_path / "sintetico.mp4"}


def test_resolution_mismatch_rechazada_antes_de_fabrica_y_salida(tmp_path) -> None:
    datos = _config(calibrada=True)
    datos["camara"] = {"resolucion_referencia": [999, 999]}
    ruta_cfg = _escribir_yaml(tmp_path, datos)
    salida = tmp_path / "no-creada"
    with pytest.raises(ValueError, match="distinta"):
        cli.procesar(cli.construir_parser().parse_args([
            "procesar", "--video", _video(tmp_path, 1), "--config", ruta_cfg,
            "--salida", str(salida),
        ]), lambda *_: pytest.fail("la fabrica debe ejecutarse despues de validar resolucion"))
    assert not salida.exists()


def test_pipeline_constructor_usa_perfil_directamente(tmp_path) -> None:
    from roadguard.tipos import ProcesamientoGeometria
    video = _video(tmp_path, 1)
    cfg = replace(configuracion_desde_dict(_config(calibrada=True)),
                  procesamiento_geometria=ProcesamientoGeometria(True, "longitudinal"))
    resultado = Pipeline(cfg, DetectorFalso()).ejecutar(video, str(tmp_path / "perfil-directo"), escribir_video=False)
    geo = resultado.resumen.parametros["procesamiento_geometria"]
    assert geo["compensar_camara"] is True
    assert geo["metodo_apoyo"] == "longitudinal"


def test_validar_longitudinal_sin_proyector_falla(tmp_path, capsys) -> None:
    datos = _config(calibrada=False)
    datos["procesamiento_geometria"] = {"metodo_apoyo": "longitudinal"}
    ruta_cfg = _escribir_yaml(tmp_path, datos)
    assert cli.main(["validar", "--video", _video(tmp_path, 1), "--config", ruta_cfg]) == 1
    assert "requiere una homografia" in capsys.readouterr().err


def test_politica_cli_se_registra_en_resumen(tmp_path) -> None:
    datos = _config(calibrada=True)
    ruta_cfg = _escribir_yaml(tmp_path, datos)
    politica = tmp_path / "politica.yaml"
    politica.write_text("umbrales:\n  cercania_thw_max: 1.7\n", encoding="utf-8")
    salida = tmp_path / "resultado"
    assert cli.main([
        "procesar", "--video", _video(tmp_path, 1), "--config", ruta_cfg,
        "--salida", str(salida), "--sin-video", "--politica", str(politica),
    ], fabrica_detector=lambda *_: DetectorFalso()) == 0
    import hashlib
    import json
    resumen = json.loads((salida / "resumen.json").read_text(encoding="utf-8"))["ejecucion"]["parametros"]["politica"]
    assert resumen["ruta"] == str(politica)
    assert resumen["sha256"] == hashlib.sha256(politica.read_bytes()).hexdigest()
    assert resumen["umbrales_efectivos"]["cercania_thw_max"] == 1.7


def test_cli_override_geometria_invierte_perfil(tmp_path) -> None:
    datos = _config(calibrada=True)
    datos["procesamiento_geometria"] = {"compensar_camara": True, "metodo_apoyo": "longitudinal"}
    ruta_cfg = _escribir_yaml(tmp_path, datos)
    salida = tmp_path / "override"
    assert cli.main([
        "procesar", "--video", _video(tmp_path, 1), "--config", ruta_cfg,
        "--salida", str(salida), "--sin-video", "--sin-compensar-camara",
        "--punto-apoyo", "centro_inferior",
    ], fabrica_detector=lambda *_: DetectorFalso()) == 0
    import json
    geo = json.loads((salida / "resumen.json").read_text(encoding="utf-8"))["ejecucion"]["parametros"]["procesamiento_geometria"]
    assert geo["compensar_camara"] is False
    assert geo["metodo_apoyo"] == "centro_inferior"


def test_pipeline_rechaza_metodo_apoyo_desconocido() -> None:
    cfg = configuracion_desde_dict(_config(calibrada=False))
    with pytest.raises(ValueError, match="metodo_apoyo"):
        Pipeline(cfg, DetectorFalso(), metodo_apoyo="otro")


def test_cam_fallo_y_recuperacion_actualiza_movimiento_y_puntos(tmp_path, monkeypatch) -> None:
    import roadguard.m3_geometria.procesador as modulo
    import roadguard.pipeline as modulo_pipeline

    traslada = np.array([[1., 0., 8.], [0., 1., 4.], [0., 0., 1.]])
    identidad = np.eye(3)
    valido = MovimientoCamara(traslada, np.linalg.inv(traslada), True)
    invalido = MovimientoCamara(None, None, False, "frame negro")
    class CompensadorFalso:
        def __init__(self, roi):
            self.n = 0
        def actualizar(self, imagen):
            self.n += 1
            return [MovimientoCamara(identidad, identidad, True), valido, invalido, valido][self.n - 1]
    monkeypatch.setattr(modulo, "CompensadorCamara", CompensadorFalso)
    anotaciones = []
    def anotar(imagen, tracks, estados, carriles, advertencia, puntajes):
        anotaciones.append((list(carriles), advertencia))
        return imagen.copy()
    monkeypatch.setattr(modulo_pipeline, "anotar_cuadro", anotar)

    video = _video(tmp_path, 4)
    cfg = configuracion_desde_dict(_config(calibrada=True))
    class DetectorRoi(DetectorFalso):
        def __init__(self):
            super().__init__()
    detector = DetectorRoi()
    class MotorCaptura:
        def __init__(self): self.estados = {}
        def actualizar(self, t, estados, relaciones, cambios):
            self.estados[round(t * FPS)] = estados
            return [], {}
        def finalizar(self): return []
    motor = MotorCaptura()
    resultado = Pipeline(cfg, detector, motor=motor, compensar_camara=True).ejecutar(
        video, str(tmp_path / "cam"), escribir_video=True, escribir_tracks=True
    )
    geo = resultado.resumen.parametros["procesamiento_geometria"]
    assert (geo["cuadros_validos"], geo["cuadros_invalidos"]) == (3, 1)
    assert any("frame negro" in a for a in resultado.resumen.advertencias)
    assert detector.llamadas == 4
    assert [bool(w and "COMPENSACION EN ESPERA" in w) for _, w in anotaciones] == [False, False, True, False]
    assert anotaciones[1][0][0].poligono[0] == pytest.approx((8.0, 4.0))
    assert anotaciones[2][0] == []
    assert anotaciones[3][0][0].poligono[0] == pytest.approx((8.0, 4.0))
    # En el segundo cuadro el vehículo avanzó 2 px, pero la cámara se trasladó
    # 4 px: el punto M3 vuelve a referencia (retrocede 2 px), no a la imagen actual.
    assert motor.estados[1][1].x_camino - motor.estados[0][1].x_camino == pytest.approx(-0.4, abs=0.08)
    failed = motor.estados[2][1]
    assert failed.x_camino is failed.y_camino is failed.velocidad is None
    assert failed.carril is None
    assert failed.carril_estimado == motor.estados[1][1].carril_estimado
    assert motor.estados[3][1].velocidad is None
    from roadguard.m5_salidas.dibujo import etiqueta_vehiculo
    assert etiqueta_vehiculo(
        Track(1, 2, 2 / FPS, "automovil", 0.9, Caja(60, 14, 101, 45), (80, 45)), failed
    ).endswith("sin carril")
    with open(resultado.ruta_tracks, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert filas and all(float(f["x1"]) >= 0 for f in filas)
    assert all(float(f["x1"]) == pytest.approx(60, abs=2) for f in filas if f["id"] == "1")
    assert {"carril_estimado", "centralidad_carril", "apoyo_x", "apoyo_y"} <= set(filas[0])


def test_longitudinal_sin_compensacion_usa_helper_y_preserva_bbox(tmp_path, monkeypatch) -> None:
    import roadguard.m3_geometria.procesador as modulo

    def helper(caja, proyector, matriz=None):
        return caja.x1 + 3.0, caja.y2 - 2.0
    monkeypatch.setattr(modulo, "estimar_apoyo_longitudinal", helper)
    cfg = configuracion_desde_dict(_config(calibrada=True))
    video = _video(tmp_path, 5)
    salida = tmp_path / "long"
    Pipeline(cfg, DetectorFalso(), metodo_apoyo="longitudinal").ejecutar(
        video, str(salida), escribir_video=False, escribir_tracks=True
    )
    with open(salida / "tracks.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows and float(rows[0]["apoyo_x"]) != pytest.approx(
        (float(rows[0]["x1"]) + float(rows[0]["x2"])) / 2
    )
    assert float(rows[0]["apoyo_x"]) == pytest.approx(float(rows[0]["x1"]) + 3)
    assert float(rows[0]["centralidad_carril"]) >= 0.0


def test_longitudinal_helper_none_no_centroid_fallback(tmp_path, monkeypatch) -> None:
    import roadguard.m3_geometria.procesador as modulo
    monkeypatch.setattr(modulo, "estimar_apoyo_longitudinal", lambda *_: None)
    cfg = configuracion_desde_dict(_config(calibrada=True))
    salida = tmp_path / "helper-none"
    Pipeline(cfg, DetectorFalso(), metodo_apoyo="longitudinal").ejecutar(
        _video(tmp_path, 3), str(salida), escribir_video=False, escribir_tracks=True
    )
    with open(salida / "tracks.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows and all(r["apoyo_x"] == r["apoyo_y"] == "" for r in rows)


def test_cam_fallo_entrega_evento_cerrado_del_motor(tmp_path, monkeypatch) -> None:
    import roadguard.m3_geometria.procesador as modulo
    from roadguard.tipos import Evento, Regla
    ident = np.eye(3)
    valid = MovimientoCamara(ident, ident, True)
    invalid = MovimientoCamara(None, None, False, "sin textura")
    class CompensadorFalso:
        def __init__(self, roi): self.i = 0
        def actualizar(self, imagen):
            self.i += 1
            return valid if self.i == 1 else invalid
    class MotorEspia:
        def __init__(self): self.calls = 0
        def actualizar(self, t, estados, relaciones, cambios):
            self.calls += 1
            event = Evento(1, Regla.CERCANIA, 0.0, 0.0, {}, {}, 40) if t > 0 else None
            return ([event] if event else []), {}
        def finalizar(self): return []
    monkeypatch.setattr(modulo, "CompensadorCamara", CompensadorFalso)
    motor = MotorEspia()
    result = Pipeline(
        configuracion_desde_dict(_config(calibrada=True)), DetectorFalso(), motor=motor,
        compensar_camara=True,
    ).ejecutar(_video(tmp_path, 2), str(tmp_path / "event"), escribir_video=False)
    assert motor.calls == 2
    assert len(result.eventos) == 1


def test_cli_tracks_escribe_una_fila_por_vehiculo_y_cuadro(tmp_path) -> None:
    video = _video(tmp_path, n_cuadros=30)
    ruta_cfg = _escribir_yaml(tmp_path, _config(calibrada=True))
    salida = str(tmp_path / "tracks")
    codigo = cli.main(
        ["procesar", "--video", video, "--config", ruta_cfg, "--salida", salida,
         "--sin-video", "--tracks"],
        fabrica_detector=lambda cfg, args: DetectorFalso(),
    )
    assert codigo == 0
    ruta = os.path.join(salida, "tracks.csv")
    assert os.path.isfile(ruta)
    with open(ruta, encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f)
        filas = list(lector)
        assert lector.fieldnames == list(COLUMNAS_TRACKS)
    assert filas, "el detector falso ve dos vehiculos por cuadro"
    cuadros = {int(f["cuadro"]) for f in filas}
    assert min(cuadros) == 0 and max(cuadros) == 29
    # Un ID aparece a lo mas una vez por cuadro.
    pares = [(f["cuadro"], f["id"]) for f in filas]
    assert len(pares) == len(set(pares))
    for f in filas:
        assert f["clase"] == "automovil"
        assert float(f["x2"]) > float(f["x1"]) and float(f["y2"]) > float(f["y1"])
        assert f["carril"] == "" or int(f["carril"]) >= 0
        assert 0.0 <= float(f["confianza"]) <= 1.0


def test_pipeline_sin_tracks_no_escribe_el_archivo(tmp_path) -> None:
    video = _video(tmp_path, n_cuadros=5)
    cfg = configuracion_desde_dict(_config(calibrada=False))
    resultado = Pipeline(cfg, DetectorFalso()).ejecutar(video, str(tmp_path / "s"), escribir_video=False)
    assert resultado.ruta_tracks is None
    assert not os.path.exists(tmp_path / "s" / "tracks.csv")


class DetectorQueSeInterrumpe(DetectorFalso):
    """Simula un Ctrl+C del usuario al llegar al cuadro `en`."""

    def __init__(self, en: int) -> None:
        super().__init__()
        self.en = en

    def detectar(self, imagen) -> list[Deteccion]:
        if self.llamadas == self.en:
            raise KeyboardInterrupt
        return super().detectar(imagen)


def test_ctrl_c_escribe_salidas_parciales(tmp_path) -> None:
    video = _video(tmp_path)
    cfg = configuracion_desde_dict(_config(calibrada=True))
    salida = str(tmp_path / "salida")

    resultado = Pipeline(cfg, DetectorQueSeInterrumpe(en=60)).ejecutar(video, salida)

    assert resultado.resumen.completada is False
    assert resultado.resumen.n_cuadros_procesados == 60
    assert any("interrumpida" in a for a in resultado.resumen.advertencias)
    _, filas, resumen = _leer_salidas(salida)
    assert resumen["ejecucion"]["completada"] is False
    # El tramo de cercania abierto al interrumpir se cierra y queda en el CSV.
    assert filas and filas[0]["regla"] == "cercania_peligrosa"
    assert os.path.isfile(os.path.join(salida, "anotado.mp4"))


def test_cli_ctrl_c_devuelve_130(tmp_path, capsys) -> None:
    video = _video(tmp_path, n_cuadros=10)
    ruta_cfg = _escribir_yaml(tmp_path, _config(calibrada=False))
    codigo = cli.main(
        ["procesar", "--video", video, "--config", ruta_cfg, "--salida", str(tmp_path / "s"),
         "--sin-video"],
        fabrica_detector=lambda cfg, args: DetectorQueSeInterrumpe(en=4),
    )
    assert codigo == 130
    assert "INCOMPLETA" in capsys.readouterr().out
