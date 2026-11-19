"""Detector RF8 de zigzag, procesado cuadro a cuadro.

Consume los ``CambioCarril`` que M3 ya confirmo con permanencia estable, asi
que los cruces breves y las oscilaciones sobre la linea nunca llegan aqui
(Paso 4). La ventana se mide sobre ``t_cruce``, que es cuando ocurrio la
maniobra; la confirmacion llega mas tarde y el detector solo reacciona cuando
la recibe (causalidad, RF5).

Una racha es una sucesion de cambios cuyas ventanas se solapan. Se emite un
solo evento por racha, en el instante en que se completa el minimo de cambios;
los cambios siguientes que prolongan la misma racha se absorben sin repetir el
evento. La racha termina cuando pasa mas de ``zigzag_ventana`` desde el ultimo
cruce.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Optional

from roadguard.tipos import CambioCarril, Evento, Regla, Umbrales

_EPS = 1e-9


@dataclass
class _Racha:
    cruces: list[CambioCarril] = field(default_factory=list)
    emitida: bool = False


class DetectorZigzag:
    """Detector RF8 streaming con un historial acotado por vehiculo.

    Los cruces confirmados se conservan hasta finalizar la sesión: su
    pertinencia depende de ``t_cruce`` y no del reloj de confirmación, pues
    las latencias de confirmación pueden ser distintas. Por vehículo solo se
    conserva la racha vigente y los cruces dentro de la ventana.
    """

    def __init__(self, umbrales: Optional[Umbrales] = None) -> None:
        self.umbrales = umbrales if umbrales is not None else Umbrales()
        u = self.umbrales
        if (
            isinstance(u.zigzag_cambios_min, bool)
            or not isinstance(u.zigzag_cambios_min, int)
            or u.zigzag_cambios_min < 1
        ):
            raise ValueError("zigzag_cambios_min debe ser entero >= 1")
        if not _finito(u.zigzag_ventana) or u.zigzag_ventana <= 0:
            raise ValueError("zigzag_ventana debe ser finito positivo")
        if (
            isinstance(u.aporte_zigzag, bool)
            or not isinstance(u.aporte_zigzag, int)
            or u.aporte_zigzag < 0
        ):
            raise ValueError("aporte_zigzag debe ser entero no negativo")
        self._rachas: dict[int, _Racha] = {}
        self._ultimo_t: Optional[float] = None
        self._finalizado = False

    def actualizar(self, t: float, cambios: Iterable[CambioCarril]) -> list[Evento]:
        """Incorpora los cambios confirmados en el instante ``t``.

        Devuelve los eventos de zigzag que nacen en este cuadro, uno por
        racha. Los cambios deben haberse confirmado en ``t`` o antes; nunca
        se usan cambios futuros.
        """
        if self._finalizado:
            raise ValueError("El detector ya fue finalizado")
        if not _finito(t) or t < 0:
            raise ValueError("t debe ser finito no negativo")
        if self._ultimo_t is not None and t <= self._ultimo_t:
            raise ValueError("t debe ser estrictamente creciente")
        lista = sorted(cambios, key=lambda c: (c.t_cruce, c.t_confirmacion))
        for c in lista:
            if c.t_confirmacion > t + _EPS:
                raise ValueError("CambioCarril confirmado en el futuro")
            if c.t_cruce > c.t_confirmacion + _EPS:
                raise ValueError("t_cruce no puede superar t_confirmacion")

        ventana = self.umbrales.zigzag_ventana
        eventos: list[Evento] = []
        for c in lista:
            racha = self._rachas.get(c.id_vehiculo)
            if racha is not None and racha.cruces and (
                c.t_cruce - racha.cruces[-1].t_cruce > ventana + _EPS
            ):
                racha = None
            if racha is None:
                racha = _Racha()
                self._rachas[c.id_vehiculo] = racha
            racha.cruces.append(c)
            racha.cruces = [
                x for x in racha.cruces if c.t_cruce - x.t_cruce <= ventana + _EPS
            ]
            if not racha.emitida and len(racha.cruces) >= self.umbrales.zigzag_cambios_min:
                racha.emitida = True
                eventos.append(self._evento(c.id_vehiculo, racha.cruces))
            # Antes de emitir basta el máximo requerido; después solo hace
            # falta el último cruce para detectar el fin/continuación de racha.
            limite = 1 if racha.emitida else self.umbrales.zigzag_cambios_min
            racha.cruces = racha.cruces[-limite:]
        self._ultimo_t = float(t)
        return eventos

    def finalizar(self) -> list[Evento]:
        """Termina la sesion. No quedan eventos pendientes: cada racha se
        emite al completarse, asi que siempre devuelve una lista vacia."""
        self._rachas.clear()
        self._finalizado = True
        return []

    def _evento(self, ident: int, cruces: list[CambioCarril]) -> Evento:
        primero, ultimo = cruces[0], cruces[-1]
        return Evento(
            id_vehiculo=ident,
            regla=Regla.ZIGZAG,
            t_inicio=primero.t_cruce,
            t_fin=ultimo.t_confirmacion,
            variables={
                "n_cambios": float(len(cruces)),
                "t_primer_cruce": primero.t_cruce,
                "t_ultimo_cruce": ultimo.t_cruce,
                "duracion_cruces": ultimo.t_cruce - primero.t_cruce,
                "carril_inicial": float(primero.carril_origen),
                "carril_final": float(ultimo.carril_destino),
                "t_confirmacion": ultimo.t_confirmacion,
            },
            umbrales={
                "zigzag_cambios_min": float(self.umbrales.zigzag_cambios_min),
                "zigzag_ventana": float(self.umbrales.zigzag_ventana),
            },
            aporte_puntaje=self.umbrales.aporte_zigzag,
        )


def _finito(x: object) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
