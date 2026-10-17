"""M5 - RF12: exportacion de eventos CSV y resumen JSON.

Esquema estable y marcas temporales basadas en FPS (M5). Cada evento debe
incluir vehiculo, intervalo, regla, variables medidas, umbrales y puntaje
(seccion 2.5, trazabilidad).
"""

from __future__ import annotations

import csv
import json
import math
import os
import tempfile
from dataclasses import asdict
from enum import Enum
from typing import Any, Optional

from roadguard.tipos import Evento, ResumenEjecucion, ResumenVehiculo

AVISO = (
    "Alertas experimentales: senalan patrones potencialmente riesgosos segun "
    "reglas y umbrales configurables, y requieren revision humana del video y "
    "su contexto. No determinan responsabilidades ni reemplazan esa revision."
)

COLUMNAS_EVENTOS: tuple[str, ...] = (
    "id_vehiculo",
    "regla",
    "t_inicio",
    "t_fin",
    "id_relacionado",
    "velocidad",
    "distancia",
    "thw",
    "ttc",
    "umbral_velocidad",
    "umbral_thw",
    "umbral_ttc",
    "aporte_puntaje",
    # Columnas agregadas: zigzag y persistencia no tienen columna propia en
    # el esquema original, y los JSON conservan todas las variables y
    # umbrales que sustentan la alerta (RF12, trazabilidad).
    "n_cambios",
    "umbral_persistencia",
    "umbral_cambios",
    "umbral_ventana",
    "variables_json",
    "umbrales_json",
)


def fila_evento(evento: Evento) -> dict[str, Any]:
    """Proyecta un Evento sobre COLUMNAS_EVENTOS."""
    v, u = evento.variables, evento.umbrales
    n_cambios = v.get("n_cambios")
    return {
        "id_vehiculo": evento.id_vehiculo,
        "regla": _valor(evento.regla),
        "t_inicio": evento.t_inicio,
        "t_fin": evento.t_fin,
        "id_relacionado": evento.id_relacionado,
        "velocidad": v.get("velocidad"),
        "distancia": v.get("distancia"),
        "thw": v.get("thw"),
        "ttc": v.get("ttc"),
        "umbral_velocidad": u.get("velocidad"),
        "umbral_thw": u.get("thw"),
        "umbral_ttc": u.get("ttc"),
        "aporte_puntaje": evento.aporte_puntaje,
        "n_cambios": None if n_cambios is None else int(n_cambios),
        "umbral_persistencia": u.get("persistencia"),
        "umbral_cambios": None if u.get("cambios") is None else int(u["cambios"]),
        "umbral_ventana": u.get("ventana"),
        "variables_json": json.dumps(limpiar_json(v), sort_keys=True),
        "umbrales_json": json.dumps(limpiar_json(u), sort_keys=True),
    }


def exportar_eventos_csv(eventos: list[Evento], ruta: str) -> None:
    """Escribe un evento por activacion, con metricas y umbrales (RF12)."""
    def escribir(f) -> None:
        w = csv.DictWriter(f, fieldnames=COLUMNAS_EVENTOS)
        w.writeheader()
        for evento in sorted(eventos, key=lambda e: (e.t_fin, e.id_vehiculo)):
            w.writerow({k: _celda(x) for k, x in fila_evento(evento).items()})

    _escritura_atomica(ruta, escribir, newline="")


def exportar_resumen_json(
    resumenes: list[ResumenVehiculo], ejecucion: ResumenEjecucion, ruta: str
) -> None:
    """Resumen jerarquico por vehiculo mas evidencia de reproducibilidad.

    Debe incluir configuracion, version del modelo, FPS y resumen de eventos
    (Paso 6, RF12).
    """
    documento = {
        "aviso": AVISO,
        "ejecucion": limpiar_json(asdict(ejecucion)),
        "resumen_eventos": limpiar_json(ejecucion.n_eventos),
        "vehiculos": [limpiar_json(asdict(r)) for r in sorted(resumenes, key=lambda r: r.id_vehiculo)],
    }
    _escritura_atomica(
        ruta, lambda f: json.dump(documento, f, ensure_ascii=False, indent=2)
    )


# ---------------------------------------------------------------------------

def _valor(x: Any) -> Any:
    return x.value if isinstance(x, Enum) else x


def limpiar_json(x: Any) -> Any:
    """Convierte enums, tuplas y no-finitos a tipos JSON estables."""
    if isinstance(x, Enum):
        return x.value
    if isinstance(x, dict):
        return {str(_valor(k)): limpiar_json(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [limpiar_json(v) for v in x]
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


def _celda(x: Optional[Any]) -> Any:
    if x is None:
        return ""
    if isinstance(x, float):
        return "" if not math.isfinite(x) else round(x, 6)
    return x


def _escritura_atomica(ruta: str, escribir, newline: Optional[str] = None) -> None:
    """Escribe en un temporal y lo renombra: nunca deja archivos a medias
    (Paso 6)."""
    directorio = os.path.dirname(os.path.abspath(ruta))
    os.makedirs(directorio, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directorio, prefix=".tmp_", suffix=os.path.basename(ruta))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline=newline) as f:
            escribir(f)
        os.replace(tmp, ruta)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
