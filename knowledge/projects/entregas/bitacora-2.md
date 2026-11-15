# Bitácora 2: avance al 2026-11-18

<!-- Nota interna, no se exporta.
**Estado (2026-11-15):** borrador de Z. Las filas de J, R y C se redactaron desde el `git log` de `main` y de `origin` al 15-nov (último commit: merge del PR #4, 21-oct), no desde lo que cada uno diría; están marcadas `[revisar: J]`, `[revisar: R]` y `[revisar: C]` y cada uno las confirma o corrige antes del 2026-11-17. Las celdas `[pendiente: medir]` son datos que no existen todavía: no se rellenan con estimaciones. El ROADMAP asigna la bitácora 2 a C; este borrador existe para que haya algo que corregir y no una página en blanco. El formato final se ajusta a lo que pida Aula.
-->

## Período

Del 2026-10-22 al 2026-11-18. Incluye además lo que entró a `main` el 20 y 21 de octubre, después del cierre de la bitácora 1 (redactada el 18-oct): la calibración de MVI_39271, la primera parte de M5 y la regla de cercanía RF7.

## Resumen

Al 2026-11-15 la suite completa pasa con **170 tests** (`python -m pytest`, 5,5 s): 57 de la base y M1 a M3, 7 de calibración, 68 de la regla de cercanía RF7, 15 de M5 y 23 de M6. En `main` está la cadena de percepción y geometría completa, la primera cámara calibrada (`configs/MVI_39271.yaml`, RMSE 0,14 m), el dibujo de cajas, ID, clase y carril con escritura de MP4, la regla RF7 con eventos trazables y la referencia de reglas sobre NGSIM con F1 de eventos.

Lo que falta es lo que convierte eso en una demo: las reglas RF8 a RF11, el CSV de eventos y el JSON por vehículo, la integración end-to-end con CLI, los YAML de las otras dos secuencias y los videos de UA-DETRAC en `datos/`. **Todo el código del período entró entre el 20 y el 21 de octubre; desde el 22-oct no hay commits en `main` ni en ninguna rama remota.** Ninguna métrica de §2.5 está medida.

## Avance por actividad (§3.3)

| Actividad | Responsable | Qué hay | Evidencia |
|---|---|---|---|
| Investigación, acceso y selección de datos | Z | Las 3 secuencias UA-DETRAC quedaron elegidas y documentadas el 17-oct (MVI_39271 base, MVI_40714 densa, MVI_40742 noche), con notas de calibración por secuencia. Lo comprometido para después del 22-oct, bajar las imágenes completas de las 3 secuencias y convertirlas a MP4 a 25 FPS para que R calibre sobre video y J integre, **no se hizo**: `datos/videos/` y `datos/anotaciones/` solo tienen `.gitkeep`. highD sigue bloqueado sin acceso | PRD de datos y evaluación §7, `m6_evaluacion/ua_detrac.py`, `datos/` vacío al 15-nov |
| Detección y seguimiento | J `[revisar: J]` | Sin cambios en el período. M2 quedó completo en el PR #1 (17-oct): YOLOv8n con mapeo COCO a 4 clases, región de interés y ByteTrack sobre NumPy y SciPy. La integración y la CLI, que el reparto le asigna a J con plazo 1-nov, no tienen código en `main` ni en ramas remotas; existe una rama local `cli-integracion` en la punta de `main`, sin commits | `m2_deteccion/`, 10 tests; `git log main` sin commits de J después del 17-oct |
| Perspectiva, carriles y trayectorias | R `[revisar: R]` | Calibración de **1 de 3** secuencias: `configs/MVI_39271.yaml` generado por `scripts/calibrar_ua_detrac.py` desde los trazos de las líneas discontinuas (6 m de trazo y 9 m de hueco, carril de 3,5 m), con `m3_geometria/calibracion.py`. RMSE de reproyección 0,14 m, máximo 0,24 m; predice los trazos lejanos a unos 5 px y da 60 km/h para un auto real entre los cuadros 1 y 11. El ancho de carril de 3,5 m sigue como `Candidata a validar`. MVI_40714 y MVI_40742 no tienen YAML: en los 7 cuadros disponibles la calzada está tapada por vehículos y faltaban más cuadros para armar un fondo limpio, que dependían de los videos de Z. Además R subió el 20-oct dos commits propios de M3 (M3-T4 geometría y carriles, M3-T5 relaciones viales), lo que corrige el «implementó J» de la bitácora 1 | Commit `c3d3be6` (21-oct), `configs/MVI_39271.yaml`, 7 tests en `test_calibracion.py`; commits `6d043ef` y `ecb78cf` (20-oct) |
| Reglas y puntaje | C `[revisar: C]` | **RF7 cercanía** en `main` por el PR #4 (21-oct): `DetectorCercania` causal, que exige velocidad sobre 5 m/s, THW bajo 1,5 s y persistencia continua de 2 s; una observación ausente o inválida, o un cambio de predecesor, cortan el tramo. Los eventos llevan vehículo, relacionado, intervalo, variables medidas, umbrales y aporte (trazabilidad de §2.5). Sin calibración emite advertencia y no genera evento. Trae una demo sintética determinista (`python scripts/demo_cercania.py`) que no usa video ni GPU. **RF8 zigzag, RF9 corte, RF10 puntaje y RF11 bandas no tienen código**; el plan ajustado los cerraba el 1-nov. Hay una rama local `m4-reglas-puntaje` en la punta de `main`, sin commits | PR #4, `m4_reglas/cercania.py` (289 líneas), 68 tests en `test_reglas_cercania.py` y `test_demo_cercania.py` |
| Integración, video y registros | J (integración) · R (M5) `[revisar: J, R]` | **M5, primera parte** en `main` (21-oct): `anotar_cuadro` dibuja carriles, caja, centro, rótulo `ID clase carril` y una franja de advertencia cuando no hay calibración; `escritor.py` escribe el MP4 anotado. La caja usa un color neutro fijo porque todavía no hay nivel de riesgo que pintar. Faltan los colores de riesgo RF11, las alertas en pantalla, el CSV de eventos y el JSON por vehículo, que dependen de M4. **La integración end-to-end no existe**: los módulos se usan como biblioteca desde los tests y no hay un comando que tome MP4 más YAML y entregue las tres salidas | Commit `1bb70b0`, `m5_salidas/dibujo.py` y `escritor.py`, 15 tests en `test_salidas.py`; README §«Alcance de esta rama» |
| Evaluación y optimización | Z | Sin cambios en el período. La referencia NGSIM y el F1 de eventos quedaron en el PR #2 (23 tests). Lo planificado para este corte no se hizo: ni la degradación de trayectorias ni el primer F1 de RF7 sobre NGSIM, que ya era posible porque RF7 está en `main` desde el 21-oct; ni el parser por cuadro de UA-DETRAC para mAP e IDF1; ni la medición de FPS, que depende de una integración que no existe | `m6_evaluacion/`, 23 tests; PRD §9, criterios 6 y 7 sin marcar |

## Decisiones del período

- **Ninguna decisión nueva registrada.** ADR-0002 (velocidad anómala) y ADR-0003 (puntaje por severidad) siguen en `Candidata a validar`; no hay registro de la respuesta del docente del 22-oct `[revisar: Z]`.
- **El reparto propuesto el 17-oct se aplicó de hecho** en los commits del 20 y 21-oct: R calibró y arrancó M5, C hizo RF7. No está registrado un acuerdo explícito del equipo `[revisar: todos]`.
- **La calibración se hace por script y no a mano.** `calibrar_ua_detrac.py` detecta los trazos blancos (top-hat sobre el gris) en varios cuadros, promedia los extremos coincidentes y genera el YAML, que no se edita a mano. Decisión de R, visible en el encabezado del YAML `[revisar: R]`.

## Hallazgos

- **Una cámara calibrada desde las líneas del pavimento da escala métrica verificable sin medir en terreno.** Con dos líneas discontinuas de norma conocida se obtuvo RMSE de 0,14 m y una velocidad de 60 km/h plausible para un auto real. El límite es que el ancho de carril (3,5 m) es una norma, no una medición, y la cámara admite entre 3,0 y 3,5 m: toda la escala lateral hereda esa incertidumbre.
- **RF7 sobre trayectorias sintéticas se comporta como está escrita:** 1,9 s de THW bajo no confirma, 3,0 s confirma a los 2,0 s, una interrupción reinicia, y sin calibración no hay evento sino advertencia. El F1 contra la referencia NGSIM sigue sin medir, así que el hallazgo del 43 % de la bitácora 1 no tiene todavía su contraparte con el detector real.

## Anexo de métricas (§2.5)

Ninguna métrica cuantitativa de la propuesta está medida al 2026-11-15. La tabla queda con las metas y las fuentes previstas; se completa antes de la demo o se declara como no medida en ella.

| Criterio | Meta | Medido | Fuente prevista | Qué falta para medirlo |
|---|---|---|---|---|
| mAP@0.5 (sin clase, «vehículo») | ≥ 0,60 | `[pendiente: medir]` | YOLOv8n preentrenado sobre MVI_39271, MVI_40714 y MVI_40742, excluyendo regiones ignoradas | Videos de las 3 secuencias en `datos/`, parser XML por cuadro, cálculo de AP |
| IDF1 | ≥ 0,60 | `[pendiente: medir]` | `motmetrics`, IoU 0,5, sobre las mismas secuencias | Lo mismo que mAP, más la salida de tracks de M2 por secuencia |
| Cambios de ID | Informe aparte | `[pendiente: medir]` | `motmetrics` | Igual que IDF1 |
| F1 de reglas (RF7, RF8, RF9 y global) | ≥ 0,75 | `[pendiente: medir]` | `m6_evaluacion.referencia` sobre NGSIM US-101 (60 s, 270 vehículos) contra M4 sobre trayectorias degradadas; emparejamiento uno a uno con tolerancia ±1 s | RF8 y RF9 en M4; degradación de trayectorias. RF7 ya se puede medir hoy sobre trayectorias limpias |
| Rendimiento | ≥ 15 FPS a 720p en Colab T4 | `[pendiente: medir]` | `fps_por_etapa` (M1 a M5) sobre las secuencias escaladas de 960×540 a 1280×720 | Integración end-to-end y cuaderno de Colab |
| Demo en 3 secuencias | Cadena completa corriendo sobre las 3 | 1 secuencia calibrada, 0 corridas end-to-end | Demo del 19-nov | YAML de MVI_40714 y MVI_40742, videos, integración |
| Tests | Sin meta en la propuesta | **170 pasan** (15-nov) | `python -m pytest` | Es la única cifra verificada del período |

## Desvíos respecto del plan

El plan por corte del ROADMAP fijaba cuatro fechas internas. Comparadas con el `git log` de `main` y de `origin` al 15-nov:

| Corte | Fecha | Qué decía el plan | Qué muestra el repositorio |
|---|---|---|---|
| YAML calibrados | 26-oct | Las 3 secuencias con región, carriles y homografía (R) | 1 de 3, y entró el 21-oct, antes del plazo. Las otras dos no tienen YAML. Parte del bloqueo es de Z: los videos completos que iban a servir de fondo limpio nunca se bajaron |
| Integración end-to-end | 1-nov | CLI con MP4 más YAML a tracks, estados y relaciones por cuadro, con M4 y M5 enchufados (J); M4 completo RF7 a RF10 (C); degradación y primer F1 (Z) | Nada de eso entró. M4 tiene solo RF7 (21-oct). No hay CLI. No hay degradación ni F1 medido |
| Código congelado | 8-nov | M5 completo, umbrales ajustados, pipeline estable en T4 | No hubo nada que congelar: el último commit de código es del 21-oct. El código quedó «congelado» por falta de avance, no por decisión |
| Mediciones de §2.5 | 12-nov | mAP, IDF1, F1 y FPS medidos | Ninguna medida. El anexo de métricas está vacío |

Otros desvíos:

- **Actividad nula entre el 22-oct y el 15-nov.** La última semana de octubre la ocupó el Taller 2 individual (publicado el 23-oct, entregado el 1-nov) y la semana del 9 al 12-nov el Control 3 de PDI, los dos previstos en el ROADMAP, pero el plan asumía que igual se avanzaba, y no se avanzó. Las tres ramas locales creadas para este corte (`cli-integracion`, `m4-reglas-puntaje`, `manual-de-uso`) están en la punta de `main`, sin commits `[revisar: J, C, R]`.
- **M4 acumula dos corrimientos.** La propuesta lo cerraba el 25-oct; la bitácora 1 lo movió al 1-nov; al 15-nov sigue en RF7. Para la demo del 19-nov hacen falta RF8 a RF11 en cuatro días, además de la integración.
- **La demo en vivo del 19-nov está en riesgo tal como fue planificada** (cadena completa sobre 3 secuencias). Lo que sí se puede mostrar hoy: detección, seguimiento, carriles y advertencia sobre MVI_39271 escribiendo un MP4; la calibración con su rejilla métrica; la demo sintética de RF7; y la referencia NGSIM. Lo que no: puntaje, bandas de color, zigzag, corte, CSV y JSON `[revisar: todos]`.
- **El manual de uso (R, 18-nov) no tiene borrador en el repo**, y la bitácora 2 que el ROADMAP asigna a C se está redactando desde Z `[revisar: C, R]`.

## Próximos pasos (hasta el 2026-11-22)

Borrador para acordar el 2026-11-16 `[revisar: todos]`. El orden es el de las dependencias: sin integración no hay demo ni video.

- J: comando end-to-end sobre MVI_39271 con lo que hay (M1 a M3, RF7 y M5 parcial), aunque M4 esté incompleto; después, FPS por etapa.
- C: RF8, RF9 y RF10 con RF11, sobre el contrato de `tipos.py`, probados primero sobre NGSIM, que ya está cargado.
- R: colores de riesgo, CSV y JSON en M5 apenas exista `PuntajeRiesgo`; manual de uso; intentar MVI_40714 con los cuadros que haya.
- Z: bajar y convertir los videos de las 3 secuencias esta semana; F1 de RF7 sobre NGSIM limpio hoy mismo, que no depende de nadie; anexo de métricas con lo que se logre medir y lo que no, declarado; guion y edición del video.

## Propuestas para validar con el docente

- Siguen abiertas ADR-0002 (velocidad anómala) y ADR-0003 (puntaje por severidad), sin respuesta registrada `[revisar: Z]`.
- Declarar en la demo qué criterios de §2.5 se midieron y cuáles no, con el procedimiento escrito para los que faltan, en vez de presentar números sin fuente.
