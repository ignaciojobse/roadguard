"""M4 - RF7: cercania peligrosa.

Activar una alerta si el seguidor supera 5 m/s y mantiene THW < 1,5 s
durante al menos 2 s. Implementado con ventana deslizante y evaluacion de
persistencia; debe evitar eventos duplicados (M4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from roadguard.tipos import Evento, Regla, Relacion, Umbrales


@dataclass
class _EstadoSeguidor:
    id_predecesor: Optional[int]
    t_inicio: float          # primer instante con la condicion cumplida
    t_ultimo: float          # ultimo instante evaluado con la condicion cumplida
    thw_min: float
    activa: bool = False     # ya se emitio el evento de esta racha


class ReglaCercania:
    """Maquina de estados por seguidor (RF7).

    Una racha empieza cuando se cumple v > 5 m/s y THW < 1,5 s, y se
    interrumpe si la condicion deja de cumplirse, si THW no esta disponible,
    si cambia el predecesor o si el seguidor deja de observarse por mas de
    `hueco_max` segundos. El evento se emite UNA vez por racha, al alcanzar
    la persistencia; no se repite mientras la condicion siga activa.
    """

    def __init__(self, umbrales: Umbrales, hueco_max: float = 0.5) -> None:
        self.umbrales = umbrales
        self.hueco_max = hueco_max
        self._estados: dict[int, _EstadoSeguidor] = {}

    def evaluar(
        self, relacion: Relacion, velocidad: Optional[float], t: float
    ) -> Optional[Evento]:
        """Devuelve un Evento cuando se cumple la persistencia de 2 s."""
        u = self.umbrales
        seguidor = relacion.id_seguidor
        cumple = (
            relacion.id_predecesor is not None
            and relacion.thw is not None   # sin calibracion no se evalua (Paso 5)
            and velocidad is not None
            and velocidad > u.cercania_velocidad_min
            and relacion.thw < u.cercania_thw_max
        )
        estado = self._estados.get(seguidor)
        if not cumple:
            self._estados.pop(seguidor, None)
            return None

        if (
            estado is None
            or estado.id_predecesor != relacion.id_predecesor
            or t - estado.t_ultimo > self.hueco_max
        ):
            estado = _EstadoSeguidor(relacion.id_predecesor, t, t, relacion.thw)
            self._estados[seguidor] = estado
        estado.t_ultimo = t
        estado.thw_min = min(estado.thw_min, relacion.thw)

        if estado.activa or t - estado.t_inicio < u.cercania_persistencia:
            return None
        estado.activa = True
        return Evento(
            id_vehiculo=seguidor,
            regla=Regla.CERCANIA,
            t_inicio=estado.t_inicio,
            t_fin=t,
            variables={
                "velocidad": velocidad,
                "distancia": relacion.distancia,
                "thw": relacion.thw,
                "ttc": relacion.ttc,
                "thw_min": estado.thw_min,
                "duracion": t - estado.t_inicio,
            },
            umbrales={
                "velocidad": u.cercania_velocidad_min,
                "thw": u.cercania_thw_max,
                "persistencia": u.cercania_persistencia,
            },
            aporte_puntaje=u.aporte_cercania,
            id_relacionado=relacion.id_predecesor,
        )

    def olvidar(self, id_vehiculo: int) -> None:
        """Reinicia el estado cuando la identidad es dudosa (riesgos 4.4)."""
        self._estados.pop(id_vehiculo, None)
