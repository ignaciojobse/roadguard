# Guion de la presentación del prototipo

RoadGuard · TEL-328 · Demostración en vivo del 19 de noviembre de 2026. Nueve láminas, unos 5 minutos y medio, más unos 6 minutos de demo interactiva.

## Regla para toda la presentación

- **Nunca decir** «infracción», «culpable», «temerario», «sanción» ni «responsable».
- **Sí decir** «patrón potencialmente riesgoso», «evento», «alerta experimental» y «revisión humana». Es una regla de la propuesta (§1.1).

## 1 · Portada (Francisco Zúñiga, 20 s)

### Qué decir

> Somos RoadGuard. En el avance de octubre les mostramos el diseño y módulos sueltos; hoy traemos el prototipo funcionando de punta a punta. Le entregamos el video de una cámara fija y su configuración, y nos devuelve el video anotado, una lista de eventos y un resumen por vehículo. Son alertas experimentales: sirven para que una persona revise solo los tramos que importan. No leemos patentes ni identificamos personas.

### Tener en cuenta

- No detenerse: 20 segundos bastan.
- Mencionar el avance da continuidad a la evaluación.

## 2 · Qué hicimos (Francisco Zúñiga, 45 s)

### Qué decir

> El problema: hay muchas cámaras fijas grabando calles, pero alguien tiene que mirar horas de video para encontrar una maniobra de riesgo. RoadGuard hace ese primer filtro. Recibe el video y la configuración de la cámara, y entrega el video anotado, la lista de eventos con las variables que los justifican y un resumen por vehículo. Lo probamos con datos públicos reales: tres secuencias de UA-DETRAC, que traen los vehículos anotados a mano, elegidas para cubrir un día normal, una cola densa con oclusiones y una de noche; y un minuto de NGSIM, una autopista de Estados Unidos con la trayectoria exacta de cada auto, para validar las reglas. Y tan importante como lo que hace: no identifica a nadie ni sanciona. Respecto del avance de octubre, pasamos de módulos sueltos, una cámara y una regla, a un sistema completo con tres reglas, tres cámaras y los siete criterios de la propuesta medidos.

### Tener en cuenta

- Es la lámina que da el contexto: no apurarla.
- **Por qué esas tres secuencias:** cubren las condiciones difíciles que pedía la propuesta (día, densidad con oclusiones y noche).
- **Por qué NGSIM:** es la única fuente pública con la posición exacta de cada auto, que es lo que hace falta para saber qué eventos deberían salir.

## 3 · Cómo funciona (Ignacio Jobse, 45 s)

### Qué decir

> Cada cuadro del video recorre seis pasos. Se lee con su tiempo exacto; YOLOv8n detecta los vehículos; ByteTrack les da un número que se mantiene mientras están en la escena; la geometría los ubica en metros, en su carril y calcula su velocidad y la separación con el de adelante; las reglas evalúan los tres patrones y el puntaje; y al final se dibuja el video y se escriben los archivos. Los seis módulos se comunican por un contrato de datos fijo, lo que nos dejó trabajar los cuatro en paralelo. Dos principios: es causal, en cada instante solo usa lo que ya pasó, como una cámara en vivo; y si no hay calibración, no inventa metros.

### Tener en cuenta

- Cada paso es un módulo que tiene su dueño en el equipo; se puede mencionar de pasada.
- **Causal** es una palabra clave: el sistema podría correr en vivo, no solo sobre videos grabados.

## 4 · Calibración (Giancarlos Ricci, 1 min)

### Qué decir

> Para evaluar conducta necesitamos metros, y la cámara solo da píxeles con perspectiva. No medimos nada en terreno: usamos lo que ya está pintado en el pavimento. Las líneas discontinuas tienen medidas de norma: trazos de 6 metros y huecos de 9, y entre dos líneas hay un carril de 3,5 metros. Marcamos los extremos de 8 trazos —son los puntos rojos— y con eso calculamos la homografía, que lleva cada píxel a metros vistos desde arriba. Esa es la rejilla celeste. El error es de 14 centímetros en esta secuencia y de 3 en MVI_40714. Como control independiente, un auto medido con esta calibración da 60 km/h, que es razonable para esa vía. La tercera secuencia es de noche, con buses tapando la calzada y sin trazos medibles, así que corre sin calibración: el sistema sigue detectando y siguiendo, pero no inventa distancias.

