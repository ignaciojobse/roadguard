"""M6 - Lectura de anotaciones UA-DETRAC y de predicciones de RoadGuard.

Anotaciones: XML por secuencia (DETRAC-Train-Annotations-XML), con
`<ignored_region>` y, por `<frame num=...>`, objetivos con `id`, `<box
left top width height>` y `<attribute vehicle_type=...>`.

Predicciones y tracks de RoadGuard: CSV con columnas
`cuadro,id_vehiculo,clase,confianza,x1,y1,x2,y2` (`id_vehiculo` vacio para
detecciones sin seguimiento). `cuadro` usa la misma numeracion que el XML
(img00001.jpg -> 1).
"""

from __future__ import annotations

import csv
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from roadguard.tipos import Caja

# Decision documentada en docs/DATOS.md: UA-DETRAC -> clases de RoadGuard.
MAPEO_UADETRAC: dict[str, str] = {
    "car": "automovil",
    "van": "automovil",
    "bus": "bus",
    "others": "camion",
}

COLUMNAS_PREDICCIONES = ("cuadro", "id_vehiculo", "clase", "confianza", "x1", "y1", "x2", "y2")


@dataclass(frozen=True)
class Objeto:
    cuadro: int
    id: Optional[int]
    clase: str
    caja: Caja
    confianza: float = 1.0


@dataclass
class Secuencia:
    nombre: str
    atributos: dict[str, str] = field(default_factory=dict)
    ignoradas: list[Caja] = field(default_factory=list)
    objetos: dict[int, list[Objeto]] = field(default_factory=lambda: defaultdict(list))


def leer_xml(ruta: str) -> Secuencia:
    raiz = ET.parse(ruta).getroot()
    seq = Secuencia(nombre=raiz.get("name", ""))
    attr = raiz.find("sequence_attribute")
    if attr is not None:
        seq.atributos = dict(attr.attrib)
    for box in raiz.findall("ignored_region/box"):
        seq.ignoradas.append(_caja(box))
    for frame in raiz.findall("frame"):
        num = int(frame.get("num"))
        for target in frame.findall("target_list/target"):
            box = target.find("box")
            atributo = target.find("attribute")
            tipo = "" if atributo is None else atributo.get("vehicle_type", "")
            seq.objetos[num].append(
                Objeto(num, int(target.get("id")), MAPEO_UADETRAC.get(tipo, tipo), _caja(box))
            )
    return seq


def leer_predicciones(ruta: str) -> dict[int, list[Objeto]]:
    salida: dict[int, list[Objeto]] = defaultdict(list)
    with open(ruta, encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f):
            cuadro = int(fila["cuadro"])
            id_v = fila.get("id_vehiculo", "")
            salida[cuadro].append(
                Objeto(
                    cuadro,
                    int(id_v) if id_v not in ("", None) else None,
                    fila["clase"],
                    Caja(float(fila["x1"]), float(fila["y1"]), float(fila["x2"]), float(fila["y2"])),
                    float(fila.get("confianza") or 1.0),
                )
            )
    return salida


def escribir_predicciones(objetos: list[Objeto], ruta: str) -> None:
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNAS_PREDICCIONES)
        for o in objetos:
            c = o.caja
            w.writerow([o.cuadro, "" if o.id is None else o.id, o.clase, round(o.confianza, 5),
                        round(c.x1, 2), round(c.y1, 2), round(c.x2, 2), round(c.y2, 2)])


def en_region_ignorada(caja: Caja, ignoradas: list[Caja]) -> bool:
    """Protocolo DETRAC: se descartan predicciones cuyo centro cae en una
    region ignorada."""
    cx, cy = (caja.x1 + caja.x2) / 2, (caja.y1 + caja.y2) / 2
    return any(r.x1 <= cx <= r.x2 and r.y1 <= cy <= r.y2 for r in ignoradas)


def iou(a: Caja, b: Caja) -> float:
    ix = max(0.0, min(a.x2, b.x2) - max(a.x1, b.x1))
    iy = max(0.0, min(a.y2, b.y2) - max(a.y1, b.y1))
    inter = ix * iy
    union = (a.x2 - a.x1) * (a.y2 - a.y1) + (b.x2 - b.x1) * (b.y2 - b.y1) - inter
    return inter / union if union > 0 else 0.0


def _caja(box) -> Caja:
    x, y = float(box.get("left")), float(box.get("top"))
    return Caja(x, y, x + float(box.get("width")), y + float(box.get("height")))
