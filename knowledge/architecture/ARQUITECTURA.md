# Arquitectura

> El detalle de cada módulo vive en su código y en [`docs/PLAN_IMPLEMENTACION.md`](../../docs/PLAN_IMPLEMENTACION.md). Acá va el mapa.

## Módulos

| Módulo | Paquete | RF | Responsable | Estado del código |
|---|---|---|---|---|
| Contrato de datos | `tipos.py`, `poligonos.py` | — | Base compartida (J) | En `main` |
| M1 Ingesta y configuración | `m1_ingesta/` | RF1, RF4 | Base compartida (J) | En `main` |
| M2 Detección y seguimiento | `m2_deteccion/` | RF2, RF3 | J | En `main` |
| M3 Geometría vial y trayectorias | `m3_geometria/` | RF4, RF5, RF6 | R (implementó J) | En `main` |
| M4 Motor de reglas y riesgo | `m4_reglas/` | RF7–RF10 | C | Parcial: cercania RF7 |
| M5 Visualización y exportación | `m5_salidas/` | RF11, RF12 | Ver [ROADMAP](../roadmap/ROADMAP.md#responsables) | Parcial: cajas, ID, carril y MP4 anotado |
| M6 Evaluación y diagnóstico | `m6_evaluacion/` | Verifica RF2–RF12 | Z | Parcial: referencia NGSIM y F1 de eventos |
| Integración y CLI | por definir | RF1, RF12 | Ver [ROADMAP](../roadmap/ROADMAP.md#responsables) | Pendiente |

Los nombres de paquete de M4 y M5 son una sugerencia; los decide su responsable.

## Flujo por cuadro

```text
MP4 + YAML
  └─ M1  cargar_configuracion · iterar_cuadros ──► (cuadro, t, imagen)
       └─ M2  DetectorVehiculos → SeguidorByteTrack ──► [Track]
            └─ M3  ProyectorCamino → HistorialCausal ──► [EstadoCinematico], [CambioCarril]
                 └─ M3  calcular_relaciones ──► [Relacion]
                      └─ M4  reglas + puntaje ──► [Evento], [PuntajeRiesgo]
                           └─ M5  MP4 anotado · eventos CSV · resumen JSON
```

M6 se engancha en dos puntos sin pasar por la cámara:

```text
NGSIM / highD ──► m6_evaluacion.ngsim ──► [EstadoCinematico], [Relacion]  (mismo contrato que M3)
                                       ├─► M4 (con degradación) ──► eventos detectados ─┐
                                       └─► referencia ──────────► eventos esperados ───┴─► F1
UA-DETRAC ──► anotaciones ──► mAP@0.5 (M2) · IDF1 y cambios de ID (M2)
```

Como M6 entrega exactamente `EstadoCinematico` y `Relacion`, **M4 se puede desarrollar y probar sobre trayectorias reales desde hoy**, sin esperar video calibrado.

## El contrato de datos

`src/roadguard/tipos.py` es la interfaz entre los cuatro integrantes. Se pueden agregar campos; renombrar o quitar, no, sin avisar al equipo. Ya trae las estructuras de M4 a M6 (`Regla`, `Evento`, `PuntajeRiesgo`, `ResumenVehiculo` y `ResumenEjecucion`), así que quien implemente esos módulos parte con los tipos listos.

## Stack

Python ≥ 3.10, Ultralytics YOLOv8n, ByteTrack, OpenCV, NumPy, SciPy, PyYAML y pytest (`requirements.txt`). Colab T4 para medir rendimiento. Sin API pública ni servicio web.

## Fuentes

- Formulario de propuesta TEL-328, 2026-09-11, §4.2. `Confirmada`.
- Código en `main` al 2026-10-17 (PR #1). `Confirmada`.
