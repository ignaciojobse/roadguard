"""RF11, RF12. Video anotado (m5_salidas), primera parte.

Casos minimos a cubrir:
  - La etiqueta lleva ID, clase y carril; sin estado de M3 no hay carril y
    fuera de todo carril se rotula "sin carril".
  - anotar_cuadro no modifica el cuadro original y dibuja sobre la caja.
  - Una caja que sale del cuadro se dibuja sin error.
  - La advertencia sin calibracion ocupa la franja superior, cabe en un
    cuadro angosto y no tapa etiquetas (Paso 5).
  - El escritor conserva FPS y resolucion, cuenta los cuadros y rechaza
    cuadros de otro tamano, FPS invalidos y sobrescribir la entrada.
"""

import numpy as np
import pytest

from roadguard.m1_ingesta.config import ADVERTENCIA_SIN_CALIBRACION_CORTA
from roadguard.m1_ingesta.video import iterar_cuadros, leer_metadatos
from roadguard.m5_salidas.dibujo import (
    COLOR_CAJA,
    anotar_cuadro,
    dibujar_advertencia,
    dibujar_vehiculo,
    etiqueta_vehiculo,
)
from roadguard.m5_salidas.escritor import ErrorSalida, EscritorVideo
from roadguard.tipos import Caja, Carril, EstadoCinematico, NivelRiesgo, PuntajeRiesgo, Track

ANCHO, ALTO = 320, 240


def _track(id_v=7, caja=Caja(100, 120, 160, 170), clase="automovil") -> Track:
    return Track(id_v, 0, 0.0, clase, 0.9, caja, caja.punto_calzada)


def _estado(id_v=7, carril=1) -> EstadoCinematico:
    return EstadoCinematico(id_v, 0, 0.0, None, None, None, carril, 1.0, False)


def _negro() -> np.ndarray:
    return np.zeros((ALTO, ANCHO, 3), np.uint8)


def test_etiqueta_con_y_sin_estado() -> None:
    assert etiqueta_vehiculo(_track()) == "ID 7 automovil"
    assert etiqueta_vehiculo(_track(), _estado(carril=1)) == "ID 7 automovil carril 1"
    assert etiqueta_vehiculo(_track(), _estado(carril=None)) == "ID 7 automovil sin carril"


@pytest.mark.parametrize(
    "estado",
    [
        _estado(carril=None),
        EstadoCinematico(7, 0, 0.0, None, None, None, 1, 1.0, False),
        EstadoCinematico(7, 0, 0.0, None, None, None, 1, 1.0, True),
    ],
)
def test_puntaje_cero_con_geometria_no_evaluable_es_verde_sin_eventos(estado, monkeypatch) -> None:
    puntaje = PuntajeRiesgo(7, 0.0, 0, NivelRiesgo.VERDE)
    assert "sin eventos" in etiqueta_vehiculo(_track(), estado, puntaje)
    colores = []
    monkeypatch.setattr("roadguard.m5_salidas.dibujo.cv2.rectangle",
                        lambda *args, **kwargs: colores.append(args[3]))
    dibujar_vehiculo(_negro(), _track(), estado, puntaje=puntaje)
    assert colores[0] == COLOR_CAJA


def test_carril_estimado_se_muestra() -> None:
    estado = EstadoCinematico(7, 0, 0.0, None, None, None, None, 0.2, False, 1)
    assert etiqueta_vehiculo(_track(), estado).endswith("carril 1 (estimado)")


