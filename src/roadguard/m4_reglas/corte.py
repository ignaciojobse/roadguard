"""M4 - RF9: corte de carril.

Activar una alerta si, dentro de 2 s tras un cambio de carril, el nuevo
seguidor presenta THW < 1,5 s o TTC < 3 s.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Optional

from roadguard.tipos import CambioCarril, Evento, Regla, Relacion, Umbrales


class ReglaCorte:
    """Ventana post-cambio sobre el nuevo seguidor (RF9).

    La ventana de 2 s se cuenta desde `t_cruce`. Como el cambio solo se
    conoce al confirmarse (`t_confirmacion`, Paso 4), la regla conserva un
    bufer causal de las relaciones de los ultimos 2 s: al registrar el
    cambio revisa lo ya observado entre `t_cruce` y la confirmacion, y luego
    sigue evaluando las relaciones nuevas hasta cerrar la ventana. Nunca usa
    informacion posterior al instante actual.

    El evento se atribuye al vehiculo que cambio de carril; el nuevo seguidor
    queda en `id_relacionado`. Se emite como maximo un evento por cambio.
    """

    def __init__(self, umbrales: Umbrales) -> None:
        self.umbrales = umbrales
        self._ventanas: dict[int, CambioCarril] = {}
        # predecesor -> relaciones recientes (relacion, velocidad del seguidor)
        self._bufer: dict[int, deque[tuple[Relacion, Optional[float]]]] = defaultdict(deque)

    def registrar_cambio(self, cambio: CambioCarril) -> Optional[Evento]:
        """Abre la ventana de 2 s posterior al cambio de carril (RF9).

        Devuelve un Evento si alguna relacion ya observada desde `t_cruce`
        cumple la condicion.
        """
        if cambio.carril_origen == cambio.carril_destino:
            return None
        self._ventanas[cambio.id_vehiculo] = cambio
        for relacion, velocidad in list(self._bufer.get(cambio.id_vehiculo, ())):
            evento = self._evaluar_en_ventana(relacion, velocidad, relacion.t)
            if evento is not None:
                return evento
        return None

    def evaluar(
        self, relacion: Relacion, t: float, velocidad: Optional[float] = None
    ) -> Optional[Evento]:
        """Evalua al NUEVO seguidor del vehiculo que cambio de carril.

        `velocidad` es la del seguidor y solo se usa como variable de
        trazabilidad.
        """
        self._purgar(t)
        if relacion.id_predecesor is None:
            return None  # sin predecesor no hay nuevo seguidor (Paso 3)
        self._bufer[relacion.id_predecesor].append((relacion, velocidad))
        return self._evaluar_en_ventana(relacion, velocidad, t)

    def olvidar(self, id_vehiculo: int) -> None:
        """Reinicia el estado cuando la identidad es dudosa (riesgos 4.4)."""
        self._ventanas.pop(id_vehiculo, None)
        self._bufer.pop(id_vehiculo, None)

    # ------------------------------------------------------------------

    def _evaluar_en_ventana(
        self, relacion: Relacion, velocidad: Optional[float], t: float
    ) -> Optional[Evento]:
        u = self.umbrales
        cambio = self._ventanas.get(relacion.id_predecesor)
        if cambio is None or relacion.carril != cambio.carril_destino:
            return None
        if not cambio.t_cruce <= relacion.t <= cambio.t_cruce + u.corte_ventana_post_cambio:
            return None
        thw_bajo = relacion.thw is not None and relacion.thw < u.corte_thw_max
        ttc_bajo = relacion.ttc is not None and relacion.ttc < u.corte_ttc_max
        if not (thw_bajo or ttc_bajo):
            return None

        del self._ventanas[cambio.id_vehiculo]
        return Evento(
            id_vehiculo=cambio.id_vehiculo,
            regla=Regla.CORTE,
            t_inicio=cambio.t_cruce,
            t_fin=t,
            variables={
                "velocidad": velocidad,
                "distancia": relacion.distancia,
                "thw": relacion.thw,
                "ttc": relacion.ttc,
                "carril_origen": float(cambio.carril_origen),
                "carril_destino": float(cambio.carril_destino),
                "latencia_confirmacion": cambio.t_confirmacion - cambio.t_cruce,
            },
            umbrales={
                "thw": u.corte_thw_max,
                "ttc": u.corte_ttc_max,
                "ventana": u.corte_ventana_post_cambio,
            },
            aporte_puntaje=u.aporte_corte,
            id_relacionado=relacion.id_seguidor,
        )

    def _purgar(self, t: float) -> None:
        limite = t - self.umbrales.corte_ventana_post_cambio
        for id_pred in list(self._bufer):
            cola = self._bufer[id_pred]
            while cola and cola[0][0].t < limite:
                cola.popleft()
            if not cola:
                del self._bufer[id_pred]
        for id_v, cambio in list(self._ventanas.items()):
            if t > cambio.t_cruce + self.umbrales.corte_ventana_post_cambio:
                del self._ventanas[id_v]
