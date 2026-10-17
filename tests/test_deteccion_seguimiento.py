"""RF2, RF3. Filtros del detector y seguimiento ByteTrack (M2).

Casos minimos a cubrir:
  - Mapeo explicito COCO -> clases de la configuracion; otras clases se
    descartan.
  - Se aplica confianza_min_deteccion y la region de interes por punto de
    contacto con la calzada.
  - Los IDs se mantienen a lo largo de la secuencia, incluso con una
    oclusion breve o con detecciones de confianza baja.
  - Un vehiculo que desaparece mas que el buffer recibe un ID nuevo.
  - Cada Track trae punto_calzada_px calculado desde su caja.

Estas pruebas no ejecutan YOLOv8n: usan la salida cruda simulada.
"""

import dataclasses

import pytest

from roadguard.m2_deteccion.detector import MAPEO_COCO, detecciones_desde_arrays, filtrar_region_interes
from roadguard.m2_deteccion.tracker import SeguidorByteTrack
from roadguard.tipos import Caja, Configuracion, Deteccion, Homografia, Umbrales

CFG = Configuracion(
    region_interes=[(0, 100), (640, 100), (640, 480), (0, 480)],
    carriles=[],
    homografia=Homografia(),
    clases=["automovil", "bus", "camion", "motocicleta"],
    umbrales=Umbrales(),
    confianza_min_deteccion=0.25,
)


def test_mapeo_coco_explicito() -> None:
    assert MAPEO_COCO == {2: "automovil", 3: "motocicleta", 5: "bus", 7: "camion"}


def test_filtros_de_clase_confianza_y_region() -> None:
    xyxy = [
        (10, 200, 50, 240),    # auto valido
        (60, 200, 90, 240),    # persona (COCO 0): descartada
        (100, 200, 140, 240),  # camion con confianza baja: descartado
        (200, 20, 260, 80),    # bus fuera de la region (contacto en y=80)
        (300, 60, 360, 150),   # bus con contacto dentro aunque la caja sobresale
    ]
    dets = detecciones_desde_arrays(xyxy, [0.9, 0.9, 0.1, 0.8, 0.7], [2, 0, 7, 5, 5], CFG)
    assert [(d.clase, d.caja.x1) for d in dets] == [("automovil", 10.0), ("bus", 300.0)]


def test_clases_configuradas() -> None:
    cfg = dataclasses.replace(CFG, clases=["bus"])
    dets = detecciones_desde_arrays([(10, 200, 50, 240), (300, 200, 360, 250)], [0.9, 0.9], [2, 5], cfg)
    assert [d.clase for d in dets] == ["bus"]


def test_filtrar_region_interes() -> None:
    dentro = Deteccion("automovil", 0.9, Caja(0, 0, 20, 300))
    fuera = Deteccion("automovil", 0.9, Caja(0, 0, 20, 50))
    assert filtrar_region_interes([dentro, fuera], CFG.region_interes) == [dentro]


def _det(x: float, y: float, conf: float = 0.9, clase: str = "automovil") -> Deteccion:
    return Deteccion(clase, conf, Caja(x, y, x + 40, y + 30))


def _correr(seguidor, secuencia, fps=25.0):
    salida = []
    for i, dets in enumerate(secuencia):
        salida.append(seguidor.actualizar(dets, i, i / fps))
    return salida


def test_ids_persistentes_con_dos_vehiculos() -> None:
    sec = [[_det(10 + 4 * i, 200), _det(300 - 3 * i, 300)] for i in range(60)]
    salida = _correr(SeguidorByteTrack(25.0), sec)
    assert {tr.id_vehiculo for tr in salida[0]} == {1, 2}
    for tracks in salida:
        por_id = {tr.id_vehiculo: tr for tr in tracks}
        assert set(por_id) == {1, 2}
        assert por_id[1].caja.x1 < por_id[2].caja.x1 or por_id[1].caja.y1 < por_id[2].caja.y1
    ultimo = {tr.id_vehiculo: tr for tr in salida[-1]}[1]
    assert ultimo.punto_calzada_px == ultimo.caja.punto_calzada
    assert ultimo.caja.x1 == pytest.approx(10 + 4 * 59, abs=2.0)


def test_oclusion_breve_conserva_id() -> None:
    sec = []
    for i in range(80):
        visible = not (30 <= i < 42)  # ~0,5 s sin detecciones
        sec.append([_det(10 + 3 * i, 200)] if visible else [])
    salida = _correr(SeguidorByteTrack(25.0), sec)
    ids = {tr.id_vehiculo for tracks in salida for tr in tracks}
    assert ids == {1}
    assert salida[35] == []  # mientras esta oculto no se reporta
    assert [tr.id_vehiculo for tr in salida[45]] == [1]


def test_confianza_baja_mantiene_el_track() -> None:
    sec = [[_det(10 + 3 * i, 200, conf=0.9 if i < 20 else 0.3)] for i in range(40)]
    salida = _correr(SeguidorByteTrack(25.0), sec)
    assert all([tr.id_vehiculo for tr in tracks] == [1] for tracks in salida)


def test_desaparicion_larga_genera_id_nuevo() -> None:
    sec = [[_det(100, 200)] for _ in range(10)] + [[] for _ in range(50)] + [[_det(100, 200)] for _ in range(5)]
    salida = _correr(SeguidorByteTrack(25.0, buffer=1.0), sec)
    assert {tr.id_vehiculo for tr in salida[-1]} == {2}


def test_aparicion_se_confirma_al_segundo_cuadro() -> None:
    sec = [[_det(10, 200)]] * 5 + [[_det(10, 200), _det(300, 300)]] * 5
    salida = _correr(SeguidorByteTrack(25.0), sec)
    assert {tr.id_vehiculo for tr in salida[5]} == {1}
    assert {tr.id_vehiculo for tr in salida[6]} == {1, 2}


def test_clase_por_votacion() -> None:
    sec = [[_det(10 + 2 * i, 200, clase="camion" if i != 3 else "bus")] for i in range(10)]
    salida = _correr(SeguidorByteTrack(25.0), sec)
    assert salida[-1][0].clase == "camion"
