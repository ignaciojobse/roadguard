# Manual de uso del prototipo RoadGuard

<!-- Nota interna, no se exporta.
Entregable del ramo para el 2026-11-18 (5 % de la nota). Fuente en Markdown; se exporta con exportar_entregable.py. Contrato de la CLI verificado el 2026-11-15 contra la rama prototipo-18nov (corrida real de `python -m roadguard procesar`).
-->

> RoadGuard es un prototipo de apoyo a la revisión humana de video de tránsito. Este manual explica cómo instalarlo, preparar un video con su configuración, ejecutarlo y leer lo que produce, sin necesidad de hablar con el equipo. Proyecto TEL-328 Procesamiento Digital de Imágenes, UTFSM, 2026.

## 1. Qué es y qué no es RoadGuard

RoadGuard analiza videos grabados por cámaras fijas en autopistas o vías de varios carriles. Detecta los vehículos, los sigue de un cuadro al siguiente asignándoles un identificador, reconstruye sus trayectorias en metros sobre el plano del camino y, sobre ese estado, busca tres patrones potencialmente riesgosos: cercanía peligrosa con el vehículo de adelante, zigzag entre carriles y corte de carril. Cada patrón que se activa queda registrado como un evento con sus variables medidas y los umbrales vigentes, y los eventos recientes de un vehículo se resumen en un puntaje de riesgo de 0 a 100 con tres bandas de color.

Las alertas son experimentales y orientan la revisión humana. Lo que el sistema entrega es una lista de momentos del video que vale la pena mirar, con la evidencia numérica de por qué se marcaron. La decisión sobre lo que ocurrió la toma una persona viendo el video.

Hay cosas que RoadGuard no hace por diseño. No reconoce patentes ni personas, y no guarda ninguna información que identifique a un conductor o a un vehículo fuera del video analizado. No emite multas ni decisiones automáticas sobre nadie, y no establece qué vehículo causó una situación. Los umbrales de las reglas (por ejemplo, 1,5 segundos de separación temporal) son parámetros configurables que se eligen para cada cámara y escenario; no son límites legales ni se presentan como tales. Por la misma razón, ningún texto, columna o rótulo del sistema califica la conducción: habla de eventos, variables medidas y puntaje.

## 2. Requisitos

El prototipo corre en Python 3.10 o superior (se desarrolló con 3.12). Funciona en Linux, macOS y Windows con las dependencias de `requirements.txt`: Ultralytics (YOLOv8), OpenCV, NumPy, SciPy y PyYAML. Se necesita conexión a internet la primera vez, para descargar los pesos del detector (unos 6 MB).

La GPU es opcional. Sin GPU, el detector corre en CPU y el procesamiento es varias veces más lento que el tiempo real; sirve para probar con un tramo corto de video (ver `--max-cuadros` en la sección 6). La referencia de rendimiento del proyecto es una GPU NVIDIA T4 como la de Google Colab, donde la meta es procesar a 15 cuadros por segundo o más un video de 720p. En un Mac con Apple Silicon se puede usar la GPU integrada con `--dispositivo mps`.

Para un video de un minuto a 25 cuadros por segundo, cuente con unos 100 MB libres en disco para el video anotado de salida, más espacio para el modelo y las dependencias (alrededor de 2 GB en total, porque Ultralytics instala PyTorch).

## 3. Instalación

Clone o descomprima el repositorio y, desde su carpeta raíz, instale las dependencias y el paquete en modo editable. Se recomienda hacerlo dentro de un entorno virtual para no mezclar versiones con otros proyectos.

