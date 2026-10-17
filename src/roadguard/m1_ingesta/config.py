"""M1 - Carga y validacion de la configuracion YAML (RF1, RF4)."""

from __future__ import annotations

import math
import os
from dataclasses import fields
from typing import Any

import yaml

from roadguard.tipos import Carril, Configuracion, Homografia, Umbrales

# RF2: clases vehiculares que el sistema sabe detectar. El mapeo desde las
# clases del modelo preentrenado esta en m2_deteccion/detector.py.
CLASES_VEHICULARES: tuple[str, ...] = ("automovil", "bus", "camion", "motocicleta")

ADVERTENCIA_SIN_CALIBRACION = (
    "SIN CALIBRACION: no hay homografia valida. Distancia, THW y TTC quedan "
    "no disponibles y se suspenden las reglas de cercania y corte de carril; "
    "deteccion, seguimiento y zigzag se mantienen (Paso 5)."
)

_CLAVES_RAIZ = {
    "camara",
    "region_interes",
    "carriles",
    "homografia",
    "clases",
    "confianza_min_deteccion",
    "confianza_min_carril",
    "permanencia_cambio_carril",
    "umbrales",
}

_UMBRALES_ENTEROS = {
    "zigzag_cambios_min",
    "aporte_cercania",
    "aporte_zigzag",
    "aporte_corte",
    "puntaje_maximo",
    "banda_verde_max",
    "banda_amarillo_max",
}


class ErrorConfiguracion(ValueError):
    """Configuracion incoherente: se rechaza antes de crear salidas (Paso 1)."""


def cargar_configuracion(ruta_yaml: str) -> Configuracion:
    """Lee el YAML de camara y devuelve una Configuracion normalizada.

    Debe validar esquema y consistencia (M1): region de interes, limites de
    carril, correspondencias de homografia, clases vehiculares y umbrales.
    Rechazar configuraciones incoherentes ANTES de crear salidas (Paso 1).
    """
    if not os.path.isfile(ruta_yaml):
        raise ErrorConfiguracion(f"No existe el archivo de configuracion: {ruta_yaml}")
    try:
        with open(ruta_yaml, encoding="utf-8") as f:
            datos = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ErrorConfiguracion(f"YAML invalido en {ruta_yaml}: {e}") from e
    return configuracion_desde_dict(datos)


def configuracion_desde_dict(datos: Any) -> Configuracion:
    """Valida un diccionario ya leido y construye la Configuracion (RF1)."""
    if not isinstance(datos, dict):
        raise ErrorConfiguracion("La configuracion debe ser un mapeo YAML")

    desconocidas = set(datos) - _CLAVES_RAIZ
    if desconocidas:
        raise ErrorConfiguracion(f"Claves desconocidas: {sorted(desconocidas)}")
    for clave in ("region_interes", "carriles", "clases"):
        if clave not in datos:
            raise ErrorConfiguracion(f"Falta la clave obligatoria '{clave}'")

    region = _poligono(datos["region_interes"], "region_interes")
    carriles = _carriles(datos["carriles"])
    homografia = _homografia(datos.get("homografia") or {})
    clases = _clases(datos["clases"])
    umbrales = _umbrales(datos.get("umbrales") or {})

    conf_det = _numero(datos.get("confianza_min_deteccion", 0.25), "confianza_min_deteccion")
    conf_carril = _numero(datos.get("confianza_min_carril", 0.60), "confianza_min_carril")
    for nombre, valor in (
        ("confianza_min_deteccion", conf_det),
        ("confianza_min_carril", conf_carril),
    ):
        if not 0.0 <= valor <= 1.0:
            raise ErrorConfiguracion(f"'{nombre}' debe estar en [0, 1]: {valor}")
    permanencia = _numero(datos.get("permanencia_cambio_carril", 1.0), "permanencia_cambio_carril")
    if permanencia <= 0:
        raise ErrorConfiguracion("'permanencia_cambio_carril' debe ser positiva")

    return Configuracion(
        region_interes=region,
        carriles=carriles,
        homografia=homografia,
        clases=clases,
        umbrales=umbrales,
        confianza_min_deteccion=conf_det,
        confianza_min_carril=conf_carril,
        permanencia_cambio_carril=permanencia,
    )


