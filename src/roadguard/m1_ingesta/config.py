"""M1 - Carga y validacion de la configuracion YAML (RF1, RF4)."""

from __future__ import annotations

import math
import os
import hashlib
from dataclasses import fields, replace
from typing import Any

import yaml

from roadguard.poligonos import area_poligono
from roadguard.tipos import (Carril, Configuracion, Homografia, Umbrales,
                             PerfilCamara, ProcesamientoGeometria, MetadatosVideo)

# RF2: clases vehiculares que el sistema sabe detectar. El mapeo desde las
# clases del modelo preentrenado esta en m2_deteccion/detector.py.
CLASES_VEHICULARES: tuple[str, ...] = ("automovil", "bus", "camion", "motocicleta")

ADVERTENCIA_SIN_CALIBRACION = (
    "SIN CALIBRACION: no hay homografia valida. Distancia, THW y TTC quedan "
    "no disponibles y se suspenden las reglas de cercania y corte de carril; "
    "deteccion, seguimiento y zigzag se mantienen (Paso 5)."
)
# Version breve para el rotulo permanente del video (Paso 5).
ADVERTENCIA_SIN_CALIBRACION_CORTA = (
    "SIN CALIBRACION: distancia, THW y TTC no disponibles; cercania y corte suspendidos"
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
    "procesamiento_geometria",
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
    camara = _perfil_camara(datos.get("camara"))
    geometria = _procesamiento_geometria(datos.get("procesamiento_geometria"))

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
        camara=camara,
        procesamiento_geometria=geometria,
    )


def _perfil_camara(valor: Any) -> PerfilCamara:
    if valor is None:
        return PerfilCamara()
    if not isinstance(valor, dict) or set(valor) - {"nombre", "descripcion", "resolucion_referencia"}:
        raise ErrorConfiguracion("'camara' debe contener solo nombre, descripcion y resolucion_referencia")
    nombre, descripcion = valor.get("nombre", ""), valor.get("descripcion", "")
    if not isinstance(nombre, str) or not isinstance(descripcion, str):
        raise ErrorConfiguracion("'camara.nombre' y 'camara.descripcion' deben ser texto")
    resolucion = valor.get("resolucion_referencia")
    if resolucion is not None:
        if (not isinstance(resolucion, list) or len(resolucion) != 2 or
                any(isinstance(x, bool) or not isinstance(x, int) or x <= 0 for x in resolucion)):
            raise ErrorConfiguracion("'camara.resolucion_referencia' debe ser [ancho, alto] entero positivo")
        resolucion = tuple(resolucion)
    return PerfilCamara(nombre, descripcion, resolucion)


def _procesamiento_geometria(valor: Any) -> ProcesamientoGeometria:
    if valor is None:
        return ProcesamientoGeometria()
    if not isinstance(valor, dict) or set(valor) - {"compensar_camara", "metodo_apoyo"}:
        raise ErrorConfiguracion("'procesamiento_geometria' contiene claves invalidas")
    compensar = valor.get("compensar_camara", False)
    metodo = valor.get("metodo_apoyo", "centro_inferior")
    if not isinstance(compensar, bool):
        raise ErrorConfiguracion("'procesamiento_geometria.compensar_camara' debe ser booleano")
    if not isinstance(metodo, str) or metodo not in {"centro_inferior", "longitudinal"}:
        raise ErrorConfiguracion("'procesamiento_geometria.metodo_apoyo' invalido")
    return ProcesamientoGeometria(compensar, metodo)


def validar_perfil_video(cfg: Configuracion, metadatos: MetadatosVideo) -> list[str]:
    """Comprueba la resolución declarada; no valida encuadre ni autoescala."""
    ref = cfg.camara.resolucion_referencia
    if ref and (metadatos.ancho, metadatos.alto) != ref:
        raise ErrorConfiguracion(
            f"Resolucion del video {metadatos.ancho}x{metadatos.alto} distinta "
            f"de la referencia {ref[0]}x{ref[1]}"
        )
    return validar_consistencia(cfg)


