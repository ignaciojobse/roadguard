"""M6 - Precision, recobrado y F1 de los eventos de reglas.

Criterio de aceptacion (seccion 2.5): F1 >= 0,75 al comparar alertas desde
trayectorias degradadas con eventos de referencia calculados desde highD o
NGSIM.
"""

from __future__ import annotations

from roadguard.m3_geometria.carriles import DetectorCambioCarril
from roadguard.m3_geometria.relaciones import calcular_relaciones
from roadguard.m4_reglas.motor import MotorReglas
from roadguard.m6_evaluacion.datasets import por_cuadro
from roadguard.tipos import EstadoCinematico, Evento, Regla, Umbrales

F1_OBJETIVO = 0.75


def eventos_desde_estados(
    estados: list[EstadoCinematico],
    umbrales: Umbrales,
    confianza_min_carril: float = 0.6,
    permanencia_cambio_carril: float = 1.0,
) -> list[Evento]:
    """Ejecuta M3 (cambios y relaciones) y M4 sobre trayectorias en el plano
    del camino, cuadro a cuadro y en orden causal. Es la misma cadena del
    pipeline a partir de `EstadoCinematico`, para que referencia y
    trayectorias degradadas se evaluen con el mismo motor (T3)."""
    detector_cambios = DetectorCambioCarril(confianza_min_carril, permanencia_cambio_carril)
    motor = MotorReglas(umbrales)
    eventos: list[Evento] = []
    for cuadro, t, grupo in por_cuadro(estados):
        cambios = []
        for e in grupo:
            c = detector_cambios.actualizar(e.id_vehiculo, e.carril, t, e.confianza_carril)
            if c is not None:
                cambios.append(c)
        relaciones = calcular_relaciones(grupo, cuadro, t)
        eventos.extend(motor.procesar_cuadro(t, grupo, relaciones, cambios))
    return eventos


def emparejar(
    referencia: list[Evento], obtenidos: list[Evento], tolerancia_temporal: float
) -> list[tuple[Evento, Evento]]:
    """Empareja uno a uno por regla y vehiculo; dos eventos coinciden si sus
    intervalos, ampliados en `tolerancia_temporal`, se solapan. Se prioriza
    la menor diferencia entre instantes de activacion."""
    candidatos = []
    for i, r in enumerate(referencia):
        for j, o in enumerate(obtenidos):
            if r.regla is not o.regla or r.id_vehiculo != o.id_vehiculo:
                continue
            if o.t_inicio <= r.t_fin + tolerancia_temporal and o.t_fin >= r.t_inicio - tolerancia_temporal:
                candidatos.append((abs(o.t_fin - r.t_fin), i, j))
    usados_r, usados_o, pares = set(), set(), []
    for _, i, j in sorted(candidatos):
        if i in usados_r or j in usados_o:
            continue
        usados_r.add(i)
        usados_o.add(j)
        pares.append((referencia[i], obtenidos[j]))
    return pares


def evaluar_reglas(
    eventos_referencia: list[Evento],
    eventos_obtenidos: list[Evento],
    tolerancia_temporal: float,
) -> dict[str, float]:
    """Devuelve precision, recobrado y F1 por regla y global.

    Claves: `<regla>.precision`, `<regla>.recobrado`, `<regla>.f1`,
    `<regla>.vp`, `<regla>.fp`, `<regla>.fn`, y lo mismo con `global`.
    Sin eventos que evaluar, precision o recobrado valen 1 (nada que errar).
    """
    pares = emparejar(eventos_referencia, eventos_obtenidos, tolerancia_temporal)
    resultado: dict[str, float] = {}
    tot_vp = tot_fp = tot_fn = 0
    for regla in Regla:
        n_ref = sum(1 for e in eventos_referencia if e.regla is regla)
        n_obt = sum(1 for e in eventos_obtenidos if e.regla is regla)
        vp = sum(1 for r, _ in pares if r.regla is regla)
        fp, fn = n_obt - vp, n_ref - vp
        resultado.update(_prf(regla.value, vp, fp, fn))
        tot_vp, tot_fp, tot_fn = tot_vp + vp, tot_fp + fp, tot_fn + fn
    resultado.update(_prf("global", tot_vp, tot_fp, tot_fn))
    return resultado


def _prf(nombre: str, vp: int, fp: int, fn: int) -> dict[str, float]:
    p = vp / (vp + fp) if vp + fp > 0 else 1.0
    r = vp / (vp + fn) if vp + fn > 0 else 1.0
    f1 = 2 * p * r / (p + r) if p + r > 0 else 0.0
    return {
        f"{nombre}.precision": p,
        f"{nombre}.recobrado": r,
        f"{nombre}.f1": f1,
        f"{nombre}.vp": float(vp),
        f"{nombre}.fp": float(fp),
        f"{nombre}.fn": float(fn),
    }
