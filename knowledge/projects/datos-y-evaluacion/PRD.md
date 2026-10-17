# PRD — Datos y evaluación

> **Dueño de la decisión:** equipo RoadGuard · **Responsable:** Francisco Zúñiga · **Alcance:** medir cada etapa por separado contra §2.5, con datos reproducibles.
>
> **Estado →** [SEGUIMIENTO](../../roadmap/SEGUIMIENTO.md). El avance no vive en este documento.

## 1. Resumen

**Hoy:** los módulos M1 a M3 tienen tests unitarios, pero ningún criterio de §2.5 está medido. No hay datos en el repo y M4 no tiene sobre qué probarse fuera de casos armados a mano.

**Después:** cada criterio tiene un dataset elegido, un procedimiento escrito y código que lo calcula. M4 se puede ejercitar sobre trayectorias reales y su F1 se calcula contra una referencia independiente.

## 2. Historia

### Antes

Quien implementa el motor de reglas escribe tests con estados inventados y no sabe si sus umbrales marcan al 5 % o al 50 % del tráfico. Quien presenta el avance no puede decir si el sistema cumple ningún criterio.

### Después

Quien implementa M4 carga 60 s de autopista real con una línea, ve cuántos eventos produce cada regla y compara contra la referencia. El equipo llega a la demo con cada número de §2.5 medido y con su procedimiento.

## 3. Objetivos y no-objetivos

- **O1 —** Referencia de reglas reproducible desde datos públicos, con el mismo contrato que M3.
- **O2 —** F1 de eventos por regla, con un emparejamiento explícito y testeado.
- **O3 —** Protocolo escrito para mAP@0.5, IDF1, cambios de ID y FPS.
- **O4 —** Tres secuencias UA-DETRAC elegidas con criterios declarados.
- **NO1 —** No se anotan eventos a mano (propuesta §2.4).
- **NO2 —** No se reentrena YOLOv8n: se evalúa el preentrenado.
- **NO3 —** No se extrapolan resultados a cámaras no evaluadas (§4.4).

## 4. Flujo: hoy → después

```text
HOY
M4 → estados inventados en tests → sin noción de la tasa real de eventos

DESPUÉS
NGSIM → cargar_ngsim → [EstadoCinematico, Relacion] ─┬─► referencia ─────────────► eventos esperados ─┐
                                                      └─► degradar → M4 ──────────► eventos detectados ─┴─► F1 por regla
UA-DETRAC → video → M2 ──► cajas e IDs ──► mAP@0.5 · IDF1 · cambios de ID
                       └─► tiempos por etapa ──► FPS
```

## 5. Datos y reglas de negocio

| Dataset | Uso | Formato y procedencia | Estado |
|---|---|---|---|
| **NGSIM US-101** | Referencia de RF7–RF9 | CSV público, data.transportation.gov `8ect-6jqj`. 10 Hz, pies y pies/s. Carriles 1–5 principales, 6 auxiliar, 7 entrada y 8 salida | `Confirmada`: muestra de 60 s descargada (72.270 filas) |
| **UA-DETRAC** | mAP, IDF1 y demo | 100 secuencias (60 de entrenamiento y 40 de prueba), 25 FPS, 960×540, anotación XML por cuadro con ID, caja, clase (`car`, `bus`, `van`, `others`) y regiones ignoradas | `Brecha`: no descargado |
| **highD** | Segunda referencia, si hay acceso | CSV por grabación, 25 Hz, con THW, TTC y carril | `Brecha`: acceso no verificado |

**Invariantes de la conversión NGSIM.** `x_camino = Local_Y` y `y_camino = Local_X`, en metros. `t` se cuenta desde el primer `Global_Time` del archivo. La distancia es `Space_Headway` (frente a frente, la misma convención que M3). THW y TTC se calculan con `calcular_thw` y `calcular_ttc` de M3, nunca se leen del archivo.

**Definiciones de la referencia** (`referencia.py`):

- **Cercanía:** el tramo sostenido de cuadros consecutivos que cumple RF7 con un mismo predecesor. Un cuadro faltante o un cambio de predecesor cortan el tramo.
- **Cambio completo:** el mismo `DetectorCambioCarril` de M3, con permanencia de 1 s.
- **Zigzag:** al menos 2 cambios con `t_cruce` dentro de 10 s. Las ventanas solapadas del mismo vehículo forman un solo evento.
- **Corte:** el primer vehículo detrás del que cambió, en el carril de destino, dentro de los 2 s desde `t_cruce`, queda con THW < 1,5 s o TTC < 3 s. El evento es del que cambió, y `id_relacionado` es el cortado.
- Las ventanas se miden desde `t_cruce` (cuando ocurrió la maniobra) y no desde la confirmación. La latencia de M4 la absorbe la tolerancia del emparejamiento.

