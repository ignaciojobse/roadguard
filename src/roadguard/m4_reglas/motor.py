"""Fachada del motor de reglas (M4): RF7 a RF11 en una sola llamada por cuadro.

Compone ``DetectorCercania``, ``DetectorZigzag``, ``DetectorCorte`` y
``CalculadorPuntaje``. Recibe por instante lo que M3 produce (estados,
relaciones y cambios de carril confirmados) y devuelve los eventos que nacen
en ese cuadro mas el puntaje de cada vehiculo presente.

Los eventos de cercania se entregan una sola vez, al cerrarse el tramo (igual
que ``ResultadoCercania.cerrados``); los de zigzag y corte, al nacer. Para el
puntaje la cercania cuenta mientras esta activa, aunque su evento aun no se
haya cerrado. ``finalizar`` entrega los tramos de cercania que seguian
abiertos al terminar el video.
"""

from __future__ import annotations

from typing import Iterable, Optional

from roadguard.m4_reglas.cercania import DetectorCercania
from roadguard.m4_reglas.corte import DetectorCorte
from roadguard.m4_reglas.puntaje import CalculadorPuntaje
from roadguard.m4_reglas.zigzag import DetectorZigzag
from roadguard.tipos import (
    CambioCarril,
    EstadoCinematico,
    Evento,
    PuntajeRiesgo,
    Relacion,
    Umbrales,
)


class MotorReglas:
    """Motor causal: en el cuadro ``t`` solo usa informacion hasta ``t``."""

    def __init__(self, umbrales: Optional[Umbrales] = None) -> None:
        self.umbrales = umbrales if umbrales is not None else Umbrales()
        self.cercania = DetectorCercania(self.umbrales)
        self.zigzag = DetectorZigzag(self.umbrales)
        self.corte = DetectorCorte(self.umbrales)
        self.puntaje = CalculadorPuntaje(self.umbrales)
        self.advertencias: tuple[str, ...] = ()
        self._ultimo_cuadro: Optional[int] = None

    def actualizar(
        self,
        t: float,
        estados: dict[int, EstadoCinematico],
        relaciones: list[Relacion],
        cambios: list[CambioCarril],
    ) -> tuple[list[Evento], dict[int, PuntajeRiesgo]]:
        """Procesa un cuadro y devuelve (eventos nuevos, puntaje por vehiculo).

        ``estados`` va indexado por ``id_vehiculo``; todos deben pertenecer al
        mismo cuadro, que es el que se pasa al detector de cercania. Si el
        cuadro llega sin vehiculos se asume el siguiente al ultimo visto.
        Las advertencias del cuadro (p. ej. sin calibracion) quedan en
        ``self.advertencias``.
        """
        cuadro = self._cuadro_de(estados.values())
        res = self.cercania.actualizar(cuadro, t, list(estados.values()), relaciones)
        nuevos: list[Evento] = list(res.cerrados)
        nuevos.extend(self.zigzag.actualizar(t, cambios))
        nuevos.extend(self.corte.actualizar(t, relaciones, cambios))
        puntajes = self.puntaje.actualizar(t, estados.keys(), res.activos, nuevos)
        self.advertencias = res.advertencias
        self._ultimo_cuadro = cuadro
        return nuevos, puntajes

    def finalizar(self) -> list[Evento]:
        """Cierra los detectores y devuelve los eventos pendientes."""
        pendientes = list(self.cercania.finalizar())
        pendientes.extend(self.zigzag.finalizar())
        pendientes.extend(self.corte.finalizar())
        return pendientes

    def _cuadro_de(self, estados: Iterable[EstadoCinematico]) -> int:
        cuadros = {e.cuadro for e in estados}
        if len(cuadros) > 1:
            raise ValueError("Todos los estados deben pertenecer al mismo cuadro")
        if cuadros:
            return cuadros.pop()
        return 0 if self._ultimo_cuadro is None else self._ultimo_cuadro + 1
