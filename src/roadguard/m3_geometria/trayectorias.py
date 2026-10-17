"""M3 - Historial causal, suavizado y velocidades (RF5)."""

from __future__ import annotations

import math
from collections import deque
from typing import Optional

from roadguard.m3_geometria.carriles import asignar_carril
from roadguard.m3_geometria.homografia import ProyectorCamino
from roadguard.tipos import Carril, EstadoCinematico, Track


class HistorialCausal:
    """Construye series temporales de posicion, velocidad y carril (RF5).

    Restriccion: en el cuadro t solo puede usarse informacion disponible
    hasta t (RF5, Paso 2). El suavizado debe ser causal.

    La velocidad y las metricas derivadas solo se calculan con historial
    suficiente; cualquier division invalida o ausencia de predecesor se
    representa como no disponible (Paso 3).

    Suavizado: ajuste lineal por minimos cuadrados sobre las muestras de los
    ultimos `ventana` segundos (ventana unilateral, solo pasado). La pendiente
    en x es la velocidad longitudinal y el valor del ajuste en `t` es la
    posicion suavizada. Se exigen `min_muestras` muestras que cubran al menos
    `min_duracion` segundos; si no, la velocidad es None.

    Identidad dudosa (riesgos 4.4): si entre dos observaciones consecutivas
    el desplazamiento implica una velocidad mayor a `velocidad_max`, se
    reinicia el historial de ese ID y se informa en `reinicios`.
    """

    def __init__(
        self,
        fps: float,
        proyector: Optional[ProyectorCamino] = None,
        carriles: Optional[list[Carril]] = None,
        ventana: float = 1.0,
        min_muestras: int = 3,
        min_duracion: float = 0.3,
        velocidad_max: float = 70.0,
    ) -> None:
        if fps <= 0:
            raise ValueError("fps debe ser positivo")
        self.fps = fps
        self.proyector = proyector
        self.carriles = carriles or []
        self.ventana = ventana
        self.min_muestras = min_muestras
        self.min_duracion = min_duracion
        self.velocidad_max = velocidad_max
        self._muestras: dict[int, deque[tuple[float, float, float]]] = {}
        self._t_ultimo: dict[int, float] = {}
        self.reinicios: list[int] = []

    def actualizar(self, track: Track) -> EstadoCinematico:
        """Incorpora un track y devuelve su estado cinematico en t."""
        carril, confianza = asignar_carril(track.punto_calzada_px, self.carriles)
        xy = None
        if self.proyector is not None:
            xy = self.proyector.proyectar(track.punto_calzada_px)
        return self.actualizar_camino(
            track.id_vehiculo, track.cuadro, track.t, xy, carril, confianza
        )

    def actualizar_camino(
        self,
        id_vehiculo: int,
        cuadro: int,
        t: float,
        xy: Optional[tuple[float, float]],
        carril: Optional[int],
        confianza_carril: float,
    ) -> EstadoCinematico:
        """Igual que `actualizar`, pero con la posicion ya en el plano del
        camino. Lo usan las trayectorias de referencia (highD/NGSIM)."""
        t_prev = self._t_ultimo.get(id_vehiculo)
        if t_prev is not None and t <= t_prev:
            raise ValueError(
                f"Orden temporal violado para ID {id_vehiculo}: t={t} <= {t_prev} (Paso 2)"
            )
        self._t_ultimo[id_vehiculo] = t

        if xy is None:
            return EstadoCinematico(
                id_vehiculo, cuadro, t, None, None, None, carril, confianza_carril, False
            )

        muestras = self._muestras.setdefault(id_vehiculo, deque())
        if muestras:
            t0, x0, y0 = muestras[-1]
            if math.dist((x0, y0), xy) / (t - t0) > self.velocidad_max:
                muestras.clear()
                self.reinicios.append(id_vehiculo)
        muestras.append((t, xy[0], xy[1]))
        while muestras and muestras[0][0] < t - self.ventana:
            muestras.popleft()

        x, y, velocidad = xy[0], xy[1], None
        if len(muestras) >= self.min_muestras and t - muestras[0][0] >= self.min_duracion:
            ajuste_x = _ajuste_lineal([(m[0], m[1]) for m in muestras], t)
            ajuste_y = _ajuste_lineal([(m[0], m[2]) for m in muestras], t)
            if ajuste_x is not None and ajuste_y is not None:
                x, velocidad = ajuste_x
                y = ajuste_y[0]
        return EstadoCinematico(
            id_vehiculo, cuadro, t, x, y, velocidad, carril, confianza_carril, True
        )

    def purgar(self, t: float, edad_max: Optional[float] = None) -> list[int]:
        """Elimina IDs no observados en `edad_max` s (por defecto 2 ventanas)."""
        edad = 2 * self.ventana if edad_max is None else edad_max
        viejos = [i for i, tu in self._t_ultimo.items() if t - tu > edad]
        for i in viejos:
            self.olvidar(i)
        return viejos

    def olvidar(self, id_vehiculo: int) -> None:
        self._muestras.pop(id_vehiculo, None)
        self._t_ultimo.pop(id_vehiculo, None)


def _ajuste_lineal(
    puntos: list[tuple[float, float]], t: float
) -> Optional[tuple[float, float]]:
    """Devuelve (valor en t, pendiente) del ajuste por minimos cuadrados."""
    n = len(puntos)
    mt = sum(p[0] for p in puntos) / n
    mv = sum(p[1] for p in puntos) / n
    stt = sum((p[0] - mt) ** 2 for p in puntos)
    if stt <= 0:
        return None  # division invalida: no disponible (Paso 3)
    pendiente = sum((p[0] - mt) * (p[1] - mv) for p in puntos) / stt
    return mv + pendiente * (t - mt), pendiente
