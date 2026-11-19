"""Mide el error de posicion de M2+M3 contra UA-DETRAC (insumo de la degradacion).

La degradacion de trayectorias del PRD de evaluacion pide que las magnitudes
del ruido "se tomen del error que se mida en M3, no se inventen". Este
script las mide sobre una corrida real: empareja, cuadro a cuadro, las cajas
de `tracks.csv` con las del XML (hungaro, IoU >= 0,5), proyecta el punto de
calzada de ambas con la homografia del YAML y compara en metros.

Uso, desde la raiz del repo:

    python scripts/medir_ruido_m3.py MVI_40714
    python scripts/medir_ruido_m3.py MVI_40714 --corrida salidas/MVI_40714 \
        --salida knowledge/projects/entregas/evidencia/reglas/ruido_MVI_40714.json

Que se reporta:

- `posicion`: sesgo (mediana) y desviacion robusta (1,4826 x MAD) del error
  longitudinal `x` y lateral `y`, mas la autocorrelacion de un cuadro a otro
  (el error de un detector no es independiente entre cuadros).
- `perdidas`: fraccion de observaciones de referencia sin deteccion dentro
  de la region de interes, y duracion media de cada hueco (oclusion).
- `identidad`: cambios de ID por vehiculo y por segundo observado.

Solo se usa la region de interes, que es lo que el sistema evalua.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "scripts"))

from medir_mvi import (  # noqa: E402
    IOU_MIN,
    en_ignorada,
    iou_matriz,
    leer_tracks,
    leer_xml,
    por_cuadro,
    punto_calzada,
)
from roadguard.m1_ingesta.config import cargar_configuracion  # noqa: E402
from roadguard.m3_geometria.homografia import ProyectorCamino  # noqa: E402
from roadguard.poligonos import punto_en_poligono  # noqa: E402

ESCALA_MAD = 1.4826


def _robusta(valores: np.ndarray) -> tuple[float, float]:
    """(mediana, 1,4826 x MAD): sesgo y desviacion sin que pesen los atipicos."""
    mediana = float(np.median(valores))
    return mediana, float(ESCALA_MAD * np.median(np.abs(valores - mediana)))


def _autocorrelacion(series: dict[int, list[tuple[int, float]]]) -> float | None:
    """Correlacion entre el error de un cuadro y el del siguiente, mismo vehiculo."""
    a, b = [], []
    for puntos in series.values():
        puntos.sort()
        media = np.mean([v for _, v in puntos])
        for (c0, v0), (c1, v1) in zip(puntos, puntos[1:]):
            if c1 == c0 + 1:
                a.append(v0 - media)
                b.append(v1 - media)
    if len(a) < 10:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def medir_ruido(ref, det, proyector: ProyectorCamino, fps: float) -> dict:
    ref_c, det_c = por_cuadro(ref), por_cuadro(det)
    errores_x, errores_y = [], []
    serie_x: dict[int, list[tuple[int, float]]] = defaultdict(list)
    serie_y: dict[int, list[tuple[int, float]]] = defaultdict(list)
    visto: dict[int, list[tuple[int, bool]]] = defaultdict(list)
    ultimo: dict[int, int] = {}
    cambios_id = 0
    for cuadro in sorted(ref_c):
        refs = ref_c[cuadro]
        dets = det_c.get(cuadro, [])
        pares = []
        if dets:
            ious = iou_matriz(refs, dets)
            filas, cols = linear_sum_assignment(-ious)
            pares = [(i, j) for i, j in zip(filas, cols) if ious[i, j] >= IOU_MIN]
        emparejadas = {i for i, _ in pares}
        for i, r in enumerate(refs):
            visto[r.ident].append((cuadro, i in emparejadas))
        for i, j in pares:
            r, d = refs[i], dets[j]
            if r.ident in ultimo and ultimo[r.ident] != d.ident:
                cambios_id += 1
            ultimo[r.ident] = d.ident
            if not proyector.disponible:
                continue
            pr = proyector.proyectar(punto_calzada(r))
            pd = proyector.proyectar(punto_calzada(d))
            if pr is None or pd is None:
                continue
            ex, ey = pd[0] - pr[0], pd[1] - pr[1]
            errores_x.append(ex)
            errores_y.append(ey)
            serie_x[r.ident].append((cuadro, ex))
            serie_y[r.ident].append((cuadro, ey))

    huecos = []
    n_obs = n_perdidas = 0
    for marcas in visto.values():
        marcas.sort()
        largo = 0
        for _, ok in marcas:
            n_obs += 1
            if ok:
                if largo:
                    huecos.append(largo)
                largo = 0
            else:
                n_perdidas += 1
                largo += 1
        if largo:
            huecos.append(largo)
    segundos_vehiculo = n_obs / fps

    return {
        "posicion": _posicion(errores_x, errores_y, serie_x, serie_y),
        "perdidas": {
            "fraccion_perdida": round(n_perdidas / n_obs, 4) if n_obs else None,
            "duracion_media_hueco_s": round(float(np.mean(huecos)) / fps, 3) if huecos else None,
            "n_huecos": len(huecos),
        },
        "identidad": {
            "cambios_id": cambios_id,
            "segundos_vehiculo": round(segundos_vehiculo, 1),
            "cambios_id_por_vehiculo_s": round(cambios_id / segundos_vehiculo, 5)
            if segundos_vehiculo
            else None,
        },
    }


def _posicion(errores_x, errores_y, serie_x, serie_y) -> dict | None:
    """Error en metros; None sin calibracion (Paso 5): no hay metros que comparar."""
    if not errores_x:
        return None
    ex, ey = np.array(errores_x), np.array(errores_y)
    sesgo_x, sigma_x = _robusta(ex)
    sesgo_y, sigma_y = _robusta(ey)
    return {
        "n_pares": int(len(ex)),
        "sesgo_x_m": round(sesgo_x, 3),
        "sigma_x_m": round(sigma_x, 3),
        "sesgo_y_m": round(sesgo_y, 3),
        "sigma_y_m": round(sigma_y, 3),
        "autocorrelacion_x": _redondear(_autocorrelacion(serie_x)),
        "autocorrelacion_y": _redondear(_autocorrelacion(serie_y)),
        "p95_abs_x_m": round(float(np.percentile(np.abs(ex - sesgo_x), 95)), 3),
        "p95_abs_y_m": round(float(np.percentile(np.abs(ey - sesgo_y), 95)), 3),
    }


def _redondear(valor: float | None) -> float | None:
    return None if valor is None else round(valor, 3)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("secuencia")
    parser.add_argument("--corrida", default=None, help="Carpeta con tracks.csv y resumen.json")
    parser.add_argument("--xml", default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument("--salida", default=None, help="Ruta del JSON de salida")
    args = parser.parse_args(argv)
    corrida = Path(args.corrida or RAIZ / "salidas" / args.secuencia)
    ruta_xml = Path(args.xml or RAIZ / "datos" / "ua-detrac" / args.secuencia / f"{args.secuencia}.xml")
    ruta_cfg = Path(args.config or RAIZ / "configs" / f"{args.secuencia}.yaml")
    ruta_salida = Path(
        args.salida
        or RAIZ / "knowledge/projects/entregas/evidencia/reglas" / f"ruido_{args.secuencia}.json"
    )

    cfg = cargar_configuracion(str(ruta_cfg))
    proyector = ProyectorCamino(cfg.homografia)
    if not proyector.disponible:
        print(
            f"{args.secuencia} no tiene calibracion: se miden perdidas e identidad, "
            "no la posicion en metros",
            file=sys.stderr,
        )
    with open(corrida / "resumen.json", encoding="utf-8") as f:
        resumen = json.load(f)["ejecucion"]
    n_cuadros = resumen["n_cuadros_procesados"]
    ref, ignoradas = leer_xml(ruta_xml)
    ref = [
        c for c in ref
        if c.cuadro < n_cuadros
        and not en_ignorada(c, ignoradas)
        and punto_en_poligono(punto_calzada(c), cfg.region_interes)
    ]
    det = [c for c in leer_tracks(corrida / "tracks.csv") if not en_ignorada(c, ignoradas)]

    documento = {
        "secuencia": args.secuencia,
        "corrida": str(corrida),
        "fps": resumen["fps_video"],
        "region": "region_interes",
        **medir_ruido(ref, det, proyector, resumen["fps_video"]),
    }
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(documento, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps(documento, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
