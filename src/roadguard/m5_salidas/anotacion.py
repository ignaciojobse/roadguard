"""M5 - RF11: composicion del MP4 anotado con OpenCV.

Dibuja caja, ID, alerta y riesgo por vehiculo, con el color de la banda
correspondiente (verde 0-29, amarillo 30-59, rojo 60-100).
"""

from __future__ import annotations

import textwrap
import unicodedata

import cv2

from roadguard.tipos import Evento, MetadatosVideo, NivelRiesgo, PuntajeRiesgo, Regla, Track

# Colores BGR de las bandas (RF11).
COLORES: dict[NivelRiesgo, tuple[int, int, int]] = {
    NivelRiesgo.VERDE: (60, 200, 60),
    NivelRiesgo.AMARILLO: (0, 215, 255),
    NivelRiesgo.ROJO: (40, 40, 230),
}
ROTULO_REGLA: dict[Regla, str] = {
    Regla.CERCANIA: "cercania",
    Regla.ZIGZAG: "zigzag",
    Regla.CORTE: "corte de carril",
}
ENCABEZADO = "RoadGuard | alertas EXPERIMENTALES - requieren revision humana"
_FUENTE = cv2.FONT_HERSHEY_SIMPLEX


def _ascii(texto: str) -> str:
    """OpenCV no dibuja tildes: se normaliza a ASCII."""
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


class AnotadorVideo:
    def __init__(self, ruta_salida: str, metadatos: MetadatosVideo) -> None:
        self.ruta = ruta_salida
        self.tam = (metadatos.ancho, metadatos.alto)
        self._escritor = cv2.VideoWriter(
            ruta_salida, cv2.VideoWriter_fourcc(*"mp4v"), metadatos.fps, self.tam
        )
        if not self._escritor.isOpened():
            raise IOError(f"No se pudo abrir el escritor MP4: {ruta_salida}")
        self._escala = max(0.4, min(1.0, metadatos.alto / 720.0))
        self.n_cuadros = 0

    def escribir_cuadro(
        self,
        imagen: "object",
        tracks: list[Track],
        puntajes: dict[int, PuntajeRiesgo],
        eventos_activos: list[Evento],
        advertencias: list[str],
    ) -> None:
        """Dibuja caja, ID, alerta y riesgo, y escribe el cuadro (RF11).

        Si falta calibracion debe mantenerse una advertencia visible en
        pantalla (Paso 5).
        """
        if self._escritor is None:
            raise IOError("El anotador ya fue cerrado")
        lienzo = imagen.copy()
        if (lienzo.shape[1], lienzo.shape[0]) != self.tam:
            lienzo = cv2.resize(lienzo, self.tam)

        alertas: dict[int, list[str]] = {}
        for ev in eventos_activos:
            rotulos = alertas.setdefault(ev.id_vehiculo, [])
            if ROTULO_REGLA[ev.regla] not in rotulos:
                rotulos.append(ROTULO_REGLA[ev.regla])

        for tr in tracks:
            p = puntajes.get(tr.id_vehiculo)
            nivel = p.nivel if p is not None else NivelRiesgo.VERDE
            color = COLORES[nivel]
            c = tr.caja
            p1, p2 = (int(c.x1), int(c.y1)), (int(c.x2), int(c.y2))
            cv2.rectangle(lienzo, p1, p2, color, 2)
            lineas = [f"ID {tr.id_vehiculo} {tr.clase} riesgo {0 if p is None else p.puntaje}"]
            if tr.id_vehiculo in alertas:
                lineas.insert(0, "alerta exp.: " + ", ".join(alertas[tr.id_vehiculo]))
            self._rotulo(lienzo, lineas, p1, color)

        self._encabezado(lienzo, advertencias)
        self._escritor.write(lienzo)
        self.n_cuadros += 1

    def cerrar(self) -> None:
        """Cierra el archivo de salida de forma segura (Paso 6)."""
        if self._escritor is not None:
            self._escritor.release()
            self._escritor = None

    def __enter__(self) -> "AnotadorVideo":
        return self

    def __exit__(self, *exc) -> None:
        self.cerrar()

    # ------------------------------------------------------------------

    def _rotulo(self, lienzo, lineas: list[str], esquina, color) -> None:
        escala = 0.45 * self._escala
        alto_linea = int(16 * self._escala) + 4
        x, y = esquina
        y0 = max(alto_linea * len(lineas), y - 4)
        for i, linea in enumerate(reversed(lineas)):
            texto = _ascii(linea)
            (w, h), _ = cv2.getTextSize(texto, _FUENTE, escala, 1)
            yb = y0 - i * alto_linea
            cv2.rectangle(lienzo, (x, yb - h - 4), (x + w + 4, yb + 2), color, -1)
            cv2.putText(lienzo, texto, (x + 2, yb - 2), _FUENTE, escala, (0, 0, 0), 1, cv2.LINE_AA)

    def _encabezado(self, lienzo, advertencias: list[str]) -> None:
        escala = 0.5 * self._escala
        alto_linea = int(20 * self._escala) + 4
        ancho_chars = max(30, int(lienzo.shape[1] / (10 * self._escala)))
        lineas: list[tuple[str, tuple[int, int, int]]] = [(ENCABEZADO, (255, 255, 255))]
        for adv in advertencias:
            for trozo in textwrap.wrap(_ascii(adv), ancho_chars):
                lineas.append((trozo, (0, 140, 255)))
        alto = alto_linea * len(lineas) + 6
        franja = lienzo[:alto].copy()
        cv2.rectangle(franja, (0, 0), (lienzo.shape[1], alto), (0, 0, 0), -1)
        cv2.addWeighted(franja, 0.65, lienzo[:alto], 0.35, 0, dst=lienzo[:alto])
        for i, (texto, color) in enumerate(lineas):
            cv2.putText(
                lienzo, _ascii(texto), (8, (i + 1) * alto_linea), _FUENTE, escala, color, 1, cv2.LINE_AA
            )
