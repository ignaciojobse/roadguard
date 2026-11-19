import pytest

from roadguard.m4_reglas import MotorReglas
from roadguard.m3_geometria.carriles import DetectorCambioCarril
from roadguard.m3_geometria.homografia import ProyectorCamino
from roadguard.m3_geometria.relaciones import calcular_relaciones
from roadguard.m3_geometria.trayectorias import HistorialCausal
from roadguard.tipos import (
    CambioCarril, Caja, Carril, EstadoCinematico, Homografia, NivelRiesgo,
    Regla, Relacion, Track, Umbrales,
)


def _estado(ident, n, t, carril=0, v=10.0, x=0.0, calibrado=True):
    return EstadoCinematico(
        ident, n, t, x if calibrado else None, 0.0 if calibrado else None,
        v if calibrado else None, carril, 0.9, calibrado,
    )


def _rel(seguidor, pred, n, t, carril=0, thw=2.0, ttc=None, calibrado=True):
    return Relacion(
        seguidor, pred, n, t, carril,
        10.0 if calibrado else None, thw if calibrado else None, ttc,
    )


def test_cercania_puntua_mientras_esta_activa_y_el_evento_llega_al_cerrar():
    m = MotorReglas()
    for n, t in enumerate([0.0, 1.0, 2.0]):
        estados = {1: _estado(1, n, t), 2: _estado(2, n, t, x=10.0)}
        rels = [_rel(1, 2, n, t, thw=1.0), _rel(2, None, n, t, thw=None)]
        eventos, puntajes = m.actualizar(t, estados, rels, [])
        assert eventos == []
    assert puntajes[1].puntaje == 40 and puntajes[1].nivel is NivelRiesgo.AMARILLO
    assert puntajes[2].puntaje == 0
    estados = {1: _estado(1, 3, 3.0), 2: _estado(2, 3, 3.0, x=30.0)}
    eventos, puntajes = m.actualizar(3.0, estados, [_rel(1, 2, 3, 3.0, thw=3.0), _rel(2, None, 3, 3.0, thw=None)], [])
    assert len(eventos) == 1 and eventos[0].regla is Regla.CERCANIA and eventos[0].t_fin == 2.0
    assert puntajes[1].puntaje == 40  # aun vigente
    assert m.finalizar() == []


def test_zigzag_y_corte_con_puntaje_acumulado_y_tope():
    m = MotorReglas()
    estados = {1: _estado(1, 0, 5.0, carril=1), 3: _estado(3, 0, 5.0, carril=1, x=-5.0)}
    rels = [_rel(1, None, 0, 5.0, carril=1, thw=None), _rel(3, 1, 0, 5.0, carril=1, thw=0.5)]
    cambios = [CambioCarril(1, 0, 1, 0.0, 1.0), CambioCarril(1, 1, 0, 2.0, 3.0), CambioCarril(1, 0, 1, 4.0, 5.0)]
    eventos, puntajes = m.actualizar(5.0, estados, rels, cambios)
    reglas = sorted(e.regla for e in eventos)
    assert reglas == [Regla.CORTE, Regla.ZIGZAG]
    corte = next(e for e in eventos if e.regla is Regla.CORTE)
    assert corte.id_vehiculo == 1 and corte.id_relacionado == 3
    assert puntajes[1].puntaje == 85 and puntajes[1].nivel is NivelRiesgo.ROJO
    assert puntajes[3].puntaje == 0


def test_sin_calibracion_no_rompe_y_deja_advertencia():
    m = MotorReglas()
    estados = {1: _estado(1, 0, 0.0, calibrado=False)}
    eventos, puntajes = m.actualizar(0.0, estados, [_rel(1, 2, 0, 0.0, calibrado=False)], [CambioCarril(1, 0, 1, -1.0, 0.0)])
    assert eventos == [] and puntajes[1].puntaje == 0
    assert m.advertencias


def test_cuadro_vacio_usa_siguiente_cuadro():
    m = MotorReglas()
    m.actualizar(0.0, {1: _estado(1, 0, 0.0)}, [_rel(1, None, 0, 0.0, thw=None)], [])
    eventos, puntajes = m.actualizar(1.0, {}, [], [])
    assert eventos == [] and puntajes == {}
    m.actualizar(2.0, {1: _estado(1, 2, 2.0)}, [_rel(1, None, 2, 2.0, thw=None)], [])


def test_estados_de_cuadros_distintos_se_rechazan():
    m = MotorReglas()
    with pytest.raises(ValueError):
        m.actualizar(0.0, {1: _estado(1, 0, 0.0), 2: _estado(2, 1, 0.0)}, [], [])


