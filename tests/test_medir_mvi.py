"""Pruebas del medidor de mAP@0.5 e IDF1 (`scripts/medir_mvi.py`) con cajas sinteticas."""

import importlib.util
import sys
from pathlib import Path

import pytest

RUTA = Path(__file__).resolve().parents[1] / "scripts" / "medir_mvi.py"
spec = importlib.util.spec_from_file_location("medir_mvi", RUTA)
medir_mvi = importlib.util.module_from_spec(spec)
sys.modules["medir_mvi"] = medir_mvi
spec.loader.exec_module(medir_mvi)

CajaRef = medir_mvi.CajaRef


def _caja(cuadro, ident, x, clase="automovil", confianza=0.9):
    return CajaRef(cuadro, ident, clase, (x, 100.0, x + 50.0, 140.0), confianza)


def _referencia(n_cuadros=4):
    # Dos vehiculos que avanzan 10 px por cuadro, separados 200 px.
    return [_caja(c, 1, 10.0 + 10 * c) for c in range(n_cuadros)] + [
        _caja(c, 2, 300.0 + 10 * c) for c in range(n_cuadros)
    ]


def test_seguimiento_perfecto_da_metricas_en_uno() -> None:
    ref = _referencia()
    det = [CajaRef(c.cuadro, c.ident + 10, c.clase, c.xyxy, 0.8) for c in ref]
    m = medir_mvi.medir(ref, det)
    assert m["map50_sin_clase"]["ap"] == pytest.approx(1.0)
    assert m["seguimiento"]["idf1"] == pytest.approx(1.0)
    assert m["seguimiento"]["cambios_id"] == 0
    assert m["seguimiento"]["mota"] == pytest.approx(1.0)


def test_cambio_de_id_baja_idf1_y_cuenta_un_cambio() -> None:
    ref = _referencia(n_cuadros=4)
    det = []
    for c in ref:
        # El vehiculo 1 cambia de ID detectado en la mitad de la secuencia.
        ident = 11 if c.ident == 1 and c.cuadro < 2 else (12 if c.ident == 1 else 22)
        det.append(CajaRef(c.cuadro, ident, c.clase, c.xyxy, 0.8))
    m = medir_mvi.medir(ref, det)
    s = m["seguimiento"]
    assert s["cambios_id"] == 1
    assert s["idtp"] == 6  # 4 del vehiculo 2 + los 2 cuadros mejor cubiertos del 1
    assert s["idf1"] == pytest.approx(2 * 6 / (2 * 6 + 2 + 2))
    assert m["map50_sin_clase"]["ap"] == pytest.approx(1.0)


def test_falsos_positivos_de_baja_confianza_no_bajan_el_ap_y_los_perdidos_si() -> None:
    ref = _referencia(n_cuadros=2)
    det = [CajaRef(c.cuadro, c.ident, c.clase, c.xyxy, 0.9) for c in ref if c.ident == 1]
    det.append(_caja(0, 99, 600.0, confianza=0.1))
    m = medir_mvi.medir(ref, det)
    ap = m["map50_sin_clase"]
    assert ap["recobrado_final"] == pytest.approx(0.5)
    assert ap["ap"] == pytest.approx(0.5)
    assert m["seguimiento"]["falsos_positivos"] == 1
    assert m["seguimiento"]["falsos_negativos"] == 2


def test_iou_bajo_no_empareja() -> None:
    ref = [_caja(0, 1, 10.0)]
    det = [_caja(0, 1, 40.0)]  # solape de 20 px sobre 50: IoU 0,25
    m = medir_mvi.medir(ref, det)
    assert m["map50_sin_clase"]["ap"] == pytest.approx(0.0)
    assert m["seguimiento"]["idf1"] == pytest.approx(0.0)


def test_xml_y_regiones_ignoradas(tmp_path) -> None:
    xml = tmp_path / "s.xml"
    xml.write_text(
        """<?xml version="1.0"?>
<sequence name="s">
  <ignored_region><box left="0" top="0" width="100" height="100"/></ignored_region>
  <frame num="1"><target_list>
    <target id="3"><box left="10" top="10" width="20" height="20"/><attribute vehicle_type="van"/></target>
    <target id="4"><box left="300" top="200" width="40" height="30"/><attribute vehicle_type="others"/></target>
  </target_list></frame>
</sequence>""",
        encoding="utf-8",
    )
    cajas, ignoradas = medir_mvi.leer_xml(xml)
    assert ignoradas == [(0.0, 0.0, 100.0, 100.0)]
    assert [c.cuadro for c in cajas] == [0, 0]
    assert [c.clase for c in cajas] == ["automovil", "camion"]
    assert cajas[1].xyxy == (300.0, 200.0, 340.0, 230.0)
    assert medir_mvi.en_ignorada(cajas[0], ignoradas) and not medir_mvi.en_ignorada(cajas[1], ignoradas)