### Tener en cuenta

- **Señalar la imagen:** los puntos rojos son los 8 puntos usados; las líneas amarillas, los carriles.
- **El RMSE es un error de ajuste**, calculado sobre los mismos 8 puntos. Si preguntan cómo se sabe que la calibración está bien, la respuesta fuerte son los **60 km/h** y que la homografía predice bien los trazos lejanos que no se usaron.
- **Decir antes de que lo pregunten** que el ancho de carril de 3,5 m sale de una norma, no de una medición.

## 5 · Reglas y puntaje (Francisco Castillo, 45 s)

### Qué decir

> Sobre esos metros evaluamos tres patrones. Cercanía: ir a más de 5 m/s con menos de 1,5 segundos de separación con el de adelante, durante 2 segundos. Zigzag: dos cambios de carril completos en 10 segundos. Corte: después de cambiarse de carril, el auto que queda atrás queda a menos de 1,5 segundos o a menos de 3 segundos de chocar. Cada evento suma puntos al vehículo: 40, 35 o 50. Los puntos caducan a los 5 segundos, y el total pinta la caja de verde, amarillo o rojo. Todos los umbrales están en el YAML: son parámetros, no límites legales. Ahora lo vemos funcionando.

### Tener en cuenta

- **Explicar THW en una frase:** cuántos segundos tardarías en llegar a donde está el auto de adelante.
- **«Tolera oclusiones de 1,5 s»** es un cambio nuevo. Si preguntan, se explica en la lámina del F1.
- **Un cambio de carril solo cuenta si el auto se queda 1 segundo en el carril nuevo.** Por eso pisar la línea no dispara un zigzag.

## 6 · Demo en vivo (unos 6 minutos)

Se abre antes de empezar con `bash scripts/demo_web.sh`: una página en el navegador que reproduce una corrida real sobre los cuadros originales y enciende, paso a paso, lo que hace cada etapa. Funciona sin red.

### Orden

1. **(Opcional, 20 s) Terminal:** `bash scripts/demo_en_vivo.sh` y Ctrl+C a los pocos segundos, para mostrar que el sistema corre de verdad.
2. **Día (MVI_39271), paso 1:** reproducir 3 s. «Esto es lo que ve una persona».
3. **Paso 2:** cada vehículo detectado con su clase.
4. **Paso 3:** cada vehículo con su número y su estela.
5. **Paso 4:** carriles, rejilla métrica, velocidad en km/h y la vista de pájaro.
6. **Paso 5:** ir al segundo 8 y reproducir. La línea amarilla une al auto 4 con el de adelante (0,5 s); a los 10 s se confirma la cercanía y su caja pasa a amarillo.
7. **Paso 6:** clic en el corte del bus en la línea de tiempo (cerca de los 44 s) y clic en el bus para ver su ficha y su puntaje. Luego clic en el corte del auto 37 y reproducir hasta los 48,6 s: llega a rojo (90 puntos).
8. **Autopista (MVI_40243), paso 5:** ir al segundo 27. Autos a 65 km/h; el auto 43 va a 1,3 s del 41 y a los 29,2 s se confirma la cercanía. Es otra cámara, calibrada con el mismo método.
9. **Semáforo (MVI_40712), paso 6:** clic en el zigzag (47 s). El auto 23 cambia dos veces de carril en 3,4 s, igual que en la anotación hecha a mano.
10. **Cola densa (MVI_40714):** todos a 0 km/h y ninguna alerta, porque la cercanía exige más de 5 m/s.
11. **Noche, sin calibración (MVI_40742), paso 4:** el sistema avisa que no hay metros, suspende cercanía y corte, y sigue funcionando.

### Teclas

- **Espacio** reproduce o pausa; **1 a 6** cambian de paso; **flechas** avanzan un cuadro (con Shift, un segundo); **f** pantalla completa.
- **Clic** en una caja o en la vista de pájaro selecciona el vehículo; clic en un evento de la línea de tiempo salta a él.

### Tener en cuenta

