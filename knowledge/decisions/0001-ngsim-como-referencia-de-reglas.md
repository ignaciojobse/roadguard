# ADR-0001 — NGSIM como referencia para validar reglas

> Estado: `accepted` · Fecha: 2026-10-17

## Contexto

El criterio de reglas de §2.5 compara las alertas de RoadGuard contra eventos de referencia calculados desde trayectorias reales. La propuesta eligió highD como primera opción y NGSIM como reemplazo, con una regla explícita en §4.4: *solicitar highD el 14 de septiembre y activar NGSIM el 21 de septiembre si continúa no disponible*.

Al 2026-10-17 el repo no tiene datos de highD ni evidencia de que haya acceso. highD exige una solicitud con aprobación manual y no se puede descargar libremente. NGSIM es público en data.transportation.gov y responde a consultas por API.

## Decisión

Usamos **NGSIM US-101** como referencia para validar RF7, RF8 y RF9. Las trayectorias se convierten al mismo contrato que produce M3 (`EstadoCinematico` y `Relacion`), y THW y TTC se recalculan con las funciones de M3 en vez de tomarse del archivo. Así la referencia y el sistema miden la misma cosa.

## Alternativas consideradas

- **A — Esperar highD:** trae THW, TTC y carriles ya calculados y menos ruido. El plazo de la propuesta venció hace casi un mes y la evaluación arranca el 26-oct, así que esperar bloquea M6 y también deja a M4 sin datos reales para probar.
- **B — Anotar eventos a mano sobre UA-DETRAC:** la propuesta lo descarta en §2.4 («no se crearán anotaciones masivas nuevas para ese propósito»).

## Consecuencias

- M4 tiene trayectorias reales desde hoy, sin esperar video calibrado.
- Se hereda el ruido conocido de NGSIM: velocidades y aceleraciones derivadas con errores y algunos solapes de vehículos (Coifman y Li, 2017). Por eso la referencia usa la velocidad, no la aceleración.
- NGSIM va a 10 Hz y el video a 25 FPS. Las reglas trabajan sobre `t` en segundos, así que no cambian.
- US-101 tiene rampas: los carriles 7 y 8 son de entrada y salida, y una incorporación desde la rampa cuenta como cambio de carril.

## Pendientes y no verificado

- **No verificado:** si se envió la solicitud de highD el 14-sep. Si hay acceso, se agrega como segunda referencia, con un cargador hermano de `m6_evaluacion/ngsim.py`.
- La muestra cargada (60 s, minuto 5 de US-101) es tráfico congestionado. Falta una ventana de flujo más libre antes de calibrar umbrales.

## Referencias

- Formulario de propuesta TEL-328, §2.4 y §4.4.
- FHWA, *Next Generation Simulation (NGSIM) Vehicle Trajectories*, data.transportation.gov, dataset `8ect-6jqj`.
- Coifman, B. y Li, L. (2017). *A critical evaluation of the Next Generation Simulation (NGSIM) vehicle trajectory dataset*. Transportation Research Part B, 105, 362–377.
- Código: `src/roadguard/m6_evaluacion/ngsim.py`, `tests/test_evaluacion.py`.
