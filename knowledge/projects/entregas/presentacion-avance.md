# Presentación de avance — guion

> **Deck:** `decks/roadguard-avance/` en el repo de decks de Pancho ([PR dreamxist/decks#1](https://github.com/dreamxist/decks/pull/1)), con PDF de respaldo `roadguard-avance.pdf`. Se avanza con flechas o espacio; `F` activa la pantalla completa. Las láminas 2 a 5 llevan una marca `[revisar: …]` para su dueño.
>
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

## Notas de orador (láminas de Z)

Cada cifra sale del knowledge o del PR #2. Si alguien pregunta por un número que no está aquí, la respuesta honesta es «no lo hemos medido todavía».

**1 · Qué es RoadGuard.** RoadGuard toma un video de una cámara fija y su configuración, y entrega el video anotado, los eventos en CSV y un resumen por vehículo. Procesa el video como si fuera en vivo: en cada instante solo usa lo que ya pasó. Las alertas son experimentales y sirven para orientar una revisión humana; no lee patentes ni identifica personas, y no sanciona. Somos cuatro, cada uno con un frente, y les vamos a contar en qué está cada uno.

**6 · Datos y evaluación.** Para validar reglas sin anotar a mano usamos trayectorias reales de NGSIM: 60 s de la autopista US-101 a 10 Hz, con 270 vehículos y 53 cambios de carril completos. Las convertimos al mismo formato que produce nuestro módulo de geometría, y THW, TTC y cambio de carril se calculan con las mismas funciones del sistema, para que la comparación sea justa. Sobre eso calculamos eventos de referencia, y el F1 empareja uno a uno con una tolerancia de ±1 s. Para detección y seguimiento ya elegimos tres secuencias de UA-DETRAC: una base de día, una densa con oclusiones y una de noche. Hoy son 78 tests: 57 de la base y 21 de evaluación.

**7 · Primer hallazgo.** Con las reglas tal como las inscribimos, cercanía peligrosa se activa en 115 de 270 vehículos: el 43 %. Es tráfico congestionado, con velocidad mediana de 12,2 m/s y THW mediano de 1,92 s, y en esas condiciones ir a menos de 1,5 s del de adelante es lo normal. No concluimos que la regla esté mal, porque falta medir en flujo libre; lo que sí muestra es que un puntaje fijo no distingue entre congestión y riesgo.

**8 · Propuestas.** Traemos dos extensiones para que usted las valide. La primera es un cuarto patrón, velocidad anómala respecto del flujo del carril, que se apoya en Solomon (1964): el riesgo crece cuando un vehículo se desvía de la velocidad del tráfico, en ambos sentidos. La segunda es un modo de puntaje por severidad, basado en las medidas TET y TIT de Minderhoud y Bovy (2001): distingue un THW de 1,4 s de uno de 0,4 s y nunca pasa de 100. RF10 se mantiene como modo por defecto; ninguna de las dos se implementa sin su visto bueno.

**9 · Plan al 19-nov.** El reparto se ajustó a lo que ya está construido, para que la carga total quede pareja. Los hitos son: YAML calibrados el 26-oct, integración y M4 el 1-nov, código congelado el 8-nov y métricas de §2.5 el 12-nov, antes de la demo del 19. El cuello de botella es la calibración: sin metros no hay reglas sobre video. Y declaramos un desvío: M4 cierra una semana después de lo inscrito.

### Respuestas preparadas

- **¿Por qué NGSIM y no highD?** La propuesta fijaba en §4.4 que, si highD no estaba disponible el 21-sep, se usaba NGSIM. NGSIM es público y tiene posiciones, velocidades y carriles cada 0,1 s.
- **¿NGSIM no tiene ruido?** Sí, está documentado (Coifman y Li, 2017). Por eso la referencia usa velocidad y no aceleración, y por eso no proponemos frenado brusco como patrón.
- **¿UA-DETRAC es autopista?** No: son avenidas urbanas multicarril de Beijing y Tianjin. Calza con «vías multicarril» de la propuesta, y lo declaramos como límite.
- **¿Cómo van a llegar a 15 FPS?** Con YOLOv8n, recortando la región de interés y midiendo cada etapa por separado antes de tocar umbrales.
- **¿Qué pasa si una cámara no se puede calibrar?** Detección y seguimiento siguen funcionando, las métricas en metros quedan como no disponibles y aparece una advertencia. Nunca se inventa un valor.