```bash
python -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

Para comprobar que todo quedó bien, corra las pruebas unitarias desde la raíz. Tardan menos de un minuto y no necesitan video, GPU ni datos externos.

```bash
python -m pytest -q
```

Si prefiere una comprobación sin pytest, el repositorio incluye una demostración determinista de la regla de cercanía que tampoco necesita video ni GPU.

```bash
python scripts/demo_cercania.py
```

En Google Colab, los mismos pasos funcionan en una celda (anteponiendo `!` a cada comando); elija un entorno con GPU T4 en «Entorno de ejecución» para la referencia de rendimiento.

## 4. Preparar un video y su configuración

RoadGuard necesita dos archivos de entrada: el video y un archivo YAML que describe la cámara. La configuración existe porque el sistema no sabe por sí solo dónde está el camino en la imagen, cuántos carriles hay ni cuántos metros mide un píxel; todo eso se declara una vez por cámara y se reutiliza para todos los videos de esa misma cámara.

### 4.1 El video

El video debe ser un archivo MP4 de una cámara fija, con una tasa de cuadros (FPS) válida en sus metadatos. El sistema la usa para convertir el número de cuadro en segundos, y todas las ventanas temporales de las reglas se evalúan en segundos, nunca en cantidad de cuadros. Si el archivo no tiene FPS o no se puede decodificar, la ejecución se rechaza antes de crear ninguna salida (sección 8).

La secuencia de referencia del proyecto es `MVI_39271` del conjunto UA-DETRAC: cámara fija, día soleado, resolución 960 por 540, 25 cuadros por segundo, con el tráfico acercándose a la cámara de derecha a izquierda. UA-DETRAC entrega las secuencias como carpetas de imágenes JPG; para usarlas aquí hay que convertirlas a MP4 conservando la tasa de cuadros, por ejemplo con `ffmpeg -framerate 25 -i img%05d.jpg -c:v libx264 -pix_fmt yuv420p MVI_39271.mp4`.

### 4.2 El archivo YAML, campo por campo

La plantilla vacía está en `configs/camara_ejemplo.yaml` y la configuración completa de la cámara de referencia en `configs/MVI_39271.yaml`. El archivo tiene nueve claves de primer nivel; cualquier otra clave se rechaza con un mensaje que la nombra. Las coordenadas de imagen van en píxeles, con el origen en la esquina superior izquierda, x hacia la derecha e y hacia abajo. Las coordenadas del camino van en metros, con x en el sentido de avance del tráfico e y lateral.

| Clave | Obligatoria | Qué contiene | Qué se valida |
|---|---|---|---|
| `camara` | No | `nombre` y `descripcion` de la cámara, solo informativos | Nada |
| `region_interes` | Sí | Polígono en píxeles con la zona de la imagen donde se aceptan detecciones; lo demás se ignora | Al menos 3 puntos `[x, y]` numéricos. Si su área es nula se advierte que no habrá detecciones |
| `carriles` | Sí | Lista de carriles, cada uno con un `indice` entero y un `poligono` en píxeles | Lista no vacía, índices enteros y únicos, cada polígono con al menos 3 puntos. Con menos de dos carriles se advierte que zigzag y corte no pueden activarse |
| `homografia` | No | `puntos_imagen` (píxeles) y `puntos_camino` (metros) con las correspondencias para pasar de la imagen al plano del camino | Las dos listas vacías significan «sin calibración» y solo producen una advertencia. Si hay puntos, deben ser al menos 4 pares, la misma cantidad en ambas listas, y entre ellos tiene que haber 4 sin 3 colineales |
| `clases` | Sí | Clases vehiculares que se detectan | Lista no vacía tomada de `automovil`, `bus`, `camion` y `motocicleta`; cualquier otra se rechaza |
| `confianza_min_deteccion` | No (0,25) | Confianza mínima que debe tener una detección del modelo para considerarse | Número entre 0 y 1 |
| `confianza_min_carril` | No (0,60) | Confianza mínima para asignar un vehículo a un carril | Número entre 0 y 1 |
| `permanencia_cambio_carril` | No (1,0 s) | Segundos que un vehículo debe permanecer estable en el carril nuevo para que el cambio cuente como completo; las oscilaciones sobre la línea no cuentan | Número positivo |
| `umbrales` | No | Los parámetros de las reglas RF7 a RF11 (sección 7) | Solo nombres conocidos, numéricos, no negativos; los tiempos y el puntaje máximo positivos; las bandas en orden |

Si una clave opcional se omite, se usa el valor por defecto indicado entre paréntesis; los umbrales omitidos toman los valores de la propuesta, que son los mismos del ejemplo.

### 4.3 Ejemplo completo

Esta es la configuración de la cámara de referencia, tal como está en `configs/MVI_39271.yaml`. Se generó con `scripts/calibrar_ua_detrac.py` (sección 5), por lo que los números de los polígonos y de la homografía son coherentes entre sí: los carriles se construyeron en metros y se proyectaron a la imagen con la misma homografía.

```yaml
camara:
  nombre: MVI_39271
  descripcion: >-
    UA-DETRAC prueba, dia soleado, camara fija. Calzada cercana (entre el
    paradero de buses y el bandejon); el trafico avanza de derecha a
    izquierda, acercandose a la camara.

# Region de interes: poligono en px, x de -25 a 25 m y todo el ancho de la calzada.
region_interes:
  - [924.6, 285.2]
  - [31.3, 545]
  - [-82.6, 374.1]
  - [724.7, 249.1]

