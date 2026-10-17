"""M6 - Degradacion sintetica de trayectorias limpias (seccion 2.4).

Las trayectorias limpias de highD o NGSIM sirven como referencia; luego se
degradan para aproximar ruido, perdida de observaciones e intercambio de
ID, y se comparan los eventos resultantes.
"""

from __future__ import annotations

from roadguard.tipos import EstadoCinematico


def degradar(
    estados: list[EstadoCinematico],
    ruido_posicion: float,
    prob_perdida: float,
    prob_intercambio_id: float,
    semilla: int,
) -> list[EstadoCinematico]:
    """Aplica ruido, perdida de observaciones e intercambio de ID.

    La semilla queda registrada para reproducibilidad (Paso 6).
    """
    raise NotImplementedError("2.4: degradacion controlada de trayectorias")
