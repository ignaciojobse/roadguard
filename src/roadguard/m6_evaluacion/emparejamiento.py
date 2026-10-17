"""Precision, recobrado y F1 de eventos (criterio de reglas, seccion 2.5).

Un evento detectado acierta si coincide con uno de referencia en vehiculo y
regla y sus intervalos se solapan, ampliados por una tolerancia que absorbe
la latencia de confirmacion. El emparejamiento es uno a uno: cada evento de
referencia se cuenta como acertado a lo mas una vez.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Protocol

from roadguard.tipos import Regla


class EventoComparable(Protocol):
    id_vehiculo: int
    regla: Regla
    t_inicio: float
    t_fin: float


@dataclass(frozen=True)
class ResultadoEventos:
    """Conteos y metricas. None cuando la division no es valida (Paso 3)."""

    verdaderos_positivos: int
    falsos_positivos: int
    falsos_negativos: int

    @property
    def precision(self) -> Optional[float]:
        detectados = self.verdaderos_positivos + self.falsos_positivos
        return self.verdaderos_positivos / detectados if detectados else None

    @property
    def recobrado(self) -> Optional[float]:
        esperados = self.verdaderos_positivos + self.falsos_negativos
        return self.verdaderos_positivos / esperados if esperados else None

    @property
    def f1(self) -> Optional[float]:
        p, r = self.precision, self.recobrado
        if p is None or r is None or p + r == 0:
            return None
        return 2 * p * r / (p + r)


def evaluar_eventos(
    detectados: Iterable[EventoComparable],
    referencia: Iterable[EventoComparable],
    tolerancia: float = 1.0,
) -> dict[Regla, ResultadoEventos]:
    """Resultado por regla. Las reglas sin eventos en ningun lado no aparecen."""
    detectados = list(detectados)
    referencia = list(referencia)
    reglas = {e.regla for e in detectados} | {e.regla for e in referencia}
    return {
        regla: _evaluar_regla(
            [e for e in detectados if e.regla == regla],
            [e for e in referencia if e.regla == regla],
            tolerancia,
        )
        for regla in reglas
    }


def resultado_global(por_regla: dict[Regla, ResultadoEventos]) -> ResultadoEventos:
    """Suma de conteos de todas las reglas (micro-promedio)."""
    return ResultadoEventos(
        sum(r.verdaderos_positivos for r in por_regla.values()),
        sum(r.falsos_positivos for r in por_regla.values()),
        sum(r.falsos_negativos for r in por_regla.values()),
    )


def _solape(a: EventoComparable, b: EventoComparable, tolerancia: float) -> float:
    """Solape de los intervalos ampliados en `tolerancia` por cada lado."""
    return min(a.t_fin, b.t_fin) - max(a.t_inicio, b.t_inicio) + 2 * tolerancia


def _evaluar_regla(
    detectados: list[EventoComparable],
    referencia: list[EventoComparable],
    tolerancia: float,
) -> ResultadoEventos:
    pares = []
    for i, d in enumerate(detectados):
        for j, r in enumerate(referencia):
            if d.id_vehiculo != r.id_vehiculo:
                continue
            solape = _solape(d, r, tolerancia)
            if solape >= 0:
                pares.append((solape, i, j))
    pares.sort(reverse=True)
    usados_d: set[int] = set()
    usados_r: set[int] = set()
    for _, i, j in pares:
        if i in usados_d or j in usados_r:
            continue
        usados_d.add(i)
        usados_r.add(j)
    vp = len(usados_d)
    return ResultadoEventos(vp, len(detectados) - vp, len(referencia) - vp)