- **Abrir la página antes de empezar** y dejarla en el paso 1 de la secuencia de día.
- **Los ID y los momentos son los mismos en cualquier computador**: la página usa los datos de la corrida guardada, no vuelve a procesar.
- **Ir despacio en los pasos 4 y 5:** son los que más explican el trabajo de PDI (la homografía y el THW).
- **Plan B:** si el navegador falla, `bash scripts/demo_en_vivo.sh` en la terminal y abrir el `anotado.mp4`. Si nada corre, reproducir el video pregrabado y decir «esto es la corrida de anoche».

## 7 · F1 de reglas (Francisco Zúñiga, 1 min)

### Qué decir

> ¿Las alertas son correctas? UA-DETRAC no trae eventos anotados, así que lo medimos de dos formas. Primero con NGSIM, que tiene la trayectoria exacta de 270 autos reales. Calculamos los eventos que deberían salir, y le dimos al sistema esas mismas trayectorias con los errores que medimos en nuestra propia cámara: cuánto se equivoca en la posición, cuántas veces pierde un auto y cuántas veces le cambia el ID. Segundo, con el video real de MVI_39271, comparado contra las cajas anotadas a mano. Las reglas solas, con datos perfectos, dan 1,00: hacen exactamente lo especificado, y esta medición además nos permitió encontrar y corregir un error en zigzag. Con los errores reales llegamos a 0,80, sobre la meta de 0,75. En el video real da 0,65, pero son solo 17 eventos, poco para concluir. La barra gris es la definición original: daba 0,54. La medición nos mostró dos problemas: una oclusión breve partía un mismo episodio en dos alertas, y el umbral de confianza de carril dejaba pasar la mitad de los cambios de carril. Los corregimos midiendo, no a ojo.

### Tener en cuenta

- **No decir que en video «cumple».** Decir que da 0,65 con muy pocos eventos.
- Es la lámina más técnica: hablar lento y señalar cada barra de arriba hacia abajo.
- **Es la lámina que más preguntas va a generar** (ver la sección de preguntas).

## 8 · Cumplimiento de §2.5 (Francisco Zúñiga, 45 s)

### Qué decir

> Contra lo que comprometimos en la propuesta, los siete criterios están medidos. Detección sobre la meta en dos de tres secuencias; la excepción es la cola densa, donde los autos se tapan entre sí. Seguimiento sobre la meta en las tres. Reglas, 0,80. Rendimiento, 65 cuadros por segundo con GPU, y 25 incluso solo con CPU, cuando la meta era 15. Y se cumplen la demo en tres secuencias, la robustez, con tests y el modo sin calibración, y la trazabilidad: cada evento trae sus variables, sus umbrales y su puntaje.

### Tener en cuenta

- **La cola densa (0,592) es el punto débil.** Mencionarlo antes de que lo pregunten.
- **El FPS se midió en un Mac M4, no en la T4 de Colab** que pedía la propuesta. Si preguntan, el argumento es que incluso sin GPU pasa la meta.

## 9 · Preguntas

- Dejar la lámina en pantalla; la frase de abajo refuerza el alcance ético.

## Preguntas probables y respuestas

### Calibración

**¿Cómo saben que la calibración es correcta?**

> Tres controles. El error de reproyección es de 14 cm. La homografía predice dónde caen los trazos lejanos, que no usamos para calcularla, con unos 5 píxeles de error. Y un auto medido da 60 km/h, que calza con la vía. Además, la focal que sale de la homografía (833 px) es la de una cámara física plausible.

**¿Por qué el ancho de carril es 3,5 m?**

> Es la norma china de vías urbanas (CJJ 37-2012). No lo medimos, y lo declaramos como límite: toda la escala lateral hereda esa incertidumbre. La longitudinal sí está confirmada por los trazos.

**¿Qué pasa si la cámara se mueve?**

> La homografía es fija, así que habría que recalibrar. El alcance de la propuesta son cámaras fijas, y elegimos secuencias con cámara estable por eso mismo.

**¿Por qué MVI_40742 no tiene escala?**

> No hay nada en el pavimento cuya medida conozcamos: la línea central es continua, es de noche y los buses tapan la calzada. La única opción era el largo de un bus, pero una caja de bus no está plana sobre el suelo y habríamos inventado un error que no podíamos verificar. Preferimos que el sistema diga «no sé la distancia».

**¿Cómo funciona el zigzag sin calibración?**

