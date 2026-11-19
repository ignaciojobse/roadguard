/* RoadGuard · demo en vivo.
 *
 * Reproduce una corrida real cuadro a cuadro sobre los JPG originales y
 * dibuja encima, por capas, lo que hace cada etapa del sistema. Los datos
 * salen de scripts/exportar_demo.py (demo_web/datos/<secuencia>.json).
 */
(() => {
  "use strict";

  const COLOR = {
    bg: "#0B0F14", surf: "#141B24", line: "#2A3644", tx: "#F2F5F8", tx2: "#9AA6B2",
    acc: "#4C9AFF", neutro: "#9AA6B2",
    verde: "#34C27A", amarillo: "#F2C230", rojo: "#FF6B6B",
  };
  const NIVEL = { verde: COLOR.verde, amarillo: COLOR.amarillo, rojo: COLOR.rojo };
  const REGLA = {
    cercania_peligrosa: { nombre: "Cercanía", letra: "C", color: "#3D8BF0" },
    zigzag: { nombre: "Zigzag", letra: "Z", color: "#C77A2E" },
    corte_de_carril: { nombre: "Corte", letra: "K", color: "#B07CE8" },
  };
  const CLASE = { automovil: "auto", bus: "bus", camion: "camión", motocicleta: "moto" };
  const TAMANO = { automovil: [4.5, 1.8], bus: [12, 2.5], camion: [8, 2.4], motocicleta: [2, 0.8] };
  const PASOS = {
    1: "<b>Cuadro.</b> El sistema recibe cada cuadro del video con su tiempo exacto, 25 por segundo. <em>Es lo mismo que vería una persona.</em>",
    2: "<b>Detectar.</b> YOLOv8n encuentra autos, buses, camiones y motos en cada cuadro. <em>Cada caja trae su clase y su confianza.</em>",
    3: "<b>Seguir.</b> ByteTrack le da a cada vehículo un número que se mantiene mientras está en escena. <em>La estela es su recorrido.</em>",
    4: "<b>Metros y carriles.</b> La homografía lleva cada vehículo a metros sobre el camino: sabemos su carril y su velocidad real. <em>Mira la vista de pájaro.</em>",
    5: "<b>Reglas y riesgo.</b> La línea une a cada auto con el de adelante y muestra su separación en segundos (THW). <em>Bajo 1,5 s por 2 s es cercanía; cada evento suma puntos y la caja cambia de color.</em>",
    6: "<b>Resultado.</b> Todo junto: cada evento con su vehículo, su regla y los valores que lo justifican. <em>Haz clic en un evento de la línea de tiempo para ir a él.</em>",
  };
  const PASO4_SIN_CALIB = "<b>Sin calibración.</b> Esta cámara no tiene una escala en el pavimento: el sistema no inventa metros. <em>Sigue detectando, siguiendo y asignando carril; cercanía y corte quedan suspendidos.</em>";

  const $ = (id) => document.getElementById(id);
  const camara = $("lienzo-camara"), ctx = camara.getContext("2d");
  const pajaro = $("lienzo-pajaro"), ctxP = pajaro.getContext("2d");
  const linea = $("lienzo-linea"), ctxL = linea.getContext("2d");

  const estado = {
    doc: null, seq: null, cuadro: 0, paso: 1, reproduciendo: false, velocidad: 1,
    seleccionado: null, imagenes: new Map(), ultimaImagen: null, acumulado: 0, tPrevio: null,
    porId: new Map(), porCuadro: [],
  };

  // ------------------------------------------------------------------ datos
  const campo = {};
  function indexar(doc) {
    doc.campos_vehiculo.forEach((n, i) => (campo[n] = i));
    estado.porCuadro = doc.cuadros.map((vs) => {
      const m = new Map();
      vs.forEach((v) => m.set(v[campo.id], v));
      return m;
    });
    estado.porId = new Map();
    doc.cuadros.forEach((vs, c) => vs.forEach((v) => {
      const id = v[campo.id];
      if (!estado.porId.has(id)) estado.porId.set(id, []);
      estado.porId.get(id).push([c, v]);
    }));
  }

  async function cargar(seq) {
    pausar();
    estado.seq = seq;
    document.querySelectorAll("#secuencias button").forEach((b) => b.classList.toggle("activo", b.dataset.seq === seq));
    const r = await fetch(`datos/${seq}.json`);
    if (!r.ok) { $("explicacion").textContent = `No encuentro datos/${seq}.json: corre scripts/exportar_demo.py ${seq}`; return; }
    estado.doc = await r.json();
    indexar(estado.doc);
    estado.imagenes.clear();
    estado.ultimaImagen = null;
    estado.seleccionado = null;
    estado.cuadro = 0;
    pintarMetricas();
    ajustarPajaro();
    precargar(0);
    actualizarPaso(estado.paso);
    dibujar();
  }

  // ---------------------------------------------------------------- imagenes
  function rutaCuadro(c) {
    const n = String(c + 1).padStart(5, "0");
    return estado.doc.patron_cuadros.replace("{:05d}", n);
  }
  function precargar(desde) {
    const doc = estado.doc;
    for (let c = desde; c < Math.min(doc.n_cuadros, desde + 75); c++) {
      if (estado.imagenes.has(c)) continue;
      const img = new Image();
      img.decoding = "async";
      img.src = rutaCuadro(c);
      img.onload = () => { if (c === estado.cuadro) dibujar(); };
      if (c === 0) img.onerror = () => {
        $("explicacion").innerHTML = `<b>Faltan los cuadros de ${estado.seq}.</b> <em>En la terminal: python scripts/bajar_ua_detrac.py ${estado.seq}</em>`;
      };
      estado.imagenes.set(c, img);
    }
    for (const c of estado.imagenes.keys()) {
      if (c < desde - 40 || c > desde + 200) estado.imagenes.delete(c);
    }
  }
  function lista(c) {
    const img = estado.imagenes.get(c);
    return img && img.complete && img.naturalWidth > 0;
  }

  // -------------------------------------------------------------- reproduccion
  function reproducir() {
    if (!estado.doc) return;
    if (estado.cuadro >= estado.doc.n_cuadros - 1) estado.cuadro = 0;
    estado.reproduciendo = true;
    estado.tPrevio = null;
    $("btn-play").textContent = "❚❚";
    requestAnimationFrame(bucle);
  }
  function pausar() {
    estado.reproduciendo = false;
    $("btn-play").textContent = "▶";
  }
  function bucle(ahora) {
    if (!estado.reproduciendo) return;
    if (estado.tPrevio !== null) estado.acumulado += ((ahora - estado.tPrevio) / 1000) * estado.velocidad;
    estado.tPrevio = ahora;
    const paso = 1 / estado.doc.fps;
    let cambio = false;
    while (estado.acumulado >= paso) {
      const sig = estado.cuadro + 1;
      if (sig >= estado.doc.n_cuadros) { pausar(); break; }
      if (!lista(sig)) { estado.acumulado = 0; break; } // espera a que cargue
      estado.cuadro = sig;
      estado.acumulado -= paso;
      cambio = true;
    }
    if (cambio) { precargar(estado.cuadro); dibujar(); }
    requestAnimationFrame(bucle);
  }
  function irA(c) {
    estado.cuadro = Math.max(0, Math.min(estado.doc.n_cuadros - 1, Math.round(c)));
    estado.acumulado = 0;
    precargar(estado.cuadro);
    dibujar();
  }

  // ------------------------------------------------------------------ pasos
  function actualizarPaso(p) {
    estado.paso = p;
    document.querySelectorAll("#pasos button").forEach((b) => {
      const n = Number(b.dataset.paso);
      b.classList.toggle("activo", n === p);
      b.classList.toggle("hecho", n < p);
    });
    const calibrado = estado.doc && estado.doc.geometria.calibrado;
    $("explicacion").innerHTML = (p >= 4 && !calibrado && p <= 5 ? PASO4_SIN_CALIB : PASOS[p]);
    dibujar();
  }

  // ------------------------------------------------------------------ dibujo
  const v = (veh, n) => veh[campo[n]];
  const fmt = (x, d = 1) => (x == null ? "—" : x.toFixed(d).replace(".", ","));
  const kmh = (ms) => (ms == null ? null : ms * 3.6);
  const pieCaja = (veh) => [(v(veh, "x1") + v(veh, "x2")) / 2, v(veh, "y2")];

  function califica(veh) {
    const u = estado.doc.umbrales;
    const thw = v(veh, "thw"), vel = v(veh, "velocidad");
    return v(veh, "id_predecesor") != null && thw != null && vel != null &&
      thw < u.cercania_thw_max && vel > u.cercania_velocidad_min;
  }

  function dibujar() {
    if (!estado.doc) return;
    dibujarCamara();
    dibujarPajaro();
    dibujarLinea();
    pintarAhora();
    pintarVehiculo();
    pintarContadores();
    const t = estado.cuadro / estado.doc.fps;
    $("reloj").textContent = `${fmt(t)} s · cuadro ${estado.cuadro + 1}`;
  }

  function dibujarCamara() {
    const doc = estado.doc, p = estado.paso, c = estado.cuadro;
    const img = lista(c) ? estado.imagenes.get(c) : estado.ultimaImagen;
    if (img) {
      if (camara.width !== img.naturalWidth) { camara.width = img.naturalWidth; camara.height = img.naturalHeight; }
      ctx.drawImage(img, 0, 0);
      estado.ultimaImagen = img;
    } else {
      ctx.fillStyle = "#000"; ctx.fillRect(0, 0, camara.width, camara.height);
    }
    const g = doc.geometria;
    const rot = $("rotulo-camara");
    rot.className = "rotulo-camara";
    if (p >= 4 && !g.calibrado) {
      rot.textContent = "SIN CALIBRACIÓN · no hay metros: cercanía y corte suspendidos";
      rot.className = "rotulo-camara visible alerta";
    }

    if (p >= 4) {
      ctx.lineWidth = 2;
      g.carriles_px.forEach((carril) => {
        ctx.strokeStyle = "rgba(242,194,48,0.75)";
        trazar(ctx, carril.poligono, true);
        ctx.stroke();
      });
      if (g.calibrado && p === 4) {
        ctx.strokeStyle = "rgba(76,154,255,0.55)"; ctx.lineWidth = 1.5;
        g.rejilla_px.forEach((l) => { trazar(ctx, l, false); ctx.stroke(); });
      }
    }
    const vehiculos = doc.cuadros[c];
    if (p >= 3) dibujarEstelas(vehiculos);
    if (p >= 5 && g.calibrado) {
      const mapa = estado.porCuadro[c];
      vehiculos.forEach((veh) => {
        if (!califica(veh)) return;
        const pred = mapa.get(v(veh, "id_predecesor"));
        if (!pred) return;
        const [ax, ay] = pieCaja(veh), [bx, by] = pieCaja(pred);
        ctx.strokeStyle = COLOR.amarillo; ctx.lineWidth = 4; ctx.setLineDash([10, 6]);
        ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.stroke(); ctx.setLineDash([]);
        etiqueta(ctx, `${fmt(v(veh, "thw"))} s`, (ax + bx) / 2, (ay + by) / 2 - 6, COLOR.amarillo, COLOR.bg, 18);
      });
    }
    if (p >= 2) vehiculos.forEach((veh) => dibujarCaja(veh));
  }

  function dibujarEstelas(vehiculos) {
    const c = estado.cuadro;
    ctx.lineWidth = 3;
    vehiculos.forEach((veh) => {
      const id = v(veh, "id");
      ctx.beginPath();
      let primero = true;
      for (let k = Math.max(0, c - 60); k <= c; k++) {
        const otro = estado.porCuadro[k].get(id);
        if (!otro) continue;
        const [x, y] = pieCaja(otro);
        if (primero) { ctx.moveTo(x, y); primero = false; } else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = id === estado.seleccionado ? "rgba(255,255,255,0.95)" : "rgba(255,255,255,0.45)";
      ctx.stroke();
    });
  }

  function dibujarCaja(veh) {
    const p = estado.paso, g = estado.doc.geometria;
    const x1 = v(veh, "x1"), y1 = v(veh, "y1"), x2 = v(veh, "x2"), y2 = v(veh, "y2");
    const id = v(veh, "id"), clase = CLASE[v(veh, "clase")] || v(veh, "clase");
    const color = p >= 5 ? NIVEL[v(veh, "nivel")] : COLOR.neutro;
    const sel = id === estado.seleccionado;
    ctx.lineWidth = sel ? 5 : 3;
    ctx.strokeStyle = sel ? "#FFFFFF" : color;
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
    if (sel) { ctx.lineWidth = 2; ctx.strokeStyle = color; ctx.strokeRect(x1 + 3, y1 + 3, x2 - x1 - 6, y2 - y1 - 6); }
    let texto;
    if (p === 2) texto = `${clase}`;
    else if (p === 3) texto = `${id} · ${clase}`;
    else {
      const partes = [`${id} · ${clase}`];
      const carril = v(veh, "carril");
      if (carril != null) partes.push(`carril ${carril}`);
      if (g.calibrado && v(veh, "velocidad") != null) partes.push(`${Math.round(kmh(v(veh, "velocidad")))} km/h`);
      if (p >= 5) partes.push(`${v(veh, "puntaje")}`);
      texto = partes.join(" · ");
    }
    etiqueta(ctx, texto, x1, Math.max(16, y1 - 4), color, COLOR.bg, 15, "izq");
  }

  function etiqueta(c2d, texto, x, y, fondo, tinta, tam, alin = "centro") {
    c2d.font = `600 ${tam}px 'Space Grotesk', system-ui, sans-serif`;
    const w = c2d.measureText(texto).width + 10, h = tam + 6;
    const x0 = alin === "izq" ? x : x - w / 2;
    c2d.fillStyle = fondo; c2d.fillRect(x0, y - h + 2, w, h);
    c2d.fillStyle = tinta; c2d.textBaseline = "alphabetic";
    c2d.fillText(texto, x0 + 5, y - 3);
  }

  function trazar(c2d, puntos, cerrar) {
    c2d.beginPath();
    puntos.forEach(([x, y], i) => (i ? c2d.lineTo(x, y) : c2d.moveTo(x, y)));
    if (cerrar) c2d.closePath();
  }

  // ------------------------------------------------------------ vista de pajaro
  let mapaP = null;
  function ajustarPajaro() {
    const g = estado.doc.geometria;
    const dpr = window.devicePixelRatio || 1;
    const ancho = pajaro.clientWidth || 600;
    if (!g.calibrado) {
      pajaro.width = ancho * dpr; pajaro.height = 170 * dpr; pajaro.style.height = "170px";
      mapaP = null; $("nota-pajaro").textContent = "sin calibración";
      return;
    }
    $("nota-pajaro").textContent = "metros sobre el camino";
    const xs = g.region_m.map((p) => p[0]), ys = g.region_m.map((p) => p[1]);
    const xmin = Math.min(...xs), xmax = Math.max(...xs), ymin = Math.min(...ys), ymax = Math.max(...ys);
    const pad = 34;
    let s = (ancho - 2 * pad) / (xmax - xmin);
    let alto = (ymax - ymin) * s + 2 * pad + 18;
    if (alto > 300) { s = (300 - 2 * pad - 18) / (ymax - ymin); alto = 300; }
    pajaro.width = ancho * dpr; pajaro.height = alto * dpr; pajaro.style.height = `${alto}px`;
    // Misma orientacion que la camara: el avance y el orden de los carriles
    // se ven hacia el mismo lado en las dos vistas.
    const corr = (a, b) => {
      const ma = a.reduce((x, y) => x + y, 0) / a.length, mb = b.reduce((x, y) => x + y, 0) / b.length;
      return a.reduce((acc, ai, i) => acc + (ai - ma) * (b[i] - mb), 0);
    };
    const pares = g.region_px.length === g.region_m.length;
    const invX = pares && corr(xs, g.region_px.map((p) => p[0])) < 0;
    const invY = pares && corr(ys, g.region_px.map((p) => p[1])) < 0;
    mapaP = { xmin, ymin, s, pad, dpr, ancho, alto, xmax, ymax, invX, invY };
  }
  const aP = (x, y) => {
    const u = (x - mapaP.xmin) * mapaP.s, w = (y - mapaP.ymin) * mapaP.s;
    const anchoUtil = (mapaP.xmax - mapaP.xmin) * mapaP.s, altoUtil = (mapaP.ymax - mapaP.ymin) * mapaP.s;
    return [mapaP.pad + (mapaP.invX ? anchoUtil - u : u), mapaP.pad + (mapaP.invY ? altoUtil - w : w)];
  };

  function dibujarPajaro() {
    const g = estado.doc.geometria, p = estado.paso;
    const dpr = window.devicePixelRatio || 1;
    ctxP.setTransform(dpr, 0, 0, dpr, 0, 0);
    const W = pajaro.width / dpr, H = pajaro.height / dpr;
    ctxP.fillStyle = COLOR.bg; ctxP.fillRect(0, 0, W, H);
    if (!mapaP) {
      ctxP.fillStyle = COLOR.tx2; ctxP.font = "500 17px 'Space Grotesk', system-ui"; ctxP.textAlign = "center";
      ctxP.fillText("Esta cámara no tiene escala en el pavimento.", W / 2, H / 2 - 12);
      ctxP.fillText("Sin metros no hay distancia, THW ni TTC.", W / 2, H / 2 + 14);
      ctxP.textAlign = "start";
      return;
    }
    ctxP.fillStyle = "#1A222D";
    trazar(ctxP, g.region_m.map(([x, y]) => aP(x, y)), true); ctxP.fill();
    g.carriles_m.forEach((carril) => {
      ctxP.strokeStyle = "rgba(242,242,242,0.35)"; ctxP.setLineDash([8, 10]); ctxP.lineWidth = 1.5;
      trazar(ctxP, carril.poligono.map(([x, y]) => aP(x, y)), true); ctxP.stroke(); ctxP.setLineDash([]);
      const cx = carril.poligono.reduce((a, q) => a + q[0], 0) / carril.poligono.length;
      const cy = carril.poligono.reduce((a, q) => a + q[1], 0) / carril.poligono.length;
      const [, ly] = aP(cx, cy);
      ctxP.fillStyle = COLOR.tx2; ctxP.font = "500 12px system-ui";
      ctxP.textAlign = "right"; ctxP.fillText(`c${carril.indice}`, mapaP.pad - 6, ly + 4); ctxP.textAlign = "start";
    });
    // escala y sentido
    ctxP.fillStyle = COLOR.tx2; ctxP.font = "500 12px system-ui";
    const abajo = mapaP.pad + (mapaP.ymax - mapaP.ymin) * mapaP.s;
    const finalX = mapaP.pad + (mapaP.xmax - mapaP.xmin) * mapaP.s;
    ctxP.fillRect(finalX - 10 * mapaP.s, abajo + 8, 10 * mapaP.s, 3);
    ctxP.fillText("10 m", finalX - 10 * mapaP.s, abajo + 24);
    ctxP.fillText(mapaP.invX ? "← sentido de avance" : "sentido de avance →", mapaP.pad, abajo + 24);
    if (p < 4) {
      ctxP.fillStyle = "rgba(11,15,20,0.72)"; ctxP.fillRect(0, 0, W, H);
      ctxP.fillStyle = COLOR.tx2; ctxP.font = "500 16px 'Space Grotesk', system-ui"; ctxP.textAlign = "center";
      ctxP.fillText("Se enciende en el paso 4: metros y carriles", W / 2, H / 2); ctxP.textAlign = "start";
      return;
    }
    const vehiculos = estado.doc.cuadros[estado.cuadro], mapa = estado.porCuadro[estado.cuadro];
    if (p >= 5) {
      vehiculos.forEach((veh) => {
        if (!califica(veh)) return;
        const pred = mapa.get(v(veh, "id_predecesor"));
        if (!pred || v(pred, "x_m") == null) return;
        const [ax, ay] = aP(v(veh, "x_m"), v(veh, "y_m")), [bx, by] = aP(v(pred, "x_m"), v(pred, "y_m"));
        ctxP.strokeStyle = COLOR.amarillo; ctxP.lineWidth = 2.5; ctxP.setLineDash([6, 4]);
        ctxP.beginPath(); ctxP.moveTo(ax, ay); ctxP.lineTo(bx, by); ctxP.stroke(); ctxP.setLineDash([]);
        etiqueta(ctxP, `${fmt(v(veh, "thw"))} s`, (ax + bx) / 2, Math.min(ay, by) - 8, COLOR.amarillo, COLOR.bg, 12);
      });
    }
    vehiculos.forEach((veh) => {
      if (v(veh, "x_m") == null) return;
      const [largo, anchoV] = TAMANO[v(veh, "clase")] || TAMANO.automovil;
      const [cx, cy] = aP(v(veh, "x_m"), v(veh, "y_m"));
      const w = largo * mapaP.s, h = anchoV * mapaP.s;
      const color = p >= 5 ? NIVEL[v(veh, "nivel")] : COLOR.acc;
      const sel = v(veh, "id") === estado.seleccionado;
      ctxP.fillStyle = color;
      ctxP.beginPath(); ctxP.roundRect(cx - w / 2, cy - h / 2, w, h, 3); ctxP.fill();
      if (sel) { ctxP.strokeStyle = "#FFFFFF"; ctxP.lineWidth = 2.5; ctxP.stroke(); }
      ctxP.fillStyle = COLOR.tx; ctxP.font = "600 12px system-ui";
      const vel = kmh(v(veh, "velocidad"));
      ctxP.fillText(`${v(veh, "id")}${vel != null ? " · " + Math.round(vel) : ""}`, cx - w / 2, cy - h / 2 - 3);
    });
  }

  // ---------------------------------------------------------- linea de tiempo
  const FILAS = ["cercania_peligrosa", "zigzag", "corte_de_carril"];
  const IZQ = 96;
  function dibujarLinea() {
    const doc = estado.doc;
    const dpr = window.devicePixelRatio || 1;
    const W = linea.clientWidth, H = 96;
    if (linea.width !== W * dpr) { linea.width = W * dpr; linea.height = H * dpr; }
    ctxL.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctxL.fillStyle = COLOR.bg; ctxL.fillRect(0, 0, W, H);
    const dur = doc.n_cuadros / doc.fps;
    const xDe = (t) => IZQ + (t / dur) * (W - IZQ - 8);
    FILAS.forEach((r, i) => {
      const y = 8 + i * 28;
      ctxL.fillStyle = COLOR.surf; ctxL.fillRect(IZQ, y, W - IZQ - 8, 22);
      ctxL.fillStyle = COLOR.tx2; ctxL.font = "500 14px 'Space Grotesk', system-ui";
      ctxL.fillText(REGLA[r].nombre, 4, y + 16);
    });
    const t = estado.cuadro / doc.fps;
    doc.eventos.forEach((e) => {
      const i = FILAS.indexOf(e.regla); if (i < 0) return;
      const y = 8 + i * 28, x0 = xDe(e.t_inicio), x1 = Math.max(xDe(e.t_fin), x0 + 5);
      ctxL.globalAlpha = e.t_inicio <= t ? 1 : 0.45;
      ctxL.fillStyle = REGLA[e.regla].color; ctxL.fillRect(x0, y + 2, x1 - x0, 18);
      ctxL.globalAlpha = 1;
      if (x1 - x0 > 22) { ctxL.fillStyle = COLOR.bg; ctxL.font = "600 12px system-ui"; ctxL.fillText(String(e.id), x0 + 3, y + 15); }
    });
    const xp = xDe(t);
    ctxL.fillStyle = COLOR.tx; ctxL.fillRect(xp - 1, 2, 2, H - 8);
  }
  function tiempoDeX(x) {
    const doc = estado.doc, W = linea.clientWidth;
    return Math.max(0, ((x - IZQ) / (W - IZQ - 8)) * (doc.n_cuadros / doc.fps));
  }

  // ---------------------------------------------------------------- paneles
  function descripcionEvento(e) {
    const vv = e.variables, nombre = (id) => {
      const info = estado.doc.vehiculos[String(id)];
      return `${info ? CLASE[info.clase] || info.clase : "vehículo"} ${id}`;
    };
    if (e.regla === "cercania_peligrosa")
      return `${nombre(e.id)} a ${fmt(vv.thw, 2)} s del ${e.id_relacionado} · ${Math.round(kmh(vv.velocidad))} km/h`;
    if (e.regla === "zigzag")
      return `${nombre(e.id)} · ${fmt(vv.n_cambios, 0)} cambios de carril en ${fmt(vv.duracion_cruces)} s`;
    const metrica = vv.thw != null ? `THW ${fmt(vv.thw, 2)} s` : (vv.ttc != null ? `TTC ${fmt(vv.ttc, 2)} s` : "");
    return `${nombre(e.id)} se metió delante del ${e.id_relacionado} · ${metrica}`;
  }

  function pintarAhora() {
    const doc = estado.doc, t = estado.cuadro / doc.fps, caja = $("ahora");
    if (estado.paso < 5) { caja.innerHTML = '<p class="nada">Los eventos aparecen desde el paso 5.</p>'; return; }
    const activos = doc.eventos.filter((e) => e.t_inicio <= t && t <= e.t_fin + 3);
    const clave = activos.map((e) => `${e.regla}${e.id}${e.t_inicio}`).join("|");
    if (caja.dataset.clave === clave) return;
    caja.dataset.clave = clave;
    if (!activos.length) {
      caja.innerHTML = `<p class="nada">Sin eventos en este momento. ${doc.geometria.calibrado ? "" : "Sin calibración solo se evalúa zigzag."}</p>`;
      return;
    }
    caja.innerHTML = activos.map((e) => `
      <div class="tarjeta" style="border-left-color:${REGLA[e.regla].color}">
        <b>${REGLA[e.regla].nombre} · +${e.aporte}</b>
        <div>${descripcionEvento(e)}</div>
        <div class="d">${fmt(e.t_inicio)} s a ${fmt(e.t_fin)} s · queda en eventos.csv con sus umbrales</div>
      </div>`).join("");
  }

  function pintarVehiculo() {
    const caja = $("vehiculo"), id = estado.seleccionado;
    if (id == null) { caja.className = "vacio"; caja.textContent = "Selecciona un vehículo en la cámara o en la vista de pájaro."; return; }
    const serie = estado.porId.get(id) || [];
    let actual = estado.porCuadro[estado.cuadro].get(id);
    const visible = !!actual;
    if (!actual) {
      const previo = serie.filter(([c]) => c <= estado.cuadro).pop() || serie[0];
      actual = previo ? previo[1] : null;
    }
    if (!actual) return;
    const clase = CLASE[v(actual, "clase")] || v(actual, "clase");
    const calib = estado.doc.geometria.calibrado;
    const dato = (val, nombre) => `<div class="dato"><b>${val}</b><span>${nombre}</span></div>`;
    caja.className = "";
    caja.innerHTML = `
      <div class="fila">
        ${dato(`${clase} ${id}`, visible ? "en escena" : "fuera de escena")}
        ${dato(v(actual, "carril") ?? "—", "carril")}
        ${dato(calib ? Math.round(kmh(v(actual, "velocidad")) ?? 0) + " km/h" : "—", "velocidad")}
        ${dato(calib && v(actual, "thw") != null ? fmt(v(actual, "thw"), 2) + " s" : "—", "THW al de adelante")}
        ${dato(`<span style="color:${NIVEL[v(actual, "nivel")]}">${v(actual, "puntaje")}</span>`, "puntaje")}
      </div>
      <canvas id="serie" width="600" height="70"></canvas>`;
    dibujarSerie($("serie"), serie);
  }

  function dibujarSerie(lienzo, serie) {
    if (!serie.length) return;
    const dpr = window.devicePixelRatio || 1, W = lienzo.clientWidth, H = 70;
    lienzo.width = W * dpr; lienzo.height = H * dpr;
    const g = lienzo.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0);
    const c0 = serie[0][0], c1 = serie[serie.length - 1][0] || c0 + 1;
    const xDe = (c) => 4 + ((c - c0) / Math.max(1, c1 - c0)) * (W - 8);
    const yDe = (p) => H - 6 - (p / 100) * (H - 14);
    g.strokeStyle = COLOR.line; g.lineWidth = 1;
    [30, 60].forEach((b) => { g.beginPath(); g.moveTo(4, yDe(b)); g.lineTo(W - 4, yDe(b)); g.stroke(); });
    g.lineWidth = 2.5;
    for (let k = 1; k < serie.length; k++) {
      const [ca, va] = serie[k - 1], [cb, vb] = serie[k];
      g.strokeStyle = NIVEL[v(vb, "nivel")];
      g.beginPath(); g.moveTo(xDe(ca), yDe(v(va, "puntaje"))); g.lineTo(xDe(cb), yDe(v(vb, "puntaje"))); g.stroke();
    }
    if (estado.cuadro >= c0 && estado.cuadro <= c1) {
      g.fillStyle = COLOR.tx; g.fillRect(xDe(estado.cuadro) - 1, 2, 2, H - 4);
    }
    g.fillStyle = COLOR.tx2; g.font = "500 11px system-ui"; g.fillText("puntaje en el tiempo", 6, 12);
  }

  function pintarContadores() {
    const doc = estado.doc, t = estado.cuadro / doc.fps;
    $("contadores").innerHTML = FILAS.map((r) => {
      const total = doc.eventos.filter((e) => e.regla === r).length;
      const hasta = doc.eventos.filter((e) => e.regla === r && e.t_inicio <= t).length;
      return `<div><b style="color:${REGLA[r].color}">${hasta}/${total}</b>${REGLA[r].nombre}</div>`;
    }).join("");
  }

  function pintarMetricas() {
    const doc = estado.doc, m = doc.metricas;
    const caja = (val, nombre) => `<div class="metrica"><b>${val}</b><span>${nombre}</span></div>`;
    $("metricas").innerHTML =
      (m ? caja(fmt(m.map50, 3), "mAP@0.5") + caja(fmt(m.idf1, 3), "IDF1") : "") +
      caja(fmt(doc.fps_procesamiento, 0), "FPS DEL SISTEMA") +
      caja(doc.eventos.length, "EVENTOS");
  }

  // --------------------------------------------------------------- interaccion
  function vehiculoEnCamara(ev) {
    const r = camara.getBoundingClientRect();
    const x = ((ev.clientX - r.left) / r.width) * camara.width, y = ((ev.clientY - r.top) / r.height) * camara.height;
    let mejor = null, area = Infinity;
    estado.doc.cuadros[estado.cuadro].forEach((veh) => {
      if (x >= v(veh, "x1") && x <= v(veh, "x2") && y >= v(veh, "y1") && y <= v(veh, "y2")) {
        const a = (v(veh, "x2") - v(veh, "x1")) * (v(veh, "y2") - v(veh, "y1"));
        if (a < area) { area = a; mejor = v(veh, "id"); }
      }
    });
    return mejor;
  }
  function vehiculoEnPajaro(ev) {
    if (!mapaP) return null;
    const r = pajaro.getBoundingClientRect();
    const x = ev.clientX - r.left, y = ev.clientY - r.top;
    let mejor = null, dist = 18;
    estado.doc.cuadros[estado.cuadro].forEach((veh) => {
      if (v(veh, "x_m") == null) return;
      const [cx, cy] = aP(v(veh, "x_m"), v(veh, "y_m"));
      const d = Math.hypot(cx - x, cy - y);
      if (d < dist) { dist = d; mejor = v(veh, "id"); }
    });
    return mejor;
  }

  camara.addEventListener("click", (ev) => { estado.seleccionado = vehiculoEnCamara(ev); dibujar(); });
  pajaro.addEventListener("click", (ev) => { estado.seleccionado = vehiculoEnPajaro(ev); dibujar(); });
  linea.addEventListener("click", (ev) => {
    const r = linea.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top;
    const t = tiempoDeX(x), fila = Math.floor((y - 8) / 28);
    const doc = estado.doc, dur = doc.n_cuadros / doc.fps, margen = (8 / (r.width - IZQ)) * dur;
    const evento = doc.eventos.find((e) => FILAS.indexOf(e.regla) === fila && t >= e.t_inicio - margen && t <= e.t_fin + margen);
    if (evento) {
      estado.seleccionado = evento.id;
      if (estado.paso < 5) actualizarPaso(6);
      irA((evento.t_inicio - 1.5) * doc.fps);
    } else irA(t * doc.fps);
  });
  $("btn-play").addEventListener("click", () => (estado.reproduciendo ? pausar() : reproducir()));
  $("btn-atras").addEventListener("click", () => { pausar(); irA(estado.cuadro - 1); });
  $("btn-adelante").addEventListener("click", () => { pausar(); irA(estado.cuadro + 1); });
  $("velocidad").addEventListener("change", (e) => (estado.velocidad = Number(e.target.value)));
  document.querySelectorAll("#pasos button").forEach((b) => b.addEventListener("click", () => actualizarPaso(Number(b.dataset.paso))));
  async function armarCamaras() {
    let indice = [];
    try {
      const r = await fetch("datos/indice.json");
      if (r.ok) indice = await r.json();
    } catch (e) { /* sin indice: se usa la lista minima */ }
    if (!indice.length) indice = [{ secuencia: "MVI_39271", titulo: "Día", subtitulo: "MVI_39271" }];
    const nav = $("secuencias");
    nav.innerHTML = indice.map((c) =>
      `<button data-seq="${c.secuencia}">${c.titulo} <small>${c.subtitulo}</small></button>`).join("");
    nav.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => cargar(b.dataset.seq)));
    return indice;
  }
  window.addEventListener("resize", () => { if (estado.doc) { ajustarPajaro(); dibujar(); } });
  document.addEventListener("keydown", (e) => {
    if (!estado.doc || e.target.tagName === "SELECT") return;
    if (e.code === "Space") { e.preventDefault(); estado.reproduciendo ? pausar() : reproducir(); }
    else if (e.key === "ArrowRight") { pausar(); irA(estado.cuadro + (e.shiftKey ? estado.doc.fps : 1)); }
    else if (e.key === "ArrowLeft") { pausar(); irA(estado.cuadro - (e.shiftKey ? estado.doc.fps : 1)); }
    else if (/^[1-6]$/.test(e.key)) actualizarPaso(Number(e.key));
    else if (e.key === "f") document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen();
    else if (e.key === "Escape") { estado.seleccionado = null; dibujar(); }
  });

  const params = new URLSearchParams(location.search);
  estado.paso = Number(params.get("paso")) || 1;
  armarCamaras().then((indice) => cargar(params.get("seq") || indice[0].secuencia)).then(() => {
    const t = Number(params.get("t"));
    if (t > 0 && estado.doc) irA(t * estado.doc.fps);
  });
})();