# Carriles: poligonos en px, construidos desde sus bordes en metros
# [-3.3, 0.0, 3.5, 7.0, 13.2]. Carril 0 junto al bandejon.
carriles:
  - indice: 0
    poligono:
      - [924.6, 285.2]
      - [31.3, 545]
      - [-0.6, 497.2]
      - [878.6, 276.9]
  - indice: 1
    poligono:
      - [878.6, 276.9]
      - [-0.6, 497.2]
      - [-28.1, 455.9]
      - [833.4, 268.7]
  - indice: 2
    poligono:
      - [833.4, 268.7]
      - [-28.1, 455.9]
      - [-50.8, 421.8]
      - [791.6, 261.2]
  - indice: 3
    poligono:
      - [791.6, 261.2]
      - [-50.8, 421.8]
      - [-82.6, 374.1]
      - [724.7, 249.1]

# Correspondencias imagen <-> camino (metros).
homografia:
  puntos_imagen:
    - [637, 338]
    - [543, 361]
    - [349, 410]
    - [161, 455]
    - [560, 328]
    - [463, 348]
    - [255, 396]
    - [69, 435]
  puntos_camino:
    - [0, 0]
    - [6, 0]
    - [15, 0]
    - [21, 0]
    - [1.635, 3.5]
    - [7.635, 3.5]
    - [16.635, 3.5]
    - [22.635, 3.5]

clases:
  - automovil
  - bus
  - camion
  - motocicleta

confianza_min_deteccion: 0.25
confianza_min_carril: 0.60
permanencia_cambio_carril: 1.0

umbrales:
  cercania_velocidad_min: 5.0      # m/s
  cercania_thw_max: 1.5            # s
  cercania_persistencia: 2.0       # s
  zigzag_cambios_min: 2
  zigzag_ventana: 10.0             # s
  corte_ventana_post_cambio: 2.0   # s
  corte_thw_max: 1.5               # s
  corte_ttc_max: 3.0               # s
  aporte_cercania: 40
  aporte_zigzag: 35
  aporte_corte: 50
  puntaje_maximo: 100
  vigencia_aporte: 5.0             # s
  banda_verde_max: 29
  banda_amarillo_max: 59
