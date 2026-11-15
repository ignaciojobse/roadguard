# RoadGuard

Sistema de deteccion y analisis de patrones de conduccion mediante vision
computacional. Proyecto TEL-328 Procesamiento Digital de Imagenes.

RoadGuard es un prototipo de apoyo para analizar videos de camaras fijas en
autopistas o vias multicarril. Detecta y sigue vehiculos y reconstruye sus
trayectorias en coordenadas del camino, para que sobre ese estado se evaluen
patrones potencialmente riesgosos.

Las alertas del sistema completo son **experimentales** y orientan la
revision humana. El sistema no reconoce patentes ni personas, no emite
sanciones automaticas y no determina responsabilidades legales. Los umbrales
son configurables y no se presentan como limites legales.

## Estado del prototipo (entrega del 18-nov)

La cadena completa M1 a M5 corre de punta a punta desde la CLI: un MP4 mas el
YAML de la camara entregan el video anotado, el CSV de eventos y el resumen
JSON. El motor de reglas por defecto evalua las tres conductas inscritas
(cercania RF7, zigzag RF8 y corte de carril RF9) y el puntaje con bandas
(RF10 y RF11). Las tres secuencias de UA-DETRAC de la demo tienen su YAML en
`configs/`. El reparto y el estado viven en `knowledge/roadmap/`.

| Modulo | Estado | Responsable (aportes) |
|---|---|---|
| Contrato de datos (`tipos.py`, `poligonos.py`) | Implementado | Ignacio Jobse |
| M1 Ingesta y configuracion | Implementado | Ignacio Jobse |
| M2 Deteccion y seguimiento | Implementado: YOLOv8n y ByteTrack | Ignacio Jobse |
| M3 Geometria vial y trayectorias | Implementado, con calibracion de las 3 secuencias | Ignacio Jobse y Giancarlos Ricci (calibracion) |
| M4 Motor de reglas y riesgo | Implementado: RF7 a RF11 | Francisco Castillo (RF7; RF8 a RF11 de Francisco Zuniga) |
| M5 Visualizacion y exportacion | Implementado: MP4 anotado con color y puntaje por banda, `eventos.csv`, `resumen.json` y `tracks.csv` | Giancarlos Ricci (con Francisco Zuniga) |
| M6 Evaluacion y diagnostico | Referencia NGSIM, F1 de eventos, mAP@0.5 e IDF1 sobre UA-DETRAC | Francisco Zuniga |
| Datos y seleccion de secuencias | NGSIM y 3 secuencias UA-DETRAC | Francisco Zuniga |
| Integracion, CLI y rendimiento | Implementado: `Pipeline`, `python -m roadguard procesar` y `scripts/perfilar_fps.py` | Ignacio Jobse (codigo de integracion de Francisco Zuniga) |

El contrato de datos de `tipos.py` es la interfaz entre modulos (`Track`,
`EstadoCinematico`, `Relacion`, `Evento`, `PuntajeRiesgo`, `ResumenVehiculo`,
`ResumenEjecucion` y los umbrales de las reglas). Los modulos se usan como
biblioteca o encadenados por `roadguard.pipeline.Pipeline` y la CLI (ver
«Uso»).

## Instalacion

```bash
pip install -r requirements.txt
pip install -e .
```

## Estructura

```
src/roadguard/
  tipos.py            Contrato de datos compartido entre modulos
  poligonos.py        Utilidades geometricas de poligonos
  pipeline.py         Integracion end-to-end: Pipeline (y MotorCercania de respaldo)
  cli.py, __main__.py Linea de comandos (python -m roadguard)
  m1_ingesta/         IC   Ingesta y configuracion        RF1, RF4
  m2_deteccion/       DTS  Deteccion y seguimiento        RF2, RF3
  m3_geometria/       GVT  Geometria vial y trayectorias  RF4, RF5, RF6
  m4_reglas/          MRR  Reglas y puntaje               RF7 a RF11
  m5_salidas/         VE   Video anotado, CSV y JSON       RF11, RF12
  m6_evaluacion/      ED   Referencias NGSIM y UA-DETRAC, metricas
scripts/              Descarga y conversion de datos, calibracion, metricas y perfil de FPS
tests/                Pruebas unitarias e integracion (pytest)
configs/              Configuraciones de camara (MVI_39271, MVI_40714, MVI_40742)
datos/                Videos, anotaciones y pesos (no versionados)
docs/                 Plan de implementacion
knowledge/            Contexto, decisiones, reparto y seguimiento del proyecto
```

