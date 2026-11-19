# Calibracion de camaras

La calibracion generica recibe mediciones externas de puntos de imagen y sus
posiciones conocidas sobre la via. No detecta marcas ni estima distancias a
partir del video. El eje `x` longitudinal debe apuntar en el sentido de avance
del trafico; `y` es lateral, en metros. El RMSE de reproyeccion solo describe
el ajuste a los puntos proporcionados y no es una medida de precision global.

Este flujo esta orientado a camaras fijas y tramos aproximadamente planos y rectos, con carriles del mismo sentido. No configura automaticamente dashcams, cambios de zoom ni intersecciones complejas.

## Preparar la definicion

Usa este esquema en un YAML:

```yaml
camara:
  nombre: camara_nueva
  descripcion: Camara fija, orientacion y condiciones conocidas.
  resolucion_referencia: [1920, 1080]
procesamiento_geometria:
  compensar_camara: false
  metodo_apoyo: centro_inferior
clases: [automovil, bus, camion, motocicleta]
calibracion:
  lineas:
    - puntos_imagen: [[u1, v1], [u2, v2]]
      posiciones: [0, 6]
      lateral: 0
    - puntos_imagen: [[u3, v3], [u4, v4]]
      posiciones: [0, 6]
      lateral: 3.5
  bordes_carriles: [-3.5, 0, 3.5, 7]
  tramo_longitudinal: [-20, 30]
```

Incluye al menos dos lineas y dos puntos por linea. Los puntos y posiciones
de cada linea deben corresponderse, las posiciones y bordes laterales deben
ser crecientes y las medidas deben ser finitas. `procesamiento_geometria` y
`clases` son opcionales; se aplican los defaults del procesador y las cuatro
clases vehiculares habituales.

Los valores de 6 m y 3,5 m del esquema son ilustrativos, no medidas universales. Reemplazalos por referencias justificadas de la vista que se esta calibrando.

## Validar y procesar

Genera un perfil validado, sin umbrales especificos de camara:

```bash
python scripts/calibrar_camara.py \
    --entrada configs/calibraciones/MVI_39271_lineas.yaml \
    --salida configs/MVI_39271_nuevo.yaml
```

La salida existente no se reemplaza salvo que se solicite expresamente con
`--sobrescribir`. La herramienta calcula carriles y region de interes, valida
el perfil completo mediante M1 y construye el proyector real antes de escribir.
Por ejemplo, para una definicion nueva, copia el esquema anterior y cambia
nombre, resolucion y mediciones segun datos obtenidos externamente.

Valida el perfil contra el video antes de procesarlo. `validar` no ejecuta
deteccion ni escribe salidas:

```bash
python -m roadguard validar --video ruta/al/video.mp4 \
    --config configs/MVI_39271_nuevo.yaml \
    --politica configs/politicas/propuesta.yaml
```

Sin `--politica`, se usan los umbrales del perfil legacy, o los defaults
generales de `Umbrales()` si el perfil no los define. Con `--politica`, el
conjunto completo del perfil se reemplaza: las claves omitidas en la politica
reciben los defaults de `Umbrales()`. Esa politica no mezcla con umbrales
legacy omitidos.

Procesa el video usando el perfil:

```bash
python -m roadguard procesar --video ruta/al/video.mp4 \
    --config configs/MVI_39271_nuevo.yaml --salida salidas/camara_nueva \
    --politica configs/politicas/propuesta.yaml
```

Usa la misma politica al validar y procesar. Puedes omitir `--politica` en ambos comandos para usar los umbrales del perfil o los defaults generales.

Un perfil de calibracion completo contiene `camara`, `region_interes`,
`carriles`, `homografia` y `clases`; puede incluir tambien
`procesamiento_geometria`. La region de interes es la region FINAL de analisis
y se deriva del tramo longitudinal y los bordes exteriores indicados. La
envolvente de las cajas se usa solo como filtro preliminar conservador: los
tracks fuera de ROI permanecen neutrales, sin metricas. Los carriles finales
son poligonos proyectados desde esos bordes. Comprueba visualmente que ROI,
carriles y sentido coincidan con la escena, y registra que mediciones son
confirmadas o candidatas; los datos no evaluables deben quedar explicitados,
no inferidos del RMSE.

El perfil declara una resolucion de referencia. RoadGuard no autoescala la
geometria: una resolucion distinta o un cambio de encuadre requiere revisar y
volver a calibrar. `--politica` reemplaza el conjunto completo de umbrales;
las claves omitidas toman los defaults de `Umbrales()`. Los flags de
procesamiento geometrico (`--compensar-camara`,
`--sin-compensar-camara`, `--punto-apoyo`) prevalecen sobre los valores del
perfil. Los perfiles legacy siguen siendo compatibles.

`configs/calibraciones/MVI_39271_lineas.yaml` conserva las mediciones
existentes de la demo. `scripts/calibrar_ua_detrac.py` permanece como
herramienta legacy para reproducir las configuraciones de demo y conserva las
opciones geometricas del perfil existente; no es el flujo para calibrar nuevas
camaras. La herramienta generica es el flujo para nuevas definiciones.
MVI_39271 se proceso con video real y apoyo longitudinal (1570 cuadros, 3 RF7,
0 RF8 y 2 RF9); esto no valida globalmente la calibracion ni su precision.
La segunda vista solo cuenta con pruebas sinteticas.
