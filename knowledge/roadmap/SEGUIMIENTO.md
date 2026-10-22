# Seguimiento

> **El estado vivo del proyecto.** Único documento donde se escribe avance. Cada quien actualiza sus filas en el mismo PR que hace el trabajo. Estados: `pendiente` · `en curso` · `en revisión` · `hecho` · `bloqueado`.
>
> Última actualización: 2026-10-21.

## Hacia el avance (21 y 22 de octubre)

| Tarea | Responsable | Estado | Evidencia o bloqueo |
|---|---|---|---|
| Acordar el reparto de [ROADMAP](./ROADMAP.md#responsables) | Todos | pendiente | Propuesta escrita el 2026-10-17 |
| Muestra NGSIM, cargador y eventos de referencia | Z | en revisión | `m6_evaluacion/`, 21 tests; PR de knowledge y M6 |
| Protocolo de evaluación escrito | Z | en revisión | [PRD de datos y evaluación](../projects/datos-y-evaluacion/PRD.md) |
| Marca RoadGuard | Z | hecho | [MARCA](../projects/entregas/marca/MARCA.md) |
| Elegir 3 secuencias UA-DETRAC para la demo | Z | en revisión | MVI_39271, MVI_40714 y MVI_40742, con notas de calibración para R ([PRD §7](../projects/datos-y-evaluacion/PRD.md#secuencias-elegidas-2026-10-17)) |
| Bitácora 1 | Z | en revisión | [Bitácora](../projects/entregas/bitacora-1.md) completa y exportada a DOCX y PDF (2026-10-18); las filas de J, R y C se redactaron desde el repo y cada uno las confirma antes del 20-oct |
| Láminas de la presentación de avance | Z | en revisión | Deck de 9 láminas con PDF de respaldo, [dreamxist/decks#1](https://github.com/dreamxist/decks/pull/1), [preview](https://decks-umbra-git-roadguard-avance-franciscozunigaps-projects.vercel.app/roadguard-avance); láminas 2–5 marcadas `[revisar]` para sus dueños |
| Plantear ADR-0002 y 0003 al docente | Z | pendiente | En la presentación del 22-oct; pregunta redactada en [mensajes](../projects/entregas/mensajes-grupo.md) |
| Enviar al grupo el reparto, los plazos y los links | Z | pendiente | Borrador en [mensajes](../projects/entregas/mensajes-grupo.md) |
| Notas de orador de las láminas de Z | Z | hecho | [Guion](../projects/entregas/presentacion-avance.md#notas-de-orador-láminas-de-z) |

## Hacia el prototipo (18 y 19 de noviembre)

| Tarea | Responsable | Estado | Evidencia o bloqueo |
|---|---|---|---|
| Base, M1, M2 y M3 | J | hecho | PR #1, 57 tests |
| Calibrar YAML de las 3 secuencias | R | pendiente | Secuencias elegidas; cuadros de referencia en `datos/ua-detrac/referencia/`. Plazo 26-oct |
| M4 reglas RF7–RF9 y puntaje RF10–RF11 | C | pendiente | Puede probar ya con `cargar_ngsim` |
| M5 MP4 anotado, CSV de eventos y JSON por vehículo | R | en curso | Primera parte en la rama `m5-salidas`: cajas, ID, clase, carril, advertencia sin calibración y escritor MP4, 15 tests. Faltan colores de riesgo, alertas, CSV y JSON, que dependen de M4 |
| Integración y CLI | J | pendiente | — |
| Degradación de trayectorias y F1 de reglas | Z | pendiente | Depende de M4 |
| Bajar las imágenes completas de las 3 secuencias y convertirlas a MP4 a 25 FPS | Z | pendiente | Posterior al 22-oct; las necesitan R para calibrar sobre video y J para integrar |
| mAP@0.5 e IDF1 sobre UA-DETRAC | Z | pendiente | Secuencias elegidas; falta el parser completo por cuadro |
| FPS a 720p en Colab T4 | J con Z | pendiente | Depende de la integración |
| highD como segunda referencia | Z | bloqueado | No hay evidencia de acceso ([ADR-0001](../decisions/0001-ngsim-como-referencia-de-reglas.md)) |
