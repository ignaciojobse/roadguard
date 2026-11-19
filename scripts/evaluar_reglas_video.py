"""F1 de reglas sobre video real: RoadGuard contra la anotacion de UA-DETRAC.

Complementa a `scripts/evaluar_reglas.py` (NGSIM degradado). Aca no se
simula nada: los eventos del sistema son los de `eventos.csv` de una corrida
real y la referencia sale de las cajas anotadas a mano de la misma
secuencia, llevadas a metros con la misma homografia y los mismos umbrales
del YAML (`m6_evaluacion.referencia_video`). La comparacion es de punta a
punta: detector, seguidor, geometria y reglas.

Requiere una corrida con `--tracks` (para traducir los IDs del sistema a los
IDs anotados) y una secuencia calibrada: sin homografia no hay metros y la
referencia queda vacia.

Uso, desde la raiz del repo:

    python scripts/evaluar_reglas_video.py MVI_39271 MVI_40714
    python scripts/evaluar_reglas_video.py MVI_39271 --corridas salidas

Limites: la referencia comparte la calibracion con el sistema (no juzga el
error de la homografia) y en una secuencia de un minuto hay pocos eventos,
asi que el F1 por regla tiene mucha varianza.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "scripts"))

from medir_mvi import en_ignorada, leer_tracks, leer_xml  # noqa: E402
from roadguard.m1_ingesta.config import cargar_configuracion  # noqa: E402
from roadguard.m3_geometria.homografia import ProyectorCamino  # noqa: E402
from roadguard.m6_evaluacion.degradacion import fraccion_con_respaldo  # noqa: E402
from roadguard.m6_evaluacion.emparejamiento import evaluar_eventos, resultado_global  # noqa: E402
from roadguard.m6_evaluacion.referencia import eventos_referencia  # noqa: E402
from roadguard.m6_evaluacion.referencia_video import (  # noqa: E402
    Caja,
    asignar_ids,
    cuadros_desde_cajas,
    leer_eventos_csv,
    traducir,
)
from roadguard.tipos import Regla  # noqa: E402

NOMBRES = {Regla.CERCANIA: "cercania", Regla.ZIGZAG: "zigzag", Regla.CORTE: "corte"}


def _r(x):
    return None if x is None else round(x, 4)


def evaluar(secuencia: str, corrida: Path, ruta_cfg: Path, ruta_xml: Path) -> dict:
    cfg = cargar_configuracion(str(ruta_cfg))
    proyector = ProyectorCamino(cfg.homografia)
    with open(corrida / "resumen.json", encoding="utf-8") as f:
        ejecucion = json.load(f)["ejecucion"]
    fps = ejecucion["fps_video"]
    n_cuadros = ejecucion["n_cuadros_procesados"]
    anotadas, ignoradas = leer_xml(ruta_xml)
    referencia_cajas = [
        Caja(c.cuadro, c.ident, c.xyxy)
        for c in anotadas
        if c.cuadro < n_cuadros and not en_ignorada(c, ignoradas)
    ]
    detectadas = [Caja(c.cuadro, c.ident, c.xyxy) for c in leer_tracks(corrida / "tracks.csv")]

    cuadros = cuadros_desde_cajas(
        referencia_cajas, fps, proyector, cfg.carriles, cfg.region_interes
    )
    referencia = eventos_referencia(cuadros, cfg.umbrales, cfg.permanencia_cambio_carril)
    sistema = traducir(leer_eventos_csv(corrida / "eventos.csv"), asignar_ids(detectadas, referencia_cajas))
    por_regla = evaluar_eventos(sistema, referencia)

    resultado = {
        "secuencia": secuencia,
        "calibrada": proyector.disponible,
        "corrida": str(corrida.relative_to(RAIZ)) if corrida.is_relative_to(RAIZ) else str(corrida),
        "eventos_referencia": {NOMBRES[k]: v for k, v in Counter(e.regla for e in referencia).items()},
        "eventos_sistema": {NOMBRES[k]: v for k, v in Counter(e.regla for e in sistema).items()},
        "por_regla": {},
    }
    for regla, nombre in NOMBRES.items():
        r = por_regla.get(regla)
        if r is None:
            continue
        resultado["por_regla"][nombre] = {
            "vp": r.verdaderos_positivos, "fp": r.falsos_positivos, "fn": r.falsos_negativos,
            "precision": _r(r.precision), "recobrado": _r(r.recobrado), "f1": _r(r.f1),
        }
    g = resultado_global(por_regla) if por_regla else None
    resultado["global"] = None if g is None else {
        "vp": g.verdaderos_positivos, "fp": g.falsos_positivos, "fn": g.falsos_negativos,
        "precision": _r(g.precision), "recobrado": _r(g.recobrado), "f1": _r(g.f1),
    }
    resultado["con_respaldo"] = _r(fraccion_con_respaldo(sistema, referencia))
    return resultado


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("secuencias", nargs="+")
    parser.add_argument("--corridas", default=str(RAIZ / "salidas"), help="Carpeta con <secuencia>/")
    parser.add_argument("--configs", default=str(RAIZ / "configs"))
    parser.add_argument(
        "--salida", default=str(RAIZ / "knowledge/projects/entregas/evidencia/reglas/f1_video.json")
    )
    args = parser.parse_args(argv)

    resultados = []
    for s in args.secuencias:
        r = evaluar(
            s,
            Path(args.corridas) / s,
            Path(args.configs) / f"{s}.yaml",
            RAIZ / "datos" / "ua-detrac" / s / f"{s}.xml",
        )
        resultados.append(r)
        g = r["global"]
        f1 = "sin eventos en ningun lado" if g is None or g["f1"] is None else f"F1 global {g['f1']:.3f}"
        print(f"{s}: referencia {r['eventos_referencia']}, sistema {r['eventos_sistema']}, {f1}")
        for nombre, m in r["por_regla"].items():
            print(f"  {nombre:9s} VP {m['vp']} FP {m['fp']} FN {m['fn']}  F1 {m['f1']}")
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        json.dump({"tolerancia_s": 1.0, "secuencias": resultados}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
