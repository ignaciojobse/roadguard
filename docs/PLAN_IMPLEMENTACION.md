# Plan de implementacion de RoadGuard

Documento de trabajo para ejecutar con Claude Code. Todo lo que sigue deriva
exclusivamente de la propuesta TEL-328 (secciones 1 a 4). No agrega alcance
nuevo.

---

## 0. Reglas que no se negocian

Antes de escribir cualquier modulo, estas restricciones vienen del documento
y condicionan el diseno de todas las tareas:

1. **Causalidad (RF5, Paso 2).** En el cuadro `t` solo puede usarse
   informacion disponible hasta `t`. Prohibido mirar cuadros futuros, incluso
   en el suavizado. El proceso es por lotes pero debe comportarse como si
   fuera una transmision en vivo.
2. **Tiempo en segundos, no en cuadros.** Las ventanas de 2 s, 5 s y 10 s se
   evaluan sobre `t` derivado de los FPS reales del archivo.
3. **Degradacion sin calibracion (Paso 5, M1).** Si falta homografia,
   distancia, THW y TTC quedan en `None`, las reglas que dependen de ellos se
   suspenden, y deteccion, seguimiento y una advertencia visible se mantienen.
4. **No disponible en vez de valor inventado (Paso 3).** Cualquier division
   invalida, historial insuficiente o ausencia de predecesor se representa
   como no disponible.
5. **Cambio de carril completo (Paso 4).** Solo se confirma tras permanencia
   estable en el nuevo carril. Las oscilaciones sobre la linea no cuentan.
6. **Trazabilidad (seccion 2.5).** Cada evento debe incluir vehiculo,
   intervalo, regla, variables medidas, umbrales y puntaje.
7. **Lenguaje de las salidas (secciones 1.1 y 1.2).** Las alertas son
   experimentales. No se afirma conduccion temeraria, culpabilidad ni
   infraccion en ningun texto, etiqueta, columna o rotulo del video.

El contrato de datos ya esta implementado en `src/roadguard/tipos.py`. **No
modificar esas estructuras sin avisar al equipo**: son la interfaz entre los
cuatro integrantes. Agregar campos esta permitido; renombrar o quitar, no.

---

## 1. Orden de trabajo

Las dependencias reales son estas. Las tareas de un mismo nivel se pueden
hacer en paralelo porque solo dependen del contrato de datos.

```
T1 M1 ingesta  ──┐
                 ├──> T4 M3 geometria ──> T5 M3 relaciones ──┐
T2 M2 deteccion ─┘                                           ├──> T7 M5 salidas ──> T8 pipeline
                                                             │
T3 M4 reglas (sobre datos sinteticos, sin esperar a M2/M3) ──┘

T6 datos (highD/NGSIM o UA-DETRAC)  ──> T9 M6 evaluacion
```

T3 es la clave para no serializar al equipo: **el motor de reglas se puede
implementar y probar completo con `EstadoCinematico` y `Relacion` construidos
a mano en los tests**, sin que exista una sola deteccion real.

---

## 2. Tareas

### T1 - M1 Ingesta y configuracion (RF1, RF4, RF12)

Archivos: `m1_ingesta/config.py`, `m1_ingesta/video.py`.

- `leer_metadatos`: validar codec, resolucion y FPS del MP4. Fallar con
  mensaje claro si el archivo no se puede abrir.
- `iterar_cuadros`: generador `(cuadro, t, imagen)` en orden temporal
  estricto. `t = cuadro / fps`.
- `cargar_configuracion`: leer el YAML con PyYAML y construir
  `Configuracion`. Validar esquema y consistencia: region de interes y
  poligonos de carril con al menos 3 puntos, homografia con pares
  balanceados de al menos 4 puntos, clases no vacias, umbrales numericos.
- `validar_consistencia`: devolver advertencias. Si
  `cfg.homografia.disponible` es False, incluir la advertencia explicita de
  falta de calibracion.
