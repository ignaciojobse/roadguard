"""Calibracion generica de camaras a partir de mediciones externas."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from roadguard.m1_ingesta.config import (  # noqa: E402
    ErrorConfiguracion,
    configuracion_desde_dict,
    validar_consistencia,
)
from roadguard.m3_geometria.calibracion import (  # noqa: E402
    LineaDiscontinua,
    calibrar_lineas,
    carriles_desde_metros,
    proyectar_a_imagen,
)
from roadguard.m3_geometria.homografia import ProyectorCamino  # noqa: E402


def _exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise ValueError(mensaje)


def _numero(valor: Any, campo: str) -> float:
    _exigir(not isinstance(valor, bool) and isinstance(valor, (int, float)), f"{campo} debe ser numerico")
    _exigir(math.isfinite(valor), f"{campo} debe ser finito")
    return float(valor)


def _lista_numerica(valor: Any, campo: str, minimo: int = 1) -> list[float]:
    _exigir(isinstance(valor, list) and len(valor) >= minimo, f"{campo} requiere al menos {minimo} valores")
    return [_numero(v, f"{campo}[{i}]") for i, v in enumerate(valor)]


def _normalizar(definicion: Any) -> dict:
    _exigir(isinstance(definicion, dict), "La definicion debe ser un mapeo YAML")
    desconocidas = set(definicion) - {"camara", "procesamiento_geometria", "clases", "calibracion"}
    _exigir(set(definicion) <= {"camara", "procesamiento_geometria", "clases", "calibracion"},
            f"Claves desconocidas en raiz: {sorted((repr(k) for k in desconocidas))}")
    _exigir("camara" in definicion and "calibracion" in definicion, "Se requieren camara y calibracion")
    camara = definicion["camara"]
    _exigir(isinstance(camara, dict) and set(camara) <= {"nombre", "descripcion", "resolucion_referencia"},
            "camara debe contener solo nombre, descripcion y resolucion_referencia")
    _exigir(isinstance(camara.get("nombre"), str) and isinstance(camara.get("descripcion", ""), str),
            "camara.nombre y camara.descripcion deben ser texto")
    resolucion = camara.get("resolucion_referencia")
    _exigir(isinstance(resolucion, list) and len(resolucion) == 2 and
            all(type(n) is int and n > 0 for n in resolucion),
            "camara.resolucion_referencia debe ser [ancho, alto] entero positivo")

    calibracion = definicion["calibracion"]
    _exigir(isinstance(calibracion, dict) and set(calibracion) == {
        "lineas", "bordes_carriles", "tramo_longitudinal"
    }, "calibracion requiere lineas, bordes_carriles y tramo_longitudinal")
    lineas_dato = calibracion["lineas"]
    _exigir(isinstance(lineas_dato, list) and len(lineas_dato) >= 2,
            "calibracion.lineas requiere al menos dos lineas")
    lineas = []
    for i, linea in enumerate(lineas_dato):
        campo = f"calibracion.lineas[{i}]"
        _exigir(isinstance(linea, dict) and set(linea) == {"puntos_imagen", "posiciones", "lateral"},
                f"{campo} requiere puntos_imagen, posiciones y lateral")
        puntos = linea["puntos_imagen"]
        _exigir(isinstance(puntos, list) and len(puntos) >= 2, f"{campo}.puntos_imagen requiere al menos 2 puntos")
        puntos = [_lista_numerica(p, f"{campo}.puntos_imagen[{j}]", 2) for j, p in enumerate(puntos)]
        _exigir(all(len(p) == 2 for p in puntos), f"{campo}.puntos_imagen requiere pares [u, v]")
        posiciones = _lista_numerica(linea["posiciones"], f"{campo}.posiciones", 2)
        _exigir(len(posiciones) == len(puntos), f"{campo}: puntos_imagen y posiciones deben tener igual longitud")
        _exigir(all(a < b for a, b in zip(posiciones, posiciones[1:])),
                f"{campo}.posiciones debe ser estrictamente creciente")
        lineas.append(LineaDiscontinua([tuple(p) for p in puntos], posiciones, _numero(linea["lateral"], f"{campo}.lateral")))
    laterales = [linea.lateral for linea in lineas]
    _exigir(all(a < b for a, b in zip(laterales, laterales[1:])),
            "calibracion.lineas debe estar ordenada por lateral creciente")
    bordes = _lista_numerica(calibracion["bordes_carriles"], "calibracion.bordes_carriles", 2)
    _exigir(all(a < b for a, b in zip(bordes, bordes[1:])),
            "calibracion.bordes_carriles debe ser estrictamente creciente")
    tramo = _lista_numerica(calibracion["tramo_longitudinal"], "calibracion.tramo_longitudinal", 2)
    _exigir(len(tramo) == 2 and tramo[0] < tramo[1], "tramo_longitudinal debe ser [inicio, fin] creciente")

    datos: dict[str, Any] = {
        "camara": camara,
        "region_interes": [],
        "carriles": [],
        "homografia": {"puntos_imagen": [], "puntos_camino": []},
        "clases": definicion.get("clases", ["automovil", "bus", "camion", "motocicleta"]),
    }
    if "procesamiento_geometria" in definicion:
        datos["procesamiento_geometria"] = definicion["procesamiento_geometria"]
    if "clases" in definicion:
        _exigir(isinstance(datos["clases"], list) and all(isinstance(c, str) for c in datos["clases"]),
                "clases debe ser una lista de textos")

    resultado = calibrar_lineas(lineas, tuple(resolucion))
    proyector = ProyectorCamino(resultado.homografia)
    _exigir(proyector.disponible, f"Proyector no disponible: {proyector.motivo_no_disponible}")
    x0, x1 = tramo
    carriles = carriles_desde_metros(resultado.homografia, x0, x1, bordes)
    region = proyectar_a_imagen(resultado.homografia, [
        (x0, bordes[0]), (x1, bordes[0]), (x1, bordes[-1]), (x0, bordes[-1])
    ])
    _exigir(all(p is not None for p in region), "La region cruza el horizonte de la imagen")
    datos.update({
        "region_interes": [list(p) for p in region],
        "carriles": [{"indice": c.indice, "poligono": [list(p) for p in c.poligono]} for c in carriles],
        "homografia": {
            "puntos_imagen": [list(p) for p in resultado.homografia.puntos_imagen],
            "puntos_camino": [list(p) for p in resultado.homografia.puntos_camino],
        },
    })
    cfg = configuracion_desde_dict(datos)
    validar_consistencia(cfg)
    return datos


def calibrar(entrada: Path, salida: Path, sobrescribir: bool = False) -> None:
    if salida.exists() and not sobrescribir:
        raise FileExistsError(f"La salida ya existe (use --sobrescribir): {salida}")
    try:
        definicion = yaml.safe_load(entrada.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML invalido: {exc}") from exc
    datos = _normalizar(definicion)
    salida.parent.mkdir(parents=True, exist_ok=True)
    contenido = yaml.safe_dump(datos, allow_unicode=True, sort_keys=False, default_flow_style=False)
    # Modo exclusivo evita pisar una salida creada concurrentemente.
    with salida.open("w" if sobrescribir else "x", encoding="utf-8") as archivo:
        archivo.write(contenido)
    print(f"Perfil valido: {salida}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", required=True, type=Path)
    parser.add_argument("--salida", required=True, type=Path)
    parser.add_argument("--sobrescribir", action="store_true")
    args = parser.parse_args()
    try:
        calibrar(args.entrada, args.salida, args.sobrescribir)
    except (OSError, ValueError, ErrorConfiguracion) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
