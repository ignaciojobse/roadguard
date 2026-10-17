"""Orquestacion de la cadena completa (seccion 4.3).

Secuencia de procesamiento y manejo de casos limite:

Paso 1. Validar video, FPS y YAML; rechazar configuraciones incoherentes
        antes de crear salidas.
Paso 2. Procesar cuadros en orden temporal y actualizar detecciones, tracks
        y estado geometrico sin acceder a cuadros futuros.
Paso 3. Calcular velocidad y metricas unicamente con historial suficiente;
        representar como no disponible cualquier division invalida o
        ausencia de predecesor.
Paso 4. Confirmar un cambio de carril solo tras permanencia estable en el
        nuevo carril.
Paso 5. Suspender o degradar alertas dependientes de distancia cuando no
        exista calibracion metrica, manteniendo deteccion, seguimiento y una
        advertencia visible.
Paso 6. Cerrar archivos de salida de forma segura e incluir configuracion,
        version del modelo, FPS y resumen de eventos para reproducibilidad.
"""

from __future__ import annotations

from roadguard.tipos import ResumenEjecucion


def ejecutar(
    ruta_video: str,
    ruta_config: str,
    directorio_salida: str,
) -> ResumenEjecucion:
    """Proceso por lotes: MP4 + YAML -> MP4 anotado + CSV + JSON (seccion 1.3).

    Orden de la cadena (seccion 1.3):
        M1 ingesta -> M2 deteccion/seguimiento -> M3 geometria y relaciones
        -> M4 reglas y puntaje -> M5 video anotado y registros.
    """
    raise NotImplementedError("Secuencia completa de la seccion 4.3")
