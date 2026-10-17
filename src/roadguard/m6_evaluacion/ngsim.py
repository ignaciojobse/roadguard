"""Trayectorias NGSIM como referencia limpia para validar reglas (seccion 2.4).

Convierte el CSV de NGSIM (pies, pies/s, 10 Hz) al contrato de datos de
M3: un `EstadoCinematico` y una `Relacion` por vehiculo y por cuadro. Asi el
motor de reglas (M4) se puede ejercitar sobre trayectorias reales sin pasar
por la camara.

Convenciones de la conversion:
  - `x_camino` es `Local_Y` (longitudinal, sentido de avance) y `y_camino`
    es `Local_X` (lateral), ambos en metros.
  - `t` en segundos desde el primer instante del archivo.
  - La distancia al predecesor es `Space_Headway` (frente a frente), que es
    la misma convencion de M3: puntos de referencia del vehiculo, sin
    descontar el largo.
  - THW y TTC se calculan con las funciones de M3, no se toman de NGSIM,
    para que la definicion sea identica a la del sistema evaluado.
"""

from __future__ import annotations

import argparse
import csv
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from roadguard.m3_geometria.relaciones import calcular_thw, calcular_ttc
from roadguard.tipos import EstadoCinematico, Relacion

PIE_A_METRO = 0.3048
FPS_NGSIM = 10.0
URL_NGSIM = "https://data.transportation.gov/resource/8ect-6jqj.csv"
COLUMNAS = (
    "vehicle_id,frame_id,global_time,local_x,local_y,v_length,v_width,"
    "v_class,v_vel,v_acc,lane_id,preceding,following,space_headway,"
    "time_headway,location"
)


@dataclass(frozen=True)
class CuadroReferencia:
    """Estado de todos los vehiculos observados en un instante."""

    cuadro: int
    t: float
    estados: list[EstadoCinematico]
    relaciones: list[Relacion]


def cargar_ngsim(ruta: str | Path) -> list[CuadroReferencia]:
    """Lee un CSV de NGSIM y devuelve los cuadros en orden temporal."""
    with open(ruta, newline="") as f:
        filas = list(csv.DictReader(f))
    if not filas:
        raise ValueError(f"El archivo NGSIM no tiene filas: {ruta}")

    t0 = min(int(fila["global_time"]) for fila in filas)
    paso_ms = 1000.0 / FPS_NGSIM

    por_cuadro: dict[int, list[dict[str, str]]] = {}
    for fila in filas:
        cuadro = round((int(fila["global_time"]) - t0) / paso_ms)
        por_cuadro.setdefault(cuadro, []).append(fila)

    cuadros: list[CuadroReferencia] = []
    for cuadro in sorted(por_cuadro):
        t = cuadro / FPS_NGSIM
        grupo = por_cuadro[cuadro]
        estados = [_estado(fila, cuadro, t) for fila in grupo]
        velocidad = {e.id_vehiculo: e.velocidad for e in estados}
        relaciones = [_relacion(fila, cuadro, t, velocidad) for fila in grupo]
        cuadros.append(CuadroReferencia(cuadro, t, estados, relaciones))
    return cuadros


def _estado(fila: dict[str, str], cuadro: int, t: float) -> EstadoCinematico:
    return EstadoCinematico(
        id_vehiculo=int(fila["vehicle_id"]),
        cuadro=cuadro,
        t=t,
        x_camino=float(fila["local_y"]) * PIE_A_METRO,
        y_camino=float(fila["local_x"]) * PIE_A_METRO,
        velocidad=float(fila["v_vel"]) * PIE_A_METRO,
        carril=int(fila["lane_id"]),
        confianza_carril=1.0,
        calibrado=True,
    )


def _relacion(
    fila: dict[str, str], cuadro: int, t: float, velocidad: dict[int, float]
) -> Relacion:
    id_seguidor = int(fila["vehicle_id"])
    id_predecesor = int(fila["preceding"]) or None
    distancia = thw = ttc = None
    if id_predecesor is not None:
        separacion = float(fila["space_headway"]) * PIE_A_METRO
        distancia = separacion if separacion > 0 else None
        v_seguidor = velocidad[id_seguidor]
        thw = calcular_thw(distancia, v_seguidor)
        v_predecesor = velocidad.get(id_predecesor)
        if v_predecesor is not None:
            ttc = calcular_ttc(distancia, v_seguidor - v_predecesor)
    return Relacion(
        id_seguidor=id_seguidor,
        id_predecesor=id_predecesor,
        cuadro=cuadro,
        t=t,
        carril=int(fila["lane_id"]),
        distancia=distancia,
        thw=thw,
        ttc=ttc,
    )


def consulta_muestra(ubicacion: str, desde_ms: int, hasta_ms: int) -> dict[str, str]:
    """Parametros SoQL para una ventana temporal de una ubicacion."""
    return {
        "$select": COLUMNAS,
        "$where": (
            f"location='{ubicacion}' AND global_time >= {desde_ms} "
            f"AND global_time < {hasta_ms}"
        ),
        "$order": "global_time,vehicle_id",
    }


def descargar_muestra(
    ubicacion: str, desde_ms: int, hasta_ms: int, salida: str | Path, lote: int = 50000
) -> int:
    """Descarga una ventana de NGSIM desde data.transportation.gov.

    Devuelve el numero de filas escritas. Pagina de a `lote` filas.
    """
    params = consulta_muestra(ubicacion, desde_ms, hasta_ms)
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    n_filas = 0
    offset = 0
    with open(salida, "w", newline="") as destino:
        while True:
            consulta = dict(params, **{"$limit": str(lote), "$offset": str(offset)})
            url = f"{URL_NGSIM}?{urllib.parse.urlencode(consulta)}"
            with urllib.request.urlopen(url, timeout=120) as respuesta:
                lineas = respuesta.read().decode("utf-8").splitlines(keepends=True)
            encabezado, cuerpo = lineas[0], lineas[1:]
            if offset == 0:
                destino.write(encabezado)
            destino.writelines(cuerpo)
            n_filas += len(cuerpo)
            if len(cuerpo) < lote:
                return n_filas
            offset += lote


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga una muestra de NGSIM.")
    parser.add_argument("--ubicacion", default="us-101")
    parser.add_argument("--desde-ms", type=int, required=True, help="Global_Time inicial")
    parser.add_argument("--duracion-s", type=float, default=60.0)
    parser.add_argument("--salida", required=True)
    args = parser.parse_args()
    hasta = args.desde_ms + int(args.duracion_s * 1000)
    n = descargar_muestra(args.ubicacion, args.desde_ms, hasta, args.salida)
    print(f"{n} filas escritas en {args.salida}")


if __name__ == "__main__":
    main()
