# Reglas de negocio

> Las reglas que el sistema implementa, con su fuente y su estado. Los valores por defecto viven en `tipos.Umbrales` y en `configs/camara_ejemplo.yaml`. Si este documento y el código difieren, manda el código y este documento se corrige.

## Reglas inscritas

| Regla | Condición | Parámetros | Estado |
|---|---|---|---|
| **RF7 · Cercanía peligrosa** | El seguidor va a más de 5 m/s y mantiene THW < 1,5 s durante al menos 2 s | `cercania_velocidad_min`, `cercania_thw_max`, `cercania_persistencia` | `Confirmada` |
| **RF8 · Zigzag** | Dos o más cambios **completos** de carril en 10 s; los cruces breves y las oscilaciones no cuentan | `zigzag_cambios_min`, `zigzag_ventana`, `permanencia_cambio_carril` | `Confirmada` |
| **RF9 · Corte de carril** | Dentro de 2 s tras un cambio, el nuevo seguidor queda con THW < 1,5 s o TTC < 3 s | `corte_ventana_post_cambio`, `corte_thw_max`, `corte_ttc_max` | `Confirmada` |
| **RF10 · Puntaje** | Suma 40 por cercanía activa, 35 por zigzag reciente y 50 por corte reciente; tope 100; cada aporte caduca a los 5 s | `aporte_*`, `puntaje_maximo`, `vigencia_aporte` | `Confirmada` |
| **RF11 · Bandas** | Verde 0–29, amarillo 30–59, rojo 60–100 | `banda_verde_max`, `banda_amarillo_max` | `Confirmada` |

## Invariantes transversales

- **Sin calibración no hay métricas de distancia.** Distancia, THW y TTC quedan en `None` y RF7 y RF9 se suspenden; detección, seguimiento y una advertencia visible se mantienen (Paso 5).
- **TTC solo con cierre positivo.** Si el seguidor no es más rápido que el predecesor, TTC no existe (RF6).
- **Trazabilidad.** Cada evento lleva vehículo, intervalo, regla, variables medidas, umbrales vigentes y aporte (§2.5).
- **Lenguaje.** Ningún texto, columna o rótulo afirma conducción temeraria, culpabilidad ni infracción (§1.1 y §1.2).

## Lo que mostró la primera medición

Sobre 60 s de NGSIM US-101 (270 vehículos, velocidad mediana 12,2 m/s, THW mediano 1,92 s), la referencia calculada con estas reglas marca **cercanía en 115 vehículos (43 %)**, corte en 19 y zigzag en 7. En tráfico congestionado, un THW bajo 1,5 s es lo normal, no la excepción. RF7 tal como está escrita no separa el riesgo de la congestión. Esto no invalida la regla, pero hay que discutirlo al calibrar umbrales y es el argumento de [ADR-0003](../decisions/0003-puntaje-ponderado-por-severidad.md). `Brecha`: falta medir en flujo libre antes de concluir.

## Extensiones propuestas

| Propuesta | Estado | Documento |
|---|---|---|
| Patrón de velocidad anómala respecto del flujo del carril | `Candidata a validar` | [ADR-0002](../decisions/0002-patron-velocidad-anomala.md) |
| Puntaje ponderado por severidad (TET/TIT) con decaimiento continuo | `Candidata a validar` | [ADR-0003](../decisions/0003-puntaje-ponderado-por-severidad.md) |

No se implementan hasta que el equipo y el docente las acepten.

## Fuentes

- Formulario de propuesta TEL-328, 2026-09-11, §2.1, §2.5 y §4.3. `Confirmada`.
- Medición propia con `m6_evaluacion.referencia` sobre NGSIM US-101, `global_time` 1118847300000–1118847360000, 2026-10-17. Reproducible con el comando de [datos-y-evaluacion](../projects/datos-y-evaluacion/datos-y-evaluacion.md).
