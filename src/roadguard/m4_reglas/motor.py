"""M4 - Orquestacion por cuadro de las reglas RF7-RF9 y el puntaje RF10.

El mismo motor lo usan el pipeline de video (T8) y la evaluacion sobre
trayectorias de referencia (T9), para que las alertas comparadas provengan
exactamente de las mismas reglas.
"""

from __future__ import annotations

from typing import Iterable

from roadguard.m4_reglas.cercania import ReglaCercania
from roadguard.m4_reglas.corte import ReglaCorte
from roadguard.m4_reglas.puntaje import AcumuladorPuntaje
from roadguard.m4_reglas.zigzag import ReglaZigzag
from roadguard.tipos import (
    CambioCarril,
    EstadoCinematico,
    Evento,
    PuntajeRiesgo,
    Relacion,
    Umbrales,
)


class MotorReglas:
    """Evalua las tres reglas en orden causal y acumula el puntaje."""

    def __init__(self, umbrales: Umbrales) -> None:
        self.umbrales = umbrales
        self.cercania = ReglaCercania(umbrales)
        self.zigzag = ReglaZigzag(umbrales)
        self.corte = ReglaCorte(umbrales)
        self.acumulador = AcumuladorPuntaje(umbrales)

    def procesar_cuadro(
        self,
        t: float,
        estados: list[EstadoCinematico],
        relaciones: list[Relacion],
        cambios: list[CambioCarril],
    ) -> list[Evento]:
        """Evalua las reglas con la informacion disponible hasta `t`.

        Los cambios se registran antes que las relaciones para que la ventana
        de corte quede abierta al evaluar las relaciones del mismo cuadro.
        """
        velocidades = {e.id_vehiculo: e.velocidad for e in estados}
        eventos: list[Evento] = []
        for cambio in cambios:
            eventos.append(self.zigzag.evaluar(cambio, t))
            eventos.append(self.corte.registrar_cambio(cambio))
        for relacion in relaciones:
            velocidad = velocidades.get(relacion.id_seguidor)
            eventos.append(self.cercania.evaluar(relacion, velocidad, t))
            eventos.append(self.corte.evaluar(relacion, t, velocidad))
        emitidos = [e for e in eventos if e is not None]
        for evento in emitidos:
            self.acumulador.registrar(evento, t)
        return emitidos

    def puntajes(self, ids: Iterable[int], t: float) -> dict[int, PuntajeRiesgo]:
        return {i: self.acumulador.puntaje_en(i, t) for i in ids}

    def olvidar(self, id_vehiculo: int) -> None:
        """Reinicia el estado de las reglas para una identidad dudosa (4.4)."""
        self.cercania.olvidar(id_vehiculo)
        self.zigzag.olvidar(id_vehiculo)
        self.corte.olvidar(id_vehiculo)
