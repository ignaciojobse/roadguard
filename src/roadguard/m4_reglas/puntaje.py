"""M4 - RF10/RF11: puntaje temporal de riesgo.

Sumar 40 puntos por cercania activa, 35 por zigzag reciente y 50 por corte
reciente; limitar el total a 100 y retirar cada aporte despues de 5 s.
Bandas de color (RF11): verde 0-29, amarillo 30-59, rojo 60-100.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from roadguard.tipos import Evento, NivelRiesgo, PuntajeRiesgo, Umbrales


class AcumuladorPuntaje:
    """Aportes con vigencia por vehiculo (RF10).

    Cada evento aporta su `aporte_puntaje` desde el instante en que se
    registra y durante `vigencia_aporte` segundos. El total se limita a
    `puntaje_maximo`.
    """

    def __init__(self, umbrales: Umbrales) -> None:
        self.umbrales = umbrales
        self._aportes: dict[int, list[tuple[float, int]]] = defaultdict(list)

    def registrar(self, evento: Evento, t: Optional[float] = None) -> None:
        """Agrega el aporte del evento al vehiculo correspondiente.

        `t` es el instante de registro; por defecto, el fin del evento.
        """
        t_registro = evento.t_fin if t is None else t
        self._aportes[evento.id_vehiculo].append((t_registro, evento.aporte_puntaje))

    def puntaje_en(self, id_vehiculo: int, t: float) -> PuntajeRiesgo:
        """Puntaje vigente en t, con aportes caducados ya retirados."""
        u = self.umbrales
        aportes = self._aportes.get(id_vehiculo, [])
        vigentes = [(tr, a) for tr, a in aportes if t - tr < u.vigencia_aporte]
        if aportes and len(vigentes) != len(aportes):
            self._aportes[id_vehiculo] = vigentes
        total = sum(a for tr, a in vigentes if tr <= t)
        total = min(total, u.puntaje_maximo)
        return PuntajeRiesgo(
            id_vehiculo=id_vehiculo,
            t=t,
            puntaje=total,
            nivel=nivel_desde_puntaje(total, u),
        )


def nivel_desde_puntaje(puntaje: int, umbrales: Umbrales) -> NivelRiesgo:
    """RF11: verde 0-29, amarillo 30-59, rojo 60-100."""
    if puntaje <= umbrales.banda_verde_max:
        return NivelRiesgo.VERDE
    if puntaje <= umbrales.banda_amarillo_max:
        return NivelRiesgo.AMARILLO
    return NivelRiesgo.ROJO
