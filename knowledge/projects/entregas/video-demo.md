# Video demo: guion y plan de producción

> Entrega del 2026-11-22 (10 %, la más pesada del proyecto). Arma y edita Z; cada integrante graba su segmento. Meta: entre 3 y 5 minutos. Estado al 2026-11-15: **borrador**. La escena 4 tiene dos versiones porque al 15-nov no existen en `main` las reglas RF8 a RF11 ni la integración; el jueves 19 se decide cuál se graba.

## Reglas que manda la marca

Todo lo que se oye y se lee en el video sigue [MARCA](./marca/MARCA.md):

- Las alertas son **experimentales** y orientan la **revisión humana**. Se dice así cada vez que aparece una alerta.
- Se habla de **patrones potencialmente riesgosos**, **eventos** y **puntaje de riesgo**.
- No se usa «infracción», «culpable», «temerario», «sanción», «responsable», «conducción temeraria» ni «multa», en voz, rótulo, columna ni título.
- Los umbrales son **parámetros configurables**, nunca límites legales.
- Fondo `#0B0F14`, texto `#F2F5F8`, un solo acento `#4C9AFF`, Space Grotesk. Verde, amarillo y rojo aparecen solo como bandas del puntaje, siempre con el número al lado.
- El símbolo del escudo va como marca de agua en la esquina inferior derecha de toda toma de pantalla; el logo completo solo en portada y cierre.
- Español de Chile neutro: sin modismos, tuteo evitado, voz en off en primera persona plural («medimos», «lo que falta»).

## Guion por escenas

Duración objetivo: 4 min 20 s. Si se corta algo, se corta la escena 3 a 20 s y la 5 a 30 s; nunca la 6.

