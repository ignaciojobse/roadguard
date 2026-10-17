"""Casos limite de M3: relaciones viales en condiciones degradadas.

Casos verificados aqui o en otros archivos:
  - Oclusiones breves: test_deteccion_seguimiento.py
  - Perdida de ID (salto imposible reinicia historial): test_geometria.py
  - Vehiculos detenidos: aqui
  - Ausencia de predecesor: aqui y test_relaciones.py
  - Cambios incompletos: test_carriles.py
  - Camaras sin calibracion: aqui (Paso 5)
"""

from roadguard.m3_geometria.relaciones import calcular_relaciones
from roadguard.tipos import EstadoCinematico

FPS = 10.0


def _estado(id_v, cuadro, t, x, v, carril=0, calibrado=True):
    return EstadoCinematico(
        id_v,
        cuadro,
        t,
        x if calibrado else None,
        1.75 if calibrado else None,
        v if calibrado else None,
        carril,
        1.0,
        calibrado,
    )


def test_vehiculo_detenido_no_tiene_thw() -> None:
    """Un seguidor detenido implica una division invalida: THW y TTC None."""
    estados = [_estado(1, 0, 0.0, 0.0, 0.0), _estado(2, 0, 0.0, 5.0, 0.0)]
    rel = {r.id_seguidor: r for r in calcular_relaciones(estados, 0, 0.0)}
    assert rel[1].id_predecesor == 2
    assert rel[1].distancia == 5.0
    assert rel[1].thw is None and rel[1].ttc is None


def test_acercarse_a_un_detenido_si_tiene_ttc() -> None:
    """Tasa de cierre positiva contra un vehiculo detenido: TTC valido."""
    estados = [_estado(1, 0, 0.0, 0.0, 10.0), _estado(2, 0, 0.0, 50.0, 0.0)]
    r = calcular_relaciones(estados, 0, 0.0)[0]
    assert r.ttc == 5.0 and r.thw == 5.0


def test_ausencia_de_predecesor() -> None:
    """Un vehiculo solo en su carril no tiene predecesor ni metricas."""
    r = calcular_relaciones([_estado(1, 0, 0.0, 0.0, 30.0)], 0, 0.0)[0]
    assert r.id_predecesor is None
    assert r.distancia is None and r.thw is None and r.ttc is None


def test_carriles_distintos_no_son_predecesores() -> None:
    estados = [_estado(1, 0, 0.0, 0.0, 20.0, carril=0), _estado(2, 0, 0.0, 15.0, 20.0, carril=1)]
    rel = {r.id_seguidor: r for r in calcular_relaciones(estados, 0, 0.0)}
    assert rel[1].id_predecesor is None and rel[2].id_predecesor is None


def test_sin_calibracion_no_hay_metricas() -> None:
    """Paso 5: sin homografia utilizable, distancia, THW y TTC quedan en None."""
    estados = [
        _estado(1, 0, 0.0, 0.0, 20.0, calibrado=False),
        _estado(2, 0, 0.0, 15.0, 20.0, calibrado=False),
    ]
    for r in calcular_relaciones(estados, 0, 0.0):
        assert r.id_predecesor is None
        assert r.distancia is None and r.thw is None and r.ttc is None
