Estándar · ticket · 2026-10-06, adaptado sin Linear: la tarea es una fila de SEGUIMIENTO y, si no cabe ahí, esta spec en `projects/<slug>/tasks/`.

# Tarea — <resultado, no actividad>

## Objetivo

Al cerrar, <quién> podrá <resultado observable>.

### Incluye

- <qué entra>

### No incluye

- <qué queda fuera y dónde va>

## Fuentes

- **PRD:** <ruta> — § <sección>
- **ADR:** <ruta> — estado: proposed / accepted
- **Propuesta TEL-328:** <RF o sección>

Si una fuente no aplica, escribir **No aplica**. Si las fuentes se contradicen, detenerse y avisar al equipo.

## Diseño

- [ ] PRD o documentación completos para este corte
- [ ] ADR si aparece una decisión estructural
- [ ] Contrato de comportamiento y plan de verificación escritos abajo

## Implementación

1. <paso concreto>
2. <documentación que cambia con el código, en el mismo PR>

## Verificación

- **Gate:** `python -m pytest`, con la salida pegada en el PR
- **Test que cubre el comportamiento:** <ruta>
- **Recorrido observable:** <video, CSV o comando que lo demuestra>

## Detención

Detenerse si una fuente se contradice, un ADR requerido sigue `proposed`, aparece alcance nuevo o no se puede producir la evidencia.