| # | Tiempo | Qué se ve en pantalla | Voz en off (texto listo para leer) | Quién graba | Material que hace falta |
|---|---|---|---|---|---|
| 1 | 0:00 a 0:25 | Portada 3 s con logo sobre fondo oscuro. Corte a un cuadro fijo de MVI_39271 sin anotar, luego un mosaico de las 3 secuencias (día, densa, noche) sin cajas. Rótulo: «Una cámara fija. Miles de vehículos por hora. Una persona mirando.» | Las autopistas y avenidas de varias pistas están llenas de cámaras fijas. Grabar es barato; mirar, no. Hoy, cuando alguien quiere saber si en esa calzada hubo maniobras de riesgo, una persona tiene que revisar horas de video, cuadro por cuadro. La mayor parte de ese tiempo no pasa nada. | Z (montaje) | 3 cuadros de referencia de UA-DETRAC (`datos/ua-detrac/referencia/*.jpg`, 960×540); logo SVG |
| 2 | 0:25 a 0:45 | El mismo cuadro de MVI_39271, ahora anotado: cajas, ID, clase y carril. Rótulo con la frase del producto. | RoadGuard toma el video de una cámara fija y su configuración, y entrega tres cosas: el video anotado, una lista de eventos y un resumen por vehículo. Marca patrones potencialmente riesgosos para que una persona revise solo esos tramos. Las alertas son experimentales: orientan la revisión humana, no la reemplazan, y el sistema no lee patentes ni identifica personas. | Z (montaje); el cuadro anotado lo genera J o R con `m5_salidas` | 1 cuadro anotado de MVI_39271 en PNG |
| 3 | 0:45 a 1:15 | Diagrama de M1 a M6 en una lámina con el estilo del deck: seis cajas encadenadas; cada una se ilumina con el acento cuando se nombra. Debajo, los nombres de paquete en monoespaciada. | Son seis módulos en cadena. Ingesta lee el video y la configuración de la cámara. Detección y seguimiento encuentra cada vehículo con YOLOv8 nano y lo sigue con ByteTrack, conservando su identidad aunque otro lo tape un momento. Geometría proyecta cada posición al plano del camino con una homografía: ahí aparecen los metros, la pista, la velocidad, y el tiempo y la distancia al vehículo de adelante. Reglas evalúa tres patrones sobre ese estado y calcula un puntaje de riesgo por vehículo. Salidas dibuja y exporta. Y evaluación mide cada etapa contra datos públicos. Todo es causal: en cada instante el sistema solo usa lo que ya pasó, como si el video fuera en vivo. | J graba la voz de este tramo si quiere; Z arma la lámina | Lámina del flujo (reusar la lámina 2 del deck de avance), exportada a 1920×1080 |
| 4A | 1:15 a 2:45 | **Versión completa** (solo si el 19-nov corre la cadena end-to-end con RF7 a RF11). Pantalla dividida: a la izquierda el MP4 anotado de MVI_39271 corriendo; a la derecha la terminal con el comando y el CSV de eventos creciendo. Se detienen tres momentos con zoom: (1) un vehículo cuyo rótulo pasa a amarillo cuando se confirma cercanía, (2) un cambio de pista doble que marca zigzag, (3) un corte donde el rótulo salta a rojo. Rótulos sobreimpresos: «Cercanía · THW 1,1 s durante 2,3 s · aporte 40», «Zigzag · 2 cambios completos en 8 s · aporte 35», «Corte · THW 0,9 s a 1,4 s del cambio · aporte 50». Al final, el JSON por vehículo. | Esta es la secuencia base: una avenida de tres pistas, de día, con un paradero de buses que genera cambios de pista reales. Cada vehículo lleva su identificador, su clase y su pista. El color del rótulo es su puntaje de riesgo: verde hasta 29, amarillo hasta 59, rojo desde 60, y el número siempre va junto al color. Aquí, el vehículo doce lleva más de dos segundos a menos de un segundo y medio del de adelante: cercanía, cuarenta puntos, amarillo. Más adelante, este otro cambia de pista dos veces en menos de diez segundos: zigzag, treinta y cinco puntos. Y acá, uno se mete delante de otro y lo deja a menos de un segundo y medio: corte de pista, cincuenta puntos, el rótulo pasa a rojo. Cada aporte caduca a los cinco segundos, así que el puntaje baja solo cuando el patrón deja de ocurrir. Todos los umbrales son parámetros del archivo de configuración, no límites legales. Cada evento queda en el CSV con el vehículo, el intervalo, las variables medidas y los umbrales vigentes, para que quien revise pueda ir directo a ese tramo y decidir. | J corre y captura; C explica reglas en voz si se prefiere | Video de MVI_39271 en MP4 a 25 FPS; YAML calibrado; comando end-to-end; grabación de pantalla a 1080p con audio del sistema apagado |
| 4B | 1:15 a 2:30 | **Versión parcial** (si el 19-nov no hay integración completa). Izquierda: el MP4 anotado con cajas, ID, clase y pista sobre MVI_39271, generado con `m5_salidas`, con la franja de advertencia visible en un clip sin calibrar. Derecha: la terminal corriendo `python scripts/demo_cercania.py`, con zoom a la cronología («t=1.9 s sin alerta confirmada, t=2.0 s activa») y al evento con sus variables y umbrales. Cierra con una tarjeta: «Zigzag, corte y puntaje: en desarrollo. No se muestran resultados que no existen.» | Esta es la secuencia base, de día, con tres pistas. Cada vehículo lleva su identificador, su clase y su pista, y cuando la cámara no está calibrada el video lo dice arriba, en una franja: sin metros no hay reglas, y el sistema nunca inventa un valor. La primera regla, cercanía, ya funciona sobre el estado que entrega geometría: exige ir a más de cinco metros por segundo y a menos de un segundo y medio del de adelante, durante al menos dos segundos seguidos. En esta corrida sintética se ve la confirmación exacta a los dos segundos, y cómo una interrupción reinicia la cuenta. El evento queda registrado con el intervalo, la velocidad, el tiempo al vehículo de adelante y los umbrales vigentes. Las otras dos reglas, zigzag y corte de pista, y el puntaje por bandas de color están diseñados y tienen su contrato de datos, pero no están integrados todavía; preferimos mostrar lo que corre y decir lo que falta. | J o R generan el MP4 anotado; C graba la terminal de RF7 | MP4 anotado de MVI_39271 (o de los cuadros que haya); grabación de la terminal a 1080p |
| 5 | 2:45 a 3:30 | Imagen de verificación de la calibración: cuadro de MVI_39271 con la rejilla métrica, los polígonos de pista y los puntos usados (`datos/ua-detrac/calibracion/MVI_39271.png`). Zoom a los trazos de la línea discontinua con las cotas «6 m» y «9 m». Luego el YAML en pantalla con las líneas de RMSE y «60 km/h» resaltadas. | Para pasar de píxeles a metros no medimos nada en terreno. Usamos lo que ya está pintado en el pavimento: las líneas discontinuas tienen una norma, seis metros de trazo y nueve de hueco, y las pistas miden tres metros y medio. Con los extremos de esos trazos en varios cuadros se calcula la homografía. El error de reproyección es de catorce centímetros, y como control cruzado, un auto real del video da sesenta kilómetros por hora, que es lo esperable en esa avenida. Esto se hizo para la primera cámara; en las otras dos los vehículos tapan las líneas en los cuadros disponibles, y cuando una cámara no se puede calibrar el sistema sigue detectando y siguiendo, pero deja las métricas de distancia como no disponibles y lo avisa. | R graba la pantalla y la voz | PNG de verificación de la calibración; `configs/MVI_39271.yaml` abierto en un editor con fondo oscuro, fuente a 20 pt o más |
| 6 | 3:30 a 4:15 | Tabla de §2.5 en una lámina: criterio, meta, medido. Las celdas medidas se rellenan con el valor real; las no medidas dicen «no medido» en texto secundario, no en rojo. Debajo, una línea: «170 tests pasan · 1 de 3 cámaras calibradas · referencia NGSIM 60 s, 270 vehículos». | Lo que sí medimos y lo que no. La suite tiene ciento setenta pruebas y todas pasan. La referencia de reglas sale de sesenta segundos de trayectorias reales de la autopista US-101, doscientos setenta vehículos, y ahí la regla de cercanía tal como está inscrita marca al cuarenta y tres por ciento de los autos, porque en congestión ir a menos de un segundo y medio es lo normal: un puntaje fijo no distingue congestión de riesgo, y eso motiva una propuesta de puntaje por severidad. `[pendiente: medir]` Precisión de detección, identidad en el seguimiento, F1 de reglas y cuadros por segundo: `[si se midieron, acá va cada valor con su dataset; si no, se lee:]` no alcanzamos a medirlos en las secuencias elegidas y no vamos a presentar números que no tenemos. El procedimiento de cada métrica está escrito y es reproducible. Dos límites más: las secuencias son avenidas urbanas, no autopistas, así que las velocidades son bajas y una de ellas casi no activa reglas; y el ancho de pista viene de una norma, no de una medición, así que toda la escala lateral hereda esa incertidumbre. | Z graba la voz y arma la lámina | Valores del anexo de métricas de la [bitácora 2](./bitacora-2.md) al 21-nov |
| 7 | 4:15 a 4:40 | Los cuatro en una toma, o cuatro recuadros con nombre y frente debajo (J detección, seguimiento e integración; R geometría, calibración y salidas; C reglas y puntaje; Z datos y evaluación). Cierra con logo, «RoadGuard · TEL-328 · UTFSM · 2026» y la línea «Alertas experimentales para orientar la revisión humana». | Somos cuatro. Ignacio hizo la base, la detección, el seguimiento y la integración. Giancarlos, la geometría, la calibración de la cámara y las salidas. Francisco Castillo, las reglas y el puntaje. Y yo, los datos y la evaluación. RoadGuard es un prototipo de apoyo a la revisión humana, y así queremos que se use. | Todos; la toma grupal el jueves 19 en la sala, o cada uno un clip de 5 s con el teléfono en horizontal | Toma grupal o 4 clips verticales de 5 s; logo completo |

