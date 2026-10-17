"""RF8. Zigzag (m4_reglas/zigzag.py).

Casos minimos a cubrir:
  - Activa con 2 cambios completos dentro de 10 s.
  - No activa con 2 cambios separados por mas de 10 s.
  - No activa con oscilaciones sobre la linea ni cruces breves (Paso 4).
  - Un cambio incompleto no cuenta.

Las oscilaciones y cruces breves se descartan en M3 (DetectorCambioCarril)
y nunca llegan a la regla; la prueba de extremo a extremo de ese caso esta
en test_carriles.py.
"""

import pytest

from roadguard.m4_reglas.zigzag import ReglaZigzag
from roadguard.tipos import CambioCarril, Regla, Umbrales


def _cambio(t_cruce: float, origen: int, destino: int, latencia: float = 1.0) -> CambioCarril:
    return CambioCarril(
        id_vehiculo=7,
        carril_origen=origen,
        carril_destino=destino,
        t_cruce=t_cruce,
        t_confirmacion=t_cruce + latencia,
    )


def test_activa_con_dos_cambios_en_10s(umbrales: Umbrales) -> None:
    regla = ReglaZigzag(umbrales)
    assert regla.evaluar(_cambio(1.0, 0, 1), 2.0) is None
    ev = regla.evaluar(_cambio(8.0, 1, 0), 9.0)
    assert ev is not None
    assert ev.regla is Regla.ZIGZAG
    assert ev.id_vehiculo == 7
    assert (ev.t_inicio, ev.t_fin) == (1.0, 9.0)
    assert ev.variables["n_cambios"] == 2
    assert ev.umbrales == {"cambios": 2.0, "ventana": 10.0}
    assert ev.aporte_puntaje == 35


def test_limite_exacto_de_10s_cuenta(umbrales: Umbrales) -> None:
    regla = ReglaZigzag(umbrales)
    regla.evaluar(_cambio(0.0, 0, 1), 1.0)
    assert regla.evaluar(_cambio(10.0, 1, 0), 11.0) is not None


def test_no_activa_con_cambios_separados_mas_de_10s(umbrales: Umbrales) -> None:
    regla = ReglaZigzag(umbrales)
    assert regla.evaluar(_cambio(0.0, 0, 1), 1.0) is None
    assert regla.evaluar(_cambio(10.5, 1, 0), 11.5) is None
    # el segundo cambio si queda disponible para una ventana posterior
    assert regla.evaluar(_cambio(15.0, 0, 1), 16.0) is not None


def test_un_solo_cambio_no_activa(umbrales: Umbrales) -> None:
    """Una oscilacion descartada por M3 deja como maximo un cambio completo."""
    regla = ReglaZigzag(umbrales)
    assert regla.evaluar(_cambio(1.0, 0, 1), 2.0) is None


def test_cambio_incompleto_no_cuenta(umbrales: Umbrales) -> None:
    regla = ReglaZigzag(umbrales)
    assert regla.evaluar(_cambio(1.0, 0, 0), 2.0) is None
    assert regla.evaluar(_cambio(3.0, 0, 1), 4.0) is None


def test_no_duplica_con_la_misma_secuencia(umbrales: Umbrales) -> None:
    regla = ReglaZigzag(umbrales)
    regla.evaluar(_cambio(1.0, 0, 1), 2.0)
    assert regla.evaluar(_cambio(3.0, 1, 0), 4.0) is not None
    # un tercer cambio solo no reutiliza los ya consumidos
    assert regla.evaluar(_cambio(5.0, 0, 1), 6.0) is None
    assert regla.evaluar(_cambio(7.0, 1, 0), 8.0) is not None


def test_vehiculos_independientes(umbrales: Umbrales) -> None:
    regla = ReglaZigzag(umbrales)
    regla.evaluar(_cambio(1.0, 0, 1), 2.0)
    otro = CambioCarril(8, 1, 0, 2.0, 3.0)
    assert regla.evaluar(otro, 3.0) is None


@pytest.mark.parametrize("minimo", [3])
def test_umbral_configurable(minimo: int) -> None:
    regla = ReglaZigzag(Umbrales(zigzag_cambios_min=minimo))
    assert regla.evaluar(_cambio(1.0, 0, 1), 2.0) is None
    assert regla.evaluar(_cambio(3.0, 1, 0), 4.0) is None
    assert regla.evaluar(_cambio(5.0, 0, 1), 6.0) is not None
