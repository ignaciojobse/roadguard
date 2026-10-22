"""Demo sintetica y determinista de RF7; no usa video, datos ni GPU."""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from roadguard.m3_geometria.relaciones import calcular_relaciones  # noqa: E402
from roadguard.m4_reglas.cercania import DetectorCercania  # noqa: E402
from roadguard.tipos import EstadoCinematico  # noqa: E402


def _frame(cuadro: int, t: float, calibrado: bool = True):
    posiciones = ((1, 20.0 * t), (2, 20.0 * t + 20.0))
    estados = [
        EstadoCinematico(
            id_vehiculo=ident,
            cuadro=cuadro,
            t=t,
            x_camino=x if calibrado else None,
            y_camino=0.0 if calibrado else None,
            velocidad=20.0 if calibrado else None,
            carril=0,
            confianza_carril=1.0,
            calibrado=calibrado,
        )
        for ident, x in posiciones
    ]
    return estados, calcular_relaciones(estados, cuadro, t)


def _ejecutar(times: list[float], *, interrupcion: bool = False, calibrado: bool = True):
    detector = DetectorCercania()
    total = []
    timeline = []
    advertencias = []
    for cuadro, t in enumerate(times):
        estados, relaciones = _frame(cuadro, t, calibrado)
        if interrupcion and t == 1.0:
            relaciones = [r for r in relaciones if r.id_seguidor != 1]
        resultado = detector.actualizar(cuadro, t, estados, relaciones)
        total.extend(resultado.cerrados)
        advertencias.extend(resultado.advertencias)
        timeline.append((t, bool(resultado.activos)))
    finalizados = detector.finalizar()
    total.extend(finalizados)
    return total, timeline, tuple(dict.fromkeys(advertencias)), tuple(finalizados)


def main() -> int:
    escenarios = [
        ("cercania 1.9 s", [i / 10 for i in range(20)], False, True, 0),
        ("cercania sostenida 3.0 s", [i / 10 for i in range(31)], False, True, 1),
        ("interrumpida antes de 2 s", [i / 10 for i in range(31)], True, True, 0),
        ("sin calibracion", [i / 10 for i in range(31)], False, False, 0),
    ]
    resultados = []
    for nombre, times, interrupcion, calibrado, esperado in escenarios:
        eventos, timeline, advertencias, finalizados = _ejecutar(
            times, interrupcion=interrupcion, calibrado=calibrado
        )
        resultados.append((nombre, eventos, timeline, esperado, advertencias, finalizados))
    sostenido = next(r for r in resultados if r[0] == "cercania sostenida 3.0 s")
    evento_sostenido = sostenido[1][0] if sostenido[1] else None
    error_sostenido = (
        evento_sostenido is None
        or evento_sostenido.variables["t_confirmacion"] != 2.0
        or evento_sostenido.t_inicio != 0.0
        or evento_sostenido.t_fin != 3.0
        or len(sostenido[5]) != 1
    )
    errores = [(n, e, esp) for n, e, _, esp, _, _ in resultados if len(e) != esp]
    if error_sostenido:
        errores.append(("cercania sostenida 3.0 s (intervalo/confirmacion)", [], 1))
    if errores:
        for nombre, eventos, esperado in errores:
            print(f"ERROR: {nombre}: eventos cerrados {len(eventos)}, esperado {esperado}", file=sys.stderr)
        return 1

    print("RoadGuard — DEMO SINTETICA / EXPERIMENTAL (no es determinacion legal)")
    print("RF7: cercania confirmada por persistencia; no se usa video ni datos externos.\n")
    for nombre, eventos, _, esperado, advertencias, _ in resultados:
        print(f"{nombre}: esperados={esperado}, cerrados={len(eventos)} — OK")
        for advertencia in advertencias:
            print(f"  advertencia: {advertencia}")
        for evento in eventos:
            v = evento.variables
            print(
                f"  vehiculo={evento.id_vehiculo} relacionado={evento.id_relacionado}; "
                f"confirmacion={v['t_confirmacion']:.1f}s; "
                f"intervalo=[{evento.t_inicio:.1f}, {evento.t_fin:.1f}]s; "
                f"velocidad={v['velocidad']:.1f}m/s THW={v['thw']:.2f}s "
                f"distancia={v['distancia']} TTC={v['ttc']}; "
                f"umbrales={evento.umbrales}; aporte={evento.aporte_puntaje} (no acumulado)"
            )
    print("\nCronologia sostenida (vehiculo seguidor):")
    for t in (0.0, 1.0, 1.9, 2.0, 2.5, 3.0):
        activa = next(
            (activa for n, _, timeline, _, _, _ in resultados
             if n == "cercania sostenida 3.0 s"
             for instante, activa in timeline if instante == t),
            False,
        )
        state = "activa" if activa else "sin alerta confirmada"
        print(f"  t={t:.1f}s: {state}")
    print("  fin de entrada: cerrada (intervalo hasta la ultima observacion valida)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
