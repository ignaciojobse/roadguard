"""M2 - Seguimiento multiobjeto con ByteTrack (RF3)."""

from __future__ import annotations

from roadguard.tipos import Deteccion, Track


class SeguidorByteTrack:
    """Asigna un ID persistente a cada vehiculo (RF3).

    Debe mantener el ID mientras el vehiculo sea observable, incluyendo
    oclusiones breves, y administrar apariciones/desapariciones (M2).
    Asocia por confianza, movimiento y solapamiento.
    """

    def __init__(self, fps: float) -> None:
        raise NotImplementedError("RF3: inicializar ByteTrack")

    def actualizar(
        self, detecciones: list[Deteccion], cuadro: int, t: float
    ) -> list[Track]:
        """Actualiza el estado del tracker y devuelve los tracks vivos."""
        raise NotImplementedError("RF3: asociacion y actualizacion de IDs")