- Rechazar configuraciones incoherentes **antes** de crear cualquier salida
  (Paso 1).

Aceptacion: carga `configs/camara_ejemplo.yaml` sin error; un YAML con
homografia vacia carga pero devuelve la advertencia; un YAML con un carril de
2 puntos falla.

---

### T2 - M2 Deteccion y seguimiento (RF2, RF3)

Archivos: `m2_deteccion/detector.py`, `m2_deteccion/tracker.py`.
Responsable segun la propuesta: Ignacio Jobse.

- `DetectorVehiculos`: Ultralytics YOLOv8n preentrenado. Detectar
  automoviles, buses, camiones y motocicletas. Registrar clase, caja y
  confianza (RF2).
- `filtrar_region_interes`: descartar detecciones cuyo punto de contacto con
  la calzada cae fuera del poligono configurado.
- Aplicar `confianza_min_deteccion` de la configuracion.
- `SeguidorByteTrack`: asociar por confianza, movimiento y solapamiento.
  Mantener el ID persistente mientras el vehiculo sea observable, incluyendo
  oclusiones breves. Administrar apariciones y desapariciones (RF3).
- Salida: lista de `Track` por cuadro, con `punto_calzada_px` ya calculado
  desde `Caja.punto_calzada`.

Decision a documentar: el mapeo entre las clases del modelo preentrenado y
las clases de la configuracion debe quedar explicito en el codigo, porque el
protocolo de evaluacion de T9 depende de el.

Aceptacion: sobre una secuencia corta, los IDs se mantienen a lo largo del
video y no se emiten detecciones fuera de la region de interes.

---

### T3 - M4 Motor de reglas y riesgo (RF7, RF8, RF9, RF10, RF11)

Archivos: `m4_reglas/cercania.py`, `zigzag.py`, `corte.py`, `puntaje.py`.
Responsable segun la propuesta: Francisco Castillo.
**Se implementa con datos sinteticos. No espera a T2 ni a T4.**

- `ReglaCercania` (RF7): maquina de estados con ventana deslizante. Activa
  cuando el seguidor supera 5 m/s y mantiene THW < 1,5 s durante al menos
  2 s. Si THW es `None`, no evalua. Evita eventos duplicados mientras la
  condicion sigue activa.
- `ReglaZigzag` (RF8): cuenta `CambioCarril` confirmados dentro de una
  ventana de 10 s. Activa con 2 o mas. Solo recibe cambios completos, los
  incompletos los descarta T4.
- `ReglaCorte` (RF9): al recibir un `CambioCarril`, abre una ventana de 2 s.
  Dentro de ella, si el nuevo seguidor presenta THW < 1,5 s o TTC < 3 s,
  activa.
- `AcumuladorPuntaje` (RF10): aportes de 40 cercania, 35 zigzag, 50 corte.
  Total limitado a 100. Cada aporte se retira a los 5 s de haberse
  registrado.
- `nivel_desde_puntaje` (RF11): 0-29 verde, 30-59 amarillo, 60-100 rojo.
- Todo evento se emite como `Evento` con `variables` y `umbrales` poblados,
  no vacios (trazabilidad, seccion 2.5).

Aceptacion: los tests `test_regla_cercania.py`, `test_regla_zigzag.py`,
`test_regla_corte.py` y `test_puntaje.py` pasan con los casos listados en sus
docstrings. Quitar el `pytestmark` de skip al implementar.

---

### T4 - M3 Geometria y carriles (RF4, RF5)

Archivos: `m3_geometria/homografia.py`, `carriles.py`, `trayectorias.py`.
Responsable segun la propuesta: Giancarlos Ricci.

- `ProyectorCamino`: homografia para vista de pajaro desde las
  correspondencias del YAML. Proyecta el punto inferior de cada caja al plano
  del camino. Si no hay calibracion, `disponible` es False y `proyectar`
  devuelve `None`.
