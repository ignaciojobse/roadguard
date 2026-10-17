# Datos de RoadGuard (T6, seccion 2.4)

Responsable segun la propuesta: Francisco Zuniga.

Los datos no se versionan (`datos/` esta en `.gitignore`). Este documento
registra que se uso, de donde viene y bajo que condiciones, para no
extrapolar resultados a camaras no evaluadas (riesgo 4.4, transferencia
entre datasets).

## 1. UA-DETRAC: deteccion y seguimiento (M2, T9)

Fuente visual principal. Videos de camaras fijas sobre vias urbanas en
China, 960x540 a 25 FPS, con cajas e IDs por vehiculo y regiones ignoradas
por secuencia. Categorias anotadas: `car`, `bus`, `van`, `others`; atributo
de clima/iluminacion por secuencia (`sunny`, `cloudy`, `rainy`, `night`).

UA-DETRAC **no** incluye etiquetas de conduccion riesgosa y la propuesta
establece que no se crearan anotaciones masivas nuevas: se usa solo para
mAP@0.5, IDF1 e intercambios de ID.

Ubicacion esperada:

```
datos/uadetrac/imagenes/MVI_XXXXX/img00001.jpg ...
datos/uadetrac/anotaciones/MVI_XXXXX.xml
```

### Mapeo de clases para la evaluacion

Decision explicita, implementada en `m6_evaluacion/deteccion.py`
(`MAPEO_UADETRAC`) y coherente con `m2_deteccion/detector.py`
(`MAPEO_COCO`):

| UA-DETRAC | RoadGuard | Nota |
|---|---|---|
| car | automovil | |
| van | automovil | YOLOv8n/COCO no tiene clase furgon; COCO suele etiquetarlas `car` o `truck` |
| bus | bus | |
| others | camion | `others` agrupa camiones y vehiculos pesados no clasificados |
| (sin categoria) | motocicleta | UA-DETRAC no anota motos: su AP no es evaluable |

Se informa tambien un AP agnostico de clase (`vehiculo`), menos sensible a
la confusion car/van/truck propia de un modelo preentrenado en COCO.

### Secuencias seleccionadas

Criterio: cubrir distintas condiciones de iluminacion/clima, con camaras
estables (`camera_state="stable"`, coherente con el supuesto de camara
fija) y vias multicarril.

Fuente usada: copia en Kaggle `bratjay/ua-detrac-orig` (11,5 GB completa),
descargable sin credenciales con `kagglehub`. Permite bajar archivos
sueltos, por lo que no hace falta el dataset completo:

```python
import kagglehub
kagglehub.dataset_download(
    "bratjay/ua-detrac-orig",
    path="DETRAC-Train-Annotations-XML/DETRAC-Train-Annotations-XML/MVI_41063.xml",
)
kagglehub.dataset_download(
    "bratjay/ua-detrac-orig",
    path="DETRAC-Images/DETRAC-Images/MVI_41063/img00001.jpg",
)
```

Preseleccion hecha leyendo solo los XML de anotacion (17-10-2026). Los
datos vienen de los atributos del XML; **las imagenes aun no se revisaron y
la validacion queda pendiente**:

| Secuencia | Particion | Resolucion | FPS | Condicion | Camara | Cuadros anotados | Vehiculos (IDs) | Veh./cuadro | Estado |
|---|---|---|---|---|---|---|---|---|---|
| MVI_41063 | train | 960x540 | 25 | sunny | stable | 1505 | 167 | 6,7 | pendiente: descarga parcial (294 de 750 cuadros) |
| MVI_40243 | train | 960x540 | 25 | cloudy | stable | 1265 | 173 | 8,3 | pendiente |
| MVI_40751 | train | 960x540 | 25 | night | stable | 1145 | 41 | 6,5 | pendiente |

Alternativa con lluvia y camara estable: MVI_63521 (2055 cuadros, 90 IDs).
Plan previsto: primeros 750 cuadros (30 s) de cada secuencia, unos 180 MB.

Para la demostracion end-to-end (>= 3 secuencias) las imagenes se pueden
convertir a MP4 con `ffmpeg -framerate 25 -i img%05d.jpg -c:v libx264
-pix_fmt yuv420p MVI_XXXXX.mp4` y procesar con una configuracion YAML por
camara.

## 2. highD / NGSIM: validacion de reglas (M4, T9)

highD se solicito al inicio del proyecto. Si no esta disponible al 21 de
septiembre de 2026, se usa NGSIM (riesgos 4.4).

| Dataset | Estado de acceso | Frecuencia | Unidades originales | Conversion |
|---|---|---|---|---|
| highD | _pendiente: registrar fecha de solicitud y respuesta_ | 25 Hz | m, m/s | `scripts/convertir_trayectorias.py highd` |
| NGSIM | publico | 10 Hz (0,1 s) | pies, pies/s | `scripts/convertir_trayectorias.py ngsim` |

### Conversion al contrato de datos

`m6_evaluacion/datasets.py` convierte cada fila a `EstadoCinematico`:

- `x_camino`: coordenada longitudinal en metros, creciente en el sentido de
  avance. En highD se usa el centro de la caja y se invierte el eje para
  `drivingDirection == 1`. En NGSIM es `Local_Y` (frente del vehiculo).
- `y_camino`: lateral en metros (`y` de highD, `Local_X` de NGSIM).
- `velocidad`: longitudinal en m/s, del propio dataset.
- `carril`: `laneId` / `Lane_ID` del dataset, con confianza 1.
- `t`: segundos desde el primer cuadro del archivo convertido.

El script escribe `datos/trayectorias/<nombre>.csv` y
`<nombre>.meta.json` con rutas, SHA-256 de los archivos de origen, filtros
(ubicacion, periodo, recorte) y FPS, de modo que la conversion es
reproducible.

### Trayectorias seleccionadas

| Archivo convertido | Fuente | Ubicacion / registro | Periodo | Vehiculos | Duracion |
|---|---|---|---|---|---|
| _pendiente_ | | | | | |

### Limitaciones conocidas

- La distancia se mide entre puntos de referencia (centro en highD, frente
  en NGSIM), sin descontar el largo del vehiculo; THW y TTC difieren de los
  que publica highD, que usan distancia parachoque a parachoque. La
  referencia de T9 se calcula con el motor de RoadGuard, no con esos campos.
- NGSIM tiene ruido conocido en velocidades y algunas filas duplicadas; el
  conversor descarta duplicados (mismo vehiculo y cuadro).
- El archivo combinado de NGSIM reutiliza IDs entre ubicaciones y periodos:
  convertir siempre con `--ubicacion` y un periodo acotado.
