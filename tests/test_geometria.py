"""RF4, RF5. Homografia e historial causal (m3_geometria).

Casos minimos a cubrir:
  - Con homografia valida, los puntos de calibracion se proyectan sobre sus
    correspondencias y un vehiculo que recorre la region produce x_camino
    monotono.
  - Sin homografia, todos los campos metricos son None y calibrado es False.
  - La velocidad solo se calcula con historial suficiente (Paso 3).
  - El historial no acepta cuadros fuera de orden (Paso 2).
  - Un salto imposible reinicia el historial de ese ID (riesgos 4.4).
"""

import pytest

from roadguard.m3_geometria.homografia import ProyectorCamino
from roadguard.m3_geometria.trayectorias import HistorialCausal
from roadguard.tipos import Caja, Carril, Homografia, Track

# Trapecio en perspectiva: la base (y=400 px) esta cerca de la camara.
# Camino: x longitudinal en el sentido de avance (alejandose), y lateral.
HOMOGRAFIA = Homografia(
    puntos_imagen=[(140, 0), (180, 0), (320, 400), (0, 400)],
    puntos_camino=[(60.0, 0.0), (60.0, 7.0), (0.0, 7.0), (0.0, 0.0)],
)
CARRILES = [
    Carril(0, [(140, 0), (160, 0), (160, 400), (0, 400)]),
    Carril(1, [(160, 0), (180, 0), (320, 400), (160, 400)]),
]


def _track(id_v: int, i: int, fps: float, x: float, y: float) -> Track:
    caja = Caja(x - 10, y - 20, x + 10, y)
    return Track(id_v, i, i / fps, "automovil", 0.9, caja, caja.punto_calzada)


def test_proyecta_puntos_de_calibracion() -> None:
    p = ProyectorCamino(HOMOGRAFIA)
    assert p.disponible
    assert p.error_reproyeccion == pytest.approx(0.0, abs=1e-6)
    for img, cam in zip(HOMOGRAFIA.puntos_imagen, HOMOGRAFIA.puntos_camino):
        assert p.proyectar(img) == pytest.approx(cam, abs=1e-6)


def test_sin_homografia_no_proyecta() -> None:
    p = ProyectorCamino(Homografia())
    assert not p.disponible
    assert p.proyectar((10, 10)) is None


def test_x_camino_monotono_con_homografia() -> None:
    fps = 25.0
    hist = HistorialCausal(fps, ProyectorCamino(HOMOGRAFIA), CARRILES)
    xs, vs = [], []
    for i in range(100):
        # avanza hacia el horizonte por el centro del carril 0
        y_px = 395 - 3.5 * i
        x_px = 80 + (150 - 80) * (395 - y_px) / 395
        e = hist.actualizar(_track(1, i, fps, x_px, y_px))
        assert e.calibrado and e.carril == 0
        xs.append(e.x_camino)
        vs.append(e.velocidad)
    assert all(b > a for a, b in zip(xs, xs[1:]))
    assert vs[0] is None                    # historial insuficiente
    assert all(v is not None and v > 0 for v in vs[10:])


def test_sin_homografia_campos_metricos_none() -> None:
    hist = HistorialCausal(25.0, ProyectorCamino(Homografia()), CARRILES)
    for i in range(30):
        e = hist.actualizar(_track(1, i, 25.0, 100, 300 - i))
        assert not e.calibrado
        assert (e.x_camino, e.y_camino, e.velocidad) == (None, None, None)
        assert e.carril == 0  # el carril se asigna en pixeles: no depende de calibracion


def test_velocidad_constante_recuperada() -> None:
    hist = HistorialCausal(10.0)
    for i in range(20):
        e = hist.actualizar_camino(1, i, i / 10.0, (5.0 + 20.0 * i / 10.0, 1.0), 0, 1.0)
    assert e.velocidad == pytest.approx(20.0)
    assert e.x_camino == pytest.approx(5.0 + 20.0 * 1.9)


def test_suavizado_es_causal() -> None:
    """El estado en t no cambia por observaciones posteriores."""
    a, b = HistorialCausal(10.0), HistorialCausal(10.0)
    xs = [0.0, 1.1, 1.9, 3.2, 3.9, 5.1, 6.0, 7.2]
    estados_a = [a.actualizar_camino(1, i, i / 10, (x, 0.0), 0, 1.0) for i, x in enumerate(xs)]
    estados_b = [b.actualizar_camino(1, i, i / 10, (x, 0.0), 0, 1.0) for i, x in enumerate(xs[:5])]
    assert estados_a[:5] == estados_b


def test_orden_temporal_estricto() -> None:
    hist = HistorialCausal(10.0)
    hist.actualizar_camino(1, 1, 0.1, (0.0, 0.0), 0, 1.0)
    with pytest.raises(ValueError, match="Orden temporal"):
        hist.actualizar_camino(1, 0, 0.0, (0.0, 0.0), 0, 1.0)


def test_salto_imposible_reinicia_historial() -> None:
    hist = HistorialCausal(10.0)
    for i in range(10):
        hist.actualizar_camino(1, i, i / 10, (2.0 * i, 0.0), 0, 1.0)
    e = hist.actualizar_camino(1, 10, 1.0, (500.0, 0.0), 0, 1.0)
    assert hist.reinicios == [1]
    assert e.velocidad is None
