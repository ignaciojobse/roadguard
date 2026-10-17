# RoadGuard

Sistema de deteccion y analisis de patrones de conduccion mediante vision
computacional. Proyecto TEL-328 Procesamiento Digital de Imagenes.

RoadGuard es un prototipo de apoyo para analizar videos de camaras fijas en
autopistas o vias multicarril. Detecta y sigue vehiculos, reconstruye sus
trayectorias en coordenadas del camino y senala tres patrones potencialmente
riesgosos (cercania peligrosa, zigzag y corte de carril) mediante reglas
explicitas.

Las alertas son **experimentales** y orientan la revision humana. El sistema
no reconoce patentes ni personas, no emite sanciones automaticas y no
determina responsabilidades legales. Los umbrales son configurables y no se
presentan como limites legales.

## Equipo

| Integrante | Modulos a cargo |
|---|---|
| Francisco Castillo | M4 reglas y riesgo, M5 integracion y salidas |
| Ignacio Jobse | M2 deteccion y seguimiento |
| Giancarlos Ricci | M3 geometria vial y trayectorias |
| Francisco Zuniga | Datos, M6 evaluacion |

## Interfaz funcional

Proceso por lotes:

```
video MP4 + configuracion YAML  ->  MP4 anotado + eventos CSV + resumen JSON
```

```bash
pip install -r requirements.txt
pip install -e .

python -m roadguard \
  --video  datos/videos/sec01.mp4 \
  --config configs/camara_ejemplo.yaml \
  --salida salidas/sec01
```

No hay API publica ni servicio web: CLI y archivos YAML.

## Estructura

```
src/roadguard/
  tipos.py            Contrato de datos compartido entre modulos
  pipeline.py         Orquestacion de la secuencia 4.3
  cli.py              Interfaz de linea de comandos
  m1_ingesta/         IC   Ingesta y configuracion        RF1, RF4, RF12
  m2_deteccion/       DTS  Deteccion y seguimiento        RF2, RF3
  m3_geometria/       GVT  Geometria vial y trayectorias  RF4, RF5, RF6
  m4_reglas/          MRR  Motor de reglas y riesgo       RF7-RF10
  m5_salidas/         VE   Visualizacion y exportacion    RF11, RF12
  m6_evaluacion/      ED   Evaluacion y diagnostico       RF2-RF12
tests/                Pruebas unitarias e integracion (pytest)
scripts/              Conversion de datasets y evaluacion (T6, T9)
configs/              Configuraciones de camara
datos/                Videos, anotaciones y trayectorias (no versionados)
salidas/              Resultados de ejecucion (no versionados)
docs/                 Plan, datos (DATOS.md) y evaluacion (EVALUACION.md)
```

Salidas de cada corrida en `--salida`:

- `video_anotado.mp4`: caja, ID, alerta experimental y riesgo por vehiculo
  (verde 0-29, amarillo 30-59, rojo 60-100), con advertencia permanente si
  falta calibracion.
- `eventos.csv`: un evento por activacion, con variables medidas y umbrales.
- `resumen.json`: resumen por vehiculo, configuracion normalizada y su
  SHA-256, version del modelo, FPS y desglose de rendimiento por etapa.

## Pruebas y evaluacion

```bash
python -m pytest
```

```bash
python scripts/convertir_trayectorias.py --help
```

```bash
python scripts/evaluar_reglas.py --help
```

```bash
python scripts/evaluar_uadetrac.py --help
```

## Convenciones

- **Tiempo**: `t` en segundos desde el inicio del video, derivado de los FPS
  reales. Las ventanas de 2 s, 5 s y 10 s se evaluan sobre `t`, nunca sobre
  conteo de cuadros.
- **Unidades**: metros, m/s, segundos.
- **Causalidad**: en el cuadro `t` solo se usa informacion disponible hasta
  `t`. Sin cuadros futuros.
- **Sin calibracion**: las metricas basadas en distancia quedan en `None` y
  se emite una advertencia explicita y visible.

Ver `docs/PLAN_IMPLEMENTACION.md` para el orden de trabajo y los criterios
de aceptacion.