def validar_consistencia(cfg: Configuracion) -> list[str]:
    """Devuelve la lista de advertencias explicitas de la configuracion.

    Si falta calibracion, debe emitirse una advertencia explicita y
    desactivarse las metricas basadas en distancia (M1, Paso 5).
    """
    advertencias: list[str] = []
    if not cfg.homografia.disponible:
        advertencias.append(ADVERTENCIA_SIN_CALIBRACION)
    if area_poligono(cfg.region_interes) <= 0:
        advertencias.append(
            "La region de interes tiene area nula: ninguna deteccion sera "
            "aceptada. Reemplazarla por la region real de la camara."
        )
    for carril in cfg.carriles:
        if area_poligono(carril.poligono) <= 0:
            advertencias.append(
                f"El carril {carril.indice} tiene area nula: no se asignaran "
                "vehiculos a ese carril."
            )
        if len(set(carril.poligono)) >= 3 and _autointersecta(carril.poligono):
            raise ErrorConfiguracion(f"El poligono del carril {carril.indice} se autointersecta")
    if len(set(cfg.region_interes)) >= 3 and _autointersecta(cfg.region_interes):
        raise ErrorConfiguracion("El poligono region_interes se autointersecta")
    advertencias.append("Sentido de circulacion y encuadre de los poligonos no verificados.")
    if len(cfg.carriles) < 2:
        advertencias.append(
            "Hay menos de dos carriles: zigzag y corte de carril no pueden activarse."
        )
    return advertencias


def cargar_politica(ruta_yaml: str, cfg: Configuracion) -> tuple[Configuracion, str]:
    """Carga umbrales explícitos reemplazando el conjunto completo."""
    if not os.path.isfile(ruta_yaml):
        raise ErrorConfiguracion(f"No existe el archivo de politica: {ruta_yaml}")
    try:
        with open(ruta_yaml, encoding="utf-8") as archivo:
            datos = yaml.safe_load(archivo)
    except yaml.YAMLError as error:
        raise ErrorConfiguracion(f"YAML de politica invalido: {error}") from error
    if not isinstance(datos, dict) or set(datos) != {"umbrales"}:
        raise ErrorConfiguracion("La politica debe contener solamente la clave 'umbrales'")
    efectiva = _umbrales(datos["umbrales"])
    with open(ruta_yaml, "rb") as archivo:
        sha = hashlib.sha256(archivo.read()).hexdigest()
    # La política es completa: claves omitidas reciben los defaults de Umbrales.
    return replace(cfg, umbrales=efectiva), sha


def _autointersecta(puntos: list[tuple[float, float]]) -> bool:
    """Detecta cruces entre lados no adyacentes, sin imponer límites de imagen."""
    def orient(a, b, c):
        return (b[0]-a[0]) * (c[1]-a[1]) - (b[1]-a[1]) * (c[0]-a[0])

    def cruza(a, b, c, d):
        o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
        if o1 * o2 < 0 and o3 * o4 < 0:
            return True

        def sobre_segmento(p, q, r):
            return (min(p[0], q[0]) <= r[0] <= max(p[0], q[0]) and
                    min(p[1], q[1]) <= r[1] <= max(p[1], q[1]))

        return (
            (o1 == 0 and sobre_segmento(a, b, c))
            or (o2 == 0 and sobre_segmento(a, b, d))
            or (o3 == 0 and sobre_segmento(c, d, a))
            or (o4 == 0 and sobre_segmento(c, d, b))
        )

    n = len(puntos)
    for i in range(n):
        a, b = puntos[i], puntos[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or j == (i + 1) % n or (j + 1) % n == i:
                continue
            if cruza(a, b, puntos[j], puntos[(j + 1) % n]):
                return True
    return False


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
