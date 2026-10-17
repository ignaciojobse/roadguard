# Contexto

## El problema

Revisar video vial a mano exige atención sostenida, y localizar maniobras relevantes cuesta cuando hay muchos vehículos, oclusiones y perspectiva. Un detector entrega cajas por cuadro, pero no explica cómo evoluciona cada vehículo ni lo relaciona con quienes van delante o detrás. RoadGuard transforma una secuencia de video en indicadores temporales interpretables, sin atribuir intenciones, culpabilidad ni infracciones.

## Qué hace

Es un proceso por lotes: **video MP4 + configuración YAML → MP4 anotado + eventos CSV + resumen JSON**. Procesa video pregrabado de cámaras fijas en autopistas multicarril como si fuera una transmisión en vivo. En el cuadro `t` solo usa información disponible hasta `t`.

La cadena es la siguiente:

1. YOLOv8n detecta los vehículos y ByteTrack mantiene su identidad.
2. Una homografía lleva el punto de contacto con la calzada a metros sobre el camino.
3. Se asigna carril, se suaviza la trayectoria y se calcula predecesor, distancia, THW y TTC.
4. Tres reglas marcan cercanía peligrosa, zigzag y corte de carril, y un puntaje de 0 a 100 resume el riesgo ([REGLAS_NEGOCIO](./REGLAS_NEGOCIO.md)).

## Alcance

**Entra:** cámaras fijas calibradas o configuradas previamente, video pregrabado, vías de varios carriles y las tres conductas.

**No entra:** cámaras móviles, patentes, identificación de personas, seguimiento entre cámaras, sanciones automáticas, uso forense y cualquier afirmación sobre conducción temeraria o culpabilidad. Las alertas son **experimentales** y orientan la revisión humana. Los umbrales son parámetros, no límites legales.

## Criterios de aceptación (§2.5 de la propuesta)

| Criterio | Meta | Dataset | Dueño de la medición |
|---|---|---|---|
| Detección | mAP@0.5 ≥ 0,60 | UA-DETRAC | M6 |
| Seguimiento | IDF1 ≥ 0,60, con informe separado de cambios de ID | UA-DETRAC | M6 |
| Reglas | F1 ≥ 0,75, alertas sobre trayectorias degradadas contra eventos de referencia | highD o NGSIM | M6 |
| Rendimiento | ≥ 15 FPS a 720p en Colab T4; 25 FPS es extensión | — | M6 con M2 |
| Demo | End-to-end en al menos tres secuencias | UA-DETRAC | Integración |
| Robustez | Oclusiones, pérdida de ID, detenidos, sin predecesor, cambios incompletos, sin calibración | Tests | Cada módulo |
| Trazabilidad | Cada evento con vehículo, intervalo, regla, variables, umbrales y puntaje | — | M4 y M5 |

## El ramo

TEL-328 Procesamiento Digital de Imágenes, USM, segundo semestre de 2026. Docente: Nicolás Torres. El proyecto vale **45 % del ramo**: propuesta 5, avance 10, prototipo 20 y video 10. Las fechas están en [ROADMAP](../roadmap/ROADMAP.md).

## Fuentes

- Formulario de propuesta TEL-328, 2026-09-11, secciones 1 y 2. `Confirmada`.
- Reglas del curso TEL-328, 2026-08-24, pesos de evaluación. `Confirmada`.
