"""Datos de la demo interactiva (M5): una corrida completa en un solo JSON.

`construir_demo` junta lo que la pagina `demo_web/` necesita para mostrar la
cadena de principio a fin sobre los cuadros originales: cajas e IDs (M2),
posicion en metros, carril, velocidad, THW y TTC (M3), puntaje y eventos
(M4), la geometria de la camara (region, carriles y una rejilla metrica en
pixeles) y las metricas medidas. Lee las salidas de una corrida hecha con
`--tracks --estados`; no vuelve a procesar el video.

Formato de cada vehiculo en `cuadros[i]` (lista compacta, para que el JSON
sea liviano): [id, clase, x1, y1, x2, y2, x_m, y_m, velocidad, carril,
id_predecesor, thw, ttc, puntaje, nivel]. Lo no disponible es null.
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from roadguard.m3_geometria.calibracion import proyectar_a_imagen
from roadguard.m3_geometria.homografia import ProyectorCamino
from roadguard.tipos import Configuracion

CAMPOS_VEHICULO = (
    "id", "clase", "x1", "y1", "x2", "y2", "x_m", "y_m", "velocidad", "carril",
    "id_predecesor", "thw", "ttc", "puntaje", "nivel",
)


def _num(texto: str, entero: bool = False) -> Optional[float]:
    if texto is None or texto == "":
        return None
    return int(float(texto)) if entero else float(texto)


def _redondear(valor: Optional[float], decimales: int = 2) -> Optional[float]:
    return None if valor is None else round(valor, decimales)


def _leer_csv(ruta: Path) -> list[dict[str, str]]:
    with open(ruta, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def geometria(cfg: Configuracion, paso_m: float = 5.0) -> dict[str, Any]:
    """Region y carriles en pixeles; con calibracion, tambien en metros y una rejilla."""
    salida: dict[str, Any] = {
        "region_px": [list(p) for p in cfg.region_interes],
        "carriles_px": [
            {"indice": c.indice, "poligono": [list(p) for p in c.poligono]} for c in cfg.carriles
        ],
        "calibrado": False,
    }
    proyector = ProyectorCamino(cfg.homografia)
    if not proyector.disponible:
        return salida
    def a_metros(poligono):
        puntos = [proyector.proyectar(tuple(p)) for p in poligono]
        return [[round(x, 2), round(y, 2)] for x, y in (p for p in puntos if p is not None)]
    region_m = a_metros(cfg.region_interes)
    xs = [p[0] for p in region_m]
    ys = [p[1] for p in region_m]
    rejilla: list[list[list[float]]] = []
    if xs and ys:
        x0, x1 = math.floor(min(xs) / paso_m) * paso_m, math.ceil(max(xs) / paso_m) * paso_m
        y0, y1 = min(ys), max(ys)
        x = x0
        while x <= x1 + 1e-9:
            linea = proyectar_a_imagen(cfg.homografia, [(x, y0), (x, y1)])
            if all(p is not None for p in linea):
                rejilla.append([[round(p[0], 1), round(p[1], 1)] for p in linea])
            x += paso_m
    salida.update(
        calibrado=True,
        region_m=region_m,
        carriles_m=[{"indice": c.indice, "poligono": a_metros(c.poligono)} for c in cfg.carriles],
        rejilla_px=rejilla,
        paso_rejilla_m=paso_m,
    )
    return salida


def construir_demo(
    secuencia: str,
    cfg: Configuracion,
    corrida: Path,
    patron_cuadros: str,
) -> dict[str, Any]:
    """Arma el documento de la demo a partir de una corrida con tracks y estados."""
    corrida = Path(corrida)
    with open(corrida / "resumen.json", encoding="utf-8") as f:
        resumen = json.load(f)
    ejecucion = resumen["ejecucion"]
    n_cuadros = ejecucion["n_cuadros_procesados"]

    estados: dict[tuple[int, int], dict[str, str]] = {
        (int(f["cuadro"]), int(f["id"])): f for f in _leer_csv(corrida / "estados.csv")
    }
    cuadros: list[list[list[Any]]] = [[] for _ in range(n_cuadros)]
    for f in _leer_csv(corrida / "tracks.csv"):
        c, ident = int(f["cuadro"]), int(f["id"])
        if not 0 <= c < n_cuadros:
            continue
        e = estados.get((c, ident), {})
        cuadros[c].append([
            ident,
            f["clase"],
            round(float(f["x1"]), 1), round(float(f["y1"]), 1),
            round(float(f["x2"]), 1), round(float(f["y2"]), 1),
            _redondear(_num(e.get("x_m", ""))),
            _redondear(_num(e.get("y_m", ""))),
            _redondear(_num(e.get("velocidad", ""))),
            _num(e.get("carril", ""), entero=True),
            _num(e.get("id_predecesor", ""), entero=True),
            _redondear(_num(e.get("thw", ""))),
            _redondear(_num(e.get("ttc", ""))),
            _num(e.get("puntaje", ""), entero=True) or 0,
            e.get("nivel") or "verde",
        ])

    eventos = []
    for f in _leer_csv(corrida / "eventos.csv"):
        variables = {
            k[len("variable_"):]: _redondear(_num(v), 2)
            for k, v in f.items()
            if k.startswith("variable_") and v != ""
        }
        eventos.append({
            "id": int(f["id_vehiculo"]),
            "regla": f["regla"],
            "t_inicio": float(f["t_inicio"]),
            "t_fin": float(f["t_fin"]),
            "id_relacionado": _num(f.get("id_relacionado", ""), entero=True),
            "aporte": int(f["aporte_puntaje"]),
            "variables": variables,
        })

    metricas = None
    if (corrida / "metricas.json").is_file():
        with open(corrida / "metricas.json", encoding="utf-8") as f:
            roi = json.load(f)["region_interes"]
        metricas = {
            "map50": roi["map50_sin_clase"]["ap"],
            "idf1": roi["seguimiento"]["idf1"],
            "cambios_id": roi["seguimiento"]["cambios_id"],
        }

    return {
        "secuencia": secuencia,
        "descripcion": cfg_descripcion(cfg),
        "fps": ejecucion["fps_video"],
        "n_cuadros": n_cuadros,
        "fps_procesamiento": round(ejecucion["fps_procesamiento"], 1),
        "patron_cuadros": patron_cuadros,
        "campos_vehiculo": list(CAMPOS_VEHICULO),
        "geometria": geometria(cfg),
        "umbrales": {
            "cercania_thw_max": cfg.umbrales.cercania_thw_max,
            "cercania_velocidad_min": cfg.umbrales.cercania_velocidad_min,
            "banda_verde_max": cfg.umbrales.banda_verde_max,
            "banda_amarillo_max": cfg.umbrales.banda_amarillo_max,
        },
        "n_eventos": ejecucion["n_eventos"],
        "metricas": metricas,
        "eventos": sorted(eventos, key=lambda e: e["t_inicio"]),
        "cuadros": cuadros,
        "vehiculos": {
            str(v["id_vehiculo"]): {"clase": v["clase"], "puntaje_maximo": v["puntaje_maximo"]}
            for v in resumen["vehiculos"]
        },
    }


def cfg_descripcion(cfg: Configuracion) -> str:
    """Una linea legible de la camara (para el titulo de la demo)."""
    return "Con calibracion" if ProyectorCamino(cfg.homografia).disponible else "Sin calibracion"


def contar_por_cuadro(documento: dict[str, Any]) -> dict[int, int]:
    """Vehiculos por cuadro (ayuda para pruebas y diagnostico)."""
    cuenta: dict[int, int] = defaultdict(int)
    for i, vehiculos in enumerate(documento["cuadros"]):
        cuenta[i] = len(vehiculos)
    return dict(cuenta)
