"""M3 - Historial causal, suavizado y velocidades (RF5)."""

from __future__ import annotations

from roadguard.tipos import EstadoCinematico, Track


class HistorialCausal:
    """Construye series temporales de posicion, velocidad y carril (RF5).

    Restriccion: en el cuadro t solo puede usarse informacion disponible
    hasta t (RF5, Paso 2). El suavizado debe ser causal.

    La velocidad y las metricas derivadas solo se calculan con historial
    suficiente; cualquier division invalida o ausencia de predecesor se
    representa como no disponible (Paso 3).
    """

    def __init__(self, fps: float) -> None:
        raise NotImplementedError("RF5: inicializar historial por ID")

    def actualizar(self, track: Track) -> EstadoCinematico:
        """Incorpora un track y devuelve su estado cinematico en t."""
        raise NotImplementedError("RF5: suavizado causal y diferencias")
