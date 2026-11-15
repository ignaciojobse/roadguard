# Bitácora 2: avance al 2026-11-18

<!-- Nota interna, no se exporta.
**Estado (2026-11-15):** borrador de Z. Las filas de J, R y C se redactaron desde el `git log` de `main` y de `origin` al 15-nov (último commit: merge del PR #4, 21-oct), no desde lo que cada uno diría; están marcadas `[revisar: J]`, `[revisar: R]` y `[revisar: C]` y cada uno las confirma o corrige antes del 2026-11-17. Las celdas `[pendiente: medir]` son datos que no existen todavía: no se rellenan con estimaciones. El ROADMAP asigna la bitácora 2 a C; este borrador existe para que haya algo que corregir y no una página en blanco. El formato final se ajusta a lo que pida Aula.
-->

## Período

Del 2026-10-22 al 2026-11-18. Incluye además lo que entró a `main` el 20 y 21 de octubre, después del cierre de la bitácora 1 (redactada el 18-oct): la calibración de MVI_39271, la primera parte de M5 y la regla de cercanía RF7.

## Resumen

Al 2026-11-15 la suite completa pasa con **232 tests** (`python -m pytest`): 57 de la base y M1 a M3, 7 de calibración, 68 de la regla de cercanía RF7, 15 de M5 y 23 de M6. En `main` está la cadena de percepción y geometría completa, la primera cámara calibrada (`configs/MVI_39271.yaml`, RMSE 0,14 m), el dibujo de cajas, ID, clase y carril con escritura de MP4, la regla RF7 con eventos trazables y la referencia de reglas sobre NGSIM con F1 de eventos.

Lo que falta es lo que convierte eso en una demo: las reglas RF8 a RF11, el CSV de eventos y el JSON por vehículo, la integración end-to-end con CLI, los YAML de las otras dos secuencias y los videos de UA-DETRAC en `datos/`. **Todo el código del período entró entre el 20 y el 21 de octubre; desde el 22-oct no hay commits en `main` ni en ninguna rama remota.** Las métricas de §2.5 medidas el 15-nov sobre MVI_39271 están en el anexo; las otras dos secuencias siguen sin medir.

## Avance por actividad (§3.3)

| Actividad | Responsable | Qué hay | Evidencia |
|---|---|---|---|
| Investigación, acceso y selección de datos | Z | Las 3 secuencias UA-DETRAC quedaron elegidas y documentadas el 17-oct (MVI_39271 base, MVI_40714 densa, MVI_40742 noche), con notas de calibración por secuencia. Lo comprometido para después del 22-oct, bajar las imágenes completas de las 3 secuencias y convertirlas a MP4 a 25 FPS para que R calibre sobre video y J integre, se hizo recién el **15-nov**: `scripts/bajar_ua_detrac.py` lee el zip del espejo por rangos HTTP y bajó las 3 secuencias completas (4.405 JPG y 3 XML, 401 MB) en menos de 3 minutos, y `ffmpeg` las dejó en `datos/videos/<secuencia>.mp4` a 960×540 y 25 FPS. highD sigue bloqueado sin acceso | PRD de datos y evaluación §7, `scripts/bajar_ua_detrac.py`, `datos/videos/` (fuera de git) |
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

Medido el 2026-11-15 sobre **MVI_39271** completa (1.570 cuadros, 62,8 s) con la cadena real: `PYTHONPATH=src python -m roadguard procesar --video datos/videos/MVI_39271.mp4 --config configs/MVI_39271.yaml --salida salidas/MVI_39271 --dispositivo mps --tracks` y después `python scripts/medir_mvi.py MVI_39271`. Los números salen de `salidas/MVI_39271/metricas.json`, copiado con la consola, el CSV de eventos y cuatro cuadros del video anotado a `knowledge/projects/entregas/evidencia/MVI_39271/`. Máquina: Apple M3 Pro, 18 GB, inferencia en MPS con `yolov8n.pt` preentrenado en COCO, sin ajuste fino.

Dos vistas de la misma corrida, porque la referencia de UA-DETRAC anota la imagen completa (calzada contraria y fondo incluidos) y el sistema solo mira la región de interés del YAML: **región de interés** restringe la referencia a las cajas cuyo punto de calzada cae dentro del polígono (6.343 de 8.449 cajas; es el alcance declarado del sistema) y **cuadro completo** usa toda la referencia y dice cuánto se pierde por recortar. En las dos se descartan las cajas con centro en las 4 regiones ignoradas del XML (53 de referencia, 29 detectadas) y se usa IoU ≥ 0,5. Clases: car y van se cuentan como automóvil, bus como bus y others como camión; la métrica principal es sin clase, como fija el PRD.

| Criterio | Meta | Medido | Fuente | Qué falta para medirlo |
|---|---|---|---|---|
| mAP@0.5 (sin clase, «vehículo») | ≥ 0,60 | MVI_39271: **0,918** en la región de interés (precisión 0,968, recobrado 0,928) y **0,693** sobre el cuadro completo (recobrado 0,700: el 25 % de la referencia está fuera de la región). Por clase en la región: automóvil 0,903, bus 0,984. MVI_40714 y MVI_40742: `[pendiente: medir]` | `evidencia/MVI_39271/metricas.json` → `region_interes.map50_sin_clase` y `cuadro_completo.map50_sin_clase`; `scripts/medir_mvi.py` (AP con interpolación en todos los puntos) | YAML de MVI_40714 y MVI_40742 (los videos ya están en `datos/videos/`) |
| IDF1 | ≥ 0,60 | MVI_39271: **0,898** en la región de interés (IDTP 5.577, IDFP 507, IDFN 766) y **0,772** sobre el cuadro completo. MOTA 0,896 y 0,680 | `metricas.json` → `seguimiento.idf1`; asignación húngara entre trayectorias (`scipy.optimize.linear_sum_assignment`) sobre cuadros con IoU ≥ 0,5 | Las otras dos secuencias |
| Cambios de ID | Informe aparte | **8** en MVI_39271 (47 trayectorias de referencia, 55 detectadas; el pipeline registró además 2 reinicios de historial por identidad dudosa) | `metricas.json` → `seguimiento.cambios_id`; `consola.txt` | Las otras dos secuencias |
| F1 de reglas (RF7, RF8, RF9 y global) | ≥ 0,75 | `[pendiente: medir]`. Sobre MVI_39271 el motor produjo **5 cercanías, 2 zigzag y 1 corte** en 62,8 s, pero UA-DETRAC no trae referencia de eventos, así que esos 8 no se pueden calificar como aciertos o falsos positivos; solo se pueden revisar a mano en el video | `evidencia/MVI_39271/eventos.csv` | La referencia de eventos vive en NGSIM (`m6_evaluacion.referencia`), y el F1 contra M4 requiere la degradación de trayectorias, que no está hecha |
| Rendimiento | ≥ 15 FPS a 720p en Colab T4 | **51,7 FPS** end-to-end a 960×540 en M3 Pro con MPS, escribiendo el MP4 anotado. Por etapa: detección 68,3 FPS (la que manda), salidas 267, seguimiento 3.251, geometría 5.820, reglas 20.596 | `consola.txt`; `metricas.json` → `fps_procesamiento` y `fps_por_etapa` | Medir en T4 y a 1280×720, que es lo que pide la propuesta; esta cifra es de otra máquina y otra resolución |
| Demo en 3 secuencias | Cadena completa corriendo sobre las 3 | **3 videos listos** en `datos/videos/` (960×540, 25 FPS) y **1 corrida end-to-end** completa (MVI_39271) | `scripts/bajar_ua_detrac.py`, `ffmpeg`; `evidencia/MVI_39271/cuadros/` | YAML de MVI_40714 y MVI_40742 |
| Tests | Sin meta en la propuesta | **232 pasan** (15-nov) | `python -m pytest` | — |

Lo que el video anotado muestra en los cuadros guardados: las cajas caen sobre los vehículos de la calzada cercana con clase correcta (los buses como bus; las van salen como automóvil porque COCO no las separa), el carril asignado es coherente con la posición, la calzada contraria y el fondo quedan sin cajas por la región de interés, y las bandas de color funcionan (bus 32 en amarillo con 50 puntos tras el corte, auto 40 en amarillo con 40 tras la cercanía). El bus 32 concentra el corte y uno de los zigzag al salir del paradero: cruza dos líneas en 5 s, que es un cambio de carril real pero de una maniobra de parada, no de conducción agresiva. Eso es un hallazgo para los umbrales, no un error del detector.

## Desvíos respecto del plan

El plan por corte del ROADMAP fijaba cuatro fechas internas. Comparadas con el `git log` de `main` y de `origin` al 15-nov:

| Corte | Fecha | Qué decía el plan | Qué muestra el repositorio |
|---|---|---|---|
| YAML calibrados | 26-oct | Las 3 secuencias con región, carriles y homografía (R) | 1 de 3, y entró el 21-oct, antes del plazo. Las otras dos no tienen YAML. Parte del bloqueo es de Z: los videos completos que iban a servir de fondo limpio nunca se bajaron |
| Integración end-to-end | 1-nov | CLI con MP4 más YAML a tracks, estados y relaciones por cuadro, con M4 y M5 enchufados (J); M4 completo RF7 a RF10 (C); degradación y primer F1 (Z) | No entró en la fecha. Hasta el 14-nov M4 tenía solo RF7 (21-oct) y no había CLI; el 15-nov Z agregó RF8 a RF11 y el pipeline con CLI en la rama `prototipo-18nov` (dos semanas tarde). No hay degradación ni F1 medido |
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