```

Algunos puntos de la región de interés y de los carriles tienen coordenadas negativas o mayores que el ancho de la imagen. Es normal: los polígonos se construyeron en metros y, al proyectarlos, los extremos del tramo caen fuera del encuadre. Solo importa la parte del polígono que queda dentro de la imagen.

Los ocho puntos de la homografía son los extremos de dos trazos consecutivos en cada una de dos líneas discontinuas vecinas. En la primera línea (y = 0) los trazos empiezan en 0 y 15 metros y terminan en 6 y 21, porque la norma de esa vía usa trazos de 6 metros con huecos de 9. La segunda línea está a 3,5 metros (el ancho de carril) y sus trazos están desplazados 1,635 metros respecto de la primera; ese desfase lo calculó la calibración, no se midió.

## 5. Calibrar una cámara nueva

Calibrar significa darle al sistema la correspondencia entre píxeles y metros sobre el camino. Sin ella, RoadGuard puede detectar y seguir vehículos y saber en qué carril van, pero no puede medir distancias ni velocidades, y por lo tanto tampoco separaciones temporales con el vehículo de adelante. La calibración se hace una vez por cámara y vale mientras la cámara no se mueva.

### 5.1 Qué hay que saber del lugar

Se necesitan al menos cuatro puntos de la imagen cuya posición real sobre el pavimento se conozca en metros, sin que tres de ellos estén alineados. Lo más práctico en una autopista es usar la señalización horizontal, porque sus medidas están normadas: dentro de una línea discontinua, el largo del trazo y del hueco son fijos (en la vía de referencia, 6 y 9 metros), y la separación entre dos líneas vecinas es el ancho de carril (habitualmente entre 3,0 y 3,5 metros). Si la cámara es propia, también sirve medir con huincha o GPS cuatro marcas visibles (esquinas de un paso peatonal, postes, tapas de alcantarilla) y anotar sus coordenadas en metros respecto de un origen cualquiera, con x en el sentido de avance e y hacia un costado.

### 5.2 Camino directo: escribir los puntos en el YAML

Si ya tiene cuatro o más puntos medidos, basta con escribir sus coordenadas de píxel en `homografia.puntos_imagen` y las de metros, en el mismo orden, en `homografia.puntos_camino`. Para leer coordenadas de píxel, abra un cuadro del video en cualquier visor de imágenes que muestre la posición del cursor, o extraiga uno con `ffmpeg -i video.mp4 -vf "select=eq(n\,0)" -vframes 1 cuadro.png`. Conviene tomar el punto donde la pintura toca el pavimento y repetir la medición en dos o tres cuadros distintos, promediando, porque la compresión del video mueve los bordes uno o dos píxeles.

Después, dibuje la región de interés y los carriles como polígonos en píxeles, uno por carril, con índices consecutivos partiendo de 0. Los carriles deben cubrir la misma zona que la región de interés y no superponerse. Luego cargue la configuración para comprobar que no tiene errores y mire el error de reproyección: es la distancia media, en metros, entre donde la homografía pone cada punto de calibración y donde usted dijo que estaba. Por debajo de 0,3 metros es una buena calibración; por encima de 1 metro conviene revisar los puntos.

```bash
python -c "
from roadguard.m1_ingesta.config import cargar_configuracion, validar_consistencia
from roadguard.m3_geometria.homografia import ProyectorCamino
cfg = cargar_configuracion('configs/mi_camara.yaml')
print(validar_consistencia(cfg))
print('RMSE (m):', ProyectorCamino(cfg.homografia).error_reproyeccion)
"
```

### 5.3 Camino asistido: calibrar desde las líneas discontinuas

Cuando la vía tiene dos líneas discontinuas visibles, el repositorio puede calcular la homografía, los carriles y la región de interés a partir de ellas. Es el método con que se generó `MVI_39271.yaml`, y resuelve un problema que la medición directa no resuelve: los trazos de dos líneas distintas no tienen por qué estar alineados entre sí, y ese desfase longitudinal no se puede medir a ojo. El módulo `roadguard.m3_geometria.calibracion` lo estima eligiendo el desfase con el que la homografía corresponde a una cámara física (píxeles cuadrados, punto principal centrado), y de paso entrega la focal implícita de la cámara como control de plausibilidad.

El procedimiento es el siguiente. Primero, elija dos líneas discontinuas vecinas y, en cada una, dos trazos consecutivos; anote las coordenadas de píxel de los cuatro extremos de cada línea en el sentido de avance (inicio y fin del primer trazo, inicio y fin del segundo). Segundo, anote el largo del trazo y del hueco según la norma de la vía, y la distancia lateral entre las dos líneas. Tercero, decida dónde están los bordes laterales de todos los carriles, en metros, relativos a la primera línea (por ejemplo `[-3.3, 0.0, 3.5, 7.0, 13.2]` para cuatro carriles) y en qué tramo longitudinal, también en metros, los trazos se distinguen bien. Con eso, agregue una entrada al diccionario `SECUENCIAS` de `scripts/calibrar_ua_detrac.py`, siguiendo la que ya existe para `MVI_39271`, ajuste `TAMANO` al ancho y alto de su video, y ejecute el script desde la raíz.

```bash
python scripts/calibrar_ua_detrac.py
```

El script escribe `configs/<nombre>.yaml` con un encabezado que informa el error de reproyección (RMSE y máximo), el desfase estimado y la focal. Si hay cuadros de la secuencia en `datos/ua-detrac/cuadros/<nombre>/`, además guarda una imagen de verificación con la rejilla métrica, los carriles y los puntos usados; mírela antes de usar la configuración, porque un punto mal anotado se nota de inmediato como una rejilla torcida. El script rechaza una sola línea y líneas con menos de dos puntos.

### 5.4 Qué pasa si no hay calibración

Si deja `puntos_imagen` y `puntos_camino` vacíos, la configuración se acepta y el sistema sigue funcionando en modo degradado. Detecta y sigue vehículos, les asigna carril y puede evaluar zigzag, porque esa regla solo usa cambios de carril. Pero distancia, velocidad, THW y TTC quedan como «no disponibles», y las reglas de cercanía y corte de carril, que dependen de ellas, se suspenden sin generar eventos. En ese caso el sistema lo avisa de tres maneras: con el mensaje «SIN CALIBRACION» en la consola al iniciar, con un rótulo permanente en el video anotado y con la misma advertencia en `resumen.json`, donde `calibrado` queda en `false`. Lo mismo ocurre si los puntos están pero la homografía resulta degenerada o deja puntos a ambos lados del horizonte.

## 6. Ejecutar y leer las salidas

### 6.1 El comando

Con el paquete instalado, la ejecución es un solo comando desde cualquier carpeta. Los tres argumentos obligatorios son el video, la configuración y la carpeta de salida, que se crea si no existe.

```bash
python -m roadguard procesar --video RUTA.mp4 --config RUTA.yaml --salida DIR
```

| Opción | Qué hace |
|---|---|
| `--video RUTA.mp4` | Video MP4 de entrada |
| `--config RUTA.yaml` | Configuración de la cámara (sección 4) |
| `--salida DIR` | Carpeta donde se escriben las tres salidas |
| `--pesos yolov8n.pt` | Pesos del detector YOLOv8. Por defecto el modelo nano preentrenado en COCO, que Ultralytics descarga solo la primera vez; puede indicar otro archivo `.pt` de la familia YOLOv8 |
| `--max-cuadros N` | Procesa solo los primeros N cuadros. Útil para probar la configuración o para correr en CPU |
| `--sin-video` | No escribe `anotado.mp4`; solo el CSV y el JSON. Acelera la corrida y ahorra disco |
| `--dispositivo cpu`, `cuda` o `mps` | Dónde corre el detector. Sin la opción, Ultralytics elige la GPU si hay una disponible |

Para la cámara de referencia, una corrida completa se ve así:

```bash
python -m roadguard procesar --video datos/MVI_39271.mp4 --config configs/MVI_39271.yaml --salida salidas/MVI_39271
```

Antes de procesar el primer cuadro, el sistema valida el video y la configuración y, si algo es incoherente, termina con un mensaje que nombra el problema sin crear ninguna salida (sección 8). Durante la corrida imprime en consola las advertencias de la configuración y el avance.

### 6.2 El video anotado

`anotado.mp4` es una copia del video de entrada, con el mismo tamaño y los mismos FPS, de modo que el cuadro n del anotado ocurre en el mismo instante que el cuadro n del original. Sobre la imagen se dibujan los límites de carril de la configuración y, para cada vehículo seguido, su caja con una etiqueta sobre el borde superior que lleva el identificador, la clase, el carril asignado y el puntaje de riesgo vigente con su banda, por ejemplo `ID 7 car carril 2 riesgo 40 amarillo` (sin tildes, porque la fuente de OpenCV no las dibuja). El color de la caja sigue la banda del puntaje: verde entre 0 y 29, amarillo entre 30 y 59 y rojo entre 60 y 100. El número siempre acompaña al color, para no depender de él. Si la cámara no está calibrada, en la parte superior hay un rótulo permanente que lo indica.

El identificador es el mismo durante toda la permanencia del vehículo en la escena, salvo que una oclusión larga lo haga perderse; en ese caso el vehículo reaparece con un identificador nuevo y en el CSV figura como otro vehículo (sección 9).

### 6.3 Los eventos en CSV

`eventos.csv` tiene una fila por evento, es decir, por cada activación confirmada de una regla sobre un vehículo. Está pensado para abrirse en una planilla o con pandas y filtrarse por regla, por vehículo o por intervalo de tiempo. Está separado por comas. Las primeras seis columnas son fijas; las siguientes dependen de la regla y llevan prefijo: `variable_` para las variables medidas y `umbral_` para los umbrales vigentes.

| Columna | Contenido |
|---|---|
| `id_vehiculo` | Identificador del vehículo al que se le atribuye el evento (el que va detrás en cercanía, el que cambia de carril en zigzag y corte) |
| `regla` | `cercania_peligrosa`, `zigzag` o `corte_de_carril` |
| `t_inicio` | Segundo del video en que la condición empezó a cumplirse |
| `t_fin` | Última observación válida en que seguía cumpliéndose. En cercanía, un predecesor distinto o una observación perdida corta el tramo |
| `id_relacionado` | El otro vehículo involucrado: el de adelante en cercanía, el que queda detrás tras el corte. Vacío en zigzag |
| `aporte_puntaje` | Puntos que el evento suma al puntaje del vehículo mientras está vigente (40, 35 o 50 por defecto) |
| `variable_*` | Una columna por variable que activó la regla, con su valor en el momento del evento: `velocidad` (m/s), `distancia` (m), `thw` (s), `ttc` (s), `t_confirmacion` (s) o el número de cambios de carril, según la regla. Vacía cuando no aplica o no está disponible |
| `umbral_*` | Una columna por umbral que se usó para evaluar la regla (por ejemplo `umbral_cercania_thw_max`), con el valor que tenía en la configuración de esa corrida, para que el evento sea auditable sin volver al YAML |

### 6.4 El resumen en JSON

`resumen.json` es la evidencia de reproducibilidad de la corrida y la vista por vehículo. Tiene dos claves: `ejecucion`, un bloque con los datos de la corrida, y `vehiculos`, una lista con un resumen por cada vehículo seguido.

| Campo | Contenido |
|---|---|
| `video` | Ruta del video procesado |
| `configuracion` | Ruta de la configuración usada |
| `configuracion_sha256` | Huella SHA-256 del archivo YAML. Dos corridas con la misma huella usaron exactamente los mismos umbrales y geometría |
| `version_modelo` | Versión de Ultralytics y archivo de pesos, por ejemplo `ultralytics 8.3.0 / yolov8n.pt` |
| `fps_video` | FPS declarados por el video de entrada |
| `fps_procesamiento` | Cuadros procesados por segundo de reloj; es la medida de rendimiento |
| `n_cuadros_procesados` | Cuadros efectivamente procesados (menor que el total si se usó `--max-cuadros`) |
| `calibrado` | `true` si hubo homografía utilizable; `false` si se corrió en modo degradado |
| `advertencias` | Lista de advertencias emitidas: sin calibración, región de área nula, menos de dos carriles |
| `n_eventos` | Cantidad de eventos por regla en toda la corrida |
| `parametros` | La configuración normalizada que se usó, incluidos los umbrales por defecto que no estaban escritos en el YAML |
| `fps_por_etapa` | Cuadros por segundo de cada etapa (detección, seguimiento, geometría, reglas, salidas), para ubicar el cuello de botella |
| `completada` | `false` si la corrida se interrumpió; las salidas parciales no deben compararse con otras |
| Por vehículo: `id_vehiculo`, `clase` | Identificador y clase detectada |
| Por vehículo: `t_primera_aparicion`, `t_ultima_aparicion` | Segundos de entrada y salida de la escena |
| Por vehículo: `n_eventos` | Cantidad de eventos de cada regla atribuidos al vehículo |
| Por vehículo: `puntaje_maximo`, `nivel_maximo` | El mayor puntaje que alcanzó y su banda (`verde`, `amarillo`, `rojo`) |

### 6.5 Cómo interpretar las reglas y el puntaje

Todas las reglas se evalúan de manera causal: en el cuadro t solo se usa lo observado hasta t, sin mirar cuadros futuros. Por eso un evento se confirma con cierta latencia respecto del momento en que la situación empezó, y por eso `t_inicio` puede ser anterior al cuadro en que el color de la caja cambió.

**RF7, cercanía peligrosa.** Se activa cuando un vehículo va a más de 5 m/s y mantiene con el que tiene adelante en su mismo carril un THW menor que 1,5 segundos durante al menos 2 segundos seguidos. El THW (time headway) es la distancia dividida por la velocidad del que va detrás: cuánto tardaría en llegar a donde está ahora el de adelante. Un predecesor distinto, una observación perdida o una medición no disponible cortan el tramo y la cuenta parte de nuevo. Aporta 40 puntos. Vale saber que en tráfico congestionado un THW bajo 1,5 segundos es lo habitual: en 60 segundos de la autopista US-101 de NGSIM, esta regla marcó al 43 % de los vehículos. Un número alto de eventos de cercanía describe el flujo, no necesariamente conductas aisladas.

**RF8, zigzag.** Se activa cuando un vehículo completa dos o más cambios de carril dentro de una ventana de 10 segundos. Un cambio cuenta como completo solo si el vehículo permanece estable en el carril nuevo durante `permanencia_cambio_carril` segundos (1 por defecto); los cruces breves sobre la línea y las oscilaciones no cuentan. Es la única regla que funciona sin calibración. Aporta 35 puntos.

**RF9, corte de carril.** Se activa cuando, dentro de los 2 segundos siguientes a un cambio de carril completo, el vehículo que quedó detrás en el carril nuevo pasa a tener un THW menor que 1,5 segundos o un TTC menor que 3 segundos respecto del que se cambió. El TTC (time to collision) es la distancia dividida por la diferencia de velocidades y solo existe si el de atrás es más rápido que el de adelante. El evento se atribuye al que cambió de carril, y `id_relacionado` es el que quedó detrás. Aporta 50 puntos.

**RF10, puntaje.** El puntaje de un vehículo en un instante es la suma de los aportes de sus eventos vigentes, con tope en 100. Cada aporte caduca 5 segundos después de que el evento termina, de modo que un vehículo que deja de hacer cosas vuelve a verde solo. Por ejemplo, un corte de carril seguido de cercanía con el vehículo cortado da 90 puntos (rojo) mientras ambos están vigentes, y baja a 40 (amarillo) cinco segundos después de que el corte termina. El puntaje no se acumula a lo largo del video: describe el momento, no el historial.

**RF11, bandas.** Verde de 0 a 29, amarillo de 30 a 59 y rojo de 60 a 100. Con los aportes por defecto, cualquier evento solo deja al vehículo al menos en amarillo, y hace falta más de un evento vigente a la vez para llegar a rojo. Los colores son una ayuda visual para dirigir la atención; el detalle está siempre en el CSV.

## 7. Ajustar umbrales

Los umbrales viven en la sección `umbrales` del YAML y se pueden cambiar sin tocar código. Después de cambiarlos, basta con volver a correr el comando; `resumen.json` guarda los valores usados y la huella del archivo, así que dos corridas con distintos umbrales son distinguibles y comparables. Los valores por defecto son los de la propuesta del proyecto y están pensados para flujo libre en autopista; no son límites legales y no hay un valor «correcto» independiente de la cámara y el tipo de tráfico.

| Umbral | Por defecto | Qué controla | Efecto de subirlo |
|---|---|---|---|
| `cercania_velocidad_min` | 5,0 m/s | Velocidad mínima del seguidor para que cuente la cercanía | Excluye la cercanía a baja velocidad, típica de congestión |
| `cercania_thw_max` | 1,5 s | THW bajo el cual hay cercanía | Más eventos; con 2 s se marca buena parte del tráfico denso |
| `cercania_persistencia` | 2,0 s | Cuánto debe durar la condición para confirmarse | Menos eventos y más tardíos; filtra aproximaciones momentáneas |
| `zigzag_cambios_min` | 2 | Cambios completos necesarios | Con 3 solo se marcan secuencias largas |
| `zigzag_ventana` | 10,0 s | Ventana en que se cuentan los cambios | Más eventos; con ventanas largas, cambios legítimos separados empiezan a sumar |
| `permanencia_cambio_carril` | 1,0 s | Permanencia para que un cambio sea completo (fuera de `umbrales`, en la raíz del YAML) | Menos cambios confirmados y más tarde; evita que las oscilaciones cuenten |
| `corte_ventana_post_cambio` | 2,0 s | Cuánto después del cambio se mira al nuevo seguidor | Más eventos, pero cada vez menos ligados al cambio |
| `corte_thw_max`, `corte_ttc_max` | 1,5 s, 3,0 s | Separación bajo la cual el cambio es un corte | Más eventos de corte |
| `aporte_cercania`, `aporte_zigzag`, `aporte_corte` | 40, 35, 50 | Peso de cada regla en el puntaje | Cambia qué combinaciones llegan a rojo |
| `puntaje_maximo` | 100 | Tope del puntaje | Debe ser mayor que `banda_amarillo_max` |
| `vigencia_aporte` | 5,0 s | Cuánto dura el aporte tras terminar el evento | Los vehículos permanecen en color más tiempo |
| `banda_verde_max`, `banda_amarillo_max` | 29, 59 | Límites superiores de verde y amarillo | Deben cumplir 0 <= verde < amarillo < máximo |

Una forma razonable de calibrar los umbrales para una cámara nueva es correr primero con los valores por defecto sobre un tramo representativo, revisar en el video anotado una muestra de los eventos de cada regla y mirar `n_eventos`. Si la mayoría de los eventos de cercanía ocurre en tráfico lento, suba `cercania_velocidad_min` antes que bajar `cercania_thw_max`. Si aparecen zigzags por vehículos que oscilan sobre una línea mal pintada, suba `permanencia_cambio_carril`. Anote el motivo de cada cambio junto al valor en el YAML; el archivo admite comentarios con `#`.

