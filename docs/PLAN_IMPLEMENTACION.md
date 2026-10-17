# Plan de implementacion de RoadGuard - base, M2 y M3

Documento de trabajo. Todo lo que sigue deriva exclusivamente de la
propuesta TEL-328 (secciones 1 a 4). No agrega alcance nuevo.

Esta rama cubre la base compartida (contrato de datos y M1 ingesta), M2
deteccion y seguimiento (Ignacio Jobse) y M3 geometria vial y trayectorias
(Giancarlos Ricci). El motor de reglas (M4), la visualizacion y exportacion
(M5), la evaluacion (M6), los datos y la integracion end-to-end se planifican
y ejecutan por separado.

---

## 0. Reglas que no se negocian

Estas restricciones vienen del documento y condicionan el diseno de todas
las tareas, incluidas las que viven fuera de esta rama:

1. **Causalidad (RF5, Paso 2).** En el cuadro `t` solo puede usarse
   informacion disponible hasta `t`. Prohibido mirar cuadros futuros, incluso
   en el suavizado. El proceso es por lotes pero debe comportarse como si
   fuera una transmision en vivo.
2. **Tiempo en segundos, no en cuadros.** Las ventanas temporales se evaluan
   sobre `t` derivado de los FPS reales del archivo.
3. **Degradacion sin calibracion (Paso 5, M1).** Si falta homografia,
   distancia, THW y TTC quedan en `None`, las reglas que dependen de ellos se
   suspenden, y deteccion, seguimiento y una advertencia visible se mantienen.
4. **No disponible en vez de valor inventado (Paso 3).** Cualquier division
   invalida, historial insuficiente o ausencia de predecesor se representa
   como no disponible.
5. **Cambio de carril completo (Paso 4).** Solo se confirma tras permanencia
   estable en el nuevo carril. Las oscilaciones sobre la linea no cuentan.
6. **Trazabilidad (seccion 2.5).** Cada evento debe incluir vehiculo,
   intervalo, regla, variables medidas, umbrales y puntaje. El estado que
   produce M3 es lo que sostiene esa trazabilidad aguas abajo.
7. **Lenguaje de las salidas (secciones 1.1 y 1.2).** Las alertas son
   experimentales. No se afirma conduccion temeraria, culpabilidad ni
   infraccion en ningun texto, etiqueta, columna o rotulo.

El contrato de datos esta implementado en `src/roadguard/tipos.py` y se
conserva completo, incluidas las estructuras que consumen M4, M5 y M6.
**No modificar esas estructuras sin avisar al equipo**: son la interfaz
entre los cuatro integrantes. Agregar campos esta permitido; renombrar o
quitar, no.

---

## 1. Orden de trabajo

Las dependencias reales dentro de esta rama son estas. T1 y T2 solo dependen
del contrato de datos, asi que se pueden hacer en paralelo.

```
T1 M1 ingesta  --+
                 +--> T4 M3 geometria --> T5 M3 relaciones
T2 M2 deteccion -+
```

La salida de T5 (`EstadoCinematico` y `Relacion` por ID y por cuadro) es el
punto de integracion con el motor de reglas. M4 se puede implementar y
probar completo construyendo esas estructuras a mano en sus tests, sin
esperar a que exista una sola deteccion real.

---

## 2. Tareas

### T1 - M1 Ingesta y configuracion (RF1, RF4)

Archivos: `m1_ingesta/config.py`, `m1_ingesta/video.py`.
Base compartida: la consumen M2 y M3.

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
las clases de la configuracion queda explicito en el codigo, porque el
protocolo de evaluacion de M6 depende de el.

Aceptacion: sobre una secuencia corta, los IDs se mantienen a lo largo del
video y no se emiten detecciones fuera de la region de interes.

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

Aceptacion: `test_relaciones.py` y `test_robustez.py` pasan con los casos de
sus docstrings.

---

## 3. Criterios de aceptacion aplicables (seccion 2.5)

De los criterios cuantitativos de la propuesta, estos dependen de los
modulos de esta rama:

| Criterio | Meta | Observacion |
|---|---|---|
| mAP@0.5 | >= 0,60 | Depende de M2. Se mide en M6, fuera de esta rama |
| IDF1 | >= 0,60 | Depende de M2, con informe separado de intercambios de ID |
| Rendimiento | >= 15 FPS a 720p en GPU Colab T4 | Depende sobre todo del costo de M2 |

Ninguno esta medido todavia: la medicion requiere el modulo de evaluacion y
las secuencias anotadas, que se trabajan por separado. Lo que si se verifica
aqui son los casos limite que caen dentro de M2 y M3:

| Caso limite | Prueba |
|---|---|
| Oclusiones breves | `tests/test_deteccion_seguimiento.py` |
| Perdida de ID y salto imposible | `tests/test_geometria.py` |
| Vehiculos detenidos | `tests/test_robustez.py` |
| Ausencia de predecesor | `tests/test_robustez.py`, `tests/test_relaciones.py` |
| Cambios incompletos | `tests/test_carriles.py` |
| Camaras sin calibracion | `tests/test_robustez.py`, `tests/test_ingesta.py` |

---

## 4. Riesgos de estos modulos (seccion 4.4)

- **Perspectiva o calibracion imprecisa**: validar puntos, limitar el
  analisis a la region confiable e informar incertidumbre. Sin homografia
  utilizable, M3 degrada a campos no disponibles en vez de inventar metros.
- **Oclusiones e intercambios de ID**: ajustar los parametros del seguidor y
  reiniciar historiales cuando la identidad sea dudosa. `HistorialCausal`
  descarta saltos imposibles.
- **Transferencia entre datasets**: documentar secuencias, resolucion y
  condiciones; no extrapolar resultados a camaras no evaluadas.
- **Rendimiento insuficiente**: reducir region o frecuencia de deteccion,
  usar YOLOv8n y perfilar etapas antes de modificar umbrales.
