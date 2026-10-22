"""Detector RF7 de cercania peligrosa, procesado cuadro a cuadro.

Los resultados son snapshots: los eventos activos aparecen una vez por frame;
al cerrar un tramo confirmado se entrega una sola vez en ``cerrados``. El
intervalo termina en la ultima observacion valida, no en el instante de cierre.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional

from roadguard.tipos import EstadoCinematico, Evento, Regla, Relacion, Umbrales

_EPS = 1e-9
_ADVERTENCIA = (
    "RF7 no evaluable para uno o mas vehiculos: "
    "calibracion, observaciones o metricas no disponibles/invalidas"
)


@dataclass(frozen=True)
class ResultadoCercania:
    """Contenedor inmutable con copias independientes de eventos.

    ``activos`` describe solo el frame actual para visualizacion; no acumular
    snapshots. ``cerrados`` entrega cada evento confirmado una sola vez para
    exportacion.
    """

    activos: tuple[Evento, ...] = ()
    cerrados: tuple[Evento, ...] = ()
    advertencias: tuple[str, ...] = ()


@dataclass
class _Tramo:
    id_predecesor: int
    inicio: float
    ultimo: float
    variables: dict[str, Optional[float]]
    confirmado: bool = False
    confirmacion: Optional[float] = None


class DetectorCercania:
    """Detector RF7 streaming con estado acotado a los tramos actuales.

    Cada actualizar valida todo el frame antes de modificar el estado.
    ``finalizar`` devuelve una vez los tramos confirmados hasta su ultima
    observacion, es idempotente y termina irreversiblemente la sesion.
    """

    def __init__(self, umbrales: Optional[Umbrales] = None) -> None:
        self.umbrales = umbrales if umbrales is not None else Umbrales()
        u = self.umbrales
        for nombre in (
            "cercania_velocidad_min", "cercania_thw_max", "cercania_persistencia"
        ):
            x = getattr(u, nombre)
            if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
                raise ValueError(f"Umbral RF7 invalido: {nombre}")
        if (
            u.cercania_velocidad_min < 0
            or u.cercania_thw_max <= 0
            or u.cercania_persistencia <= 0
        ):
            raise ValueError("Umbrales RF7 fuera de rango")
        if (
            isinstance(u.aporte_cercania, bool)
            or not isinstance(u.aporte_cercania, int)
            or u.aporte_cercania < 0
        ):
            raise ValueError("aporte_cercania debe ser entero no negativo")
        self._tramos: dict[int, _Tramo] = {}
        self._ultimo_cuadro: Optional[int] = None
        self._ultimo_t: Optional[float] = None
        self._finalizado = False

    def actualizar(
        self,
        cuadro: int,
        t: float,
        estados: Iterable[EstadoCinematico],
        relaciones: Iterable[Relacion],
    ) -> ResultadoCercania:
        """Procesa un cuadro completo, sin usar observaciones futuras.

        Ambos conjuntos deben corresponder a ``cuadro`` y ``t``. Los errores
        de identidad o tiempo se rechazan antes de modificar el historial;
        las observaciones ausentes o metricas invalidas cortan la continuidad
        y producen una advertencia. Sin predecesor no hay cercania evaluable.

        La distancia es diagnostica: puede ser None si el THW esta disponible.
        Un TTC ausente o invalido no impide RF7; esta regla solo usa velocidad
        y THW. Los eventos guardan los valores de la ultima muestra valida.
        """
        if self._finalizado:
            raise ValueError("El detector ya fue finalizado")
        if isinstance(cuadro, bool) or not isinstance(cuadro, int) or cuadro < 0:
            raise ValueError("cuadro debe ser entero no negativo")
        if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) or t < 0:
            raise ValueError("t debe ser finito no negativo")
        if self._ultimo_cuadro is not None and (
            cuadro <= self._ultimo_cuadro or t <= self._ultimo_t
        ):
            raise ValueError("cuadro y t deben ser estrictamente crecientes")
        es, rs = list(estados), list(relaciones)
        emap: dict[int, EstadoCinematico] = {}
        rmap: dict[int, Relacion] = {}
        for e in es:
            _validar_id(e.id_vehiculo, "ID de estado")
            _validar_carril(e.carril)
            if not isinstance(e.calibrado, bool):
                raise ValueError("calibrado debe ser booleano")
            if e.id_vehiculo in emap:
                raise ValueError("Estado duplicado")
            emap[e.id_vehiculo] = e
            _validar_instante(e.cuadro, e.t, cuadro, t, "Estado")
        for r in rs:
            _validar_id(r.id_seguidor, "ID de seguidor")
            if r.id_predecesor is not None:
                _validar_id(r.id_predecesor, "ID de predecesor")
            _validar_carril(r.carril)
            if r.id_seguidor in rmap:
                raise ValueError("Relacion duplicada")
            rmap[r.id_seguidor] = r
            _validar_instante(r.cuadro, r.t, cuadro, t, "Relacion")
            if r.id_predecesor == r.id_seguidor:
                raise ValueError("Relacion consigo mismo")
            e = emap.get(r.id_seguidor)
            if (
                e is not None
                and e.carril is not None
                and r.carril is not None
                and e.carril != r.carril
            ):
                raise ValueError("Carriles contradictorios")

        cerrados: list[Evento] = []
        consecutivo = self._ultimo_cuadro is None or cuadro == self._ultimo_cuadro + 1
        calificados: dict[int, tuple[int, dict[str, Optional[float]]]] = {}
        advertir = any(not e.calibrado for e in emap.values())
        advertir |= any(ident not in rmap for ident in emap)
        for ident, r in rmap.items():
            e = emap.get(ident)
            if e is None:
                advertir = True
                continue
            if r.id_predecesor is None:
                continue
            if e.carril is None or r.carril is None:
                advertir = True
                continue
            vals = (e.velocidad, r.thw)
            if (
                not e.calibrado
                or any(v is None or not _finito(v) for v in vals)
                or e.velocidad <= 0
                or r.thw < 0
            ):
                advertir = True
                continue
            if r.distancia is not None and (not _finito(r.distancia) or r.distancia < 0):
                advertir = True
                continue
            velocidad = float(e.velocidad)
            if (
                velocidad > self.umbrales.cercania_velocidad_min
                and r.thw < self.umbrales.cercania_thw_max
            ):
                ttc = (
                    float(r.ttc)
                    if r.ttc is not None and _finito(r.ttc) and r.ttc >= 0
                    else None
                )
                calificados[ident] = (
                    r.id_predecesor,
                    {
                        "t_observacion": float(t),
                        "velocidad": velocidad,
                        "distancia": r.distancia,
                        "thw": float(r.thw),
                        "ttc": ttc,
                    },
                )

        activos = []
        for ident, old in list(self._tramos.items()):
            q = calificados.get(ident)
            sigue = consecutivo and q is not None and q[0] == old.id_predecesor
            if not sigue:
                ev = self._evento(ident, old)
                if ev is not None:
                    cerrados.append(ev)
                del self._tramos[ident]
        for ident, (pred, variables) in calificados.items():
            tramo = self._tramos.get(ident)
            if tramo is None:
                tramo = _Tramo(pred, float(t), float(t), variables)
                self._tramos[ident] = tramo
            else:
                tramo.ultimo, tramo.variables = float(t), variables
            if (
                not tramo.confirmado
                and tramo.ultimo - tramo.inicio >= self.umbrales.cercania_persistencia - _EPS
            ):
                tramo.confirmado = True
                tramo.confirmacion = float(t)
            ev = self._evento(ident, tramo)
            if ev is not None:
                activos.append(ev)
        self._ultimo_cuadro, self._ultimo_t = cuadro, float(t)
        advertencias = (_ADVERTENCIA,) if advertir else ()
        return ResultadoCercania(
            tuple(sorted(activos, key=lambda e: e.id_vehiculo)),
            tuple(sorted(cerrados, key=lambda e: e.id_vehiculo)),
            advertencias,
        )

    def finalizar(self) -> list[Evento]:
        """Cierra confirmados, descarta candidatos y termina la sesion.

        Devuelve solo los eventos pendientes; repetir la llamada devuelve una
        lista vacia. Para otro video se debe crear un detector nuevo.
        """
        if self._finalizado:
            return []
        resultado = [
            ev
            for ident, tramo in sorted(self._tramos.items())
            if (ev := self._evento(ident, tramo)) is not None
        ]
        self._tramos.clear()
        self._finalizado = True
        return resultado

    def _evento(self, ident: int, tramo: _Tramo) -> Optional[Evento]:
        if not tramo.confirmado:
            return None
        variables = dict(tramo.variables)
        variables["t_confirmacion"] = tramo.confirmacion
        return Evento(
            id_vehiculo=ident,
            regla=Regla.CERCANIA,
            t_inicio=tramo.inicio,
            t_fin=tramo.ultimo,
            variables=variables,
            umbrales={
                "cercania_velocidad_min": float(self.umbrales.cercania_velocidad_min),
                "cercania_thw_max": float(self.umbrales.cercania_thw_max),
                "cercania_persistencia": float(self.umbrales.cercania_persistencia),
            },
            aporte_puntaje=self.umbrales.aporte_cercania,
            id_relacionado=tramo.id_predecesor,
        )


def _finito(x: object) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _validar_instante(
    cuadro: object, t: object, esperado_cuadro: int, esperado_t: float, tipo: str
) -> None:
    if isinstance(cuadro, bool) or not isinstance(cuadro, int):
        raise ValueError(f"{tipo}: cuadro debe ser entero")
    if (
        isinstance(t, bool)
        or not isinstance(t, (int, float))
        or not math.isfinite(t)
        or t < 0
    ):
        raise ValueError(f"{tipo}: t debe ser finito no negativo")
    if cuadro != esperado_cuadro or not math.isclose(t, esperado_t, rel_tol=0, abs_tol=_EPS):
        raise ValueError(f"{tipo} no corresponde al frame")


def _validar_id(ident: object, nombre: str) -> None:
    if isinstance(ident, bool) or not isinstance(ident, int) or ident < 0:
        raise ValueError(f"{nombre} debe ser entero no negativo")


def _validar_carril(carril: object) -> None:
    if carril is not None and (
        isinstance(carril, bool) or not isinstance(carril, int) or carril < 0
    ):
        raise ValueError("carril debe ser entero no negativo o None")
