"""M4 - RF8: zigzag.

Activar una alerta ante dos o mas cambios COMPLETOS de carril en 10 s,
descartando cruces breves u oscilaciones sobre la linea (RF8, Paso 4).
"""

from __future__ import annotations

from typing import Optional

from roadguard.tipos import CambioCarril, Evento, Umbrales


class ReglaZigzag:
    def __init__(self, umbrales: Umbrales) -> None:
        raise NotImplementedError("RF8: inicializar ventana de 10 s")

    def evaluar(self, cambio: CambioCarril, t: float) -> Optional[Evento]:
        """Devuelve un Evento al acumular >= 2 cambios completos en 10 s."""
        raise NotImplementedError("RF8: conteo de cambios en ventana")