## Datos

Los videos y los pesos no se versionan. Para dejar las tres secuencias de la
demo listas, desde la raiz:

```bash
python scripts/bajar_ua_detrac.py MVI_39271 MVI_40714 MVI_40742   # JPG y XML, ~400 MB
python scripts/jpg_a_mp4.py MVI_39271 MVI_40714 MVI_40742          # MP4 a 25 FPS, sin ffmpeg
```

Los pesos `yolov8n.pt` los baja Ultralytics la primera vez que se usan. Para
una maquina sin red (la demo en vivo), conviene dejarlos antes en
`datos/modelos/yolov8n.pt` y pasarlos con `--pesos`.

## Uso

```bash
python -m roadguard procesar --video datos/videos/MVI_39271.mp4 \
    --config configs/MVI_39271.yaml --salida salidas/MVI_39271 \
    [--pesos datos/modelos/yolov8n.pt] [--max-cuadros N] [--sin-video] [--tracks] \
    [--dispositivo cpu|cuda|mps]
```

Si la corrida se corta con Ctrl+C, igual se escriben las salidas con lo
procesado: los eventos abiertos se cierran, `resumen.json` queda con
`"completada": false` y la CLI termina con codigo 130.

Con `pip install -e .` tambien queda el comando `roadguard`. En el directorio
de salida se escriben `anotado.mp4` (cajas, ID, clase, carril, puntaje y
color por banda de riesgo), `eventos.csv` (un evento confirmado por fila:
vehiculo, regla, intervalo, vehiculo relacionado, aporte y las variables y
umbrales aplanados) y `resumen.json` (metadatos de la corrida, SHA-256 y
parametros de la configuracion, eventos por regla y un resumen por
vehiculo). Al terminar imprime cuadros procesados, FPS de procesamiento y el
conteo de eventos por regla. Con `--tracks` escribe ademas `tracks.csv` (cuadro,
id, clase, caja, carril y confianza), que es lo que lee `scripts/medir_mvi.py`
para medir mAP@0.5 e IDF1 contra el XML de UA-DETRAC. Los datos se bajan con
`scripts/bajar_ua_detrac.py` (ver el PRD de datos y evaluacion, seccion 7).

Por cada cuadro el pipeline hace: leer -> detectar -> seguir -> proyectar al
camino -> carril y estado cinematico -> relaciones (THW/TTC) -> reglas y
puntaje -> anotar -> escribir. Sin calibracion no se detiene: mantiene
cajas, ID, carril y una advertencia visible en el video; distancia, THW y
TTC quedan no disponibles y no se generan eventos de cercania (Paso 5).

El motor de reglas se inyecta en `Pipeline(cfg, detector, motor=...)` y
debe exponer `actualizar(t, estados: dict[int, EstadoCinematico],
relaciones: list[Relacion], cambios: list[CambioCarril]) ->
tuple[list[Evento], dict[int, PuntajeRiesgo]]` y `finalizar() ->
list[Evento]`. Los eventos devueltos son los confirmados y cerrados en ese
cuadro (van al CSV); los puntajes son los vigentes por vehiculo (van al
video). El motor por defecto es `m4_reglas.motor.MotorReglas`, que combina
cercania (RF7), zigzag (RF8), corte de carril (RF9) y el puntaje con
caducidad y bandas (RF10 y RF11). `pipeline.MotorCercania` queda como motor
minimo de respaldo (solo RF7 con puntaje) para pruebas.

## Rendimiento

El criterio de la propuesta es **>= 15 FPS a 720p en Colab T4**. El perfil
por etapa (lectura, deteccion, seguimiento, geometria, reglas y salidas) se
mide con:

