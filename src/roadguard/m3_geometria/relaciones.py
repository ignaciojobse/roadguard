"""M3 - Predecesor/seguidor, distancia, THW y TTC (RF6)."""

from __future__ import annotations

from typing import Optional

from roadguard.tipos import EstadoCinematico, Relacion


def calcular_relaciones(
    estados: list[EstadoCinematico], cuadro: int, t: float
) -> list[Relacion]:
    """Determina predecesor y seguidor por carril y calcula metricas (RF6).

    THW = distancia / velocidad del seguidor.
    TTC se calcula SOLO con tasa de cierre positiva; si no, queda en None.
    Sin calibracion, distancia, THW y TTC quedan en None (Paso 5).
    """
    raise NotImplementedError("RF6: emparejamiento por carril y metricas")


def calcular_thw(distancia: Optional[float], velocidad: Optional[float]) -> Optional[float]:
    """THW = distancia / velocidad del seguidor (M3). None si es invalido."""
    raise NotImplementedError("RF6: THW")


def calcular_ttc(
    distancia: Optional[float], tasa_cierre: Optional[float]
) -> Optional[float]:
    """TTC solo con tasa de cierre positiva (M3). None en caso contrario."""
    raise NotImplementedError("RF6: TTC")