## 8. Problemas frecuentes

**Los pesos de YOLO no se descargan.** La primera vez que corre, Ultralytics descarga `yolov8n.pt` desde GitHub a la carpeta actual. Sin internet, o detrás de un proxy, falla con un error de conexión. Descargue el archivo a mano desde la página de versiones de Ultralytics (`https://github.com/ultralytics/assets/releases`, archivo `yolov8n.pt`) en otra máquina, cópielo a la carpeta del proyecto e indíquelo con `--pesos ruta/yolov8n.pt`.

**«FPS invalidos» o «No se pudo decodificar el primer cuadro».** El video no declara una tasa de cuadros o usa un códec que OpenCV no puede abrir. También ocurre si el archivo no termina en `.mp4`, porque el prototipo solo acepta ese contenedor. Recodifique el video con ffmpeg fijando la tasa de cuadros real: `ffmpeg -i entrada.avi -r 25 -c:v libx264 -pix_fmt yuv420p salida.mp4`. Use la tasa de la cámara, no una inventada, porque todas las medidas de tiempo dependen de ella.

**La configuración se rechaza.** Los mensajes nombran el problema. «Claves desconocidas» indica una clave mal escrita en la raíz; «Falta la clave obligatoria» una de `region_interes`, `carriles` o `clases`; «Homografia desbalanceada» que las dos listas de puntos no tienen el mismo largo; «requiere al menos 4 pares» que faltan puntos; «es degenerada» que tres de los cuatro puntos están alineados, lo que suele pasar al tomar todos los puntos de una sola línea; «Umbrales desconocidos» un nombre de umbral mal escrito; «Bandas incoherentes» que las bandas no van en orden creciente bajo el puntaje máximo. Un error de sintaxis YAML (una sangría mal puesta, un corchete sin cerrar) se informa con la línea y columna que reporta PyYAML.

