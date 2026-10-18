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
