"""M4 - RF9: corte de carril.

Activar una alerta si, dentro de 2 s tras un cambio de carril, el nuevo
seguidor presenta THW < 1,5 s o TTC < 3 s.
"""

from __future__ import annotations

from typing import Optional

from roadguard.tipos import CambioCarril, Evento, Relacion, Umbrales


class ReglaCorte:
    def __init__(self, umbrales: Umbrales) -> None:
        raise NotImplementedError("RF9: inicializar seguimiento post-cambio")

    def registrar_cambio(self, cambio: CambioCarril) -> None:
        """Abre la ventana de 2 s posterior al cambio de carril (RF9)."""
        raise NotImplementedError("RF9: abrir ventana post-cambio")

    def evaluar(self, relacion: Relacion, t: float) -> Optional[Evento]:
        """Evalua al NUEVO seguidor del vehiculo que cambio de carril."""
        raise NotImplementedError("RF9: THW < 1,5 s o TTC < 3 s en 2 s")
