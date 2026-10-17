"""T9 - mAP@0.5, IDF1, intercambios de ID y FPS sobre una secuencia UA-DETRAC.

Ejemplo:
    python scripts/evaluar_uadetrac.py \\
        --imagenes datos/uadetrac/imagenes/MVI_20011 \\
        --anotaciones datos/uadetrac/anotaciones/MVI_20011.xml \\
        --salida salidas/evaluacion/MVI_20011 --dispositivo 0

Corre YOLOv8n (M2) y ByteTrack sobre las imagenes de la secuencia, escribe
`predicciones.csv` (detecciones con confianza >= --confianza-map, para el
calculo de AP) y `tracks.csv` (seguimiento con el piso de confianza del
pipeline), y deja las metricas en `metricas.json`.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import time
from collections import defaultdict

import cv2

from roadguard.m2_deteccion.detector import DetectorVehiculos
from roadguard.m2_deteccion.tracker import SeguidorByteTrack
from roadguard.m5_salidas.registros import limpiar_json
from roadguard.m6_evaluacion.deteccion import calcular_map
from roadguard.m6_evaluacion.rendimiento import medir_fps
from roadguard.m6_evaluacion.seguimiento import calcular_metricas_seguimiento
from roadguard.m6_evaluacion.uadetrac import Objeto, escribir_predicciones, leer_xml
from roadguard.tipos import Configuracion, Homografia, Umbrales


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--imagenes", required=True)
    p.add_argument("--anotaciones", required=True)
    p.add_argument("--salida", required=True)
    p.add_argument("--pesos", default="yolov8n.pt")
    p.add_argument("--dispositivo", default=None)
    p.add_argument("--fps", type=float, default=25.0, help="UA-DETRAC: 25 FPS")
    p.add_argument("--confianza", type=float, default=0.25, help="Piso para el seguimiento (como el pipeline)")
    p.add_argument("--confianza-map", type=float, default=0.01, help="Piso para el calculo de AP")
    p.add_argument("--max-cuadros", type=int, default=None)
    args = p.parse_args(argv)

    rutas = sorted(glob.glob(os.path.join(args.imagenes, "*.jpg")))[: args.max_cuadros]
    if not rutas:
        raise SystemExit(f"No hay imagenes .jpg en {args.imagenes}")
    alto, ancho = cv2.imread(rutas[0]).shape[:2]
    cfg = Configuracion(
        region_interes=[(0, 0), (ancho, 0), (ancho, alto), (0, alto)],
        carriles=[],
        homografia=Homografia(),
        clases=["automovil", "bus", "camion", "motocicleta"],
        umbrales=Umbrales(),
        confianza_min_deteccion=args.confianza_map,
    )
    detector = DetectorVehiculos(cfg, pesos=args.pesos, dispositivo=args.dispositivo)
    seguidor = SeguidorByteTrack(args.fps)

    detecciones, tracks = [], []
    tiempos = defaultdict(list)
    for ruta in rutas:
        cuadro = int(re.findall(r"\d+", os.path.basename(ruta))[-1])
        t = (cuadro - 1) / args.fps
        r0 = time.perf_counter()
        imagen = cv2.imread(ruta)
        r1 = time.perf_counter()
        dets = detector.detectar(imagen)
        r2 = time.perf_counter()
        trs = seguidor.actualizar([d for d in dets if d.confianza >= args.confianza], cuadro, t)
        r3 = time.perf_counter()
        tiempos["lectura"].append(r1 - r0)
        tiempos["deteccion"].append(r2 - r1)
        tiempos["seguimiento"].append(r3 - r2)
        detecciones += [Objeto(cuadro, None, d.clase, d.caja, d.confianza) for d in dets]
        tracks += [Objeto(cuadro, tr.id_vehiculo, tr.clase, tr.caja, tr.confianza) for tr in trs]

    os.makedirs(args.salida, exist_ok=True)
    escribir_predicciones(detecciones, os.path.join(args.salida, "predicciones.csv"))
    escribir_predicciones(tracks, os.path.join(args.salida, "tracks.csv"))

    seq = leer_xml(args.anotaciones)
    procesados = {int(re.findall(r"\d+", os.path.basename(r))[-1]) for r in rutas}
    verdad = {c: v for c, v in seq.objetos.items() if c in procesados}
    agrupar = lambda objs: {c: [o for o in objs if o.cuadro == c] for c in {o.cuadro for o in objs}}
    metricas = {
        "secuencia": seq.nombre,
        "atributos": seq.atributos,
        "resolucion": [ancho, alto],
        "n_cuadros": len(rutas),
        "version_modelo": detector.version_modelo,
        "parametros": vars(args),
        "deteccion": calcular_map(verdad, agrupar(detecciones), seq.ignoradas),
        "seguimiento": calcular_metricas_seguimiento(verdad, agrupar(tracks), seq.ignoradas),
        "rendimiento": medir_fps(dict(tiempos)),
    }
    with open(os.path.join(args.salida, "metricas.json"), "w", encoding="utf-8") as f:
        json.dump(limpiar_json(metricas), f, ensure_ascii=False, indent=2)

    d, s, r = metricas["deteccion"], metricas["seguimiento"], metricas["rendimiento"]
    print(
        f"{seq.nombre}: mAP@0.5={d['map_50']:.3f} (agnostico {d['ap_vehiculo']:.3f}) | "
        f"IDF1={s['idf1']:.3f} | ID switches={int(s['intercambios_id'])} | "
        f"FPS deteccion+seguimiento={r['fps_global']:.1f} (resolucion {ancho}x{alto})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
