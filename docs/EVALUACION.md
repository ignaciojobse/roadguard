# Evaluacion y diagnostico de RoadGuard (T9, M6, seccion 2.5)

Responsable segun la propuesta: Francisco Zuniga.

Este documento fija el protocolo y es la plantilla del informe de
resultados. Las celdas marcadas _pendiente_ se completan con las salidas de
los scripts; no se reportan valores que no se hayan medido.

## 1. Criterios de aceptacion

| Metrica | Criterio | Fuente | Script | Resultado |
|---|---|---|---|---|
| mAP@0.5 | >= 0,60 | secuencias seleccionadas de UA-DETRAC | `scripts/evaluar_uadetrac.py` | _pendiente_ |
| IDF1 | >= 0,60 | UA-DETRAC, con informe separado de intercambios de ID | `scripts/evaluar_uadetrac.py` | _pendiente_ |
| F1 de reglas | >= 0,75 | trayectorias degradadas vs. referencia highD/NGSIM | `scripts/evaluar_reglas.py` | _pendiente_ |
| Rendimiento | >= 15 FPS a 720p | GPU Colab T4 (25 FPS como extension) | `python -m roadguard` (`fps_por_etapa` del JSON) | _pendiente_ |
| Demostracion | >= 3 secuencias | end-to-end | `python -m roadguard` | _pendiente_ |

## 2. Protocolo

### 2.1 Deteccion y seguimiento (UA-DETRAC)

```bash
python scripts/evaluar_uadetrac.py \
  --imagenes datos/uadetrac/imagenes/MVI_XXXXX \
  --anotaciones datos/uadetrac/anotaciones/MVI_XXXXX.xml \
  --salida salidas/evaluacion/MVI_XXXXX --dispositivo 0
```

- Clases: mapeo `MAPEO_UADETRAC` (ver `docs/DATOS.md`). Se reporta mAP sobre
  las clases con anotaciones y AP agnostico (`ap_vehiculo`).
- AP: IoU >= 0,5, interpolacion de todos los puntos; predicciones con
  confianza >= 0,01 para no truncar la curva P-R.
- Regiones ignoradas: se descartan predicciones con centro dentro de ellas.
- Seguimiento: piso de confianza 0,25 (igual que el pipeline). IDF1/IDP/IDR
  segun Ristani et al.; intercambios de ID y MOTA segun CLEAR MOT.
- Las metricas se calculan por secuencia y se informan por separado; no se
  extrapolan a camaras no evaluadas (riesgo 4.4).

### 2.2 Reglas (highD o NGSIM)

```bash
python scripts/convertir_trayectorias.py highd ... --salida datos/trayectorias/highd_01.csv
python scripts/evaluar_reglas.py \
  --trayectorias datos/trayectorias/highd_01.csv \
  --config configs/camara_ejemplo.yaml \
  --ruido 0.1 0.3 0.5 --perdida 0.05 --intercambio 0.002 \
  --semillas 1 2 3 --tolerancia 1.0 \
  --salida salidas/evaluacion/reglas_highd_01.json
```

- Referencia: eventos del motor de RoadGuard (M3 + M4) sobre trayectorias
  limpias, con velocidades y carriles del dataset.
- Degradacion (`m6_evaluacion/degradacion.py`): ruido gaussiano en x e y,
  perdida de observaciones, intercambio de ID entre vehiculos cercanos y
  reasignacion de carril desde la `y` ruidosa. La velocidad se reestima con
  el mismo `HistorialCausal` del pipeline. Semillas registradas en el JSON.
- Emparejamiento: misma regla y mismo vehiculo, intervalos solapados con
  tolerancia de 1 s; uno a uno.
- Se informa precision, recobrado y F1 por regla y global, para cada nivel
  de ruido (media y minimo entre semillas).

### 2.3 Rendimiento

El JSON de cada corrida (`resumen.json`, `ejecucion.fps_por_etapa`) trae el
desglose por etapa (lectura, deteccion, seguimiento, geometria, reglas,
anotacion). Si no se alcanzan 15 FPS, la propuesta indica **primero**
reducir region o frecuencia de deteccion y perfilar etapas, y solo despues
revisar umbrales (riesgo 4.4).

## 3. Robustez (seccion 2.5)

| Caso | Verificacion automatica | Resultado sobre video real |
|---|---|---|
| Oclusiones breves | `tests/test_deteccion_seguimiento.py::test_oclusion_breve_conserva_id` | _pendiente_ |
| Perdida de ID | `tests/test_geometria.py::test_salto_imposible_reinicia_historial`; intercambios simulados en `degradar` | _pendiente_ |
| Vehiculos detenidos | `tests/test_robustez.py::test_vehiculo_detenido` | _pendiente_ |
| Ausencia de predecesor | `tests/test_robustez.py`, `tests/test_relaciones.py` | _pendiente_ |
| Cambios incompletos | `tests/test_carriles.py`, `tests/test_robustez.py` | _pendiente_ |
| Camaras sin calibracion | `tests/test_pipeline.py::test_end_to_end_sin_calibracion` | _pendiente_ |

## 4. Resultados

### 4.1 Deteccion y seguimiento

| Secuencia | Condicion | mAP@0.5 | AP agnostico | IDF1 | Intercambios de ID | FPS det.+seg. |
|---|---|---|---|---|---|---|
| MVI_41063 | sunny | _pendiente_ | | | | |
| MVI_40243 | cloudy | _pendiente_ | | | | |
| MVI_40751 | night | _pendiente_ | | | | |

Estado al 17-10-2026: el pipeline completo se ejecuto con YOLOv8n real
(ultralytics 8.4.180, MPS) sobre un video de prueba armado con la imagen
`bus.jpg` de Ultralytics: 100 cuadros a 16,5 FPS, ID estable, personas
filtradas y advertencia de calibracion visible. **Falta la validacion con
imagenes reales de trafico** (secuencias de `docs/DATOS.md`); el lector de
anotaciones si se verifico contra los XML reales de UA-DETRAC.

### 4.2 Reglas

| Trayectorias | Ruido (m) | Precision | Recobrado | F1 medio | F1 minimo |
|---|---|---|---|---|---|
| _pendiente_ | | | | | |

### 4.3 Demostracion end-to-end

| Secuencia | Calibrada | FPS de procesamiento | Eventos (cercania / zigzag / corte) | Revision humana |
|---|---|---|---|---|
| _pendiente_ | | | | |

## 5. Errores y limitaciones conocidas

- Las alertas son experimentales y orientan la revision humana; los umbrales
  son parametros, no limites legales.
- La distancia se mide entre puntos de contacto con la calzada, sin
  descontar el largo del vehiculo: THW y TTC son aproximados.
- La homografia supone un plano; pendientes o curvas fuertes degradan la
  proyeccion. El error de reproyeccion de los puntos de calibracion queda en
  `parametros.error_reproyeccion_m` del JSON.
- Las relaciones suponen que `x_camino` crece en el sentido de avance: cada
  configuracion debe cubrir un solo sentido de circulacion o calibrarse por
  separado.
- La confirmacion de cambios de carril introduce una latencia igual a
  `permanencia_cambio_carril`; la regla de corte la compensa con un bufer
  causal de 2 s, pero latencias mayores a la ventana de corte la anulan.
- El modelo preentrenado en COCO no distingue furgones; UA-DETRAC no anota
  motocicletas.
