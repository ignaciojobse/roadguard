import cv2
import numpy as np
import pytest

from roadguard.m3_geometria.movimiento import CompensadorCamara


ALTO, ANCHO = 240, 320
ROI = [(70, 80), (250, 80), (310, 239), (10, 239)]


def _imagen() -> np.ndarray:
    rng = np.random.default_rng(731)
    imagen = np.zeros((ALTO, ANCHO), dtype=np.uint8)
    # Edificios/fondo texturado concentrado en la zona superior fuera de la ROI.
    for _ in range(100):
        x, y = int(rng.integers(3, ANCHO - 12)), int(rng.integers(3, 68))
        cv2.rectangle(imagen, (x, y), (x + 5, y + 5), int(rng.integers(80, 255)), -1)
    return cv2.cvtColor(imagen, cv2.COLOR_GRAY2BGR)


def _mover(imagen: np.ndarray, dx: float, dy: float, grados: float) -> np.ndarray:
    centro = (ANCHO / 2, ALTO / 2)
    matriz = cv2.getRotationMatrix2D(centro, grados, 1.0)
    matriz[:, 2] += (dx, dy)
    return cv2.warpAffine(imagen, matriz, (ANCHO, ALTO))


def test_recupera_transformacion_referencia_y_conversion_bidireccional():
    base = _imagen()
    compensador = CompensadorCamara(ROI)
    assert compensador.actualizar(base).valido
    actual = _mover(base, 4, -3, 1.2)
    resultado = compensador.actualizar(actual)
    assert resultado.valido
    punto = (35.0, 35.0)
    punto_actual = _mover_matrix()[:, :2] @ np.asarray(punto) + _mover_matrix()[:, 2]
    recuperado = resultado.transformar_punto_actual_a_referencia(tuple(punto_actual))
    assert recuperado == pytest.approx(punto, abs=1.0)
    ida = resultado.transformar_puntos_referencia_a_actual([punto])
    assert ida is not None
    assert ida[0] == pytest.approx(tuple(punto_actual), abs=1.0)


def _mover_matrix():
    matriz = cv2.getRotationMatrix2D((ANCHO / 2, ALTO / 2), 1.2, 1.0)
    matriz[:, 2] += (4, -3)
    return matriz


def test_cambio_fuerte_solo_en_roi_no_arrastra_movimiento():
    base = _imagen()
    compensador = CompensadorCamara(ROI)
    compensador.actualizar(base)
    dx, dy, angulo = 3, 2, 0.5
    actual = _mover(base, dx, dy, angulo)
    roi = np.zeros((ALTO, ANCHO), dtype=np.uint8)
    cv2.fillPoly(roi, [np.asarray(ROI, dtype=np.int32)], 255)
    actual[roi != 0] = 255 - actual[roi != 0]
    valido = compensador.actualizar(actual)
    assert valido.valido
    punto = (35.0, 35.0)
    punto_actual = _matriz(dx, dy, angulo)[:, :2] @ punto + _matriz(dx, dy, angulo)[:, 2]
    assert valido.transformar_punto_actual_a_referencia(tuple(punto_actual)) == pytest.approx(
        punto, abs=1.0
    )


def test_fallo_tras_frame_valido_no_reutiliza_matriz_previa():
    base = _imagen()
    compensador = CompensadorCamara(ROI)
    compensador.actualizar(base)
    assert compensador.actualizar(_mover(base, 3, 2, 0.5)).valido
    sin_fondo = compensador.actualizar(np.zeros_like(base))
    assert not sin_fondo.valido
    assert sin_fondo.referencia_a_actual is None
    assert sin_fondo.actual_a_referencia is None
    assert sin_fondo.transformar_punto_actual_a_referencia((20, 20)) is None


def test_referencia_negra_no_intenta_usar_descriptores_ausentes():
    negro = np.zeros((ALTO, ANCHO, 3), dtype=np.uint8)
    compensador = CompensadorCamara(ROI)
    inicial = compensador.actualizar(negro)
    assert not inicial.valido
    assert "textura" in inicial.motivo
    siguiente = compensador.actualizar(_imagen())
    assert not siguiente.valido
    assert siguiente.motivo == "referencia sin textura suficiente"
    assert siguiente.actual_a_referencia is None


def test_prefijos_causales_independientes():
    base = _imagen()
    a, b = CompensadorCamara(ROI), CompensadorCamara(ROI)
    prefijo_a = [a.actualizar(base), a.actualizar(_mover(base, 2, 1, 0.4))]
    prefijo_b = [b.actualizar(base), b.actualizar(_mover(base, 2, 1, 0.4))]
    assert prefijo_a[1].valido and prefijo_b[1].valido
    assert prefijo_a[1].actual_a_referencia == pytest.approx(prefijo_b[1].actual_a_referencia)


def test_tamano_distinto_invalida():
    base = _imagen()
    compensador = CompensadorCamara(ROI)
    compensador.actualizar(base)
    cambio = compensador.actualizar(np.zeros((ALTO + 1, ANCHO, 3), dtype=np.uint8))
    assert not cambio.valido
    assert cambio.motivo == "cambio de tamaño de imagen"


@pytest.mark.parametrize("kwargs", [
    {"max_features": 2}, {"min_inliers": 2}, {"max_features": 3, "min_inliers": 4},
    {"max_features": 0}, {"min_inliers": 12.5}, {"umbral_ransac": 0},
    {"umbral_ransac": float("nan")}, {"umbral_ransac": float("inf")},
])
def test_rechaza_parametros_invalidos(kwargs):
    with pytest.raises(ValueError):
        CompensadorCamara(ROI, **kwargs)


@pytest.mark.parametrize("region", [[(0, 0), (1, 0)], [(0, 0), (1, 0), (float("nan"), 1)]])
def test_rechaza_roi_invalida(region):
    with pytest.raises(ValueError):
        CompensadorCamara(region)


def test_acepta_gris_bgr_y_no_muta_entrada():
    gris = cv2.cvtColor(_imagen(), cv2.COLOR_BGR2GRAY)
    original = gris.copy()
    compensador = CompensadorCamara(ROI)
    assert compensador.actualizar(gris).valido
    assert np.array_equal(gris, original)
    bgr = _imagen()
    original_bgr = bgr.copy()
    assert compensador.actualizar(_mover(bgr, 2, 1, 0.4)).valido
    assert np.array_equal(bgr, original_bgr)


def _matriz(dx, dy, grados):
    matriz = cv2.getRotationMatrix2D((ANCHO / 2, ALTO / 2), grados, 1.0)
    matriz[:, 2] += (dx, dy)
    return matriz
