"""Resumen de anotaciones UA-DETRAC para elegir secuencias (seccion 2.4).

Lee el XML oficial de una secuencia y cuenta cuadros, vehiculos, clases y
regiones ignoradas. Sirve para elegir secuencias de prueba con datos y no
solo por nombre; la evaluacion de mAP e IDF1 se construye despues.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ResumenSecuencia:
    nombre: str
    clima: Optional[str]
    estado_camara: Optional[str]
    n_cuadros: int
    n_vehiculos: int
    cajas_por_clase: dict[str, int]
    densidad_media: Optional[float]
    n_regiones_ignoradas: int


def resumir_secuencia(ruta: str | Path) -> ResumenSecuencia:
    """Resume un XML de UA-DETRAC. `densidad_media` es None sin cuadros."""
    raiz = ET.parse(ruta).getroot()
    atributos = raiz.find("sequence_attribute")
    # El XML oficial escribe "sence_weather" (sic).
    clima = None if atributos is None else atributos.get("sence_weather")
    estado = None if atributos is None else atributos.get("camera_state")

    ids: set[int] = set()
    clases: Counter[str] = Counter()
    densidades: list[int] = []
    for cuadro in raiz.iter("frame"):
        densidades.append(int(cuadro.get("density", "0")))
        for objetivo in cuadro.iter("target"):
            ids.add(int(objetivo.get("id")))
            atributo = objetivo.find("attribute")
            if atributo is not None:
                clases[atributo.get("vehicle_type", "desconocido")] += 1

    ignoradas = raiz.find("ignored_region")
    return ResumenSecuencia(
        nombre=raiz.get("name", Path(ruta).stem),
        clima=clima,
        estado_camara=estado,
        n_cuadros=len(densidades),
        n_vehiculos=len(ids),
        cajas_por_clase=dict(clases),
        densidad_media=sum(densidades) / len(densidades) if densidades else None,
        n_regiones_ignoradas=0 if ignoradas is None else len(ignoradas.findall("box")),
    )
