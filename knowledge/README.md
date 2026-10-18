# Qué es este knowledge

Estándar · knowledge · versión 2026-09-25, adaptado a RoadGuard el 2026-10-17.

Este directorio guarda lo que no cambia cuando cambia el código: el problema que resolvemos, las reglas que el sistema implementa y de dónde salen, las decisiones estructurales, el reparto del trabajo y el estado de cada frente. Lo lee cualquier integrante del equipo, o un agente, antes de tomar una tarea.

## Cómo leerlo

1. [INDEX](./INDEX.md) es la entrada.
2. Si vas a tomar una tarea, mira primero tu fila en [SEGUIMIENTO](./roadmap/SEGUIMIENTO.md) y después el proyecto o el ADR que la condiciona.
3. Si algo de acá contradice al código, manda el código, y el documento se corrige en el mismo PR.

## Dos modos de documento

- **Vivos**, con nombre fijo, se editan a medida que crecen: `CONTEXTO`, `ACTORES`, `GLOSARIO`, `REGLAS_NEGOCIO`, `ROADMAP` y `SEGUIMIENTO`.
- **Inmutables**: los ADR numerados y los PRD cerrados. Si algo cambia, se escribe otro que los supersede.

## Estado de validación

Cada regla, dato o fórmula lleva su fuente y uno de tres estados:

- `Confirmada`: está en la propuesta inscrita o la validó el equipo.
- `Candidata a validar`: propuesta por alguien, todavía no acordada.
- `Brecha`: falta el dato o la decisión, y se dice.
