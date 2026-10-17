"""M6 - mAP@0.5 sobre secuencias seleccionadas de UA-DETRAC.

Criterio de aceptacion (seccion 2.5): mAP@0.5 >= 0,60.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from roadguard.m6_evaluacion.uadetrac import (
    Objeto,
    en_region_ignorada,
    iou,
    leer_predicciones,
    leer_xml,
)
from roadguard.tipos import Caja

MAP_OBJETIVO = 0.60
AGNOSTICA = "vehiculo"


def evaluar_deteccion(ruta_anotaciones: str, ruta_predicciones: str) -> dict[str, float]:
    """Devuelve mAP@0.5 y metricas por clase."""
    seq = leer_xml(ruta_anotaciones)
    return calcular_map(seq.objetos, leer_predicciones(ruta_predicciones), seq.ignoradas)


def calcular_map(
    verdad: dict[int, list[Objeto]],
    predicciones: dict[int, list[Objeto]],
    ignoradas: Optional[list[Caja]] = None,
    umbral_iou: float = 0.5,
) -> dict[str, float]:
    """AP por clase (interpolacion de todos los puntos, como VOC 2010+) y
    mAP sobre las clases con anotaciones. Tambien `ap_vehiculo`, el AP
    agnostico de clase. Las predicciones en regiones ignoradas se descartan.
    """
    ignoradas = ignoradas or []
    preds = {
        c: [p for p in ps if not en_region_ignorada(p.caja, ignoradas)]
        for c, ps in predicciones.items()
    }
    clases = sorted({o.clase for os_ in verdad.values() for o in os_})
    salida: dict[str, float] = {}
    aps = []
    for clase in clases:
        ap, n_gt = _ap(verdad, preds, umbral_iou, clase)
        salida[f"ap_{clase}"] = ap
        salida[f"n_verdad_{clase}"] = float(n_gt)
        aps.append(ap)
    salida["map_50"] = sum(aps) / len(aps) if aps else 0.0
    salida[f"ap_{AGNOSTICA}"], salida[f"n_verdad_{AGNOSTICA}"] = _ap(verdad, preds, umbral_iou, None)
    salida["cumple_map_060"] = float(salida["map_50"] >= MAP_OBJETIVO)
    return salida


def _ap(verdad, preds, umbral_iou: float, clase: Optional[str]) -> tuple[float, int]:
    gt = defaultdict(list)
    for c, os_ in verdad.items():
        gt[c] = [o for o in os_ if clase is None or o.clase == clase]
    n_gt = sum(len(v) for v in gt.values())
    candidatos = [
        p for ps in preds.values() for p in ps if clase is None or p.clase == clase
    ]
    candidatos.sort(key=lambda p: -p.confianza)
    usados: dict[int, set[int]] = defaultdict(set)
    vp, fp = [], []
    for p in candidatos:
        mejor, idx = 0.0, -1
        for k, g in enumerate(gt.get(p.cuadro, [])):
            v = iou(p.caja, g.caja)
            if v > mejor:
                mejor, idx = v, k
        if mejor >= umbral_iou and idx not in usados[p.cuadro]:
            usados[p.cuadro].add(idx)
            vp.append(1)
            fp.append(0)
        else:
            vp.append(0)
            fp.append(1)
    if n_gt == 0:
        return 0.0, 0
    precision, recobrado = [], []
    acum_vp = acum_fp = 0
    for a, b in zip(vp, fp):
        acum_vp += a
        acum_fp += b
        precision.append(acum_vp / (acum_vp + acum_fp))
        recobrado.append(acum_vp / n_gt)
    # envolvente monotona y area bajo la curva P-R
    mrec = [0.0] + recobrado + [1.0]
    mpre = [0.0] + precision + [0.0]
    for i in range(len(mpre) - 2, -1, -1):
        mpre[i] = max(mpre[i], mpre[i + 1])
    ap = sum((mrec[i + 1] - mrec[i]) * mpre[i + 1] for i in range(len(mrec) - 1))
    return ap, n_gt
