# Seguimiento

> **El estado vivo del proyecto.** Único documento donde se escribe avance. Cada quien actualiza sus filas en el mismo PR que hace el trabajo. Estados: `pendiente` · `en curso` · `en revisión` · `hecho` · `bloqueado`.
>
> Última actualización: 2026-11-15.

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
| Calibrar YAML de las 3 secuencias | R | en curso | 1 de 3: `configs/MVI_39271.yaml` con `scripts/calibrar_ua_detrac.py` y `m3_geometria/calibracion.py` (RMSE 0,14 m; predice trazos lejanos a ~5 px; 60 km/h en un auto real). MVI_40714 y MVI_40742 tienen la calzada tapada en los 7 cuadros bajados: faltan más cuadros para armar un fondo sin vehículos. Plazo 26-oct |
| M4 reglas RF7–RF9 y puntaje RF10–RF11 | C | en revisión | RF7 de C (`cercania.py`, PR #4). RF8 `zigzag.py`, RF9 `corte.py`, RF10/RF11 `puntaje.py` y la fachada `motor.py` los agregó Z el 2026-11-15 en la rama `prototipo-18nov`, 46 tests nuevos; C valida los supuestos anotados en los docstrings |
| M5 MP4 anotado, CSV de eventos y JSON por vehículo | R | en curso | Primera parte en `main` (`m5_salidas/`): cajas, ID, clase, carril, advertencia sin calibración y escritor MP4, 15 tests. Faltan colores de riesgo, alertas, CSV y JSON, que dependen de M4 |
| Integración y CLI | J | en revisión | Z armó `pipeline.py`, `cli.py` y `m5_salidas/exportar.py` el 2026-11-15 (rama `prototipo-18nov`): `python -m roadguard procesar` escribe `anotado.mp4`, `eventos.csv` y `resumen.json`; corrida real sobre clip sintético a 23 FPS en CPU y, el 15-nov, sobre **MVI_39271 completa** (1.570 cuadros) a 51,7 FPS en MPS con `--tracks`: 5 cercanías, 2 zigzag y 1 corte; evidencia en `knowledge/projects/entregas/evidencia/MVI_39271/` |
| Manual de uso | R | en revisión | Borrador completo de Z: [manual](../projects/entregas/manual-de-uso.md) con DOCX y PDF; R revisa calibración y YAML |
| Degradación de trayectorias y F1 de reglas | Z | pendiente | Depende de M4 |
| Bajar las imágenes completas de las 3 secuencias y convertirlas a MP4 a 25 FPS | Z | hecho | 15-nov: `scripts/bajar_ua_detrac.py` (zip del espejo por rangos HTTP) y `ffmpeg`; `datos/videos/MVI_39271.mp4`, `MVI_40714.mp4` y `MVI_40742.mp4` a 960×540 y 25 FPS, más los JPG y XML en `datos/ua-detrac/<secuencia>/` (fuera de git). R ya puede calibrar las otras dos sobre video |
| mAP@0.5 e IDF1 sobre UA-DETRAC | Z | en curso | 1 de 3: MVI_39271 con `scripts/medir_mvi.py` sobre `tracks.csv` y el XML: mAP@0.5 0,918 e IDF1 0,898 en la región de interés (0,693 y 0,772 sobre el cuadro completo), 8 cambios de ID ([anexo de la bitácora 2](../projects/entregas/bitacora-2.md#anexo-de-métricas-25)). Las otras dos esperan su YAML |
| FPS a 720p en Colab T4 | J con Z | pendiente | Depende de la integración |
| Bitácora 2 | C (borrador: Z) | en curso | [Bitácora 2](../projects/entregas/bitacora-2.md) redactada el 2026-11-15 desde el `git log`; filas de J, R y C marcadas `[revisar]`, anexo de métricas en `[pendiente: medir]` |
| Video demo | Z | en curso | [Guion y plan de producción](../projects/entregas/video-demo.md); escena 4 con versión completa y parcial, se decide el 19-nov |
| highD como segunda referencia | Z | bloqueado | No hay evidencia de acceso ([ADR-0001](../decisions/0001-ngsim-como-referencia-de-reglas.md)) |
