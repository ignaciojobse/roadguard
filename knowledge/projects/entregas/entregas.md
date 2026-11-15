# Entregas del ramo — índice

> Las piezas que se evalúan además del código. Fechas y responsables en [ROADMAP](../../roadmap/ROADMAP.md#entregas-del-ramo); el estado, en [SEGUIMIENTO](../../roadmap/SEGUIMIENTO.md).

## Documentos

- [Bitácora 1](./bitacora-1.md): fuente en Markdown para el 21-oct, con exportación a [DOCX](./bitacora-1.docx) y [PDF](./bitacora-1.pdf).
- [Manual de uso](./manual-de-uso.md): instalación, configuración YAML, calibración, ejecución y lectura de salidas del prototipo, para el 18-nov, con exportación a [DOCX](./manual-de-uso.docx) y [PDF](./manual-de-uso.pdf). Lo que depende de la CLI final está marcado con comentarios «verificar con la CLI final».
- [Bitácora 2](./bitacora-2.md): borrador para el 18-nov, período 22-oct a 18-nov, con anexo de métricas de §2.5 y desvíos respecto del plan. Las filas de J, R y C están marcadas `[revisar]`; se exporta igual que la bitácora 1.
- [Demo en vivo](./demo-en-vivo.md): guion operativo del 19-nov, chequeo previo con `scripts/demo_en_vivo.sh`, plan B y cifras para responder preguntas.
- [Video demo](./video-demo.md): guion por escenas con voz en off, lista de capturas del 19-nov y plan de producción para el 22-nov.
- [Presentación de avance](./presentacion-avance.md): guion y notas de orador para el 22-oct. Preview del deck: https://decks-umbra-git-roadguard-avance-franciscozunigaps-projects.vercel.app/roadguard-avance
- [Mensajes al grupo y al profe](./mensajes-grupo.md): borradores sin enviar.
- [Marca](./marca/MARCA.md): logo, paleta, tipografía y reglas de lenguaje.

## Cómo regenerar un entregable

El Markdown es la fuente. Cuando cambia, se vuelve a exportar:

```bash
pip install python-docx   # una vez
python knowledge/projects/entregas/exportar_entregable.py knowledge/projects/entregas/bitacora-1.md
```

El comando deja `bitacora-1.docx` y `bitacora-1.pdf` junto al Markdown. El PDF se imprime con Chrome headless; si Chrome no está en la ruta estándar de macOS, se indica con `CHROME=/ruta/al/binario`. Los comentarios HTML (`<!-- -->`) son notas internas y no se exportan; los bloques de código cercados (```) se exportan en monoespaciada. LibreOffice no se usa porque en este equipo se cuelga en modo headless.

## Decisiones abiertas

- El formato exigido para las bitácoras (plantilla de Aula, extensión). **Dueño:** Z.
- La duración de la presentación de avance. **Dueño:** Z.
