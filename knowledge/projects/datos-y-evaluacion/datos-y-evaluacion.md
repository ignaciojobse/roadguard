# Datos y evaluación — índice

> Datos de referencia y protocolo para medir RoadGuard contra los criterios de §2.5: detección, seguimiento, reglas y rendimiento. Responsable: Francisco Zúñiga. **Estado →** [SEGUIMIENTO](../../roadmap/SEGUIMIENTO.md).

## Documentos

- [PRD](./PRD.md): qué se mide, con qué datos, cómo y qué falta.

## Decisiones que lo condicionan

- [ADR-0001](../../decisions/0001-ngsim-como-referencia-de-reglas.md): NGSIM como referencia de reglas.

## Decisiones abiertas

- Si existe acceso a highD. **Dueño:** Z.
- Mapeo de clases para mAP: el conjunto de prueba trae `car`, `bus`, `van` y `others`, sin motos (confirmado). Falta acordar la métrica principal sin clase. **Dueño:** Z con J.

## Secuencias de la demo

**MVI_39271** (base), **MVI_40714** (densa) y **MVI_40742** (noche). La justificación y las notas de calibración para R están en el [PRD §7](./PRD.md#secuencias-elegidas-2026-10-17).

## Implementación

- `src/roadguard/m6_evaluacion/ngsim.py`: descarga y conversión de NGSIM al contrato de M3.
- `src/roadguard/m6_evaluacion/referencia.py`: eventos de referencia RF7–RF9.
- `src/roadguard/m6_evaluacion/emparejamiento.py`: precisión, recobrado y F1 de eventos.
- `src/roadguard/m6_evaluacion/ua_detrac.py`: resumen de anotaciones XML para elegir secuencias.
- `tests/test_evaluacion.py`, `tests/test_ua_detrac.py`.

## Cómo reproducir la muestra

```bash
python -m roadguard.m6_evaluacion.ngsim --ubicacion us-101 \
  --desde-ms 1118847300000 --duracion-s 60 --salida datos/ngsim/us101_muestra.csv
```

```python
from roadguard.m6_evaluacion.ngsim import cargar_ngsim
from roadguard.m6_evaluacion.referencia import eventos_referencia
from roadguard.tipos import Umbrales

cuadros = cargar_ngsim("datos/ngsim/us101_muestra.csv")   # 600 cuadros, 270 vehículos
eventos = eventos_referencia(cuadros, Umbrales())          # 195 cercanía · 22 corte · 8 zigzag
```

Para M4: cada `CuadroReferencia` trae `estados` y `relaciones` con el mismo contrato que produce M3, así que el motor de reglas se puede alimentar cuadro a cuadro en orden de `t`.

## Cómo reproducir el F1 de reglas (18-nov)

Desde la raíz. Primero la muestra NGSIM (arriba) y corridas de UA-DETRAC con `--tracks` en `salidas/<secuencia>`; después se miden los defectos reales de la cámara, se degrada NGSIM con ellos y se compara; y aparte se compara el video real contra su anotación.

```bash
python scripts/medir_ruido_m3.py MVI_39271              # error de posición, pérdidas y cambios de ID
python scripts/medir_ruido_m3.py MVI_40714              # idem, cola densa
python scripts/evaluar_reglas.py --semillas 5           # NGSIM degradado: evidencia/reglas/f1_ngsim.json
python scripts/evaluar_reglas_video.py MVI_39271 MVI_40714   # video real: evidencia/reglas/f1_video.json
```

- `src/roadguard/m6_evaluacion/degradacion.py`: remuestreo a 25 Hz, error de posición AR(1), pérdidas por cadena de Markov, cambios de ID, y el paso de M3 + M4 en el mismo orden que el pipeline. Los eventos vuelven con el ID original para compararlos con la referencia.
- `src/roadguard/m6_evaluacion/referencia_video.py`: cajas anotadas → metros, velocidad con ajuste centrado (la referencia puede mirar el futuro), carril con los polígonos del YAML; los IDs del sistema se traducen al ID anotado con el que más cuadros comparten.
- Además del F1 uno a uno se informa la **fracción con respaldo**: qué parte de las alertas toca un evento real del mismo vehículo y regla.
- La tolerancia de interrupción de RF7 es parte de la definición de la regla, así que también la usa la referencia; M4 y la referencia coinciden exactamente sobre la trayectoria limpia con cualquier valor.

| Escenario (configuración de los YAML) | Global | Cercanía | Zigzag | Corte |
|---|---|---|---|---|
| M4 sobre trayectoria limpia | 1,00 | 1,00 | 1,00 | 1,00 |
| Sistema sin ruido (M3 + M4) | 0,89 | 0,91 | 0,55 | 0,67 |
| **NGSIM con defectos de MVI_39271** | **0,80** | **0,82** | **0,61** | **0,62** |
| NGSIM con defectos de la cola densa | 0,51 | 0,53 | 0,36 | 0,34 |
| Definición original, defectos de MVI_39271 | 0,54 | 0,54 | 0,40 | 0,51 |
| **Video real MVI_39271** (17 eventos de referencia) | **0,65** | 0,55 | 0,67 | 1,00 |

Límites: la referencia en video comparte la homografía con el sistema, así que no juzga la calibración; un minuto de video da pocos eventos; NGSIM es autopista a 10 Hz y se interpola; y el ruido se aplica a cada vehículo por separado, sin oclusiones que dependan de la geometría.
