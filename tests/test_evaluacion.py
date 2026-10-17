"""T9. Metricas de M6 sobre casos construidos a mano (seccion 2.5).

Casos minimos a cubrir:
  - F1 de reglas: coincidencia perfecta, eventos faltantes, vehiculo
    equivocado y tolerancia temporal.
  - Referencia vs. degradada con el mismo motor: sin degradacion F1 = 1;
    la degradacion es reproducible con la misma semilla.
  - mAP@0.5 con predicciones perfectas, falsos positivos y regiones
    ignoradas; lectura del XML de UA-DETRAC.
  - IDF1 e intercambios de ID.
  - FPS por etapa.
"""

from pathlib import Path

import pytest

from roadguard.m6_evaluacion.degradacion import CarrilesLaterales, degradar, reestimar_cinematica
from roadguard.m6_evaluacion.deteccion import calcular_map, evaluar_deteccion
from roadguard.m6_evaluacion.reglas import evaluar_reglas, eventos_desde_estados
from roadguard.m6_evaluacion.rendimiento import medir_fps
from roadguard.m6_evaluacion.seguimiento import calcular_metricas_seguimiento, evaluar_seguimiento
from roadguard.m6_evaluacion.uadetrac import Objeto, escribir_predicciones, leer_xml
from roadguard.tipos import Caja, EstadoCinematico, Evento, Regla, Umbrales

FPS = 10.0


def escenario() -> list[EstadoCinematico]:
    """Tres vehiculos, 12 s a 10 Hz: seguimiento cercano (V2 tras V1),
    corte de V3 delante de V2 en t=4 s y regreso de V3 en t=8 s."""
    def y_v3(t: float) -> float:
        if t < 4:
            return 1.75
        if t < 4.5:
            return 1.75 + 3.5 * (t - 4) / 0.5
        if t < 8:
            return 5.25
        if t < 8.5:
            return 5.25 - 3.5 * (t - 8) / 0.5
        return 1.75

    estados = []
    for i in range(int(12 * FPS)):
        t = i / FPS
        for id_v, x, y, v in (
            (1, 100 + 20 * t, 5.25, 20.0),
            (2, 75 + 20 * t, 5.25, 20.0),
            (3, 60 + 25 * t, y_v3(t), 25.0),
        ):
            carril = 0 if y < 3.5 else 1
            estados.append(EstadoCinematico(id_v, i, t, x, y, v, carril, 1.0, True))
    return estados


def _ev(regla: Regla, id_v: int, t0: float, t1: float) -> Evento:
    return Evento(id_v, regla, t0, t1, {"x": 1.0}, {"y": 1.0}, 40)


def test_f1_perfecto_y_errores() -> None:
    ref = [_ev(Regla.CERCANIA, 1, 0, 2), _ev(Regla.ZIGZAG, 2, 5, 9)]
    assert evaluar_reglas(ref, ref, 0.5)["global.f1"] == 1.0
    m = evaluar_reglas(ref, [_ev(Regla.CERCANIA, 1, 0.2, 2.3)], 0.5)
    assert m["global.precision"] == 1.0 and m["global.recobrado"] == 0.5
    assert m["zigzag.fn"] == 1.0
    m = evaluar_reglas(ref, [_ev(Regla.CERCANIA, 9, 0, 2), _ev(Regla.ZIGZAG, 2, 5, 9)], 0.5)
    assert m["cercania_peligrosa.fp"] == 1.0 and m["cercania_peligrosa.fn"] == 1.0
    m = evaluar_reglas([_ev(Regla.CORTE, 1, 0, 1)], [_ev(Regla.CORTE, 1, 3, 4)], 1.0)
    assert m["corte_de_carril.vp"] == 0.0
    m = evaluar_reglas([_ev(Regla.CORTE, 1, 0, 1)], [_ev(Regla.CORTE, 1, 1.5, 2)], 1.0)
    assert m["corte_de_carril.vp"] == 1.0


def test_referencia_contiene_las_tres_reglas(umbrales: Umbrales) -> None:
    ref = eventos_desde_estados(escenario(), umbrales)
    reglas = {(e.regla, e.id_vehiculo) for e in ref}
    assert (Regla.CERCANIA, 2) in reglas
    assert (Regla.CORTE, 3) in reglas
    assert (Regla.ZIGZAG, 3) in reglas


def test_sin_degradacion_f1_es_1(umbrales: Umbrales) -> None:
    limpios = escenario()
    ref = eventos_desde_estados(limpios, umbrales)
    degradados = reestimar_cinematica(degradar(limpios, 0.0, 0.0, 0.0, semilla=1), FPS)
    obtenidos = eventos_desde_estados(degradados, umbrales)
    assert evaluar_reglas(ref, obtenidos, 1.0)["global.f1"] == pytest.approx(1.0)


def test_degradacion_reproducible_y_efectiva() -> None:
    limpios = escenario()
    carriles = CarrilesLaterales.desde_estados(limpios)
    a = degradar(limpios, 0.3, 0.1, 0.05, semilla=7, carriles=carriles)
    b = degradar(limpios, 0.3, 0.1, 0.05, semilla=7, carriles=carriles)
    c = degradar(limpios, 0.3, 0.1, 0.05, semilla=8, carriles=carriles)
    assert a == b and a != c
    assert 0.8 * len(limpios) < len(a) < 0.97 * len(limpios)
    assert all(e.velocidad is None for e in a)
    # cada cuadro conserva etiquetas unicas pese a los intercambios
    por_cuadro: dict[int, list[int]] = {}
    for e in a:
        por_cuadro.setdefault(e.cuadro, []).append(e.id_vehiculo)
    assert all(len(v) == len(set(v)) for v in por_cuadro.values())