**Sin GPU el procesamiento es muy lento.** Es esperable: YOLOv8n en CPU procesa unos pocos cuadros por segundo. Para probar la configuración use `--max-cuadros 250` (diez segundos a 25 FPS) y `--sin-video`. Si tiene un Mac con Apple Silicon, `--dispositivo mps` usa la GPU integrada. Para corridas completas, Google Colab con GPU T4 es la referencia del proyecto.

**Aparece «SIN CALIBRACION» aunque escribí los puntos.** Compruebe que las dos listas tienen la misma cantidad de puntos y al menos cuatro, que no están todos sobre una misma recta y que todos corresponden al mismo lado del horizonte (puntos del cielo o muy cerca de la línea del horizonte hacen que la homografía no sea utilizable). El mensaje de la consola indica cuál de las tres causas es.

**El vehículo cambia de identificador a mitad del video.** Una oclusión larga (un camión que tapa a un auto varios segundos) hace que el seguidor pierda el vehículo y lo vuelva a crear con otro ID. Los eventos de cada tramo quedan atribuidos a identificadores distintos. No hay parámetro de usuario para esto en el prototipo; al revisar, mire los vehículos vecinos en el tiempo y el carril.

## 9. Limitaciones conocidas

RoadGuard es un prototipo académico y conviene conocer sus bordes antes de sacar conclusiones de sus salidas.

