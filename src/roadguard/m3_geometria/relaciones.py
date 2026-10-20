"""M3  Predecesor/seguidor, distancia, THW y TTC (RF6)."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Optional

from roadguard.tipos import EstadoCinematico, Relacion


def calcular_relaciones(
    estados: list[EstadoCinematico], cuadro: int, t: float
) -> list[Relacion]:
    """Determina predecesor y seguidor por carril y calcula metricas (RF6).

    THW = distancia / velocidad del seguidor.
    TTC se calcula SOLO con tasa de cierre positiva; si no, queda en None.
    Sin calibracion, distancia, THW y TTC quedan en None (Paso 5).

    Devuelve una Relacion por estado, con el vehiculo como seguidor. El
    predecesor es el vehiculo inmediatamente delante (mayor `x_camino`) en
    el mismo carril. La distancia se mide entre puntos de contacto con la
    calzada, sin descontar el largo del vehiculo. Sin carril o sin posicion
    no hay predecesor (Paso 3).
    """
    por_carril: dict[int, list[EstadoCinematico]] = defaultdict(list)
    for e in estados:
        if e.carril is not None and e.calibrado and e.x_camino is not None:
            por_carril[e.carril].append(e)

    predecesor_de: dict[int, EstadoCinematico] = {}
    for grupo in por_carril.values():
        grupo.sort(key=lambda e: e.x_camino)
        for detras, delante in zip(grupo, grupo[1:]):
            predecesor_de[detras.id_vehiculo] = delante

    relaciones: list[Relacion] = []
    for e in estados:
        pred = predecesor_de.get(e.id_vehiculo)
        distancia = thw = ttc = None
        if pred is not None:
            distancia = pred.x_camino - e.x_camino
            thw = calcular_thw(distancia, e.velocidad)
            tasa_cierre = None
            if e.velocidad is not None and pred.velocidad is not None:
                tasa_cierre = e.velocidad - pred.velocidad
            ttc = calcular_ttc(distancia, tasa_cierre)
        relaciones.append(
            Relacion(
                id_seguidor=e.id_vehiculo,
                id_predecesor=None if pred is None else pred.id_vehiculo,
                cuadro=cuadro,
                t=t,
                carril=e.carril,
                distancia=distancia,
                thw=thw,
                ttc=ttc,
            )
        )
    return relaciones


def _valido(valor: Optional[float]) -> bool:
    return valor is not None and math.isfinite(valor)


def calcular_thw(distancia: Optional[float], velocidad: Optional[float]) -> Optional[float]:
    """THW = distancia / velocidad del seguidor (M3). None si es invalido."""
    if not (_valido(distancia) and _valido(velocidad)):
        return None
    if distancia < 0 or velocidad <= 0:
        return None
    return distancia / velocidad


def calcular_ttc(
    distancia: Optional[float], tasa_cierre: Optional[float]
) -> Optional[float]:
    """TTC solo con tasa de cierre positiva (M3). None en caso contrario."""
    if not (_valido(distancia) and _valido(tasa_cierre)):
        return None
    if distancia < 0 or tasa_cierre <= 0:
        return None
    return distancia / tasa_cierre
