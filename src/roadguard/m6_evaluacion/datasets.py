"""T6 - Conversion de trayectorias de referencia al contrato de datos (2.4).

highD es la fuente preferida para desarrollar y validar reglas; si no esta
disponible se usa NGSIM (riesgos 4.4). Ambas se convierten a
`EstadoCinematico` con coordenadas del camino en metros, x en el sentido de
avance, velocidad longitudinal en m/s y carril del propio dataset. Las
trayectorias limpias son la referencia para T9: sobre ellas se calculan
eventos con el mismo motor de reglas (M3 + M4) que usa el pipeline.

Formato intermedio: CSV con una fila por EstadoCinematico
(COLUMNAS_ESTADOS) y un JSON de metadatos al lado con fuente, filtros y FPS.
"""

from __future__ import annotations

import csv
import json
import math
import os
from collections import defaultdict
from typing import Iterator, Optional

from roadguard.tipos import EstadoCinematico

PIE = 0.3048  # NGSIM publica en pies

COLUMNAS_ESTADOS: tuple[str, ...] = (
    "id_vehiculo",
    "cuadro",
    "t",
    "x_camino",
    "y_camino",
    "velocidad",
    "carril",
    "confianza_carril",
    "calibrado",
)


# ---------------------------------------------------------------------------
# highD
# ---------------------------------------------------------------------------

def cargar_highd(
    ruta_tracks: str,
    ruta_tracks_meta: str,
    ruta_recording_meta: str,
) -> tuple[list[EstadoCinematico], float]:
    """Lee XX_tracks.csv, XX_tracksMeta.csv y XX_recordingMeta.csv.

    highD entrega x, y como esquina superior izquierda de la caja en metros
    sobre la imagen aerea. Se usa el centro de la caja. Los vehiculos con
    drivingDirection == 1 avanzan hacia x decreciente: para ellos se
    invierten x, y y la velocidad, de modo que x crece en el sentido de
    avance en todos los carriles (convencion de M3). Los laneId de highD ya
    distinguen ambos sentidos.
    """
    import pandas as pd

    meta_rec = pd.read_csv(ruta_recording_meta)
    fps = float(meta_rec["frameRate"].iloc[0])
    meta = pd.read_csv(ruta_tracks_meta, usecols=["id", "drivingDirection"])
    sentido = dict(zip(meta["id"].astype(int), meta["drivingDirection"].astype(int)))
    df = pd.read_csv(
        ruta_tracks,
        usecols=["frame", "id", "x", "y", "width", "height", "xVelocity", "laneId"],
    )
    df = df.sort_values(["frame", "id"])
    frame0 = int(df["frame"].min())

    estados = []
    for fila in df.itertuples(index=False):
        signo = -1.0 if sentido.get(int(fila.id), 2) == 1 else 1.0
        estados.append(
            EstadoCinematico(
                id_vehiculo=int(fila.id),
                cuadro=int(fila.frame),
                t=(int(fila.frame) - frame0) / fps,
                x_camino=signo * (float(fila.x) + float(fila.width) / 2.0),
                y_camino=signo * (float(fila.y) + float(fila.height) / 2.0),
                velocidad=signo * float(fila.xVelocity),
                carril=int(fila.laneId),
                confianza_carril=1.0,
                calibrado=True,
            )
        )
    return estados, fps


# ---------------------------------------------------------------------------
# NGSIM
# ---------------------------------------------------------------------------

