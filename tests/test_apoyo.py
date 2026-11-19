"""Regresiones puntuales manuales; no son ground truth ni validacion global."""

import numpy as np
import pytest

from roadguard.m3_geometria.apoyo import estimar_apoyo_longitudinal
from roadguard.m3_geometria.homografia import ProyectorCamino
from roadguard.tipos import Caja, Homografia


def _proyector(m):
    # Homografia construida por API publica; sustituir matriz permite casos
    # sinteticos exactos sin depender de la rutina de ajuste de OpenCV.
    p = ProyectorCamino(Homografia([(0, 0), (1, 0), (1, 1), (0, 1)],
                                   [(0, 0), (1, 0), (1, 1), (0, 1)]))
    p.matriz = np.asarray(m, dtype=float)
    p._signo_w = 1.0
    return p


def test_corrige_extremo_para_pendiente_negativa_y_positiva():
    p = _proyector([[1, 0, 0], [.25, 1, 0], [0, 0, 1]])
    assert estimar_apoyo_longitudinal(Caja(100, 100, 200, 200), p) == pytest.approx((150, 187.5))
    p = _proyector([[1, 0, 0], [-.25, 1, 0], [0, 0, 1]])
    assert estimar_apoyo_longitudinal(Caja(100, 100, 200, 200), p) == pytest.approx((150, 187.5))


def test_frontal_no_inventa_desplazamiento_y_resultado_es_puro():
    p = _proyector(np.eye(3))
    m = np.array([[1., 0, 7], [0, 1, -3], [0, 0, 1]])
    copia = m.copy()
    assert estimar_apoyo_longitudinal(Caja(100, 100, 200, 200), p, m) == pytest.approx((157, 197))
    np.testing.assert_array_equal(m, copia)


def test_direccion_vertical_y_sin_calibracion():
    vertical = _proyector([[0, 1, 0], [1, 0, 0], [0, 0, 1]])
    caja = Caja(100, 100, 200, 200)
    assert estimar_apoyo_longitudinal(caja, vertical) == pytest.approx((150, 200))
    assert estimar_apoyo_longitudinal(caja, ProyectorCamino(Homografia())) is None


@pytest.mark.parametrize("caja", [Caja(2, 1, 1, 3), Caja(0, 0, float("nan"), 2)])
def test_rechaza_caja_invalida(caja):
    assert estimar_apoyo_longitudinal(caja, _proyector(np.eye(3))) is None


@pytest.mark.parametrize("matriz", [
    np.zeros((3, 3)),
    np.array([[1, 0, 0], [0, 1, 0], [0, 0, np.nan]]),
])
def test_rechaza_transformacion_invalida_sin_mutar(matriz):
    original = matriz.copy()
    assert estimar_apoyo_longitudinal(Caja(1, 1, 3, 4), _proyector(np.eye(3)), matriz) is None
    np.testing.assert_array_equal(matriz, original)


def test_rechaza_punto_en_horizonte():
    p = _proyector([[1, 0, 0], [0, 1, 0], [1, 0, -150]])
    assert estimar_apoyo_longitudinal(Caja(100, 100, 200, 200), p) is None