## Qué grabar el jueves 19, durante o después de la demo en vivo

Grabación de pantalla a 1920×1080 (o la resolución nativa del notebook, en proporción 16:9), 30 FPS, sin notificaciones, terminal con fondo oscuro y fuente de 18 pt o más. Cada clip con 3 s de margen antes y después. Nombrar los archivos `19nov-<escena>-<descripción>.mp4`.

- [ ] **Escena 4A o 4B, el corazón del video.** El comando completo corriendo sobre MVI_39271 de principio a fin, sin cortes, aunque dure 2 minutos. De ahí se sacan los tres momentos con zoom. Responsable: J.
- [ ] El MP4 anotado reproducido a pantalla completa, 20 s por lo menos, con pista y rótulos legibles. Responsable: J o R.
- [ ] Si existe el puntaje: 10 s donde un rótulo cambia de color, grabados dos veces (plano general y zoom). Responsable: J con C.
- [ ] Si existe el CSV: `head -20` del archivo de eventos en la terminal y el JSON de un vehículo con `cat`, cada uno 8 s quietos. Responsable: C.
- [ ] Un clip de 10 s de una secuencia **sin calibrar** (MVI_40742 o MVI_40714) con la franja de advertencia visible, para la escena 5. Responsable: R.
- [ ] La demo sintética de RF7: `python scripts/demo_cercania.py` completa, 15 s, con la terminal limpia antes de correrla. Responsable: C.
- [ ] `python -m pytest -q` corriendo hasta la línea final `N passed`. Responsable: J.
- [ ] La toma grupal de la escena 7 en la sala, con luz de frente, 10 s mirando a cámara sin hablar. Responsable: Z con el teléfono de alguien en horizontal.
- [ ] Si el docente hace una pregunta útil para la escena 6 (límites), anotarla al salir; no se graba la clase.

## Qué se puede grabar antes del jueves

Mismas reglas de pantalla. Se pueden grabar desde el 16-nov y ya quedan listos para el montaje.