def test_finalizar_entrega_cercania_abierta_y_umbrales_se_propagan():
    m = MotorReglas(Umbrales(cercania_persistencia=0.5, aporte_cercania=10))
    for n, t in enumerate([0.0, 0.5]):
        _, puntajes = m.actualizar(t, {1: _estado(1, n, t)}, [_rel(1, 2, n, t, thw=1.0)], [])
    assert puntajes[1].puntaje == 10
    fin = m.finalizar()
    assert len(fin) == 1 and fin[0].aporte_puntaje == 10
    assert m.finalizar() == []


_CARRILES_GEOMETRICOS = [
    Carril(0, [(100, 0), (200, 0), (200, 320), (100, 320)]),
    Carril(1, [(200, 0), (300, 0), (300, 320), (200, 320)]),
]
_PROYECTOR_IDENTIDAD = ProyectorCamino(Homografia(
    [(0, 0), (320, 0), (320, 320), (0, 320)],
    [(0, 0), (0, 320), (320, 320), (320, 0)],
))


def _integrar_m3_m4(
    posiciones,
    *,
    carril_actor,
    geometria_actor=None,
    n_cuadros=100,
):
    """Alimenta Tracks sintéticos a M3 y las salidas M3 a MotorReglas."""
    historial = HistorialCausal(
        25.0, _PROYECTOR_IDENTIDAD, _CARRILES_GEOMETRICOS,
        ventana=1.0, min_muestras=3, min_duracion=0.3,
    )
    detector_cambio = DetectorCambioCarril(confianza_min=0.0, permanencia=1.0)
    motor = MotorReglas()
    eventos = []
    puntajes_por_cuadro = {}
    cambios_confirmados = []
    relaciones_por_cuadro = {}
    centralidades_actor = []
    for n in range(n_cuadros):
        t = n / 25.0
        estados = []
        cambios = []
        for ident in (1, 2):
            # posiciones devuelve las coordenadas longitudinales de actor y
            # seguidor; x de imagen es lateral y determina el polígono de carril.
            longitudinal = posiciones(n, ident)
            x_lateral = (190.0 if carril_actor(n) == 0 else 202.0) if ident == 1 else 250.0
            disponible = not (ident == 1 and geometria_actor is not None
                              and not geometria_actor(n))
            caja = Caja(x_lateral - 5, longitudinal - 10, x_lateral + 5, longitudinal)
            track = Track(ident, n, t, "automovil", 1.0, caja, (x_lateral, longitudinal))
            estado = historial.actualizar(
                track, (320, 320), geometria_disponible=disponible,
            )
            estados.append(estado)
            if ident == 1:
                if estado.carril is not None:
                    centralidades_actor.append(estado.confianza_carril)
                cambio = detector_cambio.actualizar(
                    ident, estado.carril, t, estado.confianza_carril,
                )
                if cambio is not None:
                    cambios.append(cambio)
                    cambios_confirmados.append(cambio)
        relaciones = calcular_relaciones(estados, n, t)
        relaciones_por_cuadro[n] = relaciones
        nuevos, puntajes = motor.actualizar(
            t, {e.id_vehiculo: e for e in estados}, relaciones, cambios,
        )
        eventos.extend(nuevos)
        puntajes_por_cuadro[n] = puntajes
    return (
        eventos, puntajes_por_cuadro, cambios_confirmados,
        relaciones_por_cuadro, centralidades_actor,
    )


def _cambio_actor(n):
    # El actor ya estabilizó su carril inicial; cruza con centralidad baja y
    # permanece en el carril geométrico nuevo hasta confirmar.
    return 0 if n < 31 else 1


def test_integracion_m3_m4_rf9_thw_bajo_antes_de_confirmacion_recupera_historial():
    def posiciones(n, ident):
        actor = 70.0 + 0.8 * n  # 20 m/s
        seguidor = actor - 5.0 if n <= 56 else 70.0 + 0.8 * 56 + 0.2 * (n - 56)
        return actor if ident == 1 else seguidor

    eventos, puntajes, cambios, relaciones, centralidades = _integrar_m3_m4(
        posiciones, carril_actor=_cambio_actor,
    )
    assert max(centralidades) < 0.6
    assert len(cambios) == 1
    assert cambios[0].t_confirmacion - cambios[0].t_cruce >= 1.0
    assert cambios[0].t_cruce == pytest.approx(31 / 25)
    assert cambios[0].t_confirmacion > cambios[0].t_cruce
    assert any(e.regla is Regla.CORTE and e.id_vehiculo == 1 for e in eventos)
    corte = next(e for e in eventos if e.regla is Regla.CORTE)
    assert corte.variables["t_observacion"] < cambios[0].t_confirmacion
    assert puntajes[56][1].nivel is NivelRiesgo.AMARILLO
    assert puntajes[56][1].puntaje >= Umbrales().aporte_corte
    assert any(r.id_seguidor == 2 and r.thw is not None
               and r.thw >= Umbrales().corte_thw_max
               for r in relaciones[80])