def test_controles_puntuales_mvi39271():
    # Calibracion copiada de configs/MVI_39271.yaml; cajas/matrices de
    # salidas/geometria_v3/diagnostico/controles_geometria.json. Seleccion
    # manual puntual, independiente del artifact durante la ejecucion.
    from roadguard.m3_geometria.carriles import asignar_carril
    from roadguard.tipos import Carril

    h = Homografia(
        [(637,338),(543,361),(349,410),(161,455),(560,328),(463,348),(255,396),(69,435)],
        [(0,0),(6,0),(15,0),(21,0),(1.635,3.5),(7.635,3.5),(16.635,3.5),(22.635,3.5)])
    proyector = ProyectorCamino(h)
    # Controles: bus detenido ID5 cuadro 525, taxi ID11 cuadro 525,
    # minivan ID17 cuadro 700, azul ID35 cuadro 1075.
    controles = [
        # frame,id,bbox, (a,b,tx,c,d,ty), expected lane -- copied manually.
        (525,5,(671.8,195.8,814.5,274.0),(1.0001040415605251,-.0031789929988508938,-7.273348558099912,.0031789929988508938,1.0001040415605251,-3.018906962057301),3),
        (525,11,(258,360.6,428.5,442.9),(1.0001040415605251,-.0031789929988508938,-7.273348558099912,.0031789929988508938,1.0001040415605251,-3.018906962057301),0),
        (525,12,(551.8,298.2,661.7,357),(1.0001040415605251,-.0031789929988508938,-7.273348558099912,.0031789929988508938,1.0001040415605251,-3.018906962057301),1),
        (625,5,(675.6,193.5,815.3,275.8),(1.0004072352934437,-.0021107491747305008,-10.236324995986406,.0021107491747305008,1.0004072352934437,-.7346676297578915),3),
        (625,15,(412.1,303.4,536.3,365.4),(1.0004072352934437,-.0021107491747305008,-10.236324995986406,.0021107491747305008,1.0004072352934437,-.7346676297578915),1),
        (625,16,(619.4,295.1,718.4,352.2),(1.0004072352934437,-.0021107491747305008,-10.236324995986406,.0021107491747305008,1.0004072352934437,-.7346676297578915),0),
        (700,17,(247.7,353,422.2,437.8),(.9996229875179938,-.0025393296978713834,-11.16613672822961,.0025393296978713834,.9996229875179938,-1.1226249523760405),1),
        (1075,30,(411.8,220.5,639.1,335.9),(1.0005451457076417,-.006955551924754959,-18.829617948981394,.006955551924754959,1.0005451457076417,-5.348936870731365),3),
        (1075,34,(500.7,288.9,622.3,356.9),(1.0005451457076417,-.006955551924754959,-18.829617948981394,.006955551924754959,1.0005451457076417,-5.348936870731365),1),
        (1075,35,(680.2,276.9,748.4,324.6),(1.0005451457076417,-.006955551924754959,-18.829617948981394,.006955551924754959,1.0005451457076417,-5.348936870731365),1),
        (1125,30,(204.5,237.8,514.4,382.1),(1.0003434657912127,-.005589316708517395,-19.723361455124195,.005589316708517395,1.0003434657912127,-7.521513225846702),3),
        (1125,35,(333.3,336.2,459.9,411.2),(1.0003434657912127,-.005589316708517395,-19.723361455124195,.005589316708517395,1.0003434657912127,-7.521513225846702),1),
        (1425,47,(175,252.9,507,419.1),(1.0004660614291994,-.007539949230806696,-15.456677562206881,.007539949230806696,1.0004660614291994,-5.600614219182716),2),
    ]
    carriles = [
        Carril(0,[(924.6,285.2),(31.3,545),(-.6,497.2),(878.6,276.9)]),
        Carril(1,[(878.6,276.9),(-.6,497.2),(-28.1,455.9),(833.4,268.7)]),
        Carril(2,[(833.4,268.7),(-28.1,455.9),(-50.8,421.8),(791.6,261.2)]),
        Carril(3,[(791.6,261.2),(-50.8,421.8),(-82.6,374.1),(724.7,249.1)]),
    ]
    for cuadro, ident, coords, (a,b,tx,c,d,ty), esperado in controles:
        caja = Caja(*coords)
        matriz = np.array([[a,b,tx],[c,d,ty],[0,0,1]])
        punto = estimar_apoyo_longitudinal(caja, proyector, matriz)
        assert punto is not None
        # El punto devuelto está en referencia; no se deshace A.
        assert asignar_carril(punto, carriles)[0] == esperado, (cuadro, ident)
