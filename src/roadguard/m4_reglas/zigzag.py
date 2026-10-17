"""M4 - RF8: zigzag.

Activar una alerta ante dos o mas cambios COMPLETOS de carril en 10 s,
descartando cruces breves u oscilaciones sobre la linea (RF8, Paso 4).
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Optional

from roadguard.tipos import CambioCarril, Evento, Regla, Umbrales


class ReglaZigzag:
    """Ventana deslizante de cambios completos por vehiculo (RF8).

    Solo recibe `CambioCarril` confirmados por M3: los cruces breves y las
    oscilaciones ya fueron descartados por `DetectorCambioCarril` (Paso 4).
    La ventana se mide sobre `t_cruce`, el instante fisico del cambio.
    Los cambios que activan un evento se consumen, de modo que la misma
    secuencia no produce eventos duplicados.
    """

    def __init__(self, umbrales: Umbrales) -> None:
        self.umbrales = umbrales
        self._cambios: dict[int, deque[CambioCarril]] = defaultdict(deque)

    def evaluar(self, cambio: CambioCarril, t: float) -> Optional[Evento]:
        """Devuelve un Evento al acumular >= 2 cambios completos en 10 s."""
        u = self.umbrales
        if cambio.carril_origen == cambio.carril_destino:
            return None  # no es un cambio completo
        cola = self._cambios[cambio.id_vehiculo]
        cola.append(cambio)
        while cola and cambio.t_cruce - cola[0].t_cruce > u.zigzag_ventana:
            cola.popleft()
        if len(cola) < u.zigzag_cambios_min:
            return None

        cambios = list(cola)
        cola.clear()
        return Evento(
            id_vehiculo=cambio.id_vehiculo,
            regla=Regla.ZIGZAG,
            t_inicio=cambios[0].t_cruce,
            t_fin=t,
            variables={
                "n_cambios": float(len(cambios)),
                "duracion": cambios[-1].t_cruce - cambios[0].t_cruce,
                "latencia_confirmacion": cambio.t_confirmacion - cambio.t_cruce,
            },
            umbrales={
                "cambios": float(u.zigzag_cambios_min),
                "ventana": u.zigzag_ventana,
            },
            aporte_puntaje=u.aporte_zigzag,
        )

    def olvidar(self, id_vehiculo: int) -> None:
        """Reinicia el historial cuando la identidad es dudosa (riesgos 4.4)."""
        self._cambios.pop(id_vehiculo, None)
