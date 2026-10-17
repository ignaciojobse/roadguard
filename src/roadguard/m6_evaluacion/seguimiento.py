"""M6 - IDF1 e intercambios de ID.

Criterio de aceptacion (seccion 2.5): IDF1 >= 0,60 e informe separado de
cambios incorrectos de ID.
"""

from __future__ import annotations


def evaluar_seguimiento(ruta_anotaciones: str, ruta_tracks: str) -> dict[str, float]:
    """Devuelve IDF1 y el conteo de intercambios de ID."""
    raise NotImplementedError("2.5: IDF1 >= 0,60 e ID switches")
