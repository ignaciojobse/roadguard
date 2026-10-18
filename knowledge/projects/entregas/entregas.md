# Entregas del ramo — índice

> Las piezas que se evalúan además del código. Fechas y responsables en [ROADMAP](../../roadmap/ROADMAP.md#entregas-del-ramo); el estado, en [SEGUIMIENTO](../../roadmap/SEGUIMIENTO.md).

## Documentos

- [Bitácora 1](./bitacora-1.md): fuente en Markdown para el 21-oct, con exportación a [DOCX](./bitacora-1.docx) y [PDF](./bitacora-1.pdf).
- [Presentación de avance](./presentacion-avance.md): guion y notas de orador para el 22-oct. Preview del deck: https://decks-umbra-git-roadguard-avance-franciscozunigaps-projects.vercel.app/roadguard-avance
- [Mensajes al grupo y al profe](./mensajes-grupo.md): borradores sin enviar.
- [Marca](./marca/MARCA.md): logo, paleta, tipografía y reglas de lenguaje.

## Cómo regenerar un entregable

El Markdown es la fuente. Cuando cambia, se vuelve a exportar:

```bash
pip install python-docx   # una vez
python knowledge/projects/entregas/exportar_entregable.py knowledge/projects/entregas/bitacora-1.md
```

El comando deja `bitacora-1.docx` y `bitacora-1.pdf` junto al Markdown. El PDF se imprime con Chrome headless; si Chrome no está en la ruta estándar de macOS, se indica con `CHROME=/ruta/al/binario`. Los comentarios HTML (`<!-- -->`) son notas internas y no se exportan. LibreOffice no se usa porque en este equipo se cuelga en modo headless.

## Decisiones abiertas

- El formato exigido para las bitácoras (plantilla de Aula, extensión). **Dueño:** Z.
- La duración de la presentación de avance. **Dueño:** Z.
