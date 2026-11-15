"""Mide deteccion y seguimiento de una corrida sobre UA-DETRAC (seccion 2.5).

Compara `tracks.csv` (salida opcional del pipeline, `--tracks`) con el XML
oficial de la secuencia y escribe `metricas.json` en la carpeta de la
corrida. No vuelve a correr el detector.

Uso, desde la raiz del repo:

    python scripts/medir_mvi.py MVI_39271
    python scripts/medir_mvi.py MVI_39271 --corrida salidas/MVI_39271 \
        --xml datos/ua-detrac/MVI_39271/MVI_39271.xml --config configs/MVI_39271.yaml

Que se mide y como:

- Correspondencia de cuadros: `cuadro` del pipeline es 0-based y el XML
  numera desde 1 (img00001.jpg), asi que cuadro = num - 1.
- Regiones ignoradas: las cajas (de referencia o detectadas) cuyo centro cae
  dentro de un `ignored_region` del XML se descartan, como hace el toolkit
  oficial de DETRAC.
- Region de interes: el detector descarta lo que queda fuera del poligono
  `region_interes` del YAML (criterio: centro del borde inferior). La
  referencia anota la imagen completa, incluida la calzada contraria, asi
  que se reportan dos vistas: `cuadro_completo` (todas las cajas de
  referencia) y `region_interes` (solo la referencia cuyo punto de calzada
  cae en la region). La segunda es la que corresponde al alcance del
  sistema; la primera dice cuanto se pierde por recortar.
- Clases: UA-DETRAC anota car, van, bus y others; la configuracion usa
  automovil, bus, camion y motocicleta. Mapeo: car y van -> automovil,
  bus -> bus, others -> camion. La metrica principal es sin clase
  (`vehiculo`), como fija el PRD; el AP por clase se informa aparte.
- mAP@0.5: AP con interpolacion en todos los puntos (VOC 2010+), ordenando
  las detecciones por confianza y emparejando con IoU >= 0,5 una sola vez
  por caja de referencia. Sin clase es un solo AP.
- IDF1: cuenta, por cada par (id de referencia, id detectado), los cuadros
  en que se solapan con IoU >= 0,5; asigna pares con el metodo hungaro
  maximizando esos cuadros (IDTP) y deriva IDFN e IDFP del resto.
- Cambios de ID y MOTA: emparejamiento hungaro por cuadro con IoU >= 0,5;
  un cambio de ID se cuenta cuando una referencia pasa a estar emparejada
  con un id detectado distinto del anterior.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from roadguard.m1_ingesta.config import cargar_configuracion  # noqa: E402
from roadguard.poligonos import punto_en_poligono  # noqa: E402

MAPEO_CLASES = {"car": "automovil", "van": "automovil", "bus": "bus", "others": "camion"}
IOU_MIN = 0.5


@dataclass(frozen=True)
class CajaRef:
    cuadro: int
    ident: int
    clase: str
    xyxy: tuple[float, float, float, float]
    confianza: float = 1.0


def leer_xml(ruta: Path) -> tuple[list[CajaRef], list[tuple[float, float, float, float]]]:
    raiz = ET.parse(ruta).getroot()
    ignoradas = []
    region = raiz.find("ignored_region")
    if region is not None:
        for b in region.findall("box"):
            l, t = float(b.get("left")), float(b.get("top"))
            ignoradas.append((l, t, l + float(b.get("width")), t + float(b.get("height"))))
    cajas = []
    for cuadro in raiz.iter("frame"):
        num = int(cuadro.get("num")) - 1
        for objetivo in cuadro.iter("target"):
            b = objetivo.find("box")
            atributo = objetivo.find("attribute")
            tipo = atributo.get("vehicle_type", "others") if atributo is not None else "others"
            l, t = float(b.get("left")), float(b.get("top"))
            cajas.append(
                CajaRef(
                    num,
                    int(objetivo.get("id")),
                    MAPEO_CLASES.get(tipo, "camion"),
                    (l, t, l + float(b.get("width")), t + float(b.get("height"))),
                )
            )
    return cajas, ignoradas


def leer_tracks(ruta: Path) -> list[CajaRef]:
    cajas = []
    with open(ruta, encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f):
            cajas.append(
                CajaRef(
                    int(fila["cuadro"]),
                    int(fila["id"]),
                    fila["clase"],
                    (float(fila["x1"]), float(fila["y1"]), float(fila["x2"]), float(fila["y2"])),
                    float(fila.get("confianza") or 1.0),
                )
            )
    return cajas


def centro(c: CajaRef) -> tuple[float, float]:
    x1, y1, x2, y2 = c.xyxy
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def punto_calzada(c: CajaRef) -> tuple[float, float]:
    x1, _, x2, y2 = c.xyxy
    return ((x1 + x2) / 2, y2)


def en_ignorada(c: CajaRef, ignoradas) -> bool:
    cx, cy = centro(c)
    return any(x1 <= cx <= x2 and y1 <= cy <= y2 for x1, y1, x2, y2 in ignoradas)


def iou_matriz(a: list[CajaRef], b: list[CajaRef]) -> np.ndarray:
    if not a or not b:
        return np.zeros((len(a), len(b)))
    A = np.array([c.xyxy for c in a])
    B = np.array([c.xyxy for c in b])
    ix1 = np.maximum(A[:, None, 0], B[None, :, 0])
    iy1 = np.maximum(A[:, None, 1], B[None, :, 1])
    ix2 = np.minimum(A[:, None, 2], B[None, :, 2])
    iy2 = np.minimum(A[:, None, 3], B[None, :, 3])
    inter = np.clip(ix2 - ix1, 0, None) * np.clip(iy2 - iy1, 0, None)
    area_a = (A[:, 2] - A[:, 0]) * (A[:, 3] - A[:, 1])
    area_b = (B[:, 2] - B[:, 0]) * (B[:, 3] - B[:, 1])
    union = area_a[:, None] + area_b[None, :] - inter
    return np.where(union > 0, inter / union, 0.0)


def por_cuadro(cajas: list[CajaRef]) -> dict[int, list[CajaRef]]:
    d: dict[int, list[CajaRef]] = defaultdict(list)
    for c in cajas:
        d[c.cuadro].append(c)
    return d


def average_precision(ref: list[CajaRef], det: list[CajaRef]) -> dict:
    """AP@0.5 con interpolacion en todos los puntos; sin clase si se pasa todo."""
    ref_c = por_cuadro(ref)
    n_ref = len(ref)
    if n_ref == 0:
        return {"ap": None, "n_referencia": 0, "n_detecciones": len(det)}
    det_orden = sorted(det, key=lambda c: -c.confianza)
    usados: dict[int, set[int]] = defaultdict(set)
    tp = np.zeros(len(det_orden))
    fp = np.zeros(len(det_orden))
    for k, d in enumerate(det_orden):
        candidatas = ref_c.get(d.cuadro, [])
        if not candidatas:
            fp[k] = 1
            continue
        ious = iou_matriz([d], candidatas)[0]
        orden = np.argsort(-ious)
        acierto = False
        for j in orden:
            if ious[j] < IOU_MIN:
                break
            if j not in usados[d.cuadro]:
                usados[d.cuadro].add(int(j))
                acierto = True
                break
        tp[k], fp[k] = (1, 0) if acierto else (0, 1)
    tp_acum = np.cumsum(tp)
    fp_acum = np.cumsum(fp)
    recobrado = tp_acum / n_ref
    precision = tp_acum / np.maximum(tp_acum + fp_acum, 1e-9)
    r = np.concatenate(([0.0], recobrado, [recobrado[-1] if len(recobrado) else 0.0]))
    p = np.concatenate(([1.0], precision, [0.0]))
    for i in range(len(p) - 2, -1, -1):
        p[i] = max(p[i], p[i + 1])
    idx = np.where(r[1:] != r[:-1])[0]
    ap = float(np.sum((r[idx + 1] - r[idx]) * p[idx + 1]))
    return {
        "ap": round(ap, 4),
        "n_referencia": n_ref,
        "n_detecciones": len(det),
        "precision_final": round(float(precision[-1]), 4) if len(precision) else None,
        "recobrado_final": round(float(recobrado[-1]), 4) if len(recobrado) else None,
    }


def idf1(ref: list[CajaRef], det: list[CajaRef]) -> dict:
    ref_c, det_c = por_cuadro(ref), por_cuadro(det)
    solapes: dict[tuple[int, int], int] = defaultdict(int)
    for cuadro, refs in ref_c.items():
        dets = det_c.get(cuadro, [])
        if not dets:
            continue
        ious = iou_matriz(refs, dets)
        for i, r in enumerate(refs):
            for j, d in enumerate(dets):
                if ious[i, j] >= IOU_MIN:
                    solapes[(r.ident, d.ident)] += 1
    ids_ref = sorted({c.ident for c in ref})
    ids_det = sorted({c.ident for c in det})
    if not ids_ref or not ids_det:
        idtp = 0
    else:
        costo = np.zeros((len(ids_ref), len(ids_det)))
        pos_r = {v: k for k, v in enumerate(ids_ref)}
        pos_d = {v: k for k, v in enumerate(ids_det)}
        for (r, d), n in solapes.items():
            costo[pos_r[r], pos_d[d]] = -n
        filas, cols = linear_sum_assignment(costo)
        idtp = int(-costo[filas, cols].sum())
    idfn = len(ref) - idtp
    idfp = len(det) - idtp
    valor = 2 * idtp / max(2 * idtp + idfp + idfn, 1)
    return {"idf1": round(valor, 4), "idtp": idtp, "idfp": idfp, "idfn": idfn}


def clear_mot(ref: list[CajaRef], det: list[CajaRef]) -> dict:
    """FN, FP, cambios de ID y MOTA con emparejamiento hungaro por cuadro."""
    ref_c, det_c = por_cuadro(ref), por_cuadro(det)
    ultimo: dict[int, int] = {}
    fn = fp = cambios = 0
    for cuadro in sorted(set(ref_c) | set(det_c)):
        refs = ref_c.get(cuadro, [])
        dets = det_c.get(cuadro, [])
        if refs and dets:
            ious = iou_matriz(refs, dets)
            filas, cols = linear_sum_assignment(-ious)
            emparejados = [(i, j) for i, j in zip(filas, cols) if ious[i, j] >= IOU_MIN]
        else:
            emparejados = []
        for i, j in emparejados:
            r, d = refs[i].ident, dets[j].ident
            if r in ultimo and ultimo[r] != d:
                cambios += 1
            ultimo[r] = d
        fn += len(refs) - len(emparejados)
        fp += len(dets) - len(emparejados)
    n_ref = len(ref)
    mota = 1 - (fn + fp + cambios) / n_ref if n_ref else None
    return {
        "mota": round(mota, 4) if mota is not None else None,
        "falsos_negativos": fn,
        "falsos_positivos": fp,
        "cambios_id": cambios,
        "n_trayectorias_referencia": len({c.ident for c in ref}),
        "n_trayectorias_detectadas": len({c.ident for c in det}),
    }


def medir(ref: list[CajaRef], det: list[CajaRef]) -> dict:
    clases = sorted({c.clase for c in ref} | {c.clase for c in det})
    return {
        "map50_sin_clase": average_precision(ref, det),
        "ap50_por_clase": {
            k: average_precision([c for c in ref if c.clase == k], [c for c in det if c.clase == k])
            for k in clases
        },
        "seguimiento": {**idf1(ref, det), **clear_mot(ref, det)},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("secuencia")
    parser.add_argument("--corrida", default=None, help="Carpeta con tracks.csv y resumen.json")
    parser.add_argument("--xml", default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument("--salida", default=None, help="Ruta del metricas.json")
    args = parser.parse_args(argv)
    corrida = Path(args.corrida or RAIZ / "salidas" / args.secuencia)
    ruta_xml = Path(args.xml or RAIZ / "datos" / "ua-detrac" / args.secuencia / f"{args.secuencia}.xml")
    ruta_cfg = Path(args.config or RAIZ / "configs" / f"{args.secuencia}.yaml")
    ruta_salida = Path(args.salida or corrida / "metricas.json")

    cfg = cargar_configuracion(str(ruta_cfg))
    ref, ignoradas = leer_xml(ruta_xml)
    det = leer_tracks(corrida / "tracks.csv")
    with open(corrida / "resumen.json", encoding="utf-8") as f:
        resumen = json.load(f)["ejecucion"]
    cuadros_corridos = resumen["n_cuadros_procesados"]
    ref = [c for c in ref if c.cuadro < cuadros_corridos]

    n_ref_bruto, n_det_bruto = len(ref), len(det)
    ref = [c for c in ref if not en_ignorada(c, ignoradas)]
    det = [c for c in det if not en_ignorada(c, ignoradas)]
    ref_roi = [c for c in ref if punto_en_poligono(punto_calzada(c), cfg.region_interes)]

    documento = {
        "secuencia": args.secuencia,
        "corrida": str(corrida.relative_to(RAIZ)) if corrida.is_relative_to(RAIZ) else str(corrida),
        "xml": str(ruta_xml.relative_to(RAIZ)) if ruta_xml.is_relative_to(RAIZ) else str(ruta_xml),
        "configuracion": str(ruta_cfg.relative_to(RAIZ)) if ruta_cfg.is_relative_to(RAIZ) else str(ruta_cfg),
        "version_modelo": resumen["version_modelo"],
        "n_cuadros": cuadros_corridos,
        "fps_video": resumen["fps_video"],
        "fps_procesamiento": round(resumen["fps_procesamiento"], 2),
        "fps_por_etapa": {k: round(v, 1) for k, v in resumen["fps_por_etapa"].items()},
        "eventos_por_regla": resumen["n_eventos"],
        "iou_min": IOU_MIN,
        "mapeo_clases": MAPEO_CLASES,
        "regiones_ignoradas": {
            "n": len(ignoradas),
            "cajas_referencia_descartadas": n_ref_bruto - len(ref),
            "cajas_detectadas_descartadas": n_det_bruto - len(det),
        },
        "cuadro_completo": medir(ref, det),
        "region_interes": {
            "descripcion": "referencia restringida a cajas cuyo punto de calzada cae en region_interes del YAML",
            "n_referencia_fuera_de_region": len(ref) - len(ref_roi),
            **medir(ref_roi, det),
        },
    }
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(documento, f, ensure_ascii=False, indent=2)
        f.write("\n")

    for vista in ("cuadro_completo", "region_interes"):
        m = documento[vista]
        print(
            f"{vista}: mAP@0.5={m['map50_sin_clase']['ap']}  IDF1={m['seguimiento']['idf1']}  "
            f"MOTA={m['seguimiento']['mota']}  cambios_id={m['seguimiento']['cambios_id']}  "
            f"ref={m['map50_sin_clase']['n_referencia']} det={m['map50_sin_clase']['n_detecciones']}"
        )
    print(f"Escrito {ruta_salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
