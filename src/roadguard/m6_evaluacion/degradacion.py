"""M6 - Degradacion sintetica de trayectorias limpias (seccion 2.4).

Las trayectorias limpias de highD o NGSIM sirven como referencia; luego se
degradan para aproximar ruido, perdida de observaciones e intercambio de
ID, y se comparan los eventos resultantes.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import replace
from typing import Optional

from roadguard.m3_geometria.trayectorias import HistorialCausal
from roadguard.m6_evaluacion.datasets import por_cuadro
from roadguard.tipos import EstadoCinematico


class CarrilesLaterales:
    """Asignacion de carril sobre `y_camino`, para reasignar carriles desde
    posiciones ruidosas. Los centros se estiman de las trayectorias limpias
    y la confianza cae de 1 en el centro a 0 a media distancia del carril
    vecino, igual que en la asignacion por poligonos de M3."""

    def __init__(self, centros: dict[int, float]) -> None:
        self.centros = dict(sorted(centros.items(), key=lambda kv: kv[1]))
        valores = list(self.centros.values())
        claves = list(self.centros)
        self.semiancho: dict[int, float] = {}
        for i, c in enumerate(claves):
            vecinos = [abs(valores[j] - valores[i]) for j in (i - 1, i + 1) if 0 <= j < len(valores)]
            self.semiancho[c] = (min(vecinos) / 2.0) if vecinos else 1.85

    @classmethod
    def desde_estados(cls, estados: list[EstadoCinematico]) -> "CarrilesLaterales":
        sumas: dict[int, list[float]] = defaultdict(list)
        for e in estados:
            if e.carril is not None and e.y_camino is not None:
                sumas[e.carril].append(e.y_camino)
        return cls({c: sorted(v)[len(v) // 2] for c, v in sumas.items()})

    def asignar(self, y: float) -> tuple[Optional[int], float]:
        mejor, d_min = None, float("inf")
        for c, centro in self.centros.items():
            d = abs(y - centro)
            if d < d_min:
                mejor, d_min = c, d
        if mejor is None or d_min > 2 * self.semiancho[mejor]:
            return None, 0.0
        return mejor, max(0.0, 1.0 - d_min / self.semiancho[mejor])


def degradar(
    estados: list[EstadoCinematico],
    ruido_posicion: float,
    prob_perdida: float,
    prob_intercambio_id: float,
    semilla: int,
    carriles: Optional[CarrilesLaterales] = None,
    distancia_intercambio: float = 15.0,
) -> list[EstadoCinematico]:
    """Aplica ruido, perdida de observaciones e intercambio de ID.

    La semilla queda registrada para reproducibilidad (Paso 6).

    - Ruido: gaussiano de desviacion `ruido_posicion` (m) en x e y.
    - Perdida: cada observacion se descarta con probabilidad `prob_perdida`.
    - Intercambio de ID: en cada cuadro, con probabilidad
      `prob_intercambio_id`, dos vehiculos a menos de
      `distancia_intercambio` m intercambian sus etiquetas desde ese cuadro
      en adelante, como hace un seguidor real tras una oclusion.
    - Si se entregan `carriles`, el carril se reasigna desde la `y` ruidosa
      (con su confianza); si no, se conserva el del dataset.

    La velocidad de salida queda en None: debe reestimarse de forma causal
    con `reestimar_cinematica`, igual que en el pipeline de video.
    """
    rng = random.Random(semilla)
    etiqueta: dict[int, int] = {}
    salida: list[EstadoCinematico] = []
    for _, _, grupo in por_cuadro(estados):
        for e in grupo:
            etiqueta.setdefault(e.id_vehiculo, e.id_vehiculo)
        if len(grupo) >= 2 and rng.random() < prob_intercambio_id:
            a = rng.choice(grupo)
            cercanos = [
                b for b in grupo
                if b.id_vehiculo != a.id_vehiculo
                and a.x_camino is not None and b.x_camino is not None
                and abs(a.x_camino - b.x_camino) <= distancia_intercambio
            ]
            if cercanos:
                b = rng.choice(cercanos)
                etiqueta[a.id_vehiculo], etiqueta[b.id_vehiculo] = (
                    etiqueta[b.id_vehiculo],
                    etiqueta[a.id_vehiculo],
                )
        for e in grupo:
            if rng.random() < prob_perdida:
                continue
            x, y = e.x_camino, e.y_camino
            if x is not None:
                x += rng.gauss(0.0, ruido_posicion)
            if y is not None:
                y += rng.gauss(0.0, ruido_posicion)
            carril, confianza = e.carril, e.confianza_carril
            if carriles is not None and y is not None:
                carril, confianza = carriles.asignar(y)
            salida.append(
                replace(
                    e,
                    id_vehiculo=etiqueta[e.id_vehiculo],
                    x_camino=x,
                    y_camino=y,
                    velocidad=None,
                    carril=carril,
                    confianza_carril=confianza,
                )
            )
    return salida


def reestimar_cinematica(
    estados: list[EstadoCinematico], fps: float, **opciones_historial
) -> list[EstadoCinematico]:
    """Recalcula posicion suavizada y velocidad con el HistorialCausal de M3."""
    historial = HistorialCausal(fps, **opciones_historial)
    salida = []
    for _, t, grupo in por_cuadro(estados):
        for e in grupo:
            xy = None if e.x_camino is None or e.y_camino is None else (e.x_camino, e.y_camino)
            salida.append(
                historial.actualizar_camino(
                    e.id_vehiculo, e.cuadro, t, xy, e.carril, e.confianza_carril
                )
            )
        historial.purgar(t)
    return salida
