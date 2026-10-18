# Cómo se contribuye

Estándar · knowledge · versión 2026-09-25.

## El estándar

1. **Enlazar, no duplicar.** El knowledge es el vestíbulo; el detalle técnico vive junto al código y se enlaza.
2. **Qué va dónde.** Si cambia cuando cambia el código, va junto al código y en el mismo PR. Si es dominio, arquitectura o una decisión estructural, va al knowledge. En la duda, gana el código.
3. **Nada se afirma sin origen.** Toda cifra o regla lleva su fuente y su estado (`Confirmada`, `Candidata a validar` o `Brecha`).
4. **El diseño va antes que el código y queda escrito.** Si al implementar aparece una decisión que el diseño no cubría, se para, se escribe un PRD o un ADR y se vuelve.
5. **Un ADR `proposed` no se asume.** Lo que depende de él no se implementa hasta que se acepte.
6. **Cero secretos y cero datos personales versionados.** Los datasets viven en `datos/`, fuera de git.

Formato: Markdown GFM, enlaces relativos, fechas ISO 8601, documentos en español y commits en inglés. Los nombres van en `UPPER_SNAKE_CASE.md` para referencia y en `kebab-case.md` para narrativos. Sin frontmatter; las fuentes van en una sección `Fuentes` al pie.

## Adaptaciones de este equipo

- **Sin Linear.** El estado vivo (quién, qué, en qué va y para cuándo) vive **solo** en [SEGUIMIENTO](./roadmap/SEGUIMIENTO.md). Ningún otro documento repite avance.
- **Sin puntos ni estimaciones.** Un proyecto de ramo no necesita medir carga. Lo que sí se registra es quién es responsable de cada pieza, para que el trabajo quede parejo.
- **La propuesta inscrita es la fuente superior.** El formulario TEL-328 del 2026-09-11 está por encima del knowledge. Cambiar una regla RF, un criterio de aceptación o el alcance requiere un ADR y, si toca la nota, el visto bueno del docente.
- **Respetar lo construido.** Las estructuras de `tipos.py` no se renombran ni se quitan sin avisar al equipo; agregar campos está permitido. Es la regla de [`docs/PLAN_IMPLEMENTACION.md`](../docs/PLAN_IMPLEMENTACION.md) §0.
- **Un dueño por archivo a la vez.** Cada módulo tiene un responsable. Para tocar el módulo de otro, primero se le avisa.
