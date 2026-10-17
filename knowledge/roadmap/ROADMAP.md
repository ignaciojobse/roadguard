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

## Plan por corte

> Estado: `Candidata a validar`, junto con el reparto. El avance de cada tarea se escribe en [SEGUIMIENTO](./SEGUIMIENTO.md), no acá.

Además de las entregas del ramo hay dos fechas internas:

| Fecha | Corte interno | Por qué |
|---|---|---|
| **2026-10-26** | YAML calibrados de las 3 secuencias | Es el cuello de botella: sin homografía no hay metros ni reglas sobre video |
| **2026-11-01** | Integración end-to-end | Es la fecha de término de la propuesta (§3.3) |
| **2026-11-08** | Código congelado | Del 9 al 19-nov la propuesta reserva el tiempo para informe y demo, y el 12-nov es el Control 3 de PDI para los cuatro |
| **2026-11-12** | Mediciones de §2.5 cerradas | Es la fecha de término de evaluación en la propuesta (§3.3) |

La última semana de octubre viene más corta para todos: el Taller 2 individual se publica el 23-oct y se entrega el 1-nov.

### Corte 1 · Avance (21 y 22 de octubre)

| Persona | Qué entrega | Qué presenta el 22 |
|---|---|---|
| J | Revisa y mergea el PR #2; su sección de la bitácora 1 | Arquitectura y contrato de datos; M2 detección y seguimiento |
| R | Su sección de la bitácora 1; arranca la calibración apenas estén elegidas las secuencias | M3 geometría, carriles, THW y TTC |
| C | Su sección de la bitácora 1; primer esqueleto de M4 sobre NGSIM | Diseño de las máquinas de estado de RF7–RF9 |
| Z | Bitácora 1 armada, láminas y elección de las 3 secuencias UA-DETRAC | Datos, protocolo, primer hallazgo y las propuestas ADR-0002 y 0003 |

Las secciones de la bitácora se mandan a Z a más tardar el **2026-10-20**.

### Corte 2 · Integración (hasta el 1 de noviembre)

| Persona | Qué deja listo | Depende de |
|---|---|---|
| R | YAML calibrado de las 3 secuencias **el 26-oct**; M5 dibuja cajas, ID y carril | Las secuencias (Z) |
| C | M4 completo: RF7–RF10 con tests, probado sobre NGSIM | — |
| J | CLI end-to-end: MP4 + YAML → tracks, estados y relaciones por cuadro, con M4 y M5 enchufados apenas existan | YAML (R) |
| Z | Degradación de trayectorias; primer F1 de M4 sobre NGSIM | M4 (C) |

### Corte 3 · Código congelado (8 de noviembre) y medición (hasta el 12 de noviembre)

| Persona | Hasta el 8-nov | Del 9 al 12-nov |
|---|---|---|
| R | M5 completo: alertas y colores de riesgo en el video, CSV de eventos y JSON por vehículo | Corrige lo que salga al medir |
| C | Umbrales ajustados con las mediciones de M6; extensiones enchufadas, si se aceptaron | Corrige lo que salga al medir |
| J | Pipeline estable en Colab T4 y perfilado por etapa | Optimiza si no llega a 15 FPS |
| Z | mAP e IDF1 sobre UA-DETRAC; extensiones como funciones puras, si se aceptaron | F1 de reglas, FPS y resultados de §2.5 |

Los resultados de §2.5 no son una entrega del ramo: son el insumo de la bitácora 2 y de lo que se presenta en la demo.

### Corte 4 · Prototipo (18, 19 y 22 de noviembre)

| Persona | 18-nov | 19-nov · demo en vivo | 22-nov · video |
|---|---|---|---|
| J | Código fuente entregable (limpieza y README) | Corre la demo | Aporta las tomas de la demo |
| R | Manual de uso: instalación, YAML y calibración | Geometría y calibración | Su segmento |
| C | Bitácora 2 armada | Reglas y puntaje | Su segmento |
| Z | Su sección de la bitácora 2 y el anexo de métricas | Resultados de §2.5 y sus límites | Arma y edita el video |

### Cómo cuadra con el ramo

| Entrega | Fecha | Peso | Corte | Responsable |
|---|---|---|---|---|
| Bitácora 1 | mié 2026-10-21 | 5 % | 1 | Z |
| Presentación de avance | jue 2026-10-22 | 5 % | 1 | Todos |
| Bitácora 2 | mié 2026-11-18 | 5 % | 4 | C |
| Manual de uso | mié 2026-11-18 | 5 % | 4 | R |
| Código fuente | mié 2026-11-18 | 5 % | 4 | J |
| Demo en vivo | jue 2026-11-19 | 5 % | 4 | Todos |
| Video demo | dom 2026-11-22 | 10 % | 4 | Z |

Con la propuesta (5 %) suman el 45 % del proyecto.

### Desvíos y pendientes respecto de lo inscrito

- **M4 se corre una semana.** La propuesta da a reglas y puntaje del 28-sep al 25-oct, y este plan lo cierra el 1-nov. Se declara en la bitácora 1 en vez de prometer el 25-oct, porque al 2026-10-17 M4 no ha empezado.
- **`Brecha`: cuáles son las cuatro entregas con `[∗]`.** Las reglas del curso dicen que no presentarlas es nota 0, pero no queda claro cuáles son. Las dos presenciales están cubiertas con los cuatro presentes. Se confirma con el docente el 22-oct.

## Dependencias

```text
Datos NGSIM (Z) ──────────────────────────► M4 reglas (C, 1-nov) ──► F1 de reglas (Z, 12-nov)
Secuencias (Z, 22-oct) ──► Calibración YAML (R, 26-oct) ──► Integración (J, 1-nov) ──► M5 salidas (R, 8-nov) ──► Demo 19-nov
Secuencias (Z, 22-oct) ──► mAP e IDF1 (Z, 8-nov) ──► Optimización FPS (J, 12-nov)
```

El cuello de botella es la calibración: sin YAML con homografía no hay metros, sin metros no hay reglas sobre video, y sin reglas sobre video no hay demo. El segundo riesgo es M4: si no está el 1-nov, el F1 de reglas se mide recién en la semana del Control 3.

## Fuentes

- Formulario de propuesta TEL-328, §3.3. `Confirmada`.
- Reglas del curso TEL-328, 2026-08-24, y calendario de entregas al 2026-10-17. `Confirmada`.
- PR #1 en `ignaciojobse/roadguard`, mergeado el 2026-10-17. `Confirmada`.
