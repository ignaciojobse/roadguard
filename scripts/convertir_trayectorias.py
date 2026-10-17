"""T6 - Convierte highD o NGSIM al contrato de datos de RoadGuard.

Ejemplos:
    python scripts/convertir_trayectorias.py highd \\
        --tracks datos/highd/01_tracks.csv \\
        --tracks-meta datos/highd/01_tracksMeta.csv \\
        --recording-meta datos/highd/01_recordingMeta.csv \\
        --salida datos/trayectorias/highd_01.csv

    python scripts/convertir_trayectorias.py ngsim \\
        --csv datos/ngsim/Next_Generation_Simulation__NGSIM__Vehicle_Trajectories_and_Supporting_Data.csv \\
        --ubicacion us-101 --t-global-inicio <ms> --t-global-fin <ms> \\
        --salida datos/trayectorias/ngsim_us101_p1.csv

Genera el CSV de estados y un .meta.json con la fuente, los filtros y los
FPS, para que la conversion sea reproducible.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys

from roadguard.m6_evaluacion.datasets import cargar_highd, cargar_ngsim, guardar_estados_csv, recortar


def _sha256(ruta: str) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="fuente", required=True)

    h = sub.add_parser("highd")
    h.add_argument("--tracks", required=True)
    h.add_argument("--tracks-meta", required=True)
    h.add_argument("--recording-meta", required=True)

    n = sub.add_parser("ngsim")
    n.add_argument("--csv", required=True)
    n.add_argument("--ubicacion", default=None, help="us-101, i-80, ...")
    n.add_argument("--t-global-inicio", type=int, default=None, help="Global_Time minimo (ms)")
    n.add_argument("--t-global-fin", type=int, default=None, help="Global_Time maximo (ms)")

    for s in (h, n):
        s.add_argument("--salida", required=True)
        s.add_argument("--t-max", type=float, default=None, help="Recorta a los primeros N segundos")

    args = p.parse_args(argv)
    if args.fuente == "highd":
        estados, fps = cargar_highd(args.tracks, args.tracks_meta, args.recording_meta)
        archivos = [args.tracks, args.tracks_meta, args.recording_meta]
        filtros = {}
    else:
        estados, fps = cargar_ngsim(args.csv, args.ubicacion, args.t_global_inicio, args.t_global_fin)
        archivos = [args.csv]
        filtros = {
            "ubicacion": args.ubicacion,
            "t_global_inicio": args.t_global_inicio,
            "t_global_fin": args.t_global_fin,
        }
    estados = recortar(estados, t_max=args.t_max)
    if not estados:
        print("No quedaron estados tras los filtros", file=sys.stderr)
        return 1

    metadatos = {
        "fuente": args.fuente,
        "archivos": [
            {"ruta": os.path.abspath(a), "sha256": _sha256(a)} for a in archivos
        ],
        "filtros": {**filtros, "t_max": args.t_max},
        "fps": fps,
        "n_estados": len(estados),
        "n_vehiculos": len({e.id_vehiculo for e in estados}),
        "duracion_s": max(e.t for e in estados),
        "carriles": sorted({e.carril for e in estados if e.carril is not None}),
    }
    guardar_estados_csv(estados, args.salida, metadatos)
    print(
        f"{metadatos['n_vehiculos']} vehiculos, {metadatos['n_estados']} estados, "
        f"{metadatos['duracion_s']:.1f} s a {fps:g} FPS -> {args.salida}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
