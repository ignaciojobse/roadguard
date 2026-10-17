"""Verifica que el contrato de datos conserve los valores de la propuesta."""

from roadguard.tipos import Caja, Regla, Umbrales


def test_umbrales_por_defecto_coinciden_con_la_propuesta(umbrales: Umbrales) -> None:
    # RF7
    assert umbrales.cercania_velocidad_min == 5.0
    assert umbrales.cercania_thw_max == 1.5
    assert umbrales.cercania_persistencia == 2.0
    # RF8
    assert umbrales.zigzag_cambios_min == 2
    assert umbrales.zigzag_ventana == 10.0
    # RF9
    assert umbrales.corte_ventana_post_cambio == 2.0
    assert umbrales.corte_thw_max == 1.5
    assert umbrales.corte_ttc_max == 3.0
    # RF10
    assert umbrales.aporte_cercania == 40
    assert umbrales.aporte_zigzag == 35
    assert umbrales.aporte_corte == 50
    assert umbrales.puntaje_maximo == 100
    assert umbrales.vigencia_aporte == 5.0
    # RF11
    assert umbrales.banda_verde_max == 29
    assert umbrales.banda_amarillo_max == 59


def test_punto_calzada_es_centro_del_borde_inferior() -> None:
    caja = Caja(x1=10.0, y1=20.0, x2=30.0, y2=60.0)
    assert caja.punto_calzada == (20.0, 60.0)


def test_las_tres_reglas_definidas() -> None:
    assert {r.value for r in Regla} == {
        "cercania_peligrosa",
        "zigzag",
        "corte_de_carril",
    }
