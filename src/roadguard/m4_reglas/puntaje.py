"""Puntaje temporal de riesgo (RF10) y bandas de color (RF11).

Por vehiculo se suman aportes: ``aporte_cercania`` mientras la cercania esta
activa, y el aporte de cada evento de zigzag o corte reciente. Cada aporte
caduca ``vigencia_aporte`` segundos despues de su ultima observacion: para la
cercania, el ultimo cuadro en que estuvo activa; para zigzag y corte, el
instante en que el evento llego al calculador. La suma se trunca en
``puntaje_maximo`` y el nivel sale de las bandas de RF11.

El aporte de cada evento se toma del propio ``Evento`` (``aporte_puntaje``),
asi el puntaje es trazable al evento que lo produjo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Hashable, Iterable, Optional

from roadguard.tipos import Evento, NivelRiesgo, PuntajeRiesgo, Regla, Umbrales

_EPS = 1e-9


@dataclass
class _Aporte:
    regla: Regla
    valor: int
    vence: float


def nivel_de(puntaje: int, umbrales: Umbrales) -> NivelRiesgo:
    """Banda RF11 de un puntaje: verde, amarillo o rojo."""
    if puntaje <= umbrales.banda_verde_max:
        return NivelRiesgo.VERDE
    if puntaje <= umbrales.banda_amarillo_max:
        return NivelRiesgo.AMARILLO
    return NivelRiesgo.ROJO


class CalculadorPuntaje:
    """Acumulador causal de aportes con caducidad por vehiculo."""

    def __init__(self, umbrales: Optional[Umbrales] = None) -> None:
        self.umbrales = umbrales if umbrales is not None else Umbrales()
        u = self.umbrales
        for nombre in ("puntaje_maximo", "banda_verde_max", "banda_amarillo_max"):
            x = getattr(u, nombre)
            if isinstance(x, bool) or not isinstance(x, int) or x < 0:
                raise ValueError(f"Umbral RF10/RF11 invalido: {nombre}")
        if u.puntaje_maximo <= 0:
            raise ValueError("puntaje_maximo debe ser positivo")
        if not (u.banda_verde_max < u.banda_amarillo_max < u.puntaje_maximo):
            raise ValueError("Las bandas deben cumplir verde < amarillo < puntaje_maximo")
        if not _finito(u.vigencia_aporte) or u.vigencia_aporte <= 0:
            raise ValueError("vigencia_aporte debe ser finito positivo")
        self._aportes: dict[int, dict[Hashable, _Aporte]] = {}
        self._ultimo_t: Optional[float] = None

    def actualizar(
        self,
        t: float,
        ids_vehiculos: Iterable[int],
        cercania_activa: Iterable[Evento] = (),
        eventos_nuevos: Iterable[Evento] = (),
    ) -> dict[int, PuntajeRiesgo]:
        """Incorpora lo observado en ``t`` y devuelve el puntaje de cada
        vehiculo presente en ``ids_vehiculos``.

        ``cercania_activa`` son los eventos RF7 vivos en este cuadro (uno por
        vehiculo); ``eventos_nuevos`` los eventos que nacen en este cuadro.
        Repetir el mismo evento no suma dos veces: refresca su vigencia.
        """
        if not _finito(t) or t < 0:
            raise ValueError("t debe ser finito no negativo")
        if self._ultimo_t is not None and t < self._ultimo_t:
            raise ValueError("t no puede retroceder")
        vence = float(t) + self.umbrales.vigencia_aporte
        for ev in cercania_activa:
            self._registrar(ev, Regla.CERCANIA, vence)
        for ev in eventos_nuevos:
            clave: Hashable = (
                Regla.CERCANIA
                if ev.regla is Regla.CERCANIA
                else (ev.regla, ev.t_inicio, ev.id_relacionado)
            )
            self._registrar(ev, clave, vence)
        self._purgar(float(t))
        self._ultimo_t = float(t)
        return {ident: self.puntaje(ident, float(t)) for ident in sorted(set(ids_vehiculos))}

    def puntaje(self, id_vehiculo: int, t: float) -> PuntajeRiesgo:
        """Puntaje vigente de un vehiculo en ``t`` sin modificar el estado."""
        total = sum(
            a.valor
            for a in self._aportes.get(id_vehiculo, {}).values()
            if a.vence >= t - _EPS
        )
        total = min(int(total), self.umbrales.puntaje_maximo)
        return PuntajeRiesgo(id_vehiculo, float(t), total, nivel_de(total, self.umbrales))

    def _registrar(self, ev: Evento, clave: Hashable, vence: float) -> None:
        if isinstance(ev.aporte_puntaje, bool) or not isinstance(ev.aporte_puntaje, int):
            raise ValueError("aporte_puntaje debe ser entero")
        if ev.aporte_puntaje < 0:
            raise ValueError("aporte_puntaje no puede ser negativo")
        slots = self._aportes.setdefault(ev.id_vehiculo, {})
        slots[clave] = _Aporte(ev.regla, ev.aporte_puntaje, vence)

    def _purgar(self, t: float) -> None:
        for ident in list(self._aportes):
            slots = self._aportes[ident]
            for clave in [k for k, a in slots.items() if a.vence < t - _EPS]:
                del slots[clave]
            if not slots:
                del self._aportes[ident]


def _finito(x: object) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
