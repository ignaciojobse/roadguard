# Seguimiento

> **El estado vivo del proyecto.** Único documento donde se escribe avance. Cada quien actualiza sus filas en el mismo PR que hace el trabajo. Estados: `pendiente` · `en curso` · `en revisión` · `hecho` · `bloqueado`.
>
> Última actualización: 2026-10-17.

## Hacia el avance (21 y 22 de octubre)

| Tarea | Responsable | Estado | Evidencia o bloqueo |
|---|---|---|---|
| Acordar el reparto de [ROADMAP](./ROADMAP.md#responsables) | Todos | pendiente | Propuesta escrita el 2026-10-17 |
| Muestra NGSIM, cargador y eventos de referencia | Z | en revisión | `m6_evaluacion/`, 21 tests; PR de knowledge y M6 |
| Protocolo de evaluación escrito | Z | en revisión | [PRD de datos y evaluación](../projects/datos-y-evaluacion/PRD.md) |
| Elegir 3 secuencias UA-DETRAC para la demo | Z | pendiente | Criterios escritos en el PRD; falta descargar el dataset |
| Bitácora 1 | Z | en curso | [Borrador](../projects/entregas/bitacora-1.md); cada uno completa su sección |
| Láminas de la presentación de avance | Z | pendiente | [Guion](../projects/entregas/presentacion-avance.md) |
| Plantear ADR-0002 y 0003 al docente | Z | pendiente | En la presentación del 22-oct |

## Hacia el prototipo (18 y 19 de noviembre)

| Tarea | Responsable | Estado | Evidencia o bloqueo |
|---|---|---|---|
| Base, M1, M2 y M3 | J | hecho | PR #1, 57 tests |
| Calibrar YAML de las 3 secuencias | R | pendiente | Depende de la elección de secuencias |
| M4 reglas RF7–RF9 y puntaje RF10–RF11 | C | pendiente | Puede probar ya con `cargar_ngsim` |
| M5 MP4 anotado, CSV de eventos y JSON por vehículo | R | pendiente | Depende de M4 para alertas, no para cajas e ID |
| Integración y CLI | J | pendiente | — |
| Degradación de trayectorias y F1 de reglas | Z | pendiente | Depende de M4 |
| mAP@0.5 e IDF1 sobre UA-DETRAC | Z | pendiente | Depende de las secuencias |
| FPS a 720p en Colab T4 | J con Z | pendiente | Depende de la integración |
| highD como segunda referencia | Z | bloqueado | No hay evidencia de acceso ([ADR-0001](../decisions/0001-ngsim-como-referencia-de-reglas.md)) |
