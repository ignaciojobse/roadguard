"""M5 - Exportacion de eventos (CSV) y resumen de la corrida (JSON), RF12.

Cada fila del CSV es un evento auditable (seccion 2.5): vehiculo, intervalo,
regla, vehiculo relacionado, aporte al puntaje y, aplanadas, las variables
medidas (`variable_<nombre>`) y los umbrales vigentes (`umbral_<nombre>`).
Los valores no disponibles se escriben vacios, nunca como un numero.
"""

from __future__ import annotations

import csv
import dataclasses
import json
import os
from enum import Enum
from typing import Any, Iterable, Optional

from roadguard.tipos import EstadoCinematico, Evento, ResumenEjecucion, ResumenVehiculo, Track

COLUMNAS_FIJAS: tuple[str, ...] = (
    "id_vehiculo",
    "regla",
    "t_inicio",
    "t_fin",
    "id_relacionado",
    "aporte_puntaje",
)
PREFIJO_VARIABLE = "variable_"
PREFIJO_UMBRAL = "umbral_"
COLUMNAS_TRACKS: tuple[str, ...] = (
    "cuadro", "id", "clase", "x1", "y1", "x2", "y2", "carril", "confianza"
)


def columnas_eventos(eventos: Iterable[Evento]) -> list[str]:
    """Columnas fijas mas la union ordenada de variables y umbrales."""
    variables: set[str] = set()
    umbrales: set[str] = set()
    for ev in eventos:
        variables.update(ev.variables)
        umbrales.update(ev.umbrales)
    return (
        list(COLUMNAS_FIJAS)
        + [PREFIJO_VARIABLE + v for v in sorted(variables)]
        + [PREFIJO_UMBRAL + u for u in sorted(umbrales)]
    )


def fila_evento(evento: Evento, columnas: list[str]) -> dict[str, Any]:
    """Aplana un evento en una fila con las columnas dadas."""
    fila: dict[str, Any] = {c: "" for c in columnas}
    fila.update(
        id_vehiculo=evento.id_vehiculo,
        regla=evento.regla.value,
        t_inicio=evento.t_inicio,
        t_fin=evento.t_fin,
        id_relacionado=_celda(evento.id_relacionado),
        aporte_puntaje=evento.aporte_puntaje,
    )
    for nombre, valor in evento.variables.items():
        fila[PREFIJO_VARIABLE + nombre] = _celda(valor)
    for nombre, valor in evento.umbrales.items():
        fila[PREFIJO_UMBRAL + nombre] = _celda(valor)
    return fila


def escribir_eventos_csv(ruta: str, eventos: Iterable[Evento]) -> list[str]:
    """Escribe el CSV de eventos ordenado por t_inicio y devuelve sus columnas.

    Sin eventos se escribe solo el encabezado con las columnas fijas, para
    que el archivo exista y sea legible igual.
    """
    lista = sorted(eventos, key=lambda e: (e.t_inicio, e.id_vehiculo, e.regla.value))
    columnas = columnas_eventos(lista)
    _preparar_directorio(ruta)
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas)
        escritor.writeheader()
        for ev in lista:
            escritor.writerow(fila_evento(ev, columnas))
    return columnas


def escribir_resumen_json(
    ruta: str,
    resumen_ejecucion: ResumenEjecucion,
    resumen_vehiculos: Iterable[ResumenVehiculo],
) -> dict[str, Any]:
    """Escribe el resumen JSON (RF12) y devuelve el diccionario escrito.

    `ejecucion` incluye `configuracion_sha256` y `parametros` (la
    configuracion normalizada) como evidencia de reproducibilidad (Paso 6).
    `vehiculos` va ordenado por ID.
    """
    documento = {
        "ejecucion": a_json(resumen_ejecucion),
        "vehiculos": [
            a_json(v) for v in sorted(resumen_vehiculos, key=lambda v: v.id_vehiculo)
        ],
    }
    _preparar_directorio(ruta)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(documento, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return documento


class EscritorTracks:
    """Escribe `tracks.csv`: una fila por vehiculo y cuadro (salida opcional).

    Columnas: cuadro, id, clase, x1, y1, x2, y2 (pixeles), carril (vacio si
    no se asigno) y confianza de la deteccion. Sirve para medir mAP e IDF1
    contra una referencia externa sin volver a correr el detector.
    """

    def __init__(self, ruta: str) -> None:
        _preparar_directorio(ruta)
        self.ruta = ruta
        self._f = open(ruta, "w", encoding="utf-8", newline="")
        self._escritor = csv.DictWriter(self._f, fieldnames=list(COLUMNAS_TRACKS))
        self._escritor.writeheader()
        self.n_filas = 0

    def escribir(self, tracks: Iterable[Track], estados: Iterable[EstadoCinematico]) -> None:
        carriles = {e.id_vehiculo: e.carril for e in estados}
        for tr in tracks:
            c = tr.caja
            self._escritor.writerow(
                {
                    "cuadro": tr.cuadro,
                    "id": tr.id_vehiculo,
                    "clase": tr.clase,
                    "x1": round(c.x1, 1),
                    "y1": round(c.y1, 1),
                    "x2": round(c.x2, 1),
                    "y2": round(c.y2, 1),
                    "carril": _celda(carriles.get(tr.id_vehiculo)),
                    "confianza": round(tr.confianza, 4),
                }
            )
            self.n_filas += 1

    def cerrar(self) -> None:
        if not self._f.closed:
            self._f.close()


def a_json(valor: Any) -> Any:
    """Convierte dataclasses, enums y tuplas a estructuras serializables."""
    if dataclasses.is_dataclass(valor) and not isinstance(valor, type):
        return {f.name: a_json(getattr(valor, f.name)) for f in dataclasses.fields(valor)}
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, dict):
        return {str(k): a_json(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [a_json(v) for v in valor]
    return valor


def _celda(valor: Optional[Any]) -> Any:
    return "" if valor is None else valor


def _preparar_directorio(ruta: str) -> None:
    directorio = os.path.dirname(ruta)
    if directorio:
        os.makedirs(directorio, exist_ok=True)