> Solo necesita saber en qué carril va cada auto y cuándo cambia. Los carriles son polígonos en píxeles sobre la imagen, y el tiempo sale de los cuadros. Cercanía y corte sí necesitan metros, por eso se suspenden.

### Detección y seguimiento

**¿Por qué YOLOv8n y no un modelo más grande?**

> Por velocidad: la detección ya se lleva el 73 % del tiempo de cada cuadro. Con el modelo pequeño y preentrenado superamos la meta de detección sin reentrenar.

**¿Por qué la cola densa da 0,592?**

> Los autos detenidos se tapan entre sí. La precisión sigue en 99 %, así que casi no inventa vehículos; lo que baja es cuántos encuentra. Es el límite de un detector sin ajuste fino.

**¿Por qué miden en la región de interés y no en toda la imagen?**

> La anotación de UA-DETRAC incluye la calzada contraria y el fondo, que RoadGuard ignora a propósito. Contar esos autos como «no encontrados» castigaría al sistema por algo que no intenta hacer.

### F1 de reglas

**¿Ajustar dos parámetros mirando el resultado no es hacer trampa?**

> Son dos parámetros, y los elegimos con un barrido sobre dos fuentes distintas: NGSIM, con 225 eventos, y el video real. La tolerancia de 1,5 s no es arbitraria: el hueco medio que medimos cuando se pierde un auto es de 0,9 segundos. Y mostramos el resultado con la definición original, 0,54, para que se vea el efecto.

- **Si insisten:** reconocer que el F1 en video es optimista, porque es la misma secuencia con que se eligieron los parámetros. Por eso la cifra principal es la de NGSIM.

**Si la tolerancia también cambia la referencia, ¿no es trampa compararlas?**

> La tolerancia es parte de la definición de la regla, así que la referencia aplica esa misma regla, pero sobre datos perfectos. Sobre la trayectoria limpia, el sistema y la referencia coinciden exactamente. Lo que medimos es cuánto se pierde por los errores de la cámara.

**¿De dónde salen los errores que le aplicaron a NGSIM?**

> Los medimos comparando la posición que da RoadGuard con las cajas anotadas a mano en UA-DETRAC: unos 28 cm a lo largo del camino y 25 cm de lado, 7 % de observaciones perdidas y algunos cambios de ID. No los inventamos.

**¿Por qué el video da menos que NGSIM?**

> En video son solo 17 eventos de referencia, así que un evento más o menos mueve mucho el número. Y la cercanía en video tiene autos lejanos que la cámara detecta peor.

**En NGSIM la cercanía marca al 43 % de los autos. ¿La regla sirve?**

> En congestión, ir a menos de 1,5 segundos es lo normal, así que un puntaje fijo no distingue congestión de riesgo real. Por eso en el avance propusimos un puntaje ponderado por severidad, que espera su visto bueno.

### Eventos de la demo

**¿Por qué cambiaron los eventos desde el ensayo?**

> Al medir el F1 encontramos que una oclusión breve partía un mismo episodio en dos y que el umbral de carril perdía la mitad de los cambios. Ajustamos esos dos parámetros y el F1 subió de 0,54 a 0,80.

**¿Ese corte del bus es una conducta peligrosa?**

> Es una maniobra real, el bus saliendo del paradero, pero no agresiva. Por eso las alertas son para revisión humana. Un paso siguiente sería tener umbrales por clase de vehículo.

### Generales

**¿Funciona en tiempo real?**

> Sí: unos 64 cuadros por segundo con GPU en un notebook, y 25 solo con CPU, cuando el video va a 25. Además el proceso es causal: en cada instante solo usa lo que ya pasó, como si fuera una cámara en vivo.

**¿Lo midieron en la T4 de Colab?**

> No alcanzamos. Lo medimos en un notebook M4, donde incluso sin GPU supera la meta; el notebook para la T4 está listo en el repositorio.

**¿Qué pasa con la privacidad?**

> Solo trabajamos con clase de vehículo, posición y trayectoria. No leemos patentes, no identificamos personas y no emitimos sanciones.

**¿Cuántos tests tienen y qué prueban?**

> 268. Cubren cada módulo por separado, los casos difíciles (oclusiones, pérdida de ID, vehículos detenidos, falta de calibración y cambios de carril incompletos) y la integración de punta a punta.
