# Bitácora 1 — avance al 2026-10-21

<!-- Nota interna, no se exporta.
**Estado (2026-10-18):** versión completa. Las filas de J, R y C las redactó Z a partir de la evidencia del repo (PR #1, código y tests), no de lo que cada uno diría. Cada integrante **confirma o corrige su fila antes del 2026-10-20**, y agrega en «Problemas y desvíos» lo que corresponda. R: falta tu participación real en M3 más allá del código. El formato final se ajusta a lo que pida Aula.
-->

## Período

Del 2026-09-11 (inscripción) al 2026-10-21.

## Resumen

Están implementados y testeados la base compartida y los módulos de percepción y geometría: ingesta y configuración (M1), detección con YOLOv8n y seguimiento con ByteTrack (M2), y homografía, carriles, trayectorias causales y relaciones viales con THW y TTC (M3). Tienen 57 tests unitarios que cubren los casos límite de §2.5 que les corresponden. Además existe la referencia de reglas sobre trayectorias reales de NGSIM y el cálculo de F1 de eventos (M6), con 23 tests. En total hay 80 tests. Faltan el motor de reglas (M4), las salidas (M5), la integración y las mediciones de §2.5.

## Avance por actividad (§3.3)

| Actividad | Responsable | Qué hay | Evidencia |
|---|---|---|---|
| Investigación, acceso y selección de datos | Z | NGSIM elegido como referencia de reglas; muestra de 60 s de US-101 descargada y convertida; protocolo de evaluación escrito; 3 secuencias UA-DETRAC elegidas tras resumir las 40 de prueba (MVI_39271 base, MVI_40714 densa, MVI_40742 noche), con notas de calibración | `m6_evaluacion/ngsim.py`, `ua_detrac.py`, ADR-0001, PRD de datos y evaluación |
| Detección y seguimiento | J | YOLOv8n preentrenado con mapeo explícito COCO → automóvil, bus, camión y motocicleta, y filtro por región de interés. ByteTrack implementado sobre NumPy y SciPy, independiente del detector: filtro de Kalman, doble asociación por confianza (la de confianza baja recupera vehículos parcialmente ocluidos) y un buffer que conserva el ID durante oclusiones breves. Además implementó el contrato de datos y M1 | PR #1, `m2_deteccion/`, 10 tests |
| Perspectiva, carriles y trayectorias | R (implementó J) | Homografía al plano del camino; sin calibración, los campos métricos quedan no disponibles. Asignación de carril con confianza y confirmación de cambio completo por permanencia. Suavizado causal por mínimos cuadrados en una ventana de 1 s, con reinicio del historial ante saltos imposibles. Predecesor y seguidor por carril, THW y TTC | PR #1, `m3_geometria/`, 28 tests (geometría, carriles, relaciones y robustez) |
| Reglas y puntaje | C | Sin código en `main` al 2026-10-18. Las reglas RF7–RF9 ya se pueden probar sobre trayectorias reales de NGSIM; el plan ajustado cierra M4 el 1-nov | — |
| Integración, video y registros | C | Sin código en `main` al 2026-10-18; el inicio previsto era el 12-oct. En el reparto propuesto pasa a J (integración) y R (video y registros) | — |
| Evaluación y optimización | Z | Adelantado: referencia de eventos RF7–RF9 y F1 por regla | `m6_evaluacion/`, 23 tests |

## Decisiones del período

- **NGSIM reemplaza a highD** como referencia de reglas, aplicando la regla de §4.4 de la propuesta (ADR-0001).
- **El contrato de datos (`tipos.py`) queda fijo** como interfaz entre módulos: se puede agregar, no renombrar ni quitar.
- **La referencia usa las mismas funciones que M3** para THW, TTC y cambio completo, para que el F1 compare definiciones idénticas.
- **Reparto ajustado** a lo construido, propuesto en ROADMAP y por acordar.

## Hallazgo

En 60 s de US-101 con tráfico congestionado (270 vehículos, velocidad mediana 12,2 m/s, THW mediano 1,92 s), la regla de cercanía de la propuesta marca al 43 % de los vehículos. En congestión, un THW bajo 1,5 s es lo habitual. Se va a medir en flujo libre antes de concluir, y motiva la propuesta de puntaje por severidad (ADR-0003).

## Problemas y desvíos

- La selección de datos se atrasó respecto del plan (14–20 sep). Se cerró con NGSIM para reglas y con la elección de 3 secuencias UA-DETRAC el 2026-10-17. El sitio oficial de UA-DETRAC está caído; se usó un espejo público del zip original.
- El reparto real se desvió del inscrito: M3 lo implementó J. Se propone reequilibrar (ROADMAP, «Responsables»).
- **M4 se corre una semana:** la propuesta da a reglas y puntaje del 28-sep al 25-oct; el plan ajustado lo cierra el 1-nov, porque al 2026-10-17 M4 no había empezado. La integración (1-nov) y la evaluación (12-nov) se mantienen en las fechas inscritas.
- No está verificado si se solicitó acceso a highD el 14-sep.

## Próximos pasos (hasta el 2026-11-01)

- C: M4 sobre trayectorias NGSIM.
- R: calibración de las tres secuencias y M5.
- J: integración y CLI.
- Z: imágenes completas de las 3 secuencias en MP4 para R y J, degradación de trayectorias y primera medición de F1.

## Propuestas para validar con el docente

- Cuarto patrón: velocidad anómala respecto del flujo (ADR-0002).
- Puntaje ponderado por severidad TET/TIT como modo opcional de RF10 (ADR-0003).