def test_integracion_m3_m4_rf9_ttc_bajo_con_thw_alto():
    def posiciones(n, ident):
        actor = 70.0 + 0.32 * n  # 8 m/s
        seguidor = actor - 35.0 if n <= 56 else 35.0 + 0.32 * 56 + 0.8 * (n - 56)
        return actor if ident == 1 else seguidor

    eventos, _, cambios, _, centralidades = _integrar_m3_m4(
        posiciones, carril_actor=_cambio_actor,
    )
    assert max(centralidades) < 0.6
    assert len(cambios) == 1
    assert any(e.regla is Regla.CORTE and e.variables["ttc"] < Umbrales().corte_ttc_max
               and e.variables["thw"] > Umbrales().corte_thw_max for e in eventos)


def test_integracion_m3_m4_rf9_cambio_completo_holgado_no_corta():
    def posiciones(n, ident):
        actor = 70.0 + 0.4 * n
        seguidor = actor - 40.0
        return actor if ident == 1 else seguidor

    eventos, _, cambios, _, _ = _integrar_m3_m4(
        posiciones, carril_actor=_cambio_actor,
    )
    assert len(cambios) == 1
    assert not any(e.regla is Regla.CORTE for e in eventos)


@pytest.mark.parametrize("corte_por_none", [False, True])
def test_integracion_m3_m4_rf9_cruce_incompleto_o_none_no_corta(corte_por_none):
    def carril(n):
        if n < 31:
            return 0
        if n < (40 if corte_por_none else 45):
            return 1
        return 0

    def geometria(n):
        return not (corte_por_none and n == 40)

    def posiciones(n, ident):
        actor = 70.0 + 0.4 * n
        return actor if ident == 1 else actor - 5.0

    eventos, _, cambios, _, _ = _integrar_m3_m4(
        posiciones, carril_actor=carril,
        geometria_actor=geometria if corte_por_none else None,
    )
    assert cambios == []
    assert not any(e.regla is Regla.CORTE for e in eventos)


def test_integracion_m3_m4_rf9_retentativa_no_reusa_cruce_ni_relacion_anterior():
    def carril(n):
        if n < 31:
            return 0
        if n < 40:
            return 1
        return 1

    def geometria(n):
        return n != 40

    def posiciones(n, ident):
        actor = 70.0 + 0.4 * n
        # THW bajo solo durante el primer intento; en la retentativa es holgado.
        gap = 5.0 if n < 40 else 40.0
        return actor if ident == 1 else actor - gap

    eventos, _, cambios, _, _ = _integrar_m3_m4(
        posiciones, carril_actor=carril, geometria_actor=geometria,
    )
    assert len(cambios) == 1
    assert cambios[0].t_cruce > 40 / 25
    assert not any(e.regla is Regla.CORTE for e in eventos)


def test_integracion_m3_m4_rf8_dos_cambios_geometricos_bajo_centralidad_puntuan_35():
    def carril(n):
        if n < 31:
            return 0
        if n < 57:
            return 1
        return 0

    def posiciones(n, ident):
        actor = 70.0 + 0.4 * n
        return actor if ident == 1 else actor - 40.0

    eventos, puntajes, cambios, _, centralidades = _integrar_m3_m4(
        posiciones, carril_actor=carril,
    )
    assert max(centralidades) < 0.6
    assert len(cambios) == 2
    assert cambios[1].t_cruce - cambios[0].t_cruce <= Umbrales().zigzag_ventana
    assert all(c.carril_origen != c.carril_destino for c in cambios)
    zigzags = [e for e in eventos if e.regla is Regla.ZIGZAG]
    assert len(zigzags) == 1
    assert zigzags[0].variables["n_cambios"] == 2.0
    assert zigzags[0].aporte_puntaje == 35
    assert puntajes[82][1].puntaje == 35
    assert puntajes[82][1].nivel is NivelRiesgo.AMARILLO


@pytest.mark.parametrize("un_cambio", [True, False])
def test_integracion_m3_m4_rf8_un_cambio_o_cruce_incompleto_no_puntua(un_cambio):
    def carril(n):
        if n < 31:
            return 0
        if un_cambio:
            return 1
        return 1 if n < 45 else 0

    def posiciones(n, ident):
        actor = 70.0 + 0.4 * n
        return actor if ident == 1 else actor - 40.0

    eventos, _, cambios, _, _ = _integrar_m3_m4(
        posiciones, carril_actor=carril,
    )
    assert (len(cambios) == 1) if un_cambio else (cambios == [])
    assert not any(e.regla is Regla.ZIGZAG for e in eventos)
