"""Seccion 2.5. Robustez en casos limite, de extremo a extremo de M3 + M4.

Casos verificados aqui o en otros archivos:
  - Oclusiones breves: test_deteccion_seguimiento.py
  - Perdida de ID (salto imposible reinicia historial): test_geometria.py
  - Vehiculos detenidos: aqui
  - Ausencia de predecesor: aqui y test_relaciones.py
  - Cambios incompletos: aqui y test_carriles.py
  - Camaras sin calibracion: aqui y test_pipeline.py
"""

from roadguard.m3_geometria.relaciones import calcular_relaciones
from roadguard.m6_evaluacion.reglas import eventos_desde_estados
from roadguard.tipos import EstadoCinematico, Regla, Umbrales

FPS = 10.0


def _serie(id_v, x0, v, carril=0, segundos=6.0, y=1.75, calibrado=True):
    out = []
    for i in range(int(segundos * FPS)):
        t = i / FPS
        x = x0 + v * t if calibrado else None
        out.append(
            EstadoCinematico(id_v, i, t, x, y if calibrado else None, v if calibrado else None, carril, 1.0, calibrado)
        )
    return out


def test_vehiculo_detenido(umbrales: Umbrales) -> None:
    """Un seguidor detenido no tiene THW (division invalida) ni activa
    cercania; un seguidor en movimiento hacia un vehiculo detenido si tiene
    TTC valido."""
    detenido_detras = _serie(1, 0.0, 0.0) + _serie(2, 5.0, 0.0)
    rel = {r.id_seguidor: r for r in calcular_relaciones([e for e in detenido_detras if e.cuadro == 0], 0, 0.0)}
    assert rel[1].thw is None and rel[1].ttc is None
    assert eventos_desde_estados(detenido_detras, umbrales) == []

    hacia_detenido = [
        EstadoCinematico(1, 0, 0.0, 0.0, 1.75, 10.0, 0, 1.0, True),
        EstadoCinematico(2, 0, 0.0, 50.0, 1.75, 0.0, 0, 1.0, True),
    ]
    r = calcular_relaciones(hacia_detenido, 0, 0.0)[0]
    assert r.ttc == 5.0 and r.thw == 5.0


def test_ausencia_de_predecesor(umbrales: Umbrales) -> None:
    solo = _serie(1, 0.0, 30.0)
    assert eventos_desde_estados(solo, umbrales) == []


def test_cambio_incompleto_no_genera_alertas(umbrales: Umbrales) -> None:
    """V2 invade el carril de V1 por 0,5 s y vuelve: sin zigzag ni corte."""
    estados = _serie(1, 30.0, 20.0, carril=1, y=5.25)
    for i in range(int(6 * FPS)):
        t = i / FPS
        carril = 1 if 2.0 <= t < 2.5 else 0
        estados.append(EstadoCinematico(2, i, t, 35.0 + 20.0 * t, 5.0 if carril else 1.75, 20.0, carril, 0.9, True))
    eventos = eventos_desde_estados(estados, umbrales)
    assert [e for e in eventos if e.regla in (Regla.ZIGZAG, Regla.CORTE)] == []


def test_sin_calibracion_solo_mantiene_zigzag(umbrales: Umbrales) -> None:
    """Sin metricas, cercania y corte quedan suspendidas; zigzag depende solo
    de carriles y sigue disponible (Paso 5)."""
    cercanos = _serie(1, 0.0, 20.0, calibrado=False) + _serie(2, 15.0, 20.0, calibrado=False)
    assert eventos_desde_estados(cercanos, umbrales) == []

    zig = []
    for i in range(int(8 * FPS)):
        t = i / FPS
        carril = 0 if t < 2 else (1 if t < 4.5 else 0)
        zig.append(EstadoCinematico(3, i, t, None, None, None, carril, 1.0, False))
    assert [e.regla for e in eventos_desde_estados(zig, umbrales)] == [Regla.ZIGZAG]