def test_leyenda_visible_estable_con_puntajes_vacios_y_no_tapa_advertencia() -> None:
    original = _negro()
    estado = _estado(carril=1)
    advertencia = ADVERTENCIA_SIN_CALIBRACION_CORTA
    sin_mapa = anotar_cuadro(original, [_track()], [estado], advertencia=advertencia)
    mapa_vacio = anotar_cuadro(
        original, [_track()], [estado], advertencia=advertencia, puntajes={}
    )
    con_mapa = anotar_cuadro(
        original, [_track()], [estado], advertencia=advertencia,
        puntajes={7: PuntajeRiesgo(7, 0, 0, NivelRiesgo.VERDE)},
    )
    pie = slice(ALTO - 22, ALTO - 2)
    assert np.array_equal(mapa_vacio[pie], con_mapa[pie])
    assert not np.array_equal(sin_mapa[pie], mapa_vacio[pie])
    assert np.any(np.all(mapa_vacio[pie] == (45, 45, 45), axis=-1))
    assert np.any(np.all(mapa_vacio[pie] >= (150, 150, 150), axis=-1))
    alto_franja = dibujar_advertencia(_negro(), advertencia)
    assert np.array_equal(mapa_vacio[:alto_franja], sin_mapa[:alto_franja])
    assert not original.any()


def test_puntaje_evaluable_muestra_puntaje_y_banda() -> None:
    cero = PuntajeRiesgo(7, 0.0, 0, NivelRiesgo.VERDE)
    positivo = PuntajeRiesgo(7, 0.0, 40, NivelRiesgo.AMARILLO)
    evaluable = EstadoCinematico(7, 0, 0.0, 1.0, 2.0, 5.0, 1, 1.0, True)
    assert etiqueta_vehiculo(_track(), evaluable, cero).endswith("sin eventos")
    assert etiqueta_vehiculo(_track(), evaluable, positivo).endswith("puntaje 40 amarillo")


def test_puntaje_positivo_reciente_conserva_banda() -> None:
    estado = _estado(carril=None)
    puntaje = PuntajeRiesgo(7, 0.0, 40, NivelRiesgo.AMARILLO)
    texto = etiqueta_vehiculo(_track(), estado, puntaje)
    assert texto.endswith("puntaje 40 amarillo reciente")
    anotado = anotar_cuadro(_negro(), [_track()], [estado], puntajes={7: puntaje})
    assert (anotado[145, 100] == (0, 220, 255)).all()


def test_estado_sin_puntaje_conserva_etiqueta_legacy() -> None:
    assert etiqueta_vehiculo(_track(), EstadoCinematico(
        7, 0, 0.0, None, None, None, None, 1.0, False
    )) == "ID 7 automovil sin carril"


def test_rotulo_con_caja_negativa_queda_en_imagen(monkeypatch) -> None:
    import roadguard.m5_salidas.dibujo as dibujo

    original = _negro()
    anotado = original.copy()
    coords = []
    put_text = dibujo.cv2.putText
    monkeypatch.setattr(dibujo.cv2, "putText", lambda *args, **kwargs: (
        coords.append(args[2]), put_text(*args, **kwargs)
    )[1])
    dibujo.dibujar_vehiculo(anotado, _track(caja=Caja(-40, -30, 20, 15)))
    assert coords and 0 <= coords[-1][0] < ANCHO and 0 <= coords[-1][1] < ALTO
    assert not original.any()


def test_anotar_no_modifica_el_original_y_dibuja_la_caja() -> None:
    original = _negro()
    anotado = anotar_cuadro(original, [_track()], [_estado()])
    assert not original.any()
    # Borde izquierdo de la caja y punto de calzada.
    assert anotado[145, 100].any()
    assert anotado[170, 130].any()
    # Lejos de la caja no se dibuja nada.
    assert not anotado[230, 300].any()


def test_estado_se_asocia_por_id() -> None:
    otro = anotar_cuadro(_negro(), [_track(id_v=7)], [_estado(id_v=8, carril=3)])
    propio = anotar_cuadro(_negro(), [_track(id_v=7)], [_estado(id_v=7, carril=3)])
    # Con el estado de otro vehiculo la etiqueta es mas corta (sin carril).
    assert propio.sum() > otro.sum()


def test_caja_fuera_del_cuadro_no_falla() -> None:
    anotado = anotar_cuadro(_negro(), [_track(caja=Caja(-40, -30, 20, 15))])
    assert anotado.shape == (ALTO, ANCHO, 3)
    assert anotado[:15, :20].any()