- `asignar_carril`: asignacion mediante poligonos de carril, con un estado de
  confianza (RF4). Devolver `(None, 0.0)` fuera de todo carril.
- `DetectorCambioCarril`: confirma cambios completos solo tras permanencia
  estable en el nuevo carril (Paso 4). Registrar tanto `t_cruce` como
  `t_confirmacion`, porque la diferencia es la latencia de decision y debe
  poder reportarse.
- `HistorialCausal`: suavizado causal y diferencias temporales para obtener
  velocidad. Calcular solo con historial suficiente; si no, `None` (Paso 3).

Aceptacion: con homografia valida, un vehiculo que recorre la region produce
`x_camino` monotono; sin homografia, todos los campos metricos son `None` y
`calibrado` es False.

---

### T5 - M3 Relaciones viales (RF6)

Archivo: `m3_geometria/relaciones.py`. Depende de T4.

- `calcular_relaciones`: dentro de cada carril, ordenar por posicion
  longitudinal y emparejar predecesor/seguidor.
- `calcular_thw`: distancia dividida por la velocidad del seguidor. `None`
  si la velocidad es cero, negativa o `None`.
- `calcular_ttc`: solo con tasa de cierre positiva. En cualquier otro caso,
  `None`.
- Sin calibracion, los tres quedan en `None` (Paso 5).

Aceptacion: `test_relaciones.py` pasa con los casos de su docstring.

---

### T6 - Datos (seccion 2.4)

Responsable segun la propuesta: Francisco Zuniga.

- **UA-DETRAC** como fuente visual principal para deteccion y seguimiento.
  Seleccionar las secuencias de trabajo y dejarlas documentadas con
  resolucion y condiciones (riesgo de transferencia entre datasets, 4.4).
  UA-DETRAC no incluye etiquetas de conduccion riesgosa y la propuesta
  establece que no se crearan anotaciones masivas nuevas.
- **highD** para desarrollar y validar reglas sobre trayectorias reales con
  IDs, carriles, THW, TTC y cambios de carril. La propuesta fija como
  mitigacion solicitarlo al inicio y, si no esta disponible, emplear
  **NGSIM** (posiciones, velocidades y carriles cada 0,1 s).
- Cargar las trayectorias elegidas a `EstadoCinematico` y `Relacion` para que
  T9 pueda calcular eventos de referencia con el mismo motor de T3.

Aceptacion: un script reproducible que convierte el dataset elegido al
contrato de datos, mas una nota en `docs/` con secuencias, resolucion y
condiciones.

---

### T7 - M5 Visualizacion y exportacion (RF11, RF12)

Archivos: `m5_salidas/anotacion.py`, `m5_salidas/registros.py`.

- `AnotadorVideo`: OpenCV para composicion y codificacion MP4. Dibuja caja,
  ID, alerta y riesgo por vehiculo con el color de la banda (RF11). Si falta
  calibracion, mantener la advertencia visible en pantalla (Paso 5).
- `exportar_eventos_csv`: un evento por activacion, con las columnas de
  `COLUMNAS_EVENTOS`, incluyendo las variables medidas y los umbrales
  vigentes.
- `exportar_resumen_json`: resumen por vehiculo mas `ResumenEjecucion` con
  configuracion, version del modelo, FPS y resumen de eventos (Paso 6).
- Cerrar todos los archivos de forma segura, incluso si la ejecucion falla a
  mitad de camino (Paso 6).

Aceptacion: las tres salidas se generan y el JSON permite reconstruir con que
configuracion y modelo se produjo la corrida.

---

### T8 - Pipeline (seccion 4.3)

Archivo: `pipeline.py`. Responsable segun la propuesta: Francisco Castillo.

Encadenar en el orden de la seccion 1.3, respetando los seis pasos de la
seccion 4.3. Por cada cuadro:

1. Obtener imagen y `t` de M1.
2. Detectar y actualizar tracker (M2) -> `list[Track]`.
3. Proyectar, asignar carril, actualizar historial (M3) ->
   `list[EstadoCinematico]`, mas `CambioCarril` confirmados.
4. Calcular relaciones (M3) -> `list[Relacion]`.
5. Evaluar reglas y actualizar puntajes (M4) -> `list[Evento]`,
   `PuntajeRiesgo` por vehiculo.
6. Escribir cuadro anotado (M5).

Al terminar: exportar CSV y JSON, cerrar archivos, devolver
`ResumenEjecucion`.

Aceptacion: demostracion end-to-end en al menos tres secuencias
representativas (seccion 2.5).

---

### T9 - M6 Evaluacion y diagnostico (seccion 2.5)

Archivos: `m6_evaluacion/*.py`. Responsable segun la propuesta: Francisco
Zuniga.

Criterios de aceptacion cuantitativos de la propuesta:

| Metrica | Criterio | Fuente |
|---|---|---|
| mAP@0.5 | >= 0,60 | secuencias seleccionadas de UA-DETRAC |
| IDF1 | >= 0,60 | UA-DETRAC, con informe separado de cambios incorrectos de ID |
| F1 de reglas | >= 0,75 | trayectorias degradadas vs. eventos de referencia de highD/NGSIM |
| Rendimiento | >= 15 FPS a 720p | GPU Colab T4. 25 FPS como extension |
| Demostracion | >= 3 secuencias | end-to-end |

- `degradar`: aplicar ruido, perdida de observaciones e intercambio de ID
  sobre trayectorias limpias, con semilla registrada.
- `evaluar_reglas`: precision, recobrado y F1 comparando los eventos
  obtenidos desde trayectorias degradadas contra los de referencia.
- `medir_fps`: desglose por etapa. Ante rendimiento insuficiente, la
  propuesta indica reducir region o frecuencia de deteccion y perfilar etapas
  **antes** de modificar umbrales (riesgos 4.4).
- Robustez verificada en: oclusiones, perdida de ID, vehiculos detenidos,
  ausencia de predecesor, cambios incompletos y camaras sin calibracion
  (seccion 2.5).

Aceptacion: un informe de resultados con errores, limitaciones y evidencia
de aceptacion (M6).

---

## 3. Riesgos declarados y su mitigacion (seccion 4.4)

Mantener estas mitigaciones presentes durante la implementacion:

| Riesgo | Mitigacion declarada |
|---|---|
| Perspectiva o calibracion imprecisa | Validar puntos, limitar el analisis a la region confiable e informar incertidumbre |
| Oclusiones e intercambios de ID | Ajustar ByteTrack, medir IDF1 e ID switches, reiniciar historiales cuando la identidad sea dudosa |
| Transferencia entre datasets | Documentar secuencias, resolucion y condiciones; no extrapolar a camaras no evaluadas |
| Acceso tardio a highD | Reemplazo por NGSIM |
| Rendimiento insuficiente | Reducir region o frecuencia de deteccion, usar YOLOv8n y perfilar etapas antes de tocar umbrales |
| Interpretacion indebida | Rotular las alertas como experimentales, conservar evidencia y exigir revision humana |

---

## 4. Como trabajar con Claude Code sobre este repo

- Una tarea por sesion. Pasar el identificador: "implementa T3 segun
  `docs/PLAN_IMPLEMENTACION.md`".
- Exigir que los tests de la tarea pasen antes de dar por cerrada la tarea.
- No tocar `src/roadguard/tipos.py` salvo para **agregar** campos.
- Cada funcion implementada reemplaza su `NotImplementedError` pero conserva
  el docstring con la referencia al RF, porque es lo que conecta el codigo
  con el informe final.
- Al cerrar cada tarea, commit con el identificador: `T3: motor de reglas
  (RF7-RF11)`.
