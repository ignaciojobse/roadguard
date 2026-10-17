"""M6 - IDF1 e intercambios de ID.

Criterio de aceptacion (seccion 2.5): IDF1 >= 0,60 e informe separado de
cambios incorrectos de ID.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

import numpy as np
from scipy.optimize import linear_sum_assignment

from roadguard.m6_evaluacion.uadetrac import (
    Objeto,
    en_region_ignorada,
    iou,
    leer_predicciones,
    leer_xml,
)
from roadguard.tipos import Caja

IDF1_OBJETIVO = 0.60


def evaluar_seguimiento(ruta_anotaciones: str, ruta_tracks: str) -> dict[str, float]:
    """Devuelve IDF1 y el conteo de intercambios de ID."""
    seq = leer_xml(ruta_anotaciones)
    return calcular_metricas_seguimiento(seq.objetos, leer_predicciones(ruta_tracks), seq.ignoradas)


def calcular_metricas_seguimiento(
    verdad: dict[int, list[Objeto]],
    tracks: dict[int, list[Objeto]],
    ignoradas: Optional[list[Caja]] = None,
    umbral_iou: float = 0.5,
) -> dict[str, float]:
    """IDF1, IDP, IDR (Ristani et al., 2016), intercambios de ID y MOTA
    (CLEAR MOT). Los tracks en regiones ignoradas se descartan."""
    ignoradas = ignoradas or []
    tracks = {
        c: [t for t in ts if t.id is not None and not en_region_ignorada(t.caja, ignoradas)]
        for c, ts in tracks.items()
    }
    salida = _idf1(verdad, tracks, umbral_iou)
    salida.update(_clear_mot(verdad, tracks, umbral_iou))
    salida["cumple_idf1_060"] = float(salida["idf1"] >= IDF1_OBJETIVO)
    return salida


def _idf1(verdad, tracks, umbral_iou: float) -> dict[str, float]:
    n_gt = sum(len(v) for v in verdad.values())
    n_pr = sum(len(v) for v in tracks.values())
    coincidencias: dict[tuple[int, int], int] = defaultdict(int)
    for cuadro, gts in verdad.items():
        for g in gts:
            for p in tracks.get(cuadro, []):
                if iou(g.caja, p.caja) >= umbral_iou:
                    coincidencias[(g.id, p.id)] += 1
    ids_gt = sorted({g.id for gs in verdad.values() for g in gs})
    ids_pr = sorted({p.id for ps in tracks.values() for p in ps})
    idtp = 0
    if ids_gt and ids_pr:
        fila = {g: i for i, g in enumerate(ids_gt)}
        col = {p: j for j, p in enumerate(ids_pr)}
        m = np.zeros((len(ids_gt), len(ids_pr)))
        for (g, p), n in coincidencias.items():
            m[fila[g], col[p]] = n
        r, c = linear_sum_assignment(-m)
        idtp = int(m[r, c].sum())
    return {
        "idf1": 2 * idtp / (n_gt + n_pr) if n_gt + n_pr > 0 else 0.0,
        "idp": idtp / n_pr if n_pr else 0.0,
        "idr": idtp / n_gt if n_gt else 0.0,
        "idtp": float(idtp),
        "n_verdad": float(n_gt),
        "n_predicciones": float(n_pr),
    }


def _clear_mot(verdad, tracks, umbral_iou: float) -> dict[str, float]:
    ultimo: dict[int, int] = {}
    switches = vp = fp = fn = 0
    for cuadro in sorted(set(verdad) | set(tracks)):
        gts = verdad.get(cuadro, [])
        prs = tracks.get(cuadro, [])
        pares: dict[int, int] = {}
        # se conservan las correspondencias previas que siguen siendo validas
        tomados: set[int] = set()
        for i, g in enumerate(gts):
            previo = ultimo.get(g.id)
            for j, p in enumerate(prs):
                if p.id == previo and j not in tomados and iou(g.caja, p.caja) >= umbral_iou:
                    pares[i] = j
                    tomados.add(j)
                    break
        libres_g = [i for i in range(len(gts)) if i not in pares]
        libres_p = [j for j in range(len(prs)) if j not in tomados]
        if libres_g and libres_p:
            costo = np.array([[1 - iou(gts[i].caja, prs[j].caja) for j in libres_p] for i in libres_g])
            r, c = linear_sum_assignment(costo)
            for a, b in zip(r, c):
                if 1 - costo[a, b] >= umbral_iou:
                    pares[libres_g[a]] = libres_p[b]
        for i, j in pares.items():
            gid, pid = gts[i].id, prs[j].id
            if gid in ultimo and ultimo[gid] != pid:
                switches += 1
            ultimo[gid] = pid
        vp += len(pares)
        fn += len(gts) - len(pares)
        fp += len(prs) - len(pares)
    n_gt = sum(len(v) for v in verdad.values())
    return {
        "intercambios_id": float(switches),
        "mota": 1 - (fn + fp + switches) / n_gt if n_gt else 0.0,
        "vp_mot": float(vp),
        "fp_mot": float(fp),
        "fn_mot": float(fn),
    }
