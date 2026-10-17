# Presentación de avance — guion

> 2026-10-22, sala K304, presencial obligatorio. Duración por confirmar; el guion está pensado para unos 10 minutos más preguntas. Cada integrante presenta su frente.

| # | Lámina | Quién | Contenido | Evidencia a mostrar |
|---|---|---|---|---|
| 1 | Qué es RoadGuard | Z | Problema, entrada → salida y alcance: alertas experimentales, sin sanciones | Diagrama de contexto de la propuesta |
| 2 | Arquitectura y contrato | J | M1–M6 y por qué el contrato de datos permite trabajar en paralelo | `tipos.py`, flujo de ARQUITECTURA |
| 3 | Detección y seguimiento | J | YOLOv8n, mapeo de clases, ByteTrack y oclusiones | Tests de M2; si alcanza, un clip con cajas e ID |
| 4 | Geometría y relaciones | R | Homografía, carril con confianza, cambio completo, THW y TTC, degradación sin calibración | Tests de M3 y de robustez |
| 5 | Reglas y puntaje | C | Máquinas de estado de RF7–RF9 y estado de M4 | Lo que haya de M4 |
| 6 | Datos y evaluación | Z | NGSIM como referencia, protocolo de §2.5 y F1 uno a uno | `m6_evaluacion`, 21 tests |
| 7 | Primer hallazgo | Z | Cercanía en el 43 % de los vehículos en congestión, y qué significa | Cifras de REGLAS_NEGOCIO |
| 8 | Propuestas | Z | Velocidad anómala (Solomon 1964) y puntaje por severidad (Minderhoud y Bovy 2001) | ADR-0002 y 0003 |
| 9 | Plan al 19-nov | Todos | Reparto, dependencias y riesgos | ROADMAP |

**Preguntas probables:**

- *¿Por qué no highD?* Por la regla de §4.4 de la propuesta (ADR-0001).
- *¿Cómo se validan las reglas sin anotar a mano?* Con la referencia sobre trayectorias limpias, degradándolas y midiendo F1.
- *¿Cómo llegan a 15 FPS?* Con YOLOv8n, región de interés y perfilado por etapa antes de tocar umbrales.
