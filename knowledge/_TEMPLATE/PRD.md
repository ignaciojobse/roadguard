Estándar · prd · 2026-09-25

# PRD — <Proyecto>

> **Dueño de la decisión:** <persona o equipo> · **Apetito:** <tiempo o nivel de inversión> · **Alcance:** <una frase>
>
> **Estado →** [SEGUIMIENTO](../roadmap/SEGUIMIENTO.md). El estado de ejecución no vive en este documento.

## 1. Resumen

**Hoy:** <qué pasa hoy y qué costo genera>.

**Después:** <qué podrá lograr el usuario y por qué será mejor>.

## 2. Historia

### Antes

<Actor real o arquetipo validado>, en <momento concreto>, intenta <objetivo>. Hoy <fricción, riesgo o trabajo manual>.

### Después

<Mismo actor>, en ese momento, puede <resultado observable> sin <intervención o riesgo que se elimina>.

## 3. Objetivos y no-objetivos

- **O1 —** <resultado verificable>
- **O2 —** <resultado verificable>
- **NO1 —** <límite explícito que frena el «ya que estamos»>

## 4. Flujo: hoy → después

```text
HOY
<actor> → <paso actual> → <fricción o resultado insuficiente>

DESPUÉS
<actor> → <disparador> → <paso nuevo> → <resultado observable>
```

## 5. Datos y reglas de negocio

| Entidad o dato | Cambio | Invariante o procedencia |
| --- | --- | --- |
| `<entidad>` | <qué se crea, lee o cambia> | <lo que nunca se viola, o su fuente> |

## 6. Contrato de comportamiento

```text
CUANDO <disparador>
  SI <guarda que lo detiene>
    NO <resultado>
  ENTONCES <resultado observable>

Promesas: <lo que siempre se cumple>
```

## 7. Alcance

### Entra

- <capacidad>

### No entra

- <exclusión explícita>

## 8. Milestones

| Corte | Resultado verificable |
| --- | --- |
| <mes> | <qué queda funcionando y cómo se demuestra> |

El avance vive en SEGUIMIENTO. Acá solo va qué promete cada corte.

## 9. Criterios de aceptación

- [ ] <resultado verificable desde la perspectiva del actor>
- [ ] <caso de error, seguridad o no-visibilidad, cuando corresponda>

## 10. Riesgos y decisiones abiertas

| Tema | Impacto | Qué falta decidir o validar | Responsable |
| --- | --- | --- | --- |
| `<tema>` | alto / medio / bajo | <pregunta concreta> | <persona o rol> |

## Fuentes

- <reunión, entrevista, regla de negocio, ADR o documento de origen>