## 6. Contrato de comportamiento

```text
CUANDO se comparan eventos detectados contra eventos de referencia
  SI difieren en vehículo o regla
    NO hay acierto
  ENTONCES acierta el par cuyos intervalos, ampliados en ±tolerancia (1 s por defecto), se solapan;
           el emparejamiento es uno a uno y prioriza el mayor solape
Promesas: precisión, recobrado y F1 son None si su denominador es 0 (Paso 3)
```

## 7. Alcance

### Entra

- **Reglas:** referencia NGSIM, F1 por regla y global (micro-promedio), y degradación de trayectorias.
- **Detección:** mAP@0.5 de YOLOv8n preentrenado sobre las secuencias de prueba elegidas, excluyendo las regiones ignoradas de UA-DETRAC.
- **Seguimiento:** IDF1 y cambios de ID con `motmetrics` sobre las mismas secuencias.
- **Rendimiento:** FPS por etapa en Colab T4, sobre video de 1280×720.

### No entra

- Anotar conducta a mano.
- Comparar contra otros detectores o trackers.

### Protocolo propuesto para lo que falta (`Candidata a validar`)

| Criterio | Procedimiento |
|---|---|
| **mAP@0.5** | Métrica principal sin clase («vehículo»). Por clase, como informe: `car` y `van` → automóvil, `bus` → bus, `others` → camión (aproximado). Motocicleta no es evaluable, porque UA-DETRAC no la anota |
| **IDF1** | `motmetrics` con umbral de IoU 0,5, excluyendo regiones ignoradas. Los cambios de ID se reportan aparte, como pide §2.5 |
| **Degradación** | Sobre la trayectoria limpia, con semilla fija: ruido gaussiano en posición, pérdidas de tramos (oclusión) e intercambio de ID entre vecinos. Las magnitudes se toman del error que se mida en M3, no se inventan |
| **FPS** | UA-DETRAC es 960×540 y el criterio pide 720p, así que se escala a 1280×720 o se usa otro clip de 720p, y se declara cuál. Se reporta `fps_por_etapa` (M1, M2, M3, M4 y M5) |

### Criterios para elegir las 3 secuencias de la demo

Del conjunto de prueba de UA-DETRAC: (1) una de día con buen tiempo y flujo medio como caso base; (2) una con oclusiones o alta densidad; (3) una de noche o con lluvia. Las tres con al menos dos carriles en el mismo sentido y visibles completos, y con referencias rectas en la calzada para la homografía (líneas de carril y marcas de distancia conocida).

## 8. Milestones

| Corte | Resultado verificable |
|---|---|
| 2026-10-22 · avance | Referencia NGSIM con F1 testeado, protocolo escrito y primera medición de la tasa de eventos |
| 2026-11-12 · cierre de evaluación | mAP, IDF1, F1 de reglas y FPS medidos sobre las secuencias elegidas |
| 2026-11-19 · demo | Informe de resultados, fallos y limitaciones |

## 9. Criterios de aceptación

- [x] La muestra NGSIM se descarga con un comando reproducible y se convierte al contrato de M3.
- [x] THW y TTC de la referencia salen de las funciones de M3.
- [x] Los eventos de referencia respetan persistencia, cambio completo y ventana de corte (tests).
- [x] El F1 es uno a uno y queda en None sin denominador (tests).
- [ ] Las 3 secuencias UA-DETRAC están elegidas y documentadas.
- [ ] mAP@0.5, IDF1, cambios de ID y FPS están medidos.
- [ ] El F1 de reglas está medido con M4 sobre trayectorias degradadas.

## 10. Riesgos y decisiones abiertas

| Tema | Impacto | Qué falta decidir o validar | Responsable |
|---|---|---|---|
| RF7 marca al 43 % de los vehículos en congestión | alto | Medir en flujo libre; discutir umbrales o [ADR-0003](../../decisions/0003-puntaje-ponderado-por-severidad.md) | Z con C |
| Ruido de NGSIM | medio | Revisar si los cambios de carril espurios inflan zigzag | Z |
| UA-DETRAC no tiene motos | medio | Aceptar mAP sin clase como métrica principal | Z con J |
| 960×540 frente al criterio de 720p | bajo | Declarar el procedimiento de escalado | Z con J |
| highD | bajo | Confirmar si se pidió acceso | Z |

## Fuentes

- Formulario de propuesta TEL-328, §2.4, §2.5, §4.2 (M6) y §4.4.
- Wen, L. et al. (2020). *UA-DETRAC: A new benchmark and protocol for multi-object detection and tracking*. Computer Vision and Image Understanding, 193.
- [ADR-0001](../../decisions/0001-ngsim-como-referencia-de-reglas.md).
- Medición del 2026-10-17 sobre la muestra NGSIM descrita arriba.