def validar_consistencia(cfg: Configuracion) -> list[str]:
    """Devuelve la lista de advertencias explicitas de la configuracion.

    Si falta calibracion, debe emitirse una advertencia explicita y
    desactivarse las metricas basadas en distancia (M1, Paso 5).
    """
    advertencias: list[str] = []
    if not cfg.homografia.disponible:
        advertencias.append(ADVERTENCIA_SIN_CALIBRACION)
    if _area(cfg.region_interes) <= 0:
        advertencias.append(
            "La region de interes tiene area nula: ninguna deteccion sera "
            "aceptada. Reemplazarla por la region real de la camara."
        )
    for carril in cfg.carriles:
        if _area(carril.poligono) <= 0:
            advertencias.append(
                f"El carril {carril.indice} tiene area nula: no se asignaran "
                "vehiculos a ese carril."
            )
    if len(cfg.carriles) < 2:
        advertencias.append(
            "Hay menos de dos carriles: zigzag y corte de carril no pueden activarse."
        )
    return advertencias


# ---------------------------------------------------------------------------
# Validadores de esquema
# ---------------------------------------------------------------------------

def _numero(valor: Any, nombre: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ErrorConfiguracion(f"'{nombre}' debe ser numerico: {valor!r}")
    if not math.isfinite(valor):
        raise ErrorConfiguracion(f"'{nombre}' debe ser finito: {valor!r}")
    return float(valor)


def _punto(valor: Any, nombre: str) -> tuple[float, float]:
    if not isinstance(valor, (list, tuple)) or len(valor) != 2:
        raise ErrorConfiguracion(f"'{nombre}': cada punto debe ser [x, y]: {valor!r}")
    return (_numero(valor[0], nombre), _numero(valor[1], nombre))


def _puntos(valor: Any, nombre: str) -> list[tuple[float, float]]:
    if not isinstance(valor, list):
        raise ErrorConfiguracion(f"'{nombre}' debe ser una lista de puntos")
    return [_punto(p, nombre) for p in valor]


def _poligono(valor: Any, nombre: str) -> list[tuple[float, float]]:
    puntos = _puntos(valor, nombre)
    if len(puntos) < 3:
        raise ErrorConfiguracion(
            f"'{nombre}' debe tener al menos 3 puntos (tiene {len(puntos)})"
        )
    return puntos


def _carriles(valor: Any) -> list[Carril]:
    if not isinstance(valor, list) or not valor:
        raise ErrorConfiguracion("'carriles' debe ser una lista no vacia")
    carriles: list[Carril] = []
    for i, c in enumerate(valor):
        if not isinstance(c, dict) or "indice" not in c or "poligono" not in c:
            raise ErrorConfiguracion(f"carriles[{i}] debe tener 'indice' y 'poligono'")
        indice = c["indice"]
        if isinstance(indice, bool) or not isinstance(indice, int):
            raise ErrorConfiguracion(f"carriles[{i}].indice debe ser entero")
        carriles.append(Carril(indice=indice, poligono=_poligono(c["poligono"], f"carriles[{i}].poligono")))
    indices = [c.indice for c in carriles]
    if len(set(indices)) != len(indices):
        raise ErrorConfiguracion(f"Indices de carril repetidos: {indices}")
    return carriles


def _homografia(valor: Any) -> Homografia:
    if not isinstance(valor, dict):
        raise ErrorConfiguracion("'homografia' debe ser un mapeo")
    img = _puntos(valor.get("puntos_imagen") or [], "homografia.puntos_imagen")
    cam = _puntos(valor.get("puntos_camino") or [], "homografia.puntos_camino")
    if not img and not cam:
        return Homografia()  # sin calibracion: se advierte, no se rechaza (Paso 5)
    if len(img) != len(cam):
        raise ErrorConfiguracion(
            f"Homografia desbalanceada: {len(img)} puntos de imagen y {len(cam)} del camino"
        )
    if len(img) < 4:
        raise ErrorConfiguracion(f"La homografia requiere al menos 4 pares (hay {len(img)})")
    for nombre, pts in (("puntos_imagen", img), ("puntos_camino", cam)):
        if not _en_posicion_general(pts):
            raise ErrorConfiguracion(
                f"homografia.{nombre} es degenerada: se necesitan 4 puntos sin 3 colineales"
            )
    return Homografia(puntos_imagen=img, puntos_camino=cam)


def _clases(valor: Any) -> list[str]:
    if not isinstance(valor, list) or not valor:
        raise ErrorConfiguracion("'clases' debe ser una lista no vacia")
    desconocidas = [c for c in valor if c not in CLASES_VEHICULARES]
    if desconocidas:
        raise ErrorConfiguracion(
            f"Clases no soportadas: {desconocidas}. Validas: {list(CLASES_VEHICULARES)}"
        )
    return list(dict.fromkeys(valor))


def _umbrales(valor: Any) -> Umbrales:
    if not isinstance(valor, dict):
        raise ErrorConfiguracion("'umbrales' debe ser un mapeo")
    conocidos = {f.name for f in fields(Umbrales)}
    desconocidos = set(valor) - conocidos
    if desconocidos:
        raise ErrorConfiguracion(f"Umbrales desconocidos: {sorted(desconocidos)}")

    normalizados: dict[str, Any] = {}
    for nombre, v in valor.items():
        numero = _numero(v, f"umbrales.{nombre}")
        if nombre in _UMBRALES_ENTEROS:
            if numero != int(numero):
                raise ErrorConfiguracion(f"'umbrales.{nombre}' debe ser entero: {v!r}")
            normalizados[nombre] = int(numero)
        else:
            normalizados[nombre] = numero
    u = Umbrales(**normalizados)

    for nombre in conocidos - {"banda_verde_max", "banda_amarillo_max"}:
        if getattr(u, nombre) < 0:
            raise ErrorConfiguracion(f"'umbrales.{nombre}' no puede ser negativo")
    for nombre in (
        "cercania_thw_max",
        "cercania_persistencia",
        "zigzag_ventana",
        "corte_ventana_post_cambio",
        "corte_thw_max",
        "corte_ttc_max",
        "vigencia_aporte",
        "puntaje_maximo",
    ):
        if getattr(u, nombre) <= 0:
            raise ErrorConfiguracion(f"'umbrales.{nombre}' debe ser positivo")
    if u.zigzag_cambios_min < 1:
        raise ErrorConfiguracion("'umbrales.zigzag_cambios_min' debe ser al menos 1")
    if not 0 <= u.banda_verde_max < u.banda_amarillo_max < u.puntaje_maximo:
        raise ErrorConfiguracion(
            "Bandas incoherentes: se requiere 0 <= banda_verde_max < "
            "banda_amarillo_max < puntaje_maximo"
        )
    return u


# ---------------------------------------------------------------------------
# Geometria auxiliar
# ---------------------------------------------------------------------------

def _area(poligono: list[tuple[float, float]]) -> float:
    """Area absoluta por la formula del zapato."""
    s = 0.0
    n = len(poligono)
    for i in range(n):
        x1, y1 = poligono[i]
        x2, y2 = poligono[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def _en_posicion_general(puntos: list[tuple[float, float]]) -> bool:
    """True si existen 4 puntos sin 3 colineales (requisito de la homografia)."""
    from itertools import combinations

    def colineales(a, b, c) -> bool:
        cruz = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        escala = max(1.0, math.dist(a, b) * math.dist(a, c))
        return abs(cruz) <= 1e-9 * escala

    for cuatro in combinations(puntos, 4):
        if not any(colineales(*tres) for tres in combinations(cuatro, 3)):
            return True
    return False