- [ ] Escena 5: `configs/MVI_39271.yaml` abierto, scroll lento desde el encabezado hasta `carriles`, 25 s. Responsable: R.
- [ ] Escena 5: generar y capturar la imagen de verificación de la calibración con `python scripts/calibrar_ua_detrac.py` (requiere los cuadros en `datos/ua-detrac/cuadros/MVI_39271/`). PNG a resolución nativa. Responsable: R.
- [ ] Escena 3: código de `tipos.py`, de `Evento` a `ResumenEjecucion`, scroll lento 15 s, para ilustrar el contrato de datos. Responsable: J.
- [ ] Escena 3: `m4_reglas/cercania.py`, la función que confirma la persistencia, 10 s quietos. Responsable: C.
- [ ] Escena 6: `python -c` o cuaderno que carga NGSIM y cuenta eventos de referencia por regla (el comando de `datos-y-evaluacion.md`), 20 s. Responsable: Z.
- [ ] Escenas 1 y 2: los 3 cuadros de referencia de UA-DETRAC y un cuadro anotado de MVI_39271 en PNG. Responsable: Z (cuadros), J o R (anotado).
- [ ] Escena 3 y 6: láminas exportadas a 1920×1080 desde el deck de avance, con el estilo de la marca. Responsable: Z.
- [ ] Voces en off de las escenas 1, 2, 3, 6 y 7 (Z) y la escena 5 (R): grabar en un cuarto cerrado, teléfono a 20 cm de la boca, cada párrafo tres veces, enviar sin comprimir. Si una escena cambia el jueves, se regraba solo esa.

## Plan de producción

| Cuándo | Qué | Quién |
|---|---|---|
| Lun 16 a mié 18 | Grabar lo de la lista «antes del jueves»; Z arma láminas 1, 3, 6 y 7 y la plantilla de rótulos | R, J, C, Z |
| Jue 19 | Demo en vivo. Al salir, grabar la lista del jueves con el mismo notebook de la demo. Decidir 4A o 4B | Todos |
| Vie 20 | Montaje completo con las voces que haya; primer corte compartido al grupo por la noche | Z |
| Sáb 21 | Correcciones del equipo hasta las 18:00: cada uno revisa su escena y las palabras prohibidas. Z cierra el anexo de métricas de la bitácora 2 con los mismos números del video | Todos, Z |
| Dom 22 | Exportar H.264 1080p, 30 FPS, audio AAC estéreo normalizado a -16 LUFS; subir y entregar antes de las 20:00 | Z |

Formato: 16:9, 1920×1080. Marca de agua con el símbolo al 60 % de opacidad en toda toma de pantalla. Subtítulos en español quemados en la parte baja, porque el video puede verse sin audio; se generan desde el guion, no por transcripción automática. Música solo en portada y cierre, sin voz encima; en las escenas con voz, nada de fondo.

## Lista de control antes de exportar

- [ ] Ningún rótulo, subtítulo ni voz usa las palabras prohibidas de MARCA. Buscar en los subtítulos: «infracci», «culpa», «temerari», «sanci», «responsab», «multa».
- [ ] Cada alerta que aparece en pantalla va acompañada, en voz o rótulo, de «experimental» o «revisión humana» al menos una vez por escena.
- [ ] Los colores verde, amarillo y rojo aparecen solo junto a un puntaje numérico.
- [ ] Las cifras de la escena 6 coinciden con el anexo de métricas de la bitácora 2 y con lo que se dijo en la demo del 19. Lo no medido se dice como no medido.
- [ ] Duración entre 3:00 y 5:00.
- [ ] Los nombres de los cuatro integrantes y el ramo aparecen en el cierre.
- [ ] No aparece ninguna patente legible ni rostro reconocible en primer plano; si UA-DETRAC muestra alguno, se difumina.

## Decisiones abiertas

- **4A o 4B.** Se decide el jueves 19 a la salida de la demo, según lo que haya corrido. Dueño: J con Z.
- **Quién pone la voz de la escena 4.** C para las reglas o Z como narrador único. Dueño: C.
- **Formato de entrega** (enlace a YouTube no listado, archivo en Aula, o ambos). Depende de lo que pida la pauta. Dueño: Z.

## Fuentes

- [MARCA](./marca/MARCA.md), [bitácora 2](./bitacora-2.md), [presentación de avance](./presentacion-avance.md) (láminas y respuestas preparadas), [REGLAS_NEGOCIO](../../domain/REGLAS_NEGOCIO.md), [PRD de datos y evaluación](../datos-y-evaluacion/PRD.md) §7, ROADMAP «Corte 4».
