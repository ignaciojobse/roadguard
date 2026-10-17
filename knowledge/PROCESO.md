# Proceso: de la tarea al merge

> Estado: `Candidata a validar`. Recoge cómo se trabajó el PR #1 y lo deja escrito; el equipo lo confirma en la próxima reunión.

## El ciclo

1. **Tomar la tarea.** Se anota en [SEGUIMIENTO](./roadmap/SEGUIMIENTO.md) con tu nombre y pasa a `en curso`.
2. **Diseño, si hace falta.** Si la tarea abre una decisión estructural, primero va el ADR en `decisions/`; si es un frente nuevo, su carpeta en `projects/`.
3. **Rama propia** desde `main`: `<modulo>-<tema>`, por ejemplo `m4-reglas` o `m6-degradacion`.
4. **Gate local** antes de abrir el PR:

   ```bash
   pip install -r requirements.txt && pip install -e .
   python -m pytest
   ```

5. **PR a `main`** con la plantilla de [`.github/pull_request_template.md`](../.github/pull_request_template.md). Título en inglés con prefijo convencional y cuerpo en español. La sección Verificación lleva la salida real del gate.
6. **Revisión** de al menos otro integrante, idealmente el dueño del módulo que tu cambio consume.
7. **Merge** por el autor, con la revisión aprobada y el gate en verde.
8. **Cerrar la fila** en SEGUIMIENTO con el enlace al PR.

## Reglas

- Sin gate no hay PR. «No corrido» no es un estado válido.
- Un PR lleva la funcionalidad completa con sus tests y su documentación.
- La documentación que cambia con el código va en el mismo PR.
