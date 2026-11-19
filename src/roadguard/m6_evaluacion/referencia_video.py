"""Referencia de eventos desde la anotacion de UA-DETRAC (F1 de reglas en video).

UA-DETRAC no trae eventos, pero si cajas anotadas a mano con identidad
persistente. Llevadas al plano del camino con la misma homografia y los
mismos carriles del YAML, esas cajas dan trayectorias de referencia sobre
las que se calculan los eventos con `eventos_referencia`, igual que con
NGSIM. Asi el F1 de reglas se puede medir sobre el video real, de punta a
punta: detector, seguidor, geometria y reglas.

La referencia mira la trayectoria completa (no es causal): la velocidad es
la pendiente de un ajuste lineal centrado de `ventana` segundos. Lo que esta
referencia no puede juzgar es la calibracion, porque comparte la homografia
con el sistema.

Para comparar, cada ID del sistema se traduce al ID anotado con el que mas
cuadros comparte (IoU >= 0,5); un ID sin pareja queda como esta y sus
eventos cuentan como falsos positivos.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

from roadguard.m3_geometria.carriles import asignar_carril
from roadguard.m3_geometria.homografia import ProyectorCamino
from roadguard.m3_geometria.relaciones import calcular_relaciones
from roadguard.m6_evaluacion.ngsim import CuadroReferencia
from roadguard.poligonos import punto_en_poligono
from roadguard.tipos import Carril, EstadoCinematico, Regla


@dataclass(frozen=True)
class Caja:
    cuadro: int
    ident: int
    xyxy: tuple[float, float, float, float]


@dataclass(frozen=True)
class EventoLeido:
    id_vehiculo: int
    regla: Regla
    t_inicio: float
    t_fin: float


def punto_calzada(c: Caja) -> tuple[float, float]:
    x1, _, x2, y2 = c.xyxy
    return ((x1 + x2) / 2, y2)


def _ajuste(ts: np.ndarray, vs: np.ndarray, t: float) -> tuple[float, float]:
    """(valor en t, pendiente) por minimos cuadrados."""
    mt = ts.mean()
    stt = ((ts - mt) ** 2).sum()
    if stt <= 0:
        return float(vs.mean()), 0.0
    pendiente = float(((ts - mt) * (vs - vs.mean())).sum() / stt)
    return float(vs.mean() + pendiente * (t - mt)), pendiente


def cuadros_desde_cajas(
    cajas: Iterable[Caja],
    fps: float,
    proyector: ProyectorCamino,
    carriles: list[Carril],
    region: Optional[list[tuple[float, float]]] = None,
    ventana: float = 1.0,
    min_muestras: int = 5,
) -> list[CuadroReferencia]:
    """Cajas anotadas -> estados y relaciones por cuadro, en metros.

    Solo entran las cajas cuyo punto de calzada cae en `region` (si se da).
    Sin calibracion no hay metros: devuelve una lista vacia.
    """
    if not proyector.disponible:
        return []
    por_id: dict[int, list[tuple[int, float, float, Optional[int], float]]] = defaultdict(list)
    for c in cajas:
        p = punto_calzada(c)
        if region is not None and not punto_en_poligono(p, region):
            continue
        xy = proyector.proyectar(p)
        if xy is None:
            continue
        carril, confianza = asignar_carril(p, carriles)
        por_id[c.ident].append((c.cuadro, xy[0], xy[1], carril, confianza))

    medio = ventana / 2
    estados_por_cuadro: dict[int, list[EstadoCinematico]] = defaultdict(list)
    for ident, filas in por_id.items():
        filas.sort()
        ts = np.array([f[0] / fps for f in filas])
        xs = np.array([f[1] for f in filas])
        ys = np.array([f[2] for f in filas])
        for k, (cuadro, _, _, carril, confianza) in enumerate(filas):
            t = ts[k]
            sel = (ts >= t - medio - 1e-9) & (ts <= t + medio + 1e-9)
            if sel.sum() < min_muestras:
                continue
            x, v = _ajuste(ts[sel], xs[sel], t)
            y, _ = _ajuste(ts[sel], ys[sel], t)
            estados_por_cuadro[cuadro].append(
                EstadoCinematico(ident, cuadro, t, x, y, v, carril, confianza, True)
            )
    return [
        CuadroReferencia(c, c / fps, estados, calcular_relaciones(estados, c, c / fps))
        for c, estados in sorted(estados_por_cuadro.items())
    ]


def asignar_ids(
    detectadas: Iterable[Caja], referencia: Iterable[Caja], iou_min: float = 0.5
) -> dict[int, int]:
    """ID del sistema -> ID anotado con el que mas cuadros comparte."""
    ref_por_cuadro: dict[int, list[Caja]] = defaultdict(list)
    for r in referencia:
        ref_por_cuadro[r.cuadro].append(r)
    votos: dict[int, Counter] = defaultdict(Counter)
    for d in detectadas:
        mejor, mejor_iou = None, iou_min
        for r in ref_por_cuadro.get(d.cuadro, []):
            iou = _iou(d.xyxy, r.xyxy)
            if iou >= mejor_iou:
                mejor, mejor_iou = r.ident, iou
        if mejor is not None:
            votos[d.ident][mejor] += 1
    return {ident: c.most_common(1)[0][0] for ident, c in votos.items()}


def _iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def leer_eventos_csv(ruta: str | Path) -> list[EventoLeido]:
    with open(ruta, encoding="utf-8", newline="") as f:
        return [
            EventoLeido(
                int(fila["id_vehiculo"]),
                Regla(fila["regla"]),
                float(fila["t_inicio"]),
                float(fila["t_fin"]),
            )
            for fila in csv.DictReader(f)
        ]


def traducir(eventos: Iterable[EventoLeido], mapa: dict[int, int]) -> list[EventoLeido]:
    """Eventos del sistema con el ID anotado; los IDs sin pareja quedan negativos."""
    return [
        EventoLeido(mapa.get(e.id_vehiculo, -e.id_vehiculo - 1), e.regla, e.t_inicio, e.t_fin)
        for e in eventos
    ]
