# Glosario

| Término | Definición en RoadGuard | Fuente |
|---|---|---|
| **Causalidad** | En el cuadro `t` solo se usa información disponible hasta `t`; ningún cálculo mira cuadros futuros, tampoco el suavizado | Propuesta §1.3, RF5 |
| **`t`** | Segundos desde el inicio del video, derivados de los FPS reales. Las ventanas se evalúan sobre `t`, nunca sobre conteo de cuadros | `tipos.py` |
| **Punto de calzada** | Centro del borde inferior de la caja; es lo que se proyecta al camino | `tipos.Caja.punto_calzada` |
| **Homografía** | Transformación plana que lleva píxeles a metros sobre el camino (vista de pájaro). Requiere al menos 4 pares de puntos | RF4 |
| **Calibrado** | Hay homografía utilizable. Sin ella, distancia, THW y TTC quedan en `None` y las reglas que dependen de ellas se suspenden | Paso 5 |
| **Predecesor / seguidor** | Dentro de un carril, el vehículo inmediatamente adelante (mayor `x_camino`) y el que va detrás | RF6 |
| **Distancia** | Separación longitudinal entre los puntos de referencia de seguidor y predecesor, sin descontar largo de vehículo | `relaciones.py` |
| **THW** (*time headway*) | Distancia / velocidad del seguidor, en segundos. Cuánto tardaría el seguidor en llegar a donde está hoy el predecesor | RF6 |
| **TTC** (*time to collision*) | Distancia / tasa de cierre; solo existe si el seguidor es más rápido que el predecesor | RF6; FHWA SSAM |
| **Cambio completo de carril** | Cambio confirmado tras permanencia estable en el carril nuevo (1 s por defecto). Las oscilaciones sobre la línea no cuentan | Paso 4 |
| **`t_cruce` / `t_confirmacion`** | Primera observación en el carril nuevo y momento en que el cambio se confirma. La diferencia es la latencia de decisión | `tipos.CambioCarril` |
| **No disponible** | `None` en vez de un valor inventado: división inválida, historial insuficiente o falta de predecesor | Paso 3 |
| **Evento** | Una activación de regla con vehículo, intervalo, variables medidas, umbrales y aporte al puntaje | §2.5, `tipos.Evento` |
| **Evento de referencia** | Evento calculado fuera de línea sobre una trayectoria limpia (highD o NGSIM). Es el patrón contra el que se mide M4 | `m6_evaluacion/referencia.py` |
| **Trayectoria degradada** | Trayectoria limpia con ruido, pérdidas e intercambios de ID agregados para imitar lo que entrega la cámara | Propuesta §2.4 |
| **mAP@0.5** | Precisión media de detección con IoU ≥ 0,5 | §2.5 |
| **IDF1** | F1 de identidad del seguimiento: qué fracción de las detecciones lleva el ID correcto | §2.5; Ristani et al. 2016 |
| **Cambio de ID** (*ID switch*) | Un mismo vehículo real cambia de ID en el seguimiento | §2.5 |
| **F1 de reglas** | F1 entre eventos detectados y de referencia, emparejados por vehículo, regla y solape temporal | §2.5, `emparejamiento.py` |
| **TET / TIT** | *Time Exposed* y *Time Integrated* TTC: cuánto tiempo y cuánta severidad acumulada pasa un vehículo bajo un umbral | Minderhoud y Bovy 2001; ver [ADR-0003](../decisions/0003-puntaje-ponderado-por-severidad.md) |

## Fuentes

- Formulario de propuesta TEL-328, 2026-09-11. `Confirmada`.
- `src/roadguard/tipos.py` y `m3_geometria/relaciones.py`, al 2026-10-17. `Confirmada`.
- Ristani, E. et al. (2016). *Performance Measures and a Data Set for Multi-Target, Multi-Camera Tracking*. ECCV Workshops.
- Minderhoud, M. y Bovy, P. (2001). *Extended time-to-collision measures for road traffic safety assessment*. Accident Analysis & Prevention, 33(1), 89–97.