def test_dibuja_carriles() -> None:
    carril = Carril(0, [(10, 230), (150, 230), (150, 100), (10, 100)])
    anotado = anotar_cuadro(_negro(), [], carriles=[carril])
    assert anotado[230, 80].any()


def test_advertencia_en_la_franja_superior_y_cabe() -> None:
    angosto = np.zeros((ALTO, 160, 3), np.uint8)
    dibujar_advertencia(angosto, ADVERTENCIA_SIN_CALIBRACION_CORTA)
    assert angosto[2, :].any(axis=-1).all()
    assert not angosto[ALTO - 1].any()


def test_la_advertencia_no_tapa_la_etiqueta() -> None:
    alto_franja = dibujar_advertencia(_negro(), ADVERTENCIA_SIN_CALIBRACION_CORTA)
    anotado = anotar_cuadro(
        _negro(),
        [_track(caja=Caja(100, 5, 160, 60))],
        advertencia=ADVERTENCIA_SIN_CALIBRACION_CORTA,
    )
    bajo_la_franja = anotado[alto_franja : alto_franja + 20, 102:140]
    assert (bajo_la_franja == COLOR_CAJA).all(axis=-1).any()


def test_escritor_conserva_fps_resolucion_y_cuadros(tmp_path) -> None:
    ruta = str(tmp_path / "salidas" / "anotado.mp4")
    with EscritorVideo(ruta, 25.0, ANCHO, ALTO) as escritor:
        for _ in range(12):
            escritor.escribir(_negro())
    assert escritor.n_cuadros == 12
    meta = leer_metadatos(ruta)
    assert (meta.ancho, meta.alto) == (ANCHO, ALTO)
    assert meta.fps == pytest.approx(25.0)
    assert sum(1 for _ in iterar_cuadros(ruta)) == 12


def test_escritor_rechaza_cuadro_de_otro_tamano(tmp_path) -> None:
    with EscritorVideo(str(tmp_path / "a.mp4"), 25.0, ANCHO, ALTO) as escritor:
        with pytest.raises(ErrorSalida):
            escritor.escribir(np.zeros((ALTO, ANCHO + 1, 3), np.uint8))


@pytest.mark.parametrize(
    "ruta, fps", [("a.avi", 25.0), ("a.mp4", 0.0), ("a.mp4", float("nan"))]
)
def test_escritor_rechaza_parametros_invalidos(tmp_path, ruta, fps) -> None:
    with pytest.raises(ErrorSalida):
        EscritorVideo(str(tmp_path / ruta), fps, ANCHO, ALTO)


def test_escritor_cerrado_no_escribe(tmp_path) -> None:
    escritor = EscritorVideo(str(tmp_path / "a.mp4"), 25.0, ANCHO, ALTO)
    escritor.cerrar()
    with pytest.raises(ErrorSalida):
        escritor.escribir(_negro())


def test_no_sobrescribe_la_entrada(video_sintetico) -> None:
    entrada = video_sintetico()
    with pytest.raises(ErrorSalida):
        EscritorVideo.desde_metadatos(entrada, leer_metadatos(entrada))


def test_video_entrada_a_salida(video_sintetico, tmp_path) -> None:
    entrada = video_sintetico(n_cuadros=8, fps=10.0)
    meta = leer_metadatos(entrada)
    salida = str(tmp_path / "anotado.mp4")
    with EscritorVideo.desde_metadatos(salida, meta) as escritor:
        for _, _, imagen in iterar_cuadros(entrada):
            escritor.escribir(
                anotar_cuadro(imagen, [_track()], advertencia=ADVERTENCIA_SIN_CALIBRACION_CORTA)
            )
    meta_salida = leer_metadatos(salida)
    assert meta_salida.fps == pytest.approx(meta.fps)
    assert sum(1 for _ in iterar_cuadros(salida)) == 8
