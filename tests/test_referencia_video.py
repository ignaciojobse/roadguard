"""M6: referencia de eventos desde la anotacion de UA-DETRAC (F1 en video)."""

from pathlib import Path

import pytest

from roadguard.m3_geometria.homografia import ProyectorCamino
from roadguard.m6_evaluacion.referencia import eventos_referencia
from roadguard.m6_evaluacion.referencia_video import (
    Caja,
    EventoLeido,
    asignar_ids,
    cuadros_desde_cajas,
    leer_eventos_csv,
    traducir,
)
from roadguard.tipos import Carril, Homografia, Regla, Umbrales

# Imagen = camino a escala 10 px por metro: (x px, y px) -> (x/10, y/10) m.
HOMOGRAFIA = Homografia(
    [(0, 0), (1000, 0), (1000, 100), (0, 100)], [(0, 0), (100, 0), (100, 10), (0, 10)]
)
CARRILES = [
    Carril(0, [(0, 0), (1000, 0), (1000, 35), (0, 35)]),
    Carril(1, [(0, 35), (1000, 35), (1000, 70), (0, 70)]),
]
FPS = 25.0


def _caja(cuadro, ident, x_m, y_m):
    """Caja cuyo punto de calzada cae en (x_m, y_m) metros."""
    cx, cy = x_m * 10, y_m * 10
    return Caja(cuadro, ident, (cx - 20, cy - 15, cx + 20, cy))


def _pegados(segundos=4.0):
    # El 2 va 10 m detras del 1, ambos a 10 m/s en el carril 0: THW 1,0 s.
    cajas = []
    for k in range(int(segundos * FPS)):
        t = k / FPS
        cajas.append(_caja(k, 1, 30 + 10 * t, 1.75))
        cajas.append(_caja(k, 2, 20 + 10 * t, 1.75))
    return cajas


def test_cuadros_desde_cajas_da_metros_velocidad_y_carril():
    cuadros = cuadros_desde_cajas(_pegados(), FPS, ProyectorCamino(HOMOGRAFIA), CARRILES)
    estado = {e.id_vehiculo: e for e in cuadros[50].estados}
    assert estado[2].x_camino == pytest.approx(40.0, abs=0.01)
    assert estado[2].velocidad == pytest.approx(10.0, abs=0.01)
    assert estado[2].carril == 0 and estado[2].calibrado
    relacion = {r.id_seguidor: r for r in cuadros[50].relaciones}
    assert relacion[2].id_predecesor == 1
    assert relacion[2].thw == pytest.approx(1.0, abs=0.01)


def test_referencia_desde_anotacion_produce_la_cercania():
    cuadros = cuadros_desde_cajas(_pegados(), FPS, ProyectorCamino(HOMOGRAFIA), CARRILES)
    eventos = eventos_referencia(cuadros, Umbrales())
    assert [(e.id_vehiculo, e.regla) for e in eventos] == [(2, Regla.CERCANIA)]


def test_region_filtra_y_sin_calibracion_no_hay_cuadros():
    region = [(0, 0), (400, 0), (400, 100), (0, 100)]  # hasta x = 40 m
    cuadros = cuadros_desde_cajas(
        _pegados(), FPS, ProyectorCamino(HOMOGRAFIA), CARRILES, region
    )
    assert all(e.x_camino <= 40.5 for c in cuadros for e in c.estados)
    assert cuadros_desde_cajas(_pegados(), FPS, ProyectorCamino(Homografia()), CARRILES) == []


def test_asignar_ids_por_mayoria_de_cuadros():
    referencia = _pegados(1.0)
    detectadas = [Caja(c.cuadro, 100 + c.ident, c.xyxy) for c in referencia]
    detectadas.append(Caja(0, 999, (900, 900, 950, 950)))  # sin pareja
    assert asignar_ids(detectadas, referencia) == {101: 1, 102: 2}


def test_traducir_deja_negativos_los_ids_sin_pareja():
    eventos = [EventoLeido(101, Regla.CERCANIA, 0, 2), EventoLeido(7, Regla.ZIGZAG, 1, 5)]
    traducidos = traducir(eventos, {101: 1})
    assert traducidos[0].id_vehiculo == 1
    assert traducidos[1].id_vehiculo == -8


def test_leer_eventos_csv(tmp_path: Path):
    ruta = tmp_path / "eventos.csv"
    ruta.write_text(
        "id_vehiculo,regla,t_inicio,t_fin,id_relacionado,aporte_puntaje\n"
        "4,cercania_peligrosa,8.08,10.28,3,40\n"
        "32,zigzag,44.32,49.4,,35\n"
    )
    eventos = leer_eventos_csv(ruta)
    assert eventos == [
        EventoLeido(4, Regla.CERCANIA, 8.08, 10.28),
        EventoLeido(32, Regla.ZIGZAG, 44.32, 49.4),
    ]