def cargar_ngsim(
    ruta_csv: str,
    ubicacion: Optional[str] = None,
    t_global_inicio: Optional[int] = None,
    t_global_fin: Optional[int] = None,
    fps: float = 10.0,
) -> tuple[list[EstadoCinematico], float]:
    """Lee el CSV de NGSIM "Vehicle Trajectories and Supporting Data".

    Columnas usadas (sin distinguir mayusculas): Vehicle_ID, Frame_ID,
    Global_Time (ms), Local_X (lateral, pies), Local_Y (longitudinal, pies,
    crece en el sentido de avance), v_Vel (pies/s), Lane_ID y, si existe,
    Location. NGSIM publica cada 0,1 s.

    El archivo combinado mezcla ubicaciones (us-101, i-80, ...) que reusan
    IDs y cuadros: `ubicacion` filtra una sola, y `t_global_*` (ms) acotan un
    periodo. Las filas duplicadas (mismo vehiculo y cuadro) se descartan.
    """
    import pandas as pd

    columnas = pd.read_csv(ruta_csv, nrows=0).columns
    por_minuscula = {c.lower(): c for c in columnas}
    requeridas = ["vehicle_id", "frame_id", "global_time", "local_x", "local_y", "v_vel", "lane_id"]
    faltan = [c for c in requeridas if c not in por_minuscula]
    if faltan:
        raise ValueError(f"CSV de NGSIM sin columnas {faltan}")
    usar = [por_minuscula[c] for c in requeridas]
    if "location" in por_minuscula:
        usar.append(por_minuscula["location"])
    elif ubicacion is not None:
        raise ValueError("El CSV no tiene columna Location para filtrar")

    trozos = []
    for trozo in pd.read_csv(ruta_csv, usecols=usar, chunksize=500_000):
        trozo.columns = [c.lower() for c in trozo.columns]
        if ubicacion is not None:
            trozo = trozo[trozo["location"].astype(str).str.lower() == ubicacion.lower()]
        if t_global_inicio is not None:
            trozo = trozo[trozo["global_time"] >= t_global_inicio]
        if t_global_fin is not None:
            trozo = trozo[trozo["global_time"] <= t_global_fin]
        trozos.append(trozo)
    df = pd.concat(trozos, ignore_index=True)
    df = df.drop_duplicates(subset=["vehicle_id", "frame_id"]).sort_values(["frame_id", "vehicle_id"])
    if df.empty:
        return [], fps
    frame0 = int(df["frame_id"].min())

    estados = [
        EstadoCinematico(
            id_vehiculo=int(f.vehicle_id),
            cuadro=int(f.frame_id),
            t=(int(f.frame_id) - frame0) / fps,
            x_camino=float(f.local_y) * PIE,
            y_camino=float(f.local_x) * PIE,
            velocidad=float(f.v_vel) * PIE,
            carril=int(f.lane_id),
            confianza_carril=1.0,
            calibrado=True,
        )
        for f in df.itertuples(index=False)
    ]
    return estados, fps


# ---------------------------------------------------------------------------
# Formato intermedio
# ---------------------------------------------------------------------------

def guardar_estados_csv(
    estados: list[EstadoCinematico], ruta: str, metadatos: Optional[dict] = None
) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNAS_ESTADOS)
        for e in estados:
            w.writerow(
                [
                    e.id_vehiculo, e.cuadro, repr(e.t),
                    _txt(e.x_camino), _txt(e.y_camino), _txt(e.velocidad),
                    "" if e.carril is None else e.carril,
                    repr(e.confianza_carril), int(e.calibrado),
                ]
            )
    if metadatos is not None:
        with open(_ruta_meta(ruta), "w", encoding="utf-8") as f:
            json.dump(metadatos, f, ensure_ascii=False, indent=2)


def leer_estados_csv(ruta: str) -> tuple[list[EstadoCinematico], dict]:
    estados = []
    with open(ruta, encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f):
            estados.append(
                EstadoCinematico(
                    id_vehiculo=int(fila["id_vehiculo"]),
                    cuadro=int(fila["cuadro"]),
                    t=float(fila["t"]),
                    x_camino=_num(fila["x_camino"]),
                    y_camino=_num(fila["y_camino"]),
                    velocidad=_num(fila["velocidad"]),
                    carril=None if fila["carril"] == "" else int(fila["carril"]),
                    confianza_carril=float(fila["confianza_carril"]),
                    calibrado=fila["calibrado"] == "1",
                )
            )
    meta = {}
    if os.path.exists(_ruta_meta(ruta)):
        with open(_ruta_meta(ruta), encoding="utf-8") as f:
            meta = json.load(f)
    return estados, meta


def por_cuadro(estados: list[EstadoCinematico]) -> Iterator[tuple[int, float, list[EstadoCinematico]]]:
    """Agrupa en orden temporal estricto, como si fuera una transmision."""
    grupos: dict[int, list[EstadoCinematico]] = defaultdict(list)
    for e in estados:
        grupos[e.cuadro].append(e)
    for cuadro in sorted(grupos):
        grupo = sorted(grupos[cuadro], key=lambda e: e.id_vehiculo)
        yield cuadro, grupo[0].t, grupo


def recortar(
    estados: list[EstadoCinematico], t_max: Optional[float] = None, max_vehiculos: Optional[int] = None
) -> list[EstadoCinematico]:
    """Subconjunto reproducible para pruebas rapidas."""
    if t_max is not None:
        estados = [e for e in estados if e.t <= t_max]
    if max_vehiculos is not None:
        ids = sorted({e.id_vehiculo for e in estados})[:max_vehiculos]
        permitidos = set(ids)
        estados = [e for e in estados if e.id_vehiculo in permitidos]
    return estados


def _ruta_meta(ruta: str) -> str:
    return os.path.splitext(ruta)[0] + ".meta.json"


def _txt(x: Optional[float]) -> str:
    return "" if x is None or not math.isfinite(x) else repr(x)


def _num(s: str) -> Optional[float]:
    return None if s == "" else float(s)