def test_intercambio_de_id() -> None:
    limpios = escenario()
    swap = degradar(limpios, 0.0, 0.0, 1.0, semilla=3, distancia_intercambio=1000)
    assert any(
        e.id_vehiculo != o.id_vehiculo for e, o in zip(swap, sorted(limpios, key=lambda e: (e.cuadro, e.id_vehiculo)))
    )


def test_carriles_laterales() -> None:
    carriles = CarrilesLaterales({0: 1.75, 1: 5.25})
    assert carriles.asignar(1.75) == (0, 1.0)
    carril, conf = carriles.asignar(3.4)
    assert carril == 0 and conf < 0.1
    assert carriles.asignar(50.0) == (None, 0.0)


XML = """<?xml version="1.0" encoding="utf-8"?>
<sequence name="MVI_PRUEBA">
  <sequence_attribute camera_state="stable" sence_weather="sunny"/>
  <ignored_region>
    <box left="500" top="0" width="100" height="100"/>
  </ignored_region>
  <frame density="2" num="1">
    <target_list>
      <target id="1"><box left="10" top="10" width="40" height="30"/><attribute vehicle_type="car"/></target>
      <target id="2"><box left="100" top="10" width="60" height="50"/><attribute vehicle_type="bus"/></target>
    </target_list>
  </frame>
  <frame density="2" num="2">
    <target_list>
      <target id="1"><box left="14" top="10" width="40" height="30"/><attribute vehicle_type="car"/></target>
      <target id="2"><box left="104" top="10" width="60" height="50"/><attribute vehicle_type="bus"/></target>
    </target_list>
  </frame>
</sequence>
"""


def _xml(tmp_path: Path) -> str:
    ruta = tmp_path / "MVI_PRUEBA.xml"
    ruta.write_text(XML, encoding="utf-8")
    return str(ruta)


def _perfectas(seq, swap_en: int | None = None):
    salida = []
    for cuadro, objs in seq.objetos.items():
        for o in objs:
            id_p = o.id
            if swap_en is not None and cuadro >= swap_en:
                id_p = 3 - o.id
            salida.append(Objeto(cuadro, id_p, o.clase, o.caja, 0.9))
    return salida


def test_leer_xml(tmp_path: Path) -> None:
    seq = leer_xml(_xml(tmp_path))
    assert seq.nombre == "MVI_PRUEBA" and seq.atributos["sence_weather"] == "sunny"
    assert [o.clase for o in seq.objetos[1]] == ["automovil", "bus"]
    assert seq.objetos[2][0].caja == Caja(14, 10, 54, 40)
    assert seq.ignoradas == [Caja(500, 0, 600, 100)]


def test_map_perfecto_y_con_errores(tmp_path: Path) -> None:
    xml = _xml(tmp_path)
    seq = leer_xml(xml)
    preds = _perfectas(seq)
    ruta = tmp_path / "pred.csv"
    escribir_predicciones(preds, str(ruta))
    m = evaluar_deteccion(xml, str(ruta))
    assert m["map_50"] == pytest.approx(1.0) and m["ap_vehiculo"] == pytest.approx(1.0)

    # falso positivo con confianza alta: baja la precision
    fp = Objeto(1, None, "automovil", Caja(300, 300, 340, 330), 0.99)
    pred = {1: [fp] + [p for p in preds if p.cuadro == 1], 2: [p for p in preds if p.cuadro == 2]}
    assert calcular_map(seq.objetos, pred, seq.ignoradas)["ap_automovil"] < 1.0
    # el mismo falso positivo dentro de una region ignorada no penaliza
    ign = Objeto(1, None, "automovil", Caja(520, 20, 560, 50), 0.99)
    pred = {1: [ign] + [p for p in preds if p.cuadro == 1], 2: [p for p in preds if p.cuadro == 2]}
    assert calcular_map(seq.objetos, pred, seq.ignoradas)["ap_automovil"] == pytest.approx(1.0)


def test_idf1_e_intercambios(tmp_path: Path) -> None:
    xml = _xml(tmp_path)
    seq = leer_xml(xml)
    ruta = tmp_path / "tracks.csv"
    escribir_predicciones(_perfectas(seq), str(ruta))
    m = evaluar_seguimiento(xml, str(ruta))
    assert m["idf1"] == pytest.approx(1.0) and m["intercambios_id"] == 0.0 and m["mota"] == 1.0

    pred = {}
    for o in _perfectas(seq, swap_en=2):
        pred.setdefault(o.cuadro, []).append(o)
    m = calcular_metricas_seguimiento(seq.objetos, pred, seq.ignoradas)
    assert m["intercambios_id"] == 2.0
    assert m["idf1"] == pytest.approx(0.5)


def test_medir_fps() -> None:
    m = medir_fps({"deteccion": [0.04] * 10, "reglas": [0.01] * 10})
    assert m["fps_global"] == pytest.approx(20.0)
    assert m["ms_deteccion"] == pytest.approx(40.0)
    assert m["fraccion_deteccion"] == pytest.approx(0.8)
    assert m["cumple_15_fps"] == 1.0 and m["cumple_25_fps"] == 0.0
