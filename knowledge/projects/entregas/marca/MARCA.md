# Marca RoadGuard

> Marca mínima para las entregas del ramo: láminas, video y manual. Es coherente con el toolkit de decks (Space Grotesk, fondo oscuro, un acento).

## Logo

| Pieza | Archivo | Uso |
|---|---|---|
| Logo completo | [roadguard-logo.svg](./roadguard-logo.svg) | Portada, cierre y cabecera del manual |
| Símbolo | [roadguard-simbolo.svg](./roadguard-simbolo.svg) | Esquina de las láminas, favicon y marca de agua del video |

El símbolo es un escudo con una línea de carril discontinua: vigilancia del camino, sin connotación policial. Siempre va sobre fondo oscuro, sin deformarlo ni recolorearlo, y con un margen libre de al menos media altura del símbolo.

## Paleta

| Rol | Hex | Contraste sobre fondo | Uso |
|---|---|---|---|
| Fondo | `#0B0F14` | — | Fondo general (asfalto de noche) |
| Superficie | `#141B24` | — | Tarjetas, tablas y láminas alternas |
| Texto | `#F2F5F8` | 17,6 : 1 | Títulos y texto principal |
| Texto secundario | `#9AA6B2` | 7,8 : 1 | Subtítulos, notas y fuentes |
| Acento | `#4C9AFF` | 6,8 : 1 | Marca, énfasis y enlaces. **Es el único acento** |

### Colores de riesgo (RF11)

Son colores **semánticos**: se usan solo para mostrar las bandas de riesgo del puntaje, nunca como decoración.

| Banda | Puntaje | Hex | Contraste sobre fondo |
|---|---|---|---|
| Verde | 0–29 | `#34C27A` | 8,4 : 1 |
| Amarillo | 30–59 | `#F2C230` | 11,5 : 1 |
| Rojo | 60–100 | `#FF6B6B` | 6,9 : 1 |

Todos los pares de la paleta cumplen WCAG AA para texto (≥ 4,5 : 1) sobre el fondo y la superficie, que está al menos en 6,0 : 1. Sobre video, el color va siempre acompañado del número del puntaje, para no depender solo del color.

## Tipografía

- **Space Grotesk** (Google Fonts) en todo: 700 para títulos, 500 para cifras grandes y 400 para texto.
- Monoespaciada del sistema (`ui-monospace`) solo para código, rutas y nombres de módulos.
- En sala, los títulos van a 56 px o más y el texto a 28 px o más, con un máximo de unas 25 palabras de texto corrido por lámina.

## Lenguaje

- Las alertas son **experimentales** y orientan la **revisión humana**. Siempre se dice así.
- Se habla de **patrones potencialmente riesgosos**, **eventos** y **puntaje de riesgo**.
- **Nunca** se usa «infracción», «culpable», «temerario», «sanción» ni «responsable», en ningún texto, rótulo, columna o voz del video (propuesta §1.1 y §1.2).
- Los umbrales son **parámetros configurables**, no límites legales.

## Fuentes

- Propuesta TEL-328, §1.1, §1.2 y RF11.
- Toolkit de decks de Francisco Zúñiga (`shared/css/base.css`, Space Grotesk).