Las medidas en metros dependen por completo de la calibración. Un error de un par de píxeles en los puntos de calibración se traduce en decenas de centímetros en la zona lejana de la imagen, y el THW y el TTC heredan ese error. La región de interés debe acotarse a la zona donde la proyección es confiable; en la cámara de referencia son unos 50 metros de vía.

La distancia entre vehículos se mide entre los puntos donde cada caja toca el pavimento, sin descontar el largo del vehículo que va adelante. Para un bus o un camión eso sobreestima la separación real en varios metros.

La regla de cercanía, tal como está formulada, no distingue el riesgo de la congestión. En tráfico denso un THW bajo 1,5 segundos es lo normal, y la regla marca a buena parte de los vehículos. El equipo propuso un puntaje ponderado por severidad como alternativa; en este prototipo no está implementado, y la medición en flujo libre que permitiría concluir está pendiente.

El detector es YOLOv8n preentrenado en COCO, sin ajuste fino al dominio. Reconoce automóviles, buses, camiones y motocicletas; no bicicletas ni peatones. Vehículos pequeños o lejanos y escenas nocturnas o con lluvia bajan la tasa de detección, y el seguimiento pierde identificadores en oclusiones largas. De las tres secuencias UA-DETRAC elegidas por el equipo, solo la de día está calibrada; la densa y la nocturna están pendientes.

