# ADR-0002 — Cuarto patrón: velocidad anómala respecto del flujo

> Estado: `proposed` · Fecha: 2026-10-17 · Requiere: acuerdo del equipo y visto bueno del docente, porque amplía el alcance inscrito.

## Contexto

La propuesta inscribe tres conductas, y las tres dependen de la relación con un vehículo cercano (THW, TTC o cambios de carril). Ninguna mira al vehículo respecto del flujo en que circula, y esa es una de las relaciones más estudiadas entre velocidad y siniestralidad. Se busca un cuarto patrón que use datos que el sistema ya produce, que tenga respaldo bibliográfico y que no necesite un límite legal de velocidad, porque RoadGuard no sanciona.

## Decisión propuesta

Agregamos el patrón **velocidad anómala**. Se marca cuando un vehículo se desvía de la velocidad mediana de su carril en ese instante más que un umbral, de forma sostenida.

```text
CUANDO en el cuadro t el carril tiene al menos `anomala_vecinos_min` vehículos calibrados con velocidad
  SI el vehículo no tiene velocidad o el carril no alcanza el mínimo
    NO se evalúa (no disponible, Paso 3)
  ENTONCES desviacion = v − mediana(v del carril en t)
           activa si |desviacion| > `anomala_desviacion_min` durante ≥ `anomala_persistencia`
Promesas: causal (solo usa el cuadro t); suspendida sin calibración (Paso 5)
```

Valores iniciales, `Candidata a validar` hasta calibrarlos con NGSIM: `anomala_desviacion_min = 8 m/s`, `anomala_vecinos_min = 3` y `anomala_persistencia = 2 s`.

**Por qué este patrón.** Solomon (1964) y después Cirillo (1968) observaron que la tasa de accidentes crece con la desviación respecto de la velocidad media del tráfico, en ambos sentidos: tanto el que va mucho más rápido como el que va mucho más lento. La forma exacta de esa curva fue cuestionada después (Hauer, 2009), así que la usamos como fundamento del indicador, no como estimación de riesgo. El patrón usa solo `EstadoCinematico.velocidad`, que M3 ya entrega.

**Contrato de datos.** Es un cambio aditivo: un miembro nuevo `Regla.VELOCIDAD_ANOMALA` y tres campos nuevos en `Umbrales`. No renombra ni quita nada.

**Dueño.** Z implementa la regla como función pura con sus tests y su evento de referencia en M6; C solo la registra en el motor. Así no se carga más a M4.

## Alternativas consideradas

- **A — Frenado brusco:** desaceleración bajo −3,4 m/s², el valor de diseño del AASHTO Green Book para distancia de detención. Exige derivar dos veces la posición, y tanto la cámara como NGSIM (Coifman y Li, 2017) dan aceleraciones muy ruidosas. Queda como candidata si el suavizado causal de M3 resulta suficiente.
- **B — DRAC** (*deceleration rate to avoid crash*): requiere predecesor y, en la práctica, duplica lo que ya mide RF9 con TTC.
- **C — Umbral por desviación estándar** (z robusto con MAD): se adapta mejor a cada carril, pero es inestable con pocos vehículos por carril. Queda como variante a medir contra el umbral absoluto.

## Consecuencias

- Agrega una conducta que no depende de la interacción con un vecino y funciona también con tráfico ralo, siempre que haya `anomala_vecinos_min` vehículos.
- Hay que decidir su aporte al puntaje ([ADR-0003](./0003-puntaje-ponderado-por-severidad.md)).
- Suma trabajo al F1 de reglas: un cuarto tipo de evento en referencia y en emparejamiento.

## Pendientes y no verificado

- Calibrar el umbral con la distribución de desviaciones en NGSIM antes de fijarlo.
- **No verificado:** si el docente acepta ampliar a cuatro conductas. Se plantea en la presentación de avance del 22-oct.

## Referencias

- Solomon, D. (1964). *Accidents on Main Rural Highways Related to Speed, Driver, and Vehicle*. U.S. Bureau of Public Roads.
- Cirillo, J. A. (1968). *Interstate System Accident Research Study II, Interim Report II*. Public Roads, 35(3).
- Hauer, E. (2009). *Speed and Safety*. Transportation Research Record, 2103, 10–17.
- AASHTO (2018). *A Policy on Geometric Design of Highways and Streets* (Green Book), 7.ª ed., distancia de detención.
