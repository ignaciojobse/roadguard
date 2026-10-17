"""M4 - RF10/RF11: puntaje temporal de riesgo.

Sumar 40 puntos por cercania activa, 35 por zigzag reciente y 50 por corte
reciente; limitar el total a 100 y retirar cada aporte despues de 5 s.
Bandas de color (RF11): verde 0-29, amarillo 30-59, rojo 60-100.
"""

from __future__ import annotations

from roadguard.tipos import Evento, NivelRiesgo, PuntajeRiesgo, Umbrales


class AcumuladorPuntaje:
    def __init__(self, umbrales: Umbrales) -> None:
        raise NotImplementedError("RF10: inicializar aportes con vigencia")

    def registrar(self, evento: Evento) -> None:
        """Agrega el aporte del evento al vehiculo correspondiente."""
        raise NotImplementedError("RF10: registrar aporte")

    def puntaje_en(self, id_vehiculo: int, t: float) -> PuntajeRiesgo:
        """Puntaje vigente en t, con aportes caducados ya retirados."""
        raise NotImplementedError("RF10: caducidad a 5 s y tope en 100")


def nivel_desde_puntaje(puntaje: int, umbrales: Umbrales) -> NivelRiesgo:
    """RF11: verde 0-29, amarillo 30-59, rojo 60-100."""
    raise NotImplementedError("RF11: mapeo puntaje -> banda de color")