Las reglas suponen una cámara fija. Si la cámara se mueve, vibra o cambia de zoom, la calibración deja de valer y las medidas en metros pierden sentido sin que el sistema lo detecte. Los carriles son polígonos estáticos, por lo que la configuración no sirve para tramos con carriles reversibles o conos.

Por último, el sistema procesa un video completo y entrega resultados al final; no está diseñado para operar en tiempo real sobre una cámara en vivo, aunque la evaluación de reglas es causal y lo permitiría en el futuro. Y, como se dijo al principio, nada de lo que produce es una determinación sobre personas: es una lista de momentos para que alguien los mire.

## Fuentes

- Formulario de propuesta TEL-328, 2026-09-11, §1.1, §1.2, §1.3, §2.5 y RF1 a RF12.
- Código del repositorio al 2026-11-15: `m1_ingesta/config.py` y `video.py`, `m3_geometria/calibracion.py` y `homografia.py`, `m4_reglas/cercania.py`, `m5_salidas/`, `tipos.py`, `scripts/calibrar_ua_detrac.py`, `configs/MVI_39271.yaml`.
- [Reglas de negocio](../../domain/REGLAS_NEGOCIO.md), [Glosario](../../domain/GLOSARIO.md) y [Marca](./marca/MARCA.md).
- CLI `python -m roadguard procesar`, rama prototipo-18nov, verificada con una corrida real el 2026-11-15.
