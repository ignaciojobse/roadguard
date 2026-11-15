# Demo en vivo · jueves 19-nov

> Guion operativo de la demostración del prototipo (5 %, presencial obligatoria). La corre **J** en su notebook; cada uno presenta su frente ([ROADMAP, corte 4](../../roadmap/ROADMAP.md#corte-4--prototipo-18-19-y-22-de-noviembre)). Lo que se graba para el video está en [video-demo](./video-demo.md#qué-grabar-el-jueves-19-durante-o-después-de-la-demo-en-vivo).
>
> Ensayada de punta a punta el 2026-11-15 en el notebook de J (Apple M4, MPS): 238 tests pasan y MVI_39271 corre completa a 63–69 FPS, con 5 cercanías, 2 zigzag y 1 corte, los mismos eventos que la corrida de Z.

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
| 0:00 | J | Terminal con `bash scripts/demo_en_vivo.sh` corriendo: primero el chequeo y los 238 tests | Qué es RoadGuard en una frase: video de cámara fija más su configuración entrega video anotado, eventos y resumen por vehículo, para orientar la revisión humana. Las alertas son experimentales |
| 0:45 | J | La CLI procesando MVI_39271: 1.570 cuadros en unos 25 s | Los seis módulos en cadena, causal cuadro a cuadro. Corre a más del doble del tiempo real del video (25 FPS) |
| 1:30 | R | `configs/MVI_39271.yaml` y `evidencia/MVI_40714/calibracion.png` | Calibración desde las líneas del pavimento: homografía, RMSE 0,14 m; carriles; por qué MVI_40742 va sin calibración |
| 3:00 | C | `anotado.mp4` que abre el script; pausa en 10 s (auto 4 pasa a amarillo, 40) y en 49 s (bus 30 en rojo, 85) | Las tres reglas y el puntaje: cercanía (THW < 1,5 s durante 2 s), zigzag (2 cambios en 10 s), corte (THW < 1,5 s tras el cambio); aportes 40/35/50 que caducan a los 5 s; bandas verde, amarillo y rojo |
| 4:30 | C | La tabla de eventos que imprime el script y `resumen.json` | Cada evento con su intervalo, variables medidas y umbrales vigentes: trazable |
| 5:15 | J | `bash scripts/demo_en_vivo.sh MVI_40742` (o el respaldo) | Sin calibración el sistema no inventa metros: franja «SIN CALIBRACION», cercanía y corte suspendidos, detección y seguimiento siguen |
| 6:15 | Z | Anexo de métricas de la bitácora 2 | mAP@0.5 0,918 e IDF1 0,898 en la región de interés de MVI_39271; FPS; qué no se midió (F1 de reglas) y por qué |
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
| ¿Los eventos son correctos? | No hay referencia de eventos en UA-DETRAC; los 8 de MVI_39271 se revisan a mano. El corte y un zigzag del bus 30 son una maniobra real de salida del paradero, no conducción agresiva: es un hallazgo para los umbrales | `salidas/demo/MVI_39271/eventos.csv` |
| ¿Por qué a 720p hay 7 cercanías y no 5? | El video escalado cambia levemente las cajas de YOLO y con ellas el THW cerca del umbral. Zigzag y corte no cambian | `evidencia/rendimiento/perfil_720p_m4_mps.json` |
| ¿Identifica personas o patentes? | No. Solo clase de vehículo, posición y trayectoria. No sanciona ni determina responsabilidades | README |
