"""M1 - Carga y validacion de la configuracion YAML (RF1, RF4)."""

from __future__ import annotations

from roadguard.tipos import Configuracion


def cargar_configuracion(ruta_yaml: str) -> Configuracion:
    """Lee el YAML de camara y devuelve una Configuracion normalizada.

    Debe validar esquema y consistencia (M1): region de interes, limites de
    carril, correspondencias de homografia, clases vehiculares y umbrales.
    Rechazar configuraciones incoherentes ANTES de crear salidas (Paso 1).
    """
    raise NotImplementedError("RF1: cargar y validar YAML")


def validar_consistencia(cfg: Configuracion) -> list[str]:
    """Devuelve la lista de advertencias explicitas de la configuracion.

    Si falta calibracion, debe emitirse una advertencia explicita y
    desactivarse las metricas basadas en distancia (M1, Paso 5).
    """
    raise NotImplementedError("RF1/RF4: validaciones de esquema y consistencia")
