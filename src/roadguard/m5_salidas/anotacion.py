"""M5 - RF11: composicion del MP4 anotado con OpenCV.

Dibuja caja, ID, alerta y riesgo por vehiculo, con el color de la banda
correspondiente (verde 0-29, amarillo 30-59, rojo 60-100).
"""

from __future__ import annotations

from roadguard.tipos import Evento, MetadatosVideo, PuntajeRiesgo, Track


class AnotadorVideo:
    def __init__(self, ruta_salida: str, metadatos: MetadatosVideo) -> None:
        raise NotImplementedError("RF11: abrir escritor MP4")

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
        raise NotImplementedError("RF11: dibujo y escritura de cuadro")

    def cerrar(self) -> None:
        """Cierra el archivo de salida de forma segura (Paso 6)."""
        raise NotImplementedError("Paso 6: cierre seguro del MP4")
