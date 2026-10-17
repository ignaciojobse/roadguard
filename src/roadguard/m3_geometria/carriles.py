"""M3 - Asignacion de carril mediante poligonos (RF4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from roadguard.tipos import CambioCarril, Carril


def asignar_carril(
    punto_px: tuple[float, float], carriles: list[Carril]
) -> tuple[Optional[int], float]:
    """Devuelve (indice_carril, confianza) para un punto de calzada (RF4).

    La confianza vale 1 en el eje del carril y cae linealmente a 0 sobre la
    linea divisoria. Se mide sobre la seccion mas angosta del poligono que
    pasa por el punto (horizontal o vertical), que es la direccion del ancho
    del carril tanto en vistas frontales como laterales. Fuera de todo
    carril devuelve (None, 0.0). Si el punto cae en poligonos solapados, se
    elige el de mayor confianza.
    """
    mejor: tuple[Optional[int], float] = (None, 0.0)
    for carril in carriles:
        if not _dentro(punto_px, carril.poligono):
            continue
        confianza = _confianza(punto_px, carril.poligono)
        if mejor[0] is None or confianza > mejor[1]:
            mejor = (carril.indice, confianza)
    return mejor


@dataclass
class _EstadoCarril:
    estable: Optional[int] = None
    candidato: Optional[int] = None
    t_cruce: Optional[float] = None
    t_estable_inicio: Optional[float] = None


class DetectorCambioCarril:
    """Confirma cambios de carril COMPLETOS (Paso 4).

    Un cambio solo se confirma tras permanencia estable en el nuevo carril.
    Las oscilaciones sobre la linea no cuentan como cambio completo y deben
    descartarse (Paso 4, M4).

    Maquina de estados por vehiculo:
      - `estable`: ultimo carril confirmado. El carril inicial tambien exige
        `permanencia` segundos, pero no genera CambioCarril.
      - `candidato`: carril distinto al estable donde se observo el vehiculo.
        `t_cruce` es la primera observacion en el.
      - El cambio se confirma cuando el vehiculo acumula `permanencia`
        segundos de observaciones con confianza >= `confianza_min` en el
        candidato. Una observacion confiable de vuelta en el carril estable
        cancela el candidato (oscilacion). Las observaciones de baja
        confianza (sobre la linea) o fuera de carril no confirman ni
        cancelan.
    """

    def __init__(self, confianza_min: float, permanencia: float = 1.0) -> None:
        self.confianza_min = confianza_min
        self.permanencia = permanencia
        self._estados: dict[int, _EstadoCarril] = {}

    def actualizar(
        self,
        id_vehiculo: int,
        carril: Optional[int],
        t: float,
        confianza: float = 1.0,
    ) -> Optional[CambioCarril]:
        """Devuelve un CambioCarril cuando se confirma, si no None."""
        if carril is None:
            return None
        e = self._estados.setdefault(id_vehiculo, _EstadoCarril())
        confiable = confianza >= self.confianza_min

        if carril == e.estable:
            if confiable:
                e.candidato = e.t_cruce = e.t_estable_inicio = None
            return None

        if carril != e.candidato:
            if not confiable and e.candidato is not None:
                return None
            e.candidato = carril
            e.t_cruce = t
            e.t_estable_inicio = t if confiable else None
        elif confiable and e.t_estable_inicio is None:
            e.t_estable_inicio = t

        if e.t_estable_inicio is None or t - e.t_estable_inicio < self.permanencia:
            return None

        cambio = None
        if e.estable is not None:
            cambio = CambioCarril(
                id_vehiculo=id_vehiculo,
                carril_origen=e.estable,
                carril_destino=e.candidato,
                t_cruce=e.t_cruce,
                t_confirmacion=t,
            )
        e.estable = e.candidato
        e.candidato = e.t_cruce = e.t_estable_inicio = None
        return cambio

    def carril_estable(self, id_vehiculo: int) -> Optional[int]:
        e = self._estados.get(id_vehiculo)
        return None if e is None else e.estable

    def olvidar(self, id_vehiculo: int) -> None:
        """Reinicia el estado cuando la identidad es dudosa (riesgos 4.4)."""
        self._estados.pop(id_vehiculo, None)


# ---------------------------------------------------------------------------
# Geometria de poligonos
# ---------------------------------------------------------------------------

def _dentro(p: tuple[float, float], poligono: list[tuple[float, float]]) -> bool:
    """Ray casting; los puntos sobre el borde cuentan como dentro."""
    x, y = p
    n = len(poligono)
    dentro = False
    for i in range(n):
        x1, y1 = poligono[i]
        x2, y2 = poligono[(i + 1) % n]
        if _sobre_segmento(p, (x1, y1), (x2, y2)):
            return True
        if (y1 > y) != (y2 > y):
            x_int = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_int:
                dentro = not dentro
    return dentro


def _sobre_segmento(p, a, b, tol: float = 1e-9) -> bool:
    cruz = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    if abs(cruz) > tol * max(1.0, abs(b[0] - a[0]) + abs(b[1] - a[1])):
        return False
    return min(a[0], b[0]) - tol <= p[0] <= max(a[0], b[0]) + tol and min(a[1], b[1]) - tol <= p[1] <= max(a[1], b[1]) + tol


def _seccion(p: tuple[float, float], poligono, eje: int) -> Optional[tuple[float, float]]:
    """Intervalo del poligono que contiene a p sobre la recta horizontal
    (eje=0, varia x) o vertical (eje=1, varia y) que pasa por p."""
    fijo = p[1 - eje]
    cortes: list[float] = []
    n = len(poligono)
    for i in range(n):
        a, b = poligono[i], poligono[(i + 1) % n]
        fa, fb = a[1 - eje], b[1 - eje]
        if (fa > fijo) != (fb > fijo):
            s = (fijo - fa) / (fb - fa)
            cortes.append(a[eje] + s * (b[eje] - a[eje]))
    cortes.sort()
    v = p[eje]
    for lo, hi in zip(cortes[0::2], cortes[1::2]):
        if lo <= v <= hi:
            return lo, hi
    return None


def _confianza(p: tuple[float, float], poligono) -> float:
    mejor: Optional[float] = None
    ancho_min = float("inf")
    for eje in (0, 1):
        sec = _seccion(p, poligono, eje)
        if sec is None:
            continue
        lo, hi = sec
        ancho = hi - lo
        if ancho <= 0:
            continue
        if ancho < ancho_min:
            ancho_min = ancho
            margen = min(p[eje] - lo, hi - p[eje])
            mejor = max(0.0, min(1.0, margen / (ancho / 2.0)))
    return 0.0 if mejor is None else mejor
