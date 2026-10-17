# Roadmap

> Entrada de la carpeta: [SEGUIMIENTO](./SEGUIMIENTO.md) (estado vivo) · [HISTORIAL](./HISTORIAL.md) (cierres).

## Hacia dónde

Llegar al **19-nov** con la cadena completa corriendo en vivo sobre tres secuencias, con las métricas de §2.5 medidas, sean buenas o malas, y con una explicación de por qué. El orden es: integrar temprano con datos reales, medir y después ajustar.

## Entregas del ramo

| Fecha | Entrega | Peso | Presencial |
|---|---|---|---|
| 2026-09-11 | Propuesta: formulario de inscripción | 5 % | — |
| **2026-10-21** | Avance: bitácora 1 | 5 % | — |
| **2026-10-22** | Avance: presentación en clases, sala K304 | 5 % | **Sí; no presentarse es nota 0** |
| 2026-11-18 | Prototipo: bitácora 2, manual de uso y código fuente | 5 % cada uno | — |
| **2026-11-19** | Prototipo: demostración en vivo | 5 % | **Sí; no presentarse es nota 0** |
| 2026-11-22 | Video demo | 10 % | — |

## Responsables

> Estado: `Candidata a validar`. Propuesta del 2026-10-17 para acordar en equipo antes del 21-oct.

**Por qué reajustar.** El reparto de la propuesta (§3.3) supuso que cada módulo lo hacía su responsable. En la práctica J construyó la base, M1, M2 y M3 en el PR #1. Eso deja a R sin su frente y a C con los tres módulos que faltan para que exista una demo (reglas, salidas e integración), que además son el camino crítico. La idea es que la carga **acumulada** al 19-nov quede pareja: quien ya hizo más tiene menos por delante.

| Frente | Propuesta (§3.3) | Reparto propuesto | Por qué |
|---|---|---|---|
| Datos y protocolo de evaluación | Z | **Z** | Atrasado. Esta entrega lo cierra para reglas (NGSIM); falta elegir las secuencias de UA-DETRAC |
| M2 Detección y seguimiento | J | **J** · hecho | — |
| M3 Geometría y trayectorias | R | **J** · hecho | J lo implementó junto con la base |
| Calibración de las 3 secuencias (YAML: región, carriles, homografía) | — (implícito en M3) | **R** | Es la parte de M3 que el código no resuelve: trabajo manual por cámara, y condición para cualquier demo con metros |
| M4 Reglas y puntaje | C | **C** | Se mantiene. Con NGSIM puede probar sobre trayectorias reales desde hoy |
| M5 Video anotado y registros | C | **R** | Le quita a C un módulo completo. R conoce la geometría para dibujar sobre el camino |
| Integración y CLI | C | **J** | Arma la tubería sobre su propia biblioteca, así que es corto para él |
| M6 Evaluación (mAP, IDF1, F1 de reglas, degradación) | Z | **Z** | Se mantiene |
| Optimización de FPS | Z | **J** con Z | Perfilar M2 es terreno de J; Z mide |
| Extensiones (ADR-0002 y 0003), si se aceptan | — | **Z** | Las propuso Z; C solo las registra en M4 |

**Entregas compartidas.** Cada una con un responsable que la arma y todos aportando su sección:

| Entrega | Arma | Aportan |
|---|---|---|
| Bitácora 1 (21-oct) | Z | Todos, con su sección |
| Presentación de avance (22-oct) | Z arma las láminas | Cada uno presenta su frente |
| Bitácora 2 (18-nov) | C | Todos |
| Manual de uso (18-nov) | R | J con la CLI |
| Código fuente (18-nov) | J | Todos |
| Demo en vivo (19-nov) | J | Todos |
| Video demo (22-nov) | Z | Todos |

## Dependencias

```text
Datos NGSIM (Z) ─────────────► M4 reglas (C) ──► F1 de reglas (Z)
Calibración YAML (R) ──► Integración (J) ──► M5 salidas (R) ──► Demo 19-nov
UA-DETRAC secuencias (Z) ──► mAP e IDF1 (Z) ──► Optimización FPS (J)
```

El cuello de botella es la calibración: sin YAML con homografía no hay metros, sin metros no hay reglas sobre video, y sin reglas sobre video no hay demo.

## Fuentes

- Formulario de propuesta TEL-328, §3.3. `Confirmada`.
- Reglas del curso TEL-328, 2026-08-24. `Confirmada`.
- PR #1 en `ignaciojobse/roadguard`, mergeado el 2026-10-17. `Confirmada`.
