# Cómo correr la demo de RoadGuard

Guía para quien presente la demo en vivo. No hace falta saber cómo está hecho el sistema: basta con seguir los pasos en orden. Probado en macOS con Python 3.12.

## Qué es la demo

Una página en el navegador que reproduce una corrida real de RoadGuard sobre los cuadros originales del video y enciende, paso a paso, lo que hace cada etapa: cuadro, detección, seguimiento, metros y carriles, reglas y riesgo, y resultado. Tiene cinco cámaras y funciona **sin internet** una vez instalada.

## 1. Preparar el computador (una vez, con internet)

Desde una terminal:

```bash
git clone https://github.com/ignaciojobse/roadguard.git
cd roadguard
git checkout demo-interactiva-final
```

Si ya tienes el repositorio:

```bash
cd roadguard
git fetch origin
git checkout demo-interactiva-final
git pull
```

Crea el entorno de Python e instala lo necesario. En Mac el comando es `python3`, no `python`:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .
```

Baja los cuadros de las cinco cámaras. Son unos 680 MB y tarda unos minutos; si se corta, vuelve a correrlo y sigue donde quedó:

```bash
.venv/bin/python scripts/bajar_ua_detrac.py MVI_39271 MVI_40243 MVI_40712 MVI_40714 MVI_40742
```

Los datos de cada corrida ya vienen en el repositorio (`demo_web/datos/`), así que **no hace falta correr el modelo** para la demo.

## 2. Abrir la demo

```bash
bash scripts/demo_web.sh
```

Se abre el navegador en `http://127.0.0.1:8000/demo_web/`. Si el puerto 8000 está ocupado, el script usa el siguiente libre y muestra la dirección en la terminal.

- **No cierres esa terminal mientras presentas:** es el servidor de la demo.
- **Para cerrarla:** Ctrl+C en esa terminal.
- **Ábrela antes de empezar** y déjala en el paso 1 de la cámara Día.

## 3. Cómo se usa

| Tecla o acción | Qué hace |
|---|---|
| Espacio | Reproduce o pausa |
| 1 a 6 | Cambia de paso (cada paso agrega una capa) |
| Flecha derecha o izquierda | Avanza o retrocede un cuadro (con Shift, un segundo) |
| f | Pantalla completa |
| Clic en una caja o en la vista de pájaro | Selecciona el vehículo y muestra su ficha y su puntaje en el tiempo |
| Clic en un evento de la línea de tiempo | Salta a ese momento y selecciona el vehículo |
| Botones de arriba | Cambian de cámara |
| Esc | Quita la selección |

## 4. Orden sugerido (unos 6 minutos)

| Cámara | Qué hacer | Qué decir |
|---|---|---|
| **Día** | Paso 1 y reproducir 3 s | Esto es lo que ve una persona: un cuadro con su tiempo |
| Día | Paso 2 | YOLOv8n encuentra cada vehículo con su clase |
| Día | Paso 3 | ByteTrack le da a cada uno un número estable; la estela es su recorrido |
| Día | Paso 4 | La homografía lo lleva a metros: carril, velocidad en km/h y la vista de pájaro |
| Día | Paso 5, ir al segundo 8 (Shift + flecha) y reproducir | La línea amarilla es la separación con el de adelante: el auto 4 va a 0,5 s; a los 10 s se confirma la cercanía y su caja pasa a amarillo |
| Día | Paso 6, clic en el corte del bus en la línea de tiempo (cerca de los 44 s) y clic en el bus | El bus sale del paradero y se mete delante de otro: el sistema lo marca y su ficha muestra el puntaje. Es una maniobra real, no agresiva: por eso son alertas para revisión humana |
| Día | Clic en el corte del auto 37 y reproducir hasta los 48,6 s | Cercanía más corte: 90 puntos, rojo |
| **Autopista** | Paso 5, ir al segundo 27 y reproducir | Otra cámara, calibrada igual desde sus trazos: autos a 65 km/h. El auto 43 va a 1,3 s del 41 y a los 29,2 s se confirma la cercanía |
| **Semáforo** | Paso 6, clic en el zigzag (47 s) | El auto 23 cambia dos veces de carril en 3,4 s: zigzag. Coincide con la anotación hecha a mano |
| **Cola densa** | Paso 5 | Todos a 0 km/h: no hay alertas, porque la cercanía exige más de 5 m/s. Un taco no es conducción riesgosa |
| **Noche** | Paso 4 | No hay escala en el pavimento: el sistema avisa, no inventa metros y suspende cercanía y corte. Sigue detectando, siguiendo y evaluando zigzag |

Los números de vehículo y los segundos son **los mismos en cualquier computador**: la página usa la corrida guardada, no vuelve a procesar el video.

## 5. Si algo falla

| Problema | Solución |
|---|---|
| `command not found: python` | En Mac se usa `python3` o, mejor, `.venv/bin/python` |
| `Address already in use` | Ya hay una demo abierta: usa esa pestaña, o cierra la otra con Ctrl+C. El script nuevo elige otro puerto solo |
| Una cámara se ve en negro y dice «Faltan los cuadros» | Correr el `bajar_ua_detrac.py` del paso 1 para esa cámara |
| `No module named roadguard` (solo en la corrida por terminal) | Anteponer `PYTHONPATH=src` al comando |
| Windows, sin `bash` | Desde la raíz del repo: `.venv\Scripts\python -m http.server 8000` y abrir `http://127.0.0.1:8000/demo_web/` |
| El navegador no anda | Plan B: la corrida por terminal (sección 6) y el video anotado |

## 6. Opcional: mostrar que el sistema corre de verdad

La demo del navegador reproduce una corrida guardada. Para mostrar el sistema procesando en vivo hace falta, además, el video y los pesos del modelo (una vez, con internet):

```bash
.venv/bin/python scripts/jpg_a_mp4.py MVI_39271
mkdir -p datos/modelos
curl -L -o datos/modelos/yolov8n.pt https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt
```

Y en la presentación:

```bash
bash scripts/demo_en_vivo.sh
```

Corre el chequeo, los tests y procesa MVI_39271 completa (unos 25 s con GPU). Se puede cortar con Ctrl+C a los pocos segundos: igual escribe las salidas.

## Más detalle

- Guion de la presentación, con lo que se dice en cada lámina y las preguntas probables: `knowledge/projects/entregas/guion-presentacion.pdf`.
- Guion operativo de la demo y cifras para responder preguntas: `knowledge/projects/entregas/demo-en-vivo.md`.
- Cómo funciona el sistema por dentro: `README.md`.
