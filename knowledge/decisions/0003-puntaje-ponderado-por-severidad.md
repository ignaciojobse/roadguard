# ADR-0003 — Puntaje ponderado por severidad

> Estado: `proposed` · Fecha: 2026-10-17 · Requiere: acuerdo del equipo y visto bueno del docente, porque cambia RF10.

## Contexto

RF10 suma aportes fijos: 40 por cercanía, 35 por zigzag y 50 por corte, con tope en 100 y retiro de cada aporte a los 5 s. Tiene tres limitaciones:

1. **No distingue severidad.** Un THW de 1,4 s y uno de 0,4 s aportan lo mismo.
2. **El tope trunca.** Dos eventos ya pueden pasar de 100, y desde ahí el puntaje deja de distinguir.
3. **El retiro es un escalón.** El riesgo cae de golpe a los 5 s, y eso se ve como parpadeo en el video.

La primera medición sobre NGSIM US-101 lo hace concreto: en congestión, RF7 marca al 43 % de los vehículos ([REGLAS_NEGOCIO](../domain/REGLAS_NEGOCIO.md#lo-que-mostró-la-primera-medición)). Con aportes fijos, casi la mitad del tráfico queda en la misma banda.

## Decisión propuesta

Agregamos un **modo de puntaje por severidad** y conservamos RF10 como modo por defecto. Así lo inscrito sigue intacto y en la demo se pueden comparar ambos.

**1. Severidad por evento, sᵢ ∈ [0, 1],** tomada de las medidas extendidas de TTC de Minderhoud y Bovy (2001). Su *Time Integrated TTC* (TIT) integra cuánto bajo el umbral estuvo el indicador durante todo el tiempo de exposición:

```text
cercanía:  s = min(1, ∫ (THW* − THW) dt / (THW* · T*))     THW* = cercania_thw_max, T* = cercania_persistencia
corte:     s = max(1 − THW_min / THW*, 1 − TTC_min / TTC*)   recortado a [0, 1]
zigzag:    s = 1                                              sin medida continua en la propuesta
```

**2. Combinación acotada.** Los aportes se combinan como probabilidades independientes, de modo que el resultado nunca pasa de 100 y cada evento extra suma cada vez menos:

```text
aᵢ(t) = wᵢ · sᵢ · exp(−(t − t_finᵢ) / τ)
R(t)  = 100 · (1 − Πᵢ (1 − aᵢ(t)))
```

**3. Pesos y decaimiento.** Los pesos parten de los de RF10 (w = 0,40 · 0,35 · 0,50), para no inventar valores. τ = 5 / ln 10 ≈ 2,2 s hace que a los 5 s quede el 10 % del aporte, y bajo el 5 % el aporte se retira. El cálculo es causal porque solo usa eventos ya cerrados en `t`.

**Contrato de datos.** Es aditivo: un campo `modo_puntaje` en `Umbrales` (`"suma"` por defecto, o `"severidad"`) y la severidad dentro de `Evento.variables`. `Evento.aporte_puntaje` y `PuntajeRiesgo` no cambian.

**Dueño.** Z escribe las funciones de severidad y combinación como módulo puro con sus tests; C las invoca desde M4.

## Alternativas consideradas

- **A — Dejar RF10 como está:** es lo inscrito y lo más simple de explicar, pero no resuelve la saturación en congestión.
- **B — Calibrar los pesos por regresión contra la severidad de referencia** (correlación entre el puntaje máximo y el TTC mínimo o el TIT de la trayectoria limpia): es el paso natural después de este ADR. No se propone ahora porque elegir el objetivo de la calibración es otra decisión.
- **C — Ponderar por clase de vehículo** (camión o bus pesan más): tiene sentido físico, pero la clasificación de M2 introduce error y no hay fuente que fije los factores.

## Consecuencias

- El puntaje distingue severidad y no se satura. Las bandas RF11 se mantienen.
- La trazabilidad mejora, porque el evento guarda su severidad además de la regla.
- Hay que explicar una fórmula más en el manual y en la demo.
- M6 gana una métrica adicional: la correlación entre el puntaje y la severidad de referencia.

## Pendientes y no verificado

- **No verificado:** si el docente acepta modificar RF10, aunque sea como modo opcional.
- Medir la distribución de bandas de los dos modos sobre la misma muestra de NGSIM antes de defenderlo.

## Referencias

- Minderhoud, M. y Bovy, P. (2001). *Extended time-to-collision measures for road traffic safety assessment*. Accident Analysis & Prevention, 33(1), 89–97.
- FHWA (2008). *Surrogate Safety Assessment Model (SSAM)*, FHWA-HRT-08-051. Referencia [5] de la propuesta.
- Formulario de propuesta TEL-328, RF10 y RF11.
