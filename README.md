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

## Alcance de esta rama

Esta rama contiene la base compartida, los modulos de percepcion y geometria,
la referencia M6 y avances parciales de M4 (RF7) y M5. El motor de reglas
completo, la visualizacion y exportacion completa y la integracion end-to-end
aun no estan disponibles. El reparto y el estado viven en `knowledge/roadmap/`.

| Modulo | Estado en esta rama | Responsable |
|---|---|---|
| Contrato de datos (`tipos.py`, `poligonos.py`) | Implementado | Base compartida |
| M1 Ingesta y configuracion | Implementado | Base compartida |
| M2 Deteccion y seguimiento | Implementado | Ignacio Jobse |
| M3 Geometria vial y trayectorias | Implementado | Giancarlos Ricci |
| M4 Motor de reglas y riesgo | Parcial: cercania (RF7) | Francisco Castillo |
| M5 Visualizacion y exportacion | Parcial: cajas, ID, carril y MP4 anotado | Francisco Castillo |
| M6 Evaluacion y diagnostico | Parcial: referencia NGSIM y F1 de eventos | Francisco Zuniga |
| Datos y seleccion de secuencias | Parcial: NGSIM listo, UA-DETRAC pendiente | Francisco Zuniga |

El contrato de datos de `tipos.py` se conserva completo, incluidas las
estructuras que consumen los modulos posteriores (`Evento`, `PuntajeRiesgo`,
`ResumenVehiculo`, `ResumenEjecucion`) y los umbrales de las reglas. Esa es
la interfaz contra la que se integraran M4, M5 y M6, y por eso se mantiene
estable aunque su implementacion viva en otra rama.

No hay CLI ni pipeline end-to-end en esta rama: los modulos se usan como
biblioteca y se ejercitan desde las pruebas.

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
  m1_ingesta/         IC   Ingesta y configuracion        RF1, RF4
  m2_deteccion/       DTS  Deteccion y seguimiento        RF2, RF3
  m3_geometria/       GVT  Geometria vial y trayectorias  RF4, RF5, RF6
  m4_reglas/          Motor parcial: cercania (RF7)
  m5_salidas/         VE   Video anotado (parcial)              RF11, RF12
  m6_evaluacion/      ED   Datos de referencia y metricas de eventos
tests/                Pruebas unitarias (pytest)
configs/              Configuraciones de camara
datos/                Videos y anotaciones (no versionados)
docs/                 Plan de implementacion
knowledge/            Contexto, decisiones, reparto y seguimiento del proyecto
```

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

### Primer avance de M4: cercania (RF7)

`DetectorCercania` procesa cada cuadro causalmente. Por defecto, la cercania
exige velocidad sobre el umbral, THW bajo el umbral y persistencia continua de
2 s; una observacion ausente o invalida, o un cambio de predecesor, corta el tramo.
`entradas` abajo representa los datos que aporta el llamador por cuadro.
`activos` son snapshots
para visualizacion y no deben acumularse; `cerrados` y `finalizar()` entregan
eventos confirmados, cuyo fin es la ultima observacion valida. Sin calibracion
se emite advertencia y no se genera evento. El aporte RF7 (40 por defecto) no
es un puntaje acumulado. RF8, RF9, acumulacion/bandas RF10–RF11 e integracion
end-to-end siguen pendientes; resultados experimentales requieren revision
humana y no son determinaciones legales.

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
