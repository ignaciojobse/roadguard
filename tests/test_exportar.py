"""RF12. Exportacion de eventos CSV y resumen JSON (m5_salidas/exportar).

Casos minimos a cubrir:
  - El CSV lleva las columnas fijas y, aplanadas, variables y umbrales.
  - Los valores None se escriben vacios y las filas van por t_inicio.
  - Sin eventos se escribe solo el encabezado.
  - El JSON incluye configuracion_sha256, parametros y los enums por valor.
"""

import csv
import json

from roadguard.m5_salidas.exportar import (
    COLUMNAS_FIJAS,
    escribir_eventos_csv,
    escribir_resumen_json,
)
from roadguard.tipos import Evento, NivelRiesgo, Regla, ResumenEjecucion, ResumenVehiculo


def _evento(id_v=1, t0=2.0, ttc=None) -> Evento:
    return Evento(
        id_vehiculo=id_v,
        regla=Regla.CERCANIA,
        t_inicio=t0,
        t_fin=t0 + 2.5,
        variables={"velocidad": 12.0, "thw": 0.8, "ttc": ttc},
        umbrales={"cercania_thw_max": 1.5},
        aporte_puntaje=40,
        id_relacionado=2,
    )


def test_csv_columnas_y_valores(tmp_path) -> None:
    ruta = str(tmp_path / "eventos.csv")
    columnas = escribir_eventos_csv(ruta, [_evento(t0=5.0), _evento(id_v=3, t0=1.0, ttc=4.0)])
    assert columnas[: len(COLUMNAS_FIJAS)] == list(COLUMNAS_FIJAS)
    assert columnas[len(COLUMNAS_FIJAS):] == [
        "variable_thw", "variable_ttc", "variable_velocidad", "umbral_cercania_thw_max",
    ]
    with open(ruta, encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    assert [fila["id_vehiculo"] for fila in filas] == ["3", "1"]
    assert filas[0]["regla"] == "cercania_peligrosa"
    assert filas[0]["variable_ttc"] == "4.0"
    assert filas[1]["variable_ttc"] == ""
    assert filas[1]["id_relacionado"] == "2"
    assert filas[1]["aporte_puntaje"] == "40"
    assert filas[1]["umbral_cercania_thw_max"] == "1.5"


def test_csv_sin_eventos_escribe_encabezado(tmp_path) -> None:
    ruta = str(tmp_path / "sub" / "eventos.csv")
    assert escribir_eventos_csv(ruta, []) == list(COLUMNAS_FIJAS)
    with open(ruta, encoding="utf-8") as f:
        lineas = f.read().splitlines()
    assert lineas == [",".join(COLUMNAS_FIJAS)]


def test_json_resumen(tmp_path) -> None:
    ruta = str(tmp_path / "resumen.json")
    ejecucion = ResumenEjecucion(
        video="v.mp4", configuracion="c.yaml", version_modelo="falso", fps_video=25.0,
        fps_procesamiento=10.0, n_cuadros_procesados=5, calibrado=False,
        advertencias=["SIN CALIBRACION"], configuracion_sha256="abc",
        parametros={"umbrales": {"aporte_cercania": 40}}, n_eventos={"cercania_peligrosa": 1},
    )
    vehiculos = [
        ResumenVehiculo(2, "bus", 0.0, 1.0, {}, 0, NivelRiesgo.VERDE),
        ResumenVehiculo(1, "automovil", 0.0, 2.0, {"cercania_peligrosa": 1}, 40, NivelRiesgo.AMARILLO),
    ]
    escribir_resumen_json(ruta, ejecucion, vehiculos)
    with open(ruta, encoding="utf-8") as f:
        doc = json.load(f)
    assert doc["ejecucion"]["configuracion_sha256"] == "abc"
    assert doc["ejecucion"]["parametros"]["umbrales"]["aporte_cercania"] == 40
    assert doc["ejecucion"]["calibrado"] is False
    assert doc["ejecucion"]["completada"] is True
    assert [v["id_vehiculo"] for v in doc["vehiculos"]] == [1, 2]
    assert doc["vehiculos"][0]["nivel_maximo"] == "amarillo"
