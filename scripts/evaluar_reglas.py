"""F1 de reglas sobre NGSIM degradado (criterio de reglas de la seccion 2.5).

Calcula los eventos de referencia sobre la trayectoria limpia de NGSIM y los
compara con lo que produce el sistema (M3 + M4) cuando recibe esa misma
trayectoria con los defectos medidos en UA-DETRAC. Escribe un JSON con todos
los escenarios y muestra una tabla.

Uso, desde la raiz del repo (antes: bajar la muestra NGSIM y correr
`scripts/medir_ruido_m3.py` sobre MVI_39271 y MVI_40714):

    python scripts/evaluar_reglas.py
    python scripts/evaluar_reglas.py --semillas 5 \
        --salida knowledge/projects/entregas/evidencia/reglas/f1_ngsim.json

Escenarios:

- `m4_trayectoria_limpia`: M4 directo sobre los estados de NGSIM. Control:
  si las reglas cumplen su especificacion, el F1 es 1.
- `sistema_sin_ruido`: la trayectoria limpia pasa por M3 (25 Hz, velocidad
  causal, carril con confianza) y M4. Mide lo que cuesta M3 por si solo.
- `flujo_medido`: error de posicion, perdidas y cambios de ID medidos en
  MVI_39271, la secuencia principal (flujo medio). Es el escenario principal.
- `cola_densa_medida`: todo medido en MVI_40714 (40 % de perdidas).
- `flujo_solo_*`: un defecto por vez, para ver cual pesa mas.
- `flujo_ruido_x2`: el error de posicion al doble.
- `flujo_confianza_carril_0`: el escenario principal con
  `confianza_min_carril` = 0.

Los umbrales y la confianza de carril salen del YAML (`--config`, por
defecto `configs/MVI_39271.yaml`). Como referencia se repiten los escenarios
principales con la definicion original de la propuesta (sin tolerancia de
interrupcion en RF7 y confianza de carril 0,6), en `original`.

Los escenarios con azar se repiten con varias semillas y se reportan media y
desviacion estandar. La tolerancia del emparejamiento es 1 s.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import statistics
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from roadguard.m1_ingesta.config import cargar_configuracion  # noqa: E402
from roadguard.m6_evaluacion.degradacion import (  # noqa: E402
    AsignadorCarrilNGSIM,
    ParametrosDegradacion,
    evaluar_degradacion,
    eventos_m4_limpio,
    fraccion_con_respaldo,
)
from roadguard.m6_evaluacion.emparejamiento import evaluar_eventos, resultado_global  # noqa: E402
from roadguard.m6_evaluacion.ngsim import cargar_ngsim  # noqa: E402
from roadguard.m6_evaluacion.referencia import eventos_referencia  # noqa: E402
from roadguard.tipos import Regla, Umbrales  # noqa: E402

EVIDENCIA = RAIZ / "knowledge/projects/entregas/evidencia/reglas"
NOMBRES = {Regla.CERCANIA: "cercania", Regla.ZIGZAG: "zigzag", Regla.CORTE: "corte"}


def _leer(ruta: Path) -> dict:
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def parametros_medidos(ruido_posicion: dict, ruido_perdidas: dict) -> ParametrosDegradacion:
    pos = ruido_posicion["posicion"]
    perd = ruido_perdidas["perdidas"]
    ident = ruido_perdidas["identidad"]
    return ParametrosDegradacion(
        sigma_x=pos["sigma_x_m"],
        sigma_y=pos["sigma_y_m"],
        autocorrelacion_x=pos["autocorrelacion_x"],
        autocorrelacion_y=pos["autocorrelacion_y"],
        fraccion_perdida=perd["fraccion_perdida"],
        duracion_hueco=perd["duracion_media_hueco_s"],
        cambios_id_por_s=ident["cambios_id_por_vehiculo_s"],
        fps=ruido_perdidas["fps"],
    )


def _metricas(por_regla, respaldo=None) -> dict:
    salida = {}
    for regla, nombre in NOMBRES.items():
        r = por_regla.get(regla)
        if r is None:
            continue
        salida[nombre] = {
            "vp": r.verdaderos_positivos,
            "fp": r.falsos_positivos,
            "fn": r.falsos_negativos,
            "precision": r.precision,
            "recobrado": r.recobrado,
            "f1": r.f1,
            "con_respaldo": None if respaldo is None else respaldo.get(regla),
        }
    g = resultado_global(por_regla)
    salida["global"] = {
        "vp": g.verdaderos_positivos,
        "fp": g.falsos_positivos,
        "fn": g.falsos_negativos,
        "precision": g.precision,
        "recobrado": g.recobrado,
        "f1": g.f1,
    }
    return salida


def _resumir(corridas: list[dict]) -> dict:
    """Media y desviacion de cada metrica sobre las semillas."""
    resumen: dict = {}
    for clave in corridas[0]:
        resumen[clave] = {}
        for metrica in corridas[0][clave]:
            valores = [c[clave][metrica] for c in corridas if c[clave][metrica] is not None]
            if not valores:
                resumen[clave][metrica] = None
                continue
            media = statistics.fmean(valores)
            resumen[clave][metrica] = {
                "media": round(media, 4),
                "desv": round(statistics.pstdev(valores), 4) if len(valores) > 1 else 0.0,
            }
    return resumen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ngsim", default=str(RAIZ / "datos/ngsim/us101_muestra.csv"))
    parser.add_argument("--ruido-flujo", default=str(EVIDENCIA / "ruido_MVI_39271.json"))
    parser.add_argument("--ruido-denso", default=str(EVIDENCIA / "ruido_MVI_40714.json"))
    parser.add_argument("--semillas", type=int, default=5)
    parser.add_argument("--config", default=str(RAIZ / "configs/MVI_39271.yaml"))
    parser.add_argument("--salida", default=str(EVIDENCIA / "f1_ngsim.json"))
    args = parser.parse_args(argv)

    cfg = cargar_configuracion(args.config)
    cuadros = cargar_ngsim(args.ngsim)
    asignador = AsignadorCarrilNGSIM.desde_cuadros(cuadros)
    ruido_flujo = _leer(Path(args.ruido_flujo))
    ruido_denso = _leer(Path(args.ruido_denso))
    flujo = parametros_medidos(ruido_flujo, ruido_flujo)
    denso = parametros_medidos(ruido_denso, ruido_denso)

    configurada, detalle, n_ref = _evaluar(
        cuadros, asignador, flujo, denso, cfg.umbrales, cfg.confianza_min_carril,
        args.semillas, completo=True,
    )
    original, _, n_ref_original = _evaluar(
        cuadros, asignador, flujo, denso, Umbrales(), 0.6, args.semillas, completo=False,
    )
    documento = {
        "ngsim": str(Path(args.ngsim).relative_to(RAIZ)) if Path(args.ngsim).is_relative_to(RAIZ) else args.ngsim,
        "vehiculos": len({e.id_vehiculo for c in cuadros for e in c.estados}),
        "duracion_s": cuadros[-1].t,
        "tolerancia_s": 1.0,
        "meta_f1": 0.75,
        "configuracion": {
            "archivo": str(Path(args.config).relative_to(RAIZ)) if Path(args.config).is_relative_to(RAIZ) else args.config,
            "confianza_min_carril": cfg.confianza_min_carril,
            "cercania_tolerancia_interrupcion": cfg.umbrales.cercania_tolerancia_interrupcion,
        },
        "eventos_referencia": n_ref,
        "escenarios": detalle,
        "resultados": configurada,
        "original": {
            "descripcion": "definicion de la propuesta: sin tolerancia en RF7, confianza de carril 0,6",
            "eventos_referencia": n_ref_original,
            "resultados": original,
        },
    }
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(documento, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Configuracion {documento['configuracion']}; referencia {n_ref}")
    _tabla(configurada)
    print(f"Definicion original; referencia {n_ref_original}")
    _tabla(original)
    return 0


def _tabla(resultados: dict) -> None:
    print(f"{'escenario':28s} {'global':>8s} {'cercania':>9s} {'zigzag':>8s} {'corte':>8s} {'respaldo cerc.':>15s}")
    for nombre, r in resultados.items():
        def f1(clave):
            v = r[clave]["f1"]
            return "—" if v is None else f"{(v['media'] if isinstance(v, dict) else v):.3f}"
        resp = r["cercania"]["con_respaldo"]
        resp = "—" if resp is None else f"{(resp['media'] if isinstance(resp, dict) else resp):.3f}"
        print(f"{nombre:28s} {f1('global'):>8s} {f1('cercania'):>9s} {f1('zigzag'):>8s} {f1('corte'):>8s} {resp:>15s}")


def _evaluar(cuadros, asignador, flujo, denso, umbrales, confianza, semillas, completo):
    referencia = eventos_referencia(cuadros, umbrales)

    escenarios: dict[str, tuple[ParametrosDegradacion, float, bool]] = {
        "sistema_sin_ruido": (ParametrosDegradacion(fps=flujo.fps), confianza, False),
        "flujo_medido": (flujo, confianza, True),
        "cola_densa_medida": (denso, confianza, True),
        "flujo_solo_posicion": (
            dataclasses.replace(flujo, fraccion_perdida=0.0, cambios_id_por_s=0.0),
            confianza, True,
        ),
        "flujo_solo_perdidas": (
            dataclasses.replace(flujo, sigma_x=0.0, sigma_y=0.0, cambios_id_por_s=0.0),
            confianza, True,
        ),
        "flujo_solo_cambios_id": (
            dataclasses.replace(flujo, sigma_x=0.0, sigma_y=0.0, fraccion_perdida=0.0),
            confianza, True,
        ),
        "flujo_ruido_x2": (flujo.escalado(2.0), confianza, True),
        "flujo_confianza_carril_0": (flujo, 0.0, True),
    }

    if not completo:
        escenarios = {k: escenarios[k] for k in ("sistema_sin_ruido", "flujo_medido", "cola_densa_medida")}
    limpio = eventos_m4_limpio(cuadros, umbrales)
    por_regla = evaluar_eventos(limpio, referencia)
    respaldo = {
        regla: fraccion_con_respaldo(
            [d for d in limpio if d.regla == regla], [r for r in referencia if r.regla == regla]
        )
        for regla in Regla
    }
    resultados: dict = {"m4_trayectoria_limpia": _metricas(por_regla, respaldo)}
    detalle: dict = {}
    for nombre, (p, conf, con_azar) in escenarios.items():
        rango = range(semillas) if con_azar else range(1)
        corridas = []
        for s in rango:
            r = evaluar_degradacion(
                cuadros, dataclasses.replace(p, semilla=s), umbrales, referencia, asignador,
                confianza_min_carril=conf,
            )
            corridas.append(_metricas(r.por_regla, r.con_respaldo))
        resultados[nombre] = corridas[0] if len(corridas) == 1 else _resumir(corridas)
        detalle[nombre] = {
            "parametros": dataclasses.asdict(p),
            "confianza_min_carril": conf,
            "semillas": len(corridas),
        }
        print(f"{nombre}: listo", file=sys.stderr)

    n_ref = {NOMBRES[r]: sum(e.regla == r for e in referencia) for r in Regla}
    return resultados, detalle, n_ref


if __name__ == "__main__":
    raise SystemExit(main())
