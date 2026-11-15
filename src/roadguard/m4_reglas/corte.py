"""Detector RF9 de corte de carril, procesado cuadro a cuadro.

Tras un cambio de carril completo del vehiculo A (``CambioCarril`` de M3), se
observa durante ``corte_ventana_post_cambio`` segundos desde ``t_cruce`` al
nuevo seguidor B: el primer vehiculo que aparece detras de A en el carril de
destino. Si en esa ventana B queda con THW < ``corte_thw_max`` o
TTC < ``corte_ttc_max``, se emite un evento de corte para A con
``id_relacionado`` = B.

Causalidad: M3 confirma el cambio despues del cruce (permanencia estable),
asi que al recibirlo ya paso parte de la ventana. Para no perder esas
observaciones el detector conserva las relaciones de los ultimos
``corte_ventana_post_cambio`` segundos y las reexamina al confirmarse el
cambio. Solo se usa informacion ya observada; nunca cuadros futuros.

Sin calibracion THW y TTC llegan en None y la regla no evalua nada: se
suspende sin romper (Paso 5).
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Iterable, Optional

from roadguard.tipos import CambioCarril, Evento, Regla, Relacion, Umbrales

_EPS = 1e-9


@dataclass
class _Seguimiento:
    cambio: CambioCarril
    fin_ventana: float
    seguidor: Optional[int] = None


class DetectorCorte:
    """Detector RF9 streaming con memoria acotada a la ventana post cambio."""

    def __init__(self, umbrales: Optional[Umbrales] = None) -> None:
        self.umbrales = umbrales if umbrales is not None else Umbrales()
        u = self.umbrales
        for nombre in ("corte_ventana_post_cambio", "corte_thw_max", "corte_ttc_max"):
            x = getattr(u, nombre)
            if not _finito(x) or x <= 0:
                raise ValueError(f"Umbral RF9 invalido: {nombre}")
        if isinstance(u.aporte_corte, bool) or not isinstance(u.aporte_corte, int) or u.aporte_corte < 0:
            raise ValueError("aporte_corte debe ser entero no negativo")
        self._historial: deque[tuple[float, tuple[Relacion, ...]]] = deque()
        self._seguimientos: list[_Seguimiento] = []
        self._ultimo_t: Optional[float] = None
        self._finalizado = False

    def actualizar(
        self,
        t: float,
        relaciones: Iterable[Relacion],
        cambios: Iterable[CambioCarril],
    ) -> list[Evento]:
        """Procesa las relaciones del cuadro ``t`` y los cambios confirmados.

        Devuelve los eventos de corte que nacen en este cuadro: a lo mas uno
        por cambio de carril, emitido en la primera observacion que cumple la
        condicion. Un cambio sin seguidor o sin metricas no genera nada.
        """
        if self._finalizado:
            raise ValueError("El detector ya fue finalizado")
        if not _finito(t) or t < 0:
            raise ValueError("t debe ser finito no negativo")
        if self._ultimo_t is not None and t <= self._ultimo_t:
            raise ValueError("t debe ser estrictamente creciente")
        rels = tuple(relaciones)
        nuevos = list(cambios)
        for c in nuevos:
            if c.t_confirmacion > t + _EPS:
                raise ValueError("CambioCarril confirmado en el futuro")

        ventana = self.umbrales.corte_ventana_post_cambio
        self._historial.append((float(t), rels))
        while self._historial and t - self._historial[0][0] > ventana + _EPS:
            self._historial.popleft()

        eventos: list[Evento] = []
        recientes: list[_Seguimiento] = []
        for c in nuevos:
            seg = _Seguimiento(c, c.t_cruce + ventana)
            ev = None
            for t_obs, rels_obs in self._historial:
                if t_obs < c.t_cruce - _EPS:
                    continue
                ev = self._examinar(seg, t_obs, rels_obs)
                if ev is not None:
                    break
            if ev is not None:
                eventos.append(ev)
            elif t <= seg.fin_ventana + _EPS:
                recientes.append(seg)

        vigentes: list[_Seguimiento] = []
        for seg in self._seguimientos:
            if t > seg.fin_ventana + _EPS:
                continue
            ev = self._examinar(seg, float(t), rels)
            if ev is not None:
                eventos.append(ev)
            else:
                vigentes.append(seg)
        self._seguimientos = vigentes + recientes
        self._ultimo_t = float(t)
        return sorted(eventos, key=lambda e: (e.id_vehiculo, e.t_inicio))

    def finalizar(self) -> list[Evento]:
        """Termina la sesion. Los seguimientos abiertos sin condicion cumplida
        se descartan; no hay eventos pendientes que entregar."""
        self._seguimientos.clear()
        self._historial.clear()
        self._finalizado = True
        return []

    def _examinar(
        self, seg: _Seguimiento, t_obs: float, rels: tuple[Relacion, ...]
    ) -> Optional[Evento]:
        if t_obs > seg.fin_ventana + _EPS:
            return None
        c = seg.cambio
        for r in rels:
            if r.id_predecesor != c.id_vehiculo or r.carril != c.carril_destino:
                continue
            if seg.seguidor is None:
                seg.seguidor = r.id_seguidor
            if r.id_seguidor != seg.seguidor:
                continue
            thw = r.thw if _finito(r.thw) and r.thw >= 0 else None
            ttc = r.ttc if _finito(r.ttc) and r.ttc >= 0 else None
            thw_bajo = thw is not None and thw < self.umbrales.corte_thw_max
            ttc_bajo = ttc is not None and ttc < self.umbrales.corte_ttc_max
            if thw_bajo or ttc_bajo:
                return self._evento(seg, t_obs, r, thw, ttc)
        return None

    def _evento(
        self,
        seg: _Seguimiento,
        t_obs: float,
        r: Relacion,
        thw: Optional[float],
        ttc: Optional[float],
    ) -> Evento:
        c = seg.cambio
        return Evento(
            id_vehiculo=c.id_vehiculo,
            regla=Regla.CORTE,
            t_inicio=c.t_cruce,
            t_fin=t_obs,
            variables={
                "t_cruce": c.t_cruce,
                "t_confirmacion": c.t_confirmacion,
                "t_observacion": t_obs,
                "carril_origen": float(c.carril_origen),
                "carril_destino": float(c.carril_destino),
                "distancia": r.distancia,
                "thw": thw,
                "ttc": ttc,
            },
            umbrales={
                "corte_ventana_post_cambio": float(self.umbrales.corte_ventana_post_cambio),
                "corte_thw_max": float(self.umbrales.corte_thw_max),
                "corte_ttc_max": float(self.umbrales.corte_ttc_max),
            },
            aporte_puntaje=self.umbrales.aporte_corte,
            id_relacionado=seg.seguidor,
        )


def _finito(x: object) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
