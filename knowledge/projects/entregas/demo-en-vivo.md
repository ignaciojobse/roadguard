# Demo en vivo · jueves 19-nov

> Guion operativo de la demostración del prototipo (5 %, presencial obligatoria). La corre **J** en su notebook; cada uno presenta su frente ([ROADMAP, corte 4](../../roadmap/ROADMAP.md#corte-4--prototipo-18-19-y-22-de-noviembre)). Lo que se graba para el video está en [video-demo](./video-demo.md#qué-grabar-el-jueves-19-durante-o-después-de-la-demo-en-vivo).
>
> Ensayada de punta a punta el 2026-11-15 en el notebook de J (Apple M4, MPS): 238 tests pasan y MVI_39271 corre completa a 63–69 FPS, con 5 cercanías, 2 zigzag y 1 corte, los mismos eventos que la corrida de Z.
>
> **Actualización del 18-nov:** con los ajustes de reglas de ese día (tolerancia de 1,5 s en RF7 y confianza de carril 0,3, en los YAML) MVI_39271 da **10 cercanías, 1 zigzag y 3 cortes**, MVI_40714 ninguno y MVI_40742 1 zigzag; 268 tests pasan. Corrida de referencia en `evidencia/reglas/corridas/`. **J tiene que repetir el ensayo del miércoles con `git pull`**: los ID de los vehículos pueden variar entre máquinas, así que se confirman los momentos de pausa en su `eventos.csv`.

## Demo interactiva en el navegador (18-nov)

Es la demo principal. Muestra el trabajo de punta a punta sobre los cuadros originales, una etapa a la vez, y la puede manejar cualquiera del grupo. El flujo anterior por terminal queda como respaldo.

```bash
bash scripts/demo_web.sh
```

Abre `http://127.0.0.1:8000/demo_web/` sin red: los cuadros (`datos/ua-detrac/`) y los datos de cada corrida (`demo_web/datos/*.json`, generados por `scripts/exportar_demo.py`) son locales. Los datos vienen de una corrida real con la configuración final, así que los eventos y los ID son los mismos en cualquier computador.

**Teclas:** espacio reproduce o pausa · `1` a `6` cambian de paso · flechas avanzan un cuadro (con Shift, un segundo) · `f` pantalla completa · Esc quita la selección. Clic en una caja o en la vista de pájaro selecciona el vehículo; clic en un evento de la línea de tiempo salta a él.

| Momento | Qué se hace | Qué se dice |
|---|---|---|
| 0:00 | (Opcional, 20 s) En la terminal, `bash scripts/demo_en_vivo.sh` y cortar con Ctrl+C a los pocos segundos | El sistema corre de verdad, a unos 60 cuadros por segundo; lo que sigue es esa misma corrida, explicada |
| 0:20 | Día (MVI_39271), **paso 1**, reproducir 3 s | Esto es lo que ve una persona: un cuadro con su tiempo |
| 0:40 | **Paso 2** | YOLOv8n encuentra cada vehículo con su clase |
| 1:00 | **Paso 3** | ByteTrack le da a cada uno un número estable; la estela es su recorrido |
| 1:20 | **Paso 4** | La homografía lo lleva a metros: carril, velocidad en km/h y la vista de pájaro |
| 2:00 | **Paso 5**, ir al segundo 8 (flechas con Shift) y reproducir | La línea amarilla es la separación con el de adelante: el auto 4 va a 0,5 s; a los 10 s se confirma la cercanía y su caja pasa a amarillo |
| 2:45 | **Paso 6**, clic en el corte del bus en la línea de tiempo (cerca de los 44 s) y clic en el bus | El bus sale del paradero y se mete delante de otro: el sistema lo marca y su ficha muestra el puntaje en el tiempo. Es una maniobra real, no agresiva: por eso son alertas para revisión humana |
| 3:30 | Clic en el corte del auto 37 (46 s) y reproducir hasta los 48,6 s | Cercanía más corte: 90 puntos, rojo |
| 3:50 | Cambiar a **Autopista** (MVI_40243), paso 5, ir al segundo 27 y reproducir | Otra cámara, calibrada igual desde sus trazos: autos a 65 km/h. El auto 43 va a 1,3 s del 41 y a los 29,2 s se confirma la cercanía. Son casos al límite del umbral de 1,5 s |
| 4:15 | Cambiar a **Semáforo** (MVI_40712), paso 6, clic en el zigzag (47 s) | El auto 23 hace dos cambios de carril en 3,4 s: zigzag. Coincide con lo que sale de la anotación hecha a mano |
| 4:00 | Cambiar a **Cola densa** (MVI_40714) | Todos a 0 km/h: no hay alertas, porque la cercanía exige más de 5 m/s. Un taco no es conducción riesgosa |
| 4:30 | Cambiar a **Noche, sin calibración** (MVI_40742), paso 4 | No hay escala en el pavimento: el sistema avisa, no inventa metros y suspende cercanía y corte; sigue detectando, siguiendo y evaluando zigzag |

**Si el navegador falla:** volver al flujo por terminal de más abajo (`bash scripts/demo_en_vivo.sh` y el `anotado.mp4`).

## Miércoles 18, antes de dormir

1. `git pull` en `main` y `bash scripts/demo_en_vivo.sh chequeo`: todo en `OK` (Python, dependencias, pesos en `datos/modelos/yolov8n.pt`, los 3 videos y sus YAML, dispositivo `mps`).
2. Correr la demo completa una vez (`bash scripts/demo_en_vivo.sh`) y dejar `salidas/demo/MVI_39271/` como **respaldo pregrabado**. Copiar además `salidas/tomas/` (clips y cuadros ya recortados) a un pendrive.
3. Notebook cargado, cargador en la mochila, adaptador HDMI o USB-C probado.

## En la sala, 10 minutos antes

- Modo No molestar activado, notificaciones y WhatsApp Web cerrados.
- Terminal en pantalla completa, fondo oscuro, fuente de 18 pt o más, carpeta del repo abierta.
- Pantalla en espejo, no extendida, para que lo que ve J sea lo que ve la sala.
- `bash scripts/demo_en_vivo.sh chequeo` una última vez. No hace falta red: los pesos están locales y `YOLO_OFFLINE=1`.

## Guion (unos 8 minutos)

| Min | Quién | Qué se muestra | Qué se dice |
|---|---|---|---|
| 0:00 | J | Terminal con `bash scripts/demo_en_vivo.sh` corriendo: primero el chequeo y los 268 tests | Qué es RoadGuard en una frase: video de cámara fija más su configuración entrega video anotado, eventos y resumen por vehículo, para orientar la revisión humana. Las alertas son experimentales |
| 0:45 | J | La CLI procesando MVI_39271: 1.570 cuadros en unos 25 s | Los seis módulos en cadena, causal cuadro a cuadro. Corre a más del doble del tiempo real del video (25 FPS) |
| 1:30 | R | `configs/MVI_39271.yaml` y `evidencia/MVI_40714/calibracion.png` | Calibración desde las líneas del pavimento: homografía, RMSE 0,14 m; carriles; por qué MVI_40742 va sin calibración |
| 3:00 | C | `anotado.mp4` que abre el script; pausa en 10 s (auto 4 pasa a amarillo, 40) y en 48,6 s (auto 37 en rojo, 90: cercanía más corte, justo antes de salir de cuadro; confirmar el ID en `eventos.csv`) | Las tres reglas y el puntaje: cercanía (THW < 1,5 s durante 2 s, tolerando oclusiones de hasta 1,5 s), zigzag (2 cambios en 10 s), corte (THW < 1,5 s tras el cambio); aportes 40/35/50 que caducan a los 5 s; bandas verde, amarillo y rojo |
| 4:30 | C | La tabla de eventos que imprime el script y `resumen.json` | Cada evento con su intervalo, variables medidas y umbrales vigentes: trazable |
| 5:15 | J | `bash scripts/demo_en_vivo.sh MVI_40742` (o el respaldo) | Sin calibración el sistema no inventa metros: franja «SIN CALIBRACION», cercanía y corte suspendidos, detección y seguimiento siguen |
| 6:15 | Z | Láminas de resultados | mAP@0.5 0,918 e IDF1 0,898 en la región de interés de MVI_39271; F1 de reglas 0,80 sobre NGSIM degradado y 0,65 sobre el video real; FPS; lo que falta (la T4) |
| 7:30 | Todos | — | Límites: buses cortados por el borde u ocluidos producen cambios de carril falsos; el ancho de carril es norma, no medición. Preguntas |

## Plan B

| Si pasa esto | Se hace esto |
|---|---|
| MPS falla o el notebook se pone lento | Volver a correr con CPU: `PYTHONPATH=src YOLO_OFFLINE=1 .venv/bin/python -m roadguard procesar --video datos/videos/MVI_39271.mp4 --config configs/MVI_39271.yaml --salida salidas/demo/cpu --pesos datos/modelos/yolov8n.pt --dispositivo cpu`. Va a unos 25 FPS a 720p y más rápido a 960×540 |
| Se pasa el tiempo con la corrida | Ctrl+C: igual quedan `eventos.csv` y `resumen.json` con lo procesado y `"completada": false`. Seguir con el respaldo |
| `No module named roadguard` | Usar el script, que fija `PYTHONPATH=src`; a mano, anteponer `PYTHONPATH=src` al comando. Pasa porque iCloud vuelve a ocultar los `.pth` del venv en el Escritorio |
| El proyector no toma el notebook | Mostrar desde el pendrive `salidas/tomas/` (clips de 20 s y 10 s y cuadros PNG) en el computador de la sala |
| Nada corre | Reproducir `salidas/demo/MVI_39271/anotado.mp4` pregrabado y abrir `eventos.csv`; decirlo explícitamente: «esto es la corrida de anoche» |

## Cifras para responder preguntas

| Pregunta probable | Respuesta | Fuente |
|---|---|---|
| ¿Cumple los 15 FPS a 720p? | En el notebook de J, a 1280×720: 65,6 FPS con MPS y 24,9 FPS solo con CPU. La detección se lleva el 73 % del tiempo (11,2 de 15,3 ms por cuadro). En la T4 de Colab: lo que dé `scripts/perfil_colab_t4.ipynb` | `evidencia/rendimiento/` |
| ¿Qué tan bien detecta y sigue? | MVI_39271, región de interés: mAP@0.5 0,918, IDF1 0,898, 8 cambios de ID. La cola densa (MVI_40714) es la más difícil: mAP 0,592 | [bitácora 2, anexo](./bitacora-2.md#anexo-de-métricas-25) |
| ¿Los eventos son correctos? | Se midió de dos formas. Sobre NGSIM, con los errores de nuestra cámara: F1 0,80 (meta 0,75). Sobre MVI_39271, contra los eventos que salen de las cajas anotadas a mano: F1 0,65, con los 3 cortes correctos; son 17 eventos, poca muestra. El corte del bus es su salida del paradero: maniobra real, no agresiva | `evidencia/reglas/f1_ngsim.json` y `f1_video.json` |
| ¿Por qué cambiaron los eventos desde el 15-nov? | La evaluación mostró que una oclusión breve partía un episodio de cercanía en dos y que la confianza de carril de 0,6 dejaba pasar la mitad de los cambios. Se ajustaron los dos parámetros en el YAML después de medir: F1 de 0,54 a 0,80 en NGSIM y de 0,57 a 0,65 en video | Bitácora 2, hallazgos |
| ¿Por qué a 720p hay 7 cercanías y no 5? | El video escalado cambia levemente las cajas de YOLO y con ellas el THW cerca del umbral. Zigzag y corte no cambian | `evidencia/rendimiento/perfil_720p_m4_mps.json` |
| ¿Identifica personas o patentes? | No. Solo clase de vehículo, posición y trayectoria. No sanciona ni determina responsabilidades | README |
