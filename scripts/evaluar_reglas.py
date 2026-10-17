"""T9 - F1 de reglas: trayectorias degradadas vs. referencia (seccion 2.5).

Ejemplo:
    python scripts/evaluar_reglas.py \\
        --trayectorias datos/trayectorias/highd_01.csv \\
        --config configs/camara_ejemplo.yaml \\
        --ruido 0.1 0.3 0.5 --perdida 0.05 --intercambio 0.002 \\
        --semillas 1 2 3 --tolerancia 1.0 \\
        --salida salidas/evaluacion/reglas_highd_01.json

La referencia se calcula con el motor de RoadGuard (M3 + M4) sobre las
trayectorias limpias; cada combinacion (ruido, semilla) se degrada, se
reestima la cinematica de forma causal y se vuelve a pasar por el mismo
motor. Las semillas y parametros quedan en el JSON (Paso 6).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
from dataclasses import asdict

from roadguard.m1_ingesta.config import cargar_configuracion
from roadguard.m5_salidas.registros import limpiar_json
from roadguard.m6_evaluacion.datasets import leer_estados_csv, recortar
from roadguard.m6_evaluacion.degradacion import CarrilesLaterales, degradar, reestimar_cinematica
from roadguard.m6_evaluacion.reglas import F1_OBJETIVO, evaluar_reglas, eventos_desde_estados
from roadguard.tipos import Regla, Umbrales


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--trayectorias", required=True)
    p.add_argument("--config", default=None, help="YAML de donde tomar umbrales y parametros de carril")
    p.add_argument("--ruido", type=float, nargs="+", default=[0.1, 0.3, 0.5], help="sigma en metros")
    p.add_argument("--perdida", type=float, default=0.05)
    p.add_argument("--intercambio", type=float, default=0.002)
    p.add_argument("--semillas", type=int, nargs="+", default=[1, 2, 3])
    p.add_argument("--tolerancia", type=float, default=1.0, help="segundos")
    p.add_argument("--sin-reasignar-carril", action="store_true")
    p.add_argument("--t-max", type=float, default=None)
    p.add_argument("--salida", required=True)
    args = p.parse_args(argv)

    umbrales, conf_carril, permanencia = Umbrales(), 0.6, 1.0
    if args.config:
        cfg = cargar_configuracion(args.config)
        umbrales, conf_carril, permanencia = cfg.umbrales, cfg.confianza_min_carril, cfg.permanencia_cambio_carril

    limpios, meta = leer_estados_csv(args.trayectorias)
    limpios = recortar(limpios, t_max=args.t_max)
    fps = float(meta.get("fps") or 0) or _fps_estimado(limpios)
    carriles = None if args.sin_reasignar_carril else CarrilesLaterales.desde_estados(limpios)

    referencia = eventos_desde_estados(limpios, umbrales, conf_carril, permanencia)
    corridas = []
    for ruido in args.ruido:
        for semilla in args.semillas:
            degradados = degradar(limpios, ruido, args.perdida, args.intercambio, semilla, carriles)
            obtenidos = eventos_desde_estados(
                reestimar_cinematica(degradados, fps), umbrales, conf_carril, permanencia
            )
            metricas = evaluar_reglas(referencia, obtenidos, args.tolerancia)
            corridas.append({"ruido": ruido, "semilla": semilla, "n_obtenidos": len(obtenidos), "metricas": metricas})
            print(f"ruido={ruido:.2f} semilla={semilla}: F1 global={metricas['global.f1']:.3f}")

    resumen = {}
    for ruido in args.ruido:
        f1s = [c["metricas"]["global.f1"] for c in corridas if c["ruido"] == ruido]
        resumen[str(ruido)] = {"f1_media": statistics.mean(f1s), "f1_min": min(f1s)}
    documento = {
        "trayectorias": os.path.abspath(args.trayectorias),
        "metadatos_trayectorias": meta,
        "fps": fps,
        "parametros": {
            "perdida": args.perdida,
            "intercambio": args.intercambio,
            "ruido": args.ruido,
            "semillas": args.semillas,
            "tolerancia": args.tolerancia,
            "reasignar_carril": carriles is not None,
            "umbrales": asdict(umbrales),
            "confianza_min_carril": conf_carril,
            "permanencia_cambio_carril": permanencia,
        },
        "referencia": {r.value: sum(1 for e in referencia if e.regla is r) for r in Regla},
        "corridas": corridas,
        "resumen": resumen,
        "criterio_f1": F1_OBJETIVO,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.salida)), exist_ok=True)
    with open(args.salida, "w", encoding="utf-8") as f:
        json.dump(limpiar_json(documento), f, ensure_ascii=False, indent=2)

    print("\n| Ruido (m) | F1 medio | F1 minimo | Cumple >= 0,75 |\n|---|---|---|---|")
    for ruido, r in resumen.items():
        print(f"| {ruido} | {r['f1_media']:.3f} | {r['f1_min']:.3f} | {'si' if r['f1_min'] >= F1_OBJETIVO else 'no'} |")
    print(f"\nEventos de referencia: {documento['referencia']}")
    return 0


def _fps_estimado(estados) -> float:
    ts = sorted({e.t for e in estados})
    pasos = [b - a for a, b in zip(ts, ts[1:]) if b > a]
    return 1.0 / statistics.median(pasos) if pasos else 10.0


if __name__ == "__main__":
    raise SystemExit(main())
