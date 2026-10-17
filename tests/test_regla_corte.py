"""RF9. Corte de carril (m4_reglas/corte.py).

Casos minimos a cubrir:
  - Activa si el nuevo seguidor tiene THW < 1,5 s dentro de 2 s del cambio.
  - Activa si el nuevo seguidor tiene TTC < 3 s dentro de 2 s del cambio.
  - No activa si la condicion ocurre despues de los 2 s.
  - No activa si no hay nuevo seguidor (ausencia de predecesor, Paso 3).
"""

from typing import Optional

import pytest

from roadguard.m4_reglas.corte import ReglaCorte
from roadguard.tipos import CambioCarril, Regla, Relacion, Umbrales

CORTADOR = 10
SEGUIDOR = 20


def _cambio(t_cruce: float = 1.0, t_conf: float = 1.5) -> CambioCarril:
    return CambioCarril(CORTADOR, carril_origen=0, carril_destino=1, t_cruce=t_cruce, t_confirmacion=t_conf)


def _rel(
    t: float,
    thw: Optional[float] = None,
    ttc: Optional[float] = None,
    predecesor: Optional[int] = CORTADOR,
    carril: int = 1,
) -> Relacion:
    return Relacion(SEGUIDOR, predecesor, cuadro=0, t=t, carril=carril, distancia=15.0, thw=thw, ttc=ttc)


def test_activa_por_thw_dentro_de_2s(umbrales: Umbrales) -> None:
    regla = ReglaCorte(umbrales)
    assert regla.registrar_cambio(_cambio()) is None
    ev = regla.evaluar(_rel(2.0, thw=1.0, ttc=8.0), 2.0, velocidad=15.0)
    assert ev is not None
    assert ev.regla is Regla.CORTE
    assert ev.id_vehiculo == CORTADOR
    assert ev.id_relacionado == SEGUIDOR
    assert (ev.t_inicio, ev.t_fin) == (1.0, 2.0)
    assert ev.variables["thw"] == 1.0 and ev.variables["velocidad"] == 15.0
    assert ev.umbrales == {"thw": 1.5, "ttc": 3.0, "ventana": 2.0}
    assert ev.aporte_puntaje == 50


def test_activa_por_ttc_dentro_de_2s(umbrales: Umbrales) -> None:
    regla = ReglaCorte(umbrales)
    regla.registrar_cambio(_cambio())
    assert regla.evaluar(_rel(2.5, thw=2.0, ttc=2.5), 2.5) is not None


def test_no_activa_despues_de_2s(umbrales: Umbrales) -> None:
    regla = ReglaCorte(umbrales)
    regla.registrar_cambio(_cambio(t_cruce=1.0))
    assert regla.evaluar(_rel(2.0, thw=2.0, ttc=9.0), 2.0) is None
    assert regla.evaluar(_rel(3.04, thw=1.0, ttc=1.0), 3.04) is None


def test_no_activa_sin_nuevo_seguidor(umbrales: Umbrales) -> None:
    regla = ReglaCorte(umbrales)
    regla.registrar_cambio(_cambio())
    # nadie tiene al cortador como predecesor
    assert regla.evaluar(_rel(2.0, thw=1.0, predecesor=None), 2.0) is None
    assert regla.evaluar(_rel(2.0, thw=1.0, predecesor=99), 2.0) is None


def test_no_activa_sin_metricas(umbrales: Umbrales) -> None:
    """Sin calibracion THW y TTC son None: la regla queda suspendida (Paso 5)."""
    regla = ReglaCorte(umbrales)
    regla.registrar_cambio(_cambio())
    assert regla.evaluar(_rel(2.0), 2.0) is None


def test_no_activa_en_otro_carril(umbrales: Umbrales) -> None:
    regla = ReglaCorte(umbrales)
    regla.registrar_cambio(_cambio())
    assert regla.evaluar(_rel(2.0, thw=1.0, carril=0), 2.0) is None


def test_revisa_lo_observado_entre_cruce_y_confirmacion(umbrales: Umbrales) -> None:
    """La confirmacion llega tarde (Paso 4); el bufer causal no se pierde."""
    regla = ReglaCorte(umbrales)
    assert regla.evaluar(_rel(0.5, thw=1.0), 0.5) is None   # antes del cruce
    assert regla.evaluar(_rel(1.2, thw=1.1), 1.2) is None   # aun no confirmado
    ev = regla.registrar_cambio(_cambio(t_cruce=1.0, t_conf=1.6))
    assert ev is not None
    assert ev.t_fin == pytest.approx(1.2)
    assert ev.variables["thw"] == 1.1


def test_relacion_previa_al_cruce_no_cuenta(umbrales: Umbrales) -> None:
    regla = ReglaCorte(umbrales)
    regla.evaluar(_rel(0.5, thw=1.0), 0.5)
    assert regla.registrar_cambio(_cambio(t_cruce=1.0, t_conf=1.6)) is None


def test_un_evento_por_cambio(umbrales: Umbrales) -> None:
    regla = ReglaCorte(umbrales)
    regla.registrar_cambio(_cambio())
    assert regla.evaluar(_rel(1.8, thw=1.0), 1.8) is not None
    assert regla.evaluar(_rel(1.9, thw=0.9), 1.9) is None