```bash
python scripts/perfilar_fps.py --video datos/videos/MVI_39271.mp4 \
    --config configs/MVI_39271.yaml --alto 720 --dispositivo cuda
```

UA-DETRAC es 960x540, asi que el script escala video y configuracion a
1280x720 (los puntos del camino en metros no cambian), hace una inferencia de
calentamiento y escribe `perfil.json`. Para la T4, abrir
`scripts/perfil_colab_t4.ipynb` en Colab con `Entorno de ejecucion ->
Cambiar tipo -> T4 GPU` y ejecutar todas las celdas: clona el repo, instala,
baja MVI_39271 y corre el perfil con y sin MP4 anotado. Las cifras medidas
estan en la bitacora 2, anexo de metricas.

## Uso como biblioteca

```python
from roadguard.m1_ingesta.config import cargar_configuracion
from roadguard.m2_deteccion.detector import DetectorVehiculos
from roadguard.m2_deteccion.tracker import SeguidorByteTrack
from roadguard.m3_geometria.homografia import ProyectorCamino
from roadguard.m3_geometria.trayectorias import HistorialCausal
from roadguard.m3_geometria.relaciones import calcular_relaciones

cfg = cargar_configuracion("configs/camara_ejemplo.yaml")
detector = DetectorVehiculos(cfg, pesos="yolov8n.pt")
seguidor = SeguidorByteTrack(fps=25.0)
historial = HistorialCausal(25.0, ProyectorCamino(cfg.homografia), cfg.carriles)
```

Por cada cuadro, en orden temporal: detectar, actualizar el seguidor,
alimentar el historial causal y calcular las relaciones del cuadro. El
resultado es el estado cinematico y las relaciones por ID, que es
exactamente lo que consume el motor de reglas.

### Reglas por separado: cercania (RF7)

Cada regla de `m4_reglas` tambien se usa sola. `DetectorCercania` procesa
cada cuadro causalmente. Por defecto, la cercania
exige velocidad sobre el umbral, THW bajo el umbral y persistencia continua de
2 s; una observacion ausente o invalida, o un cambio de predecesor, corta el tramo.
`entradas` abajo representa los datos que aporta el llamador por cuadro.
`activos` son snapshots
para visualizacion y no deben acumularse; `cerrados` y `finalizar()` entregan
eventos confirmados, cuyo fin es la ultima observacion valida. Sin calibracion
se emite advertencia y no se genera evento. El aporte RF7 (40 por defecto) no
es un puntaje acumulado: la acumulacion y las bandas las hace
`CalculadorPuntaje` dentro de `MotorReglas`. Los resultados son
experimentales, requieren revision humana y no son determinaciones legales.

```python
from roadguard.m4_reglas import DetectorCercania

detector = DetectorCercania(cfg.umbrales)
eventos_cerrados = []
for cuadro, t, estados, relaciones in entradas:
    resultado = detector.actualizar(cuadro, t, estados, relaciones)
    eventos_cerrados.extend(resultado.cerrados)
    activos = resultado.activos
    advertencias = resultado.advertencias
eventos_cerrados.extend(detector.finalizar())
```

Demo determinista sin video, datos externos ni GPU, desde la raiz:

```bash
python scripts/demo_cercania.py
python -m pytest tests/test_reglas_cercania.py tests/test_demo_cercania.py -q
```

## Pruebas

```bash
python -m pytest
```

## Convenciones

- **Tiempo**: `t` en segundos desde el inicio del video, derivado de los FPS
  reales. Las ventanas temporales se evaluan sobre `t`, nunca sobre conteo
  de cuadros.
- **Unidades**: metros, m/s, segundos.
- **Causalidad**: en el cuadro `t` solo se usa informacion disponible hasta
  `t`. Sin cuadros futuros.
- **Sin calibracion**: las metricas basadas en distancia quedan en `None` y
  el consumidor debe degradar las alertas que dependen de ellas, emitiendo
  una advertencia explicita.

Ver `docs/PLAN_IMPLEMENTACION.md` para el orden de trabajo y los criterios
de aceptacion que aplican a estos modulos.
