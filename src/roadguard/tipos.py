"""Contrato de datos compartido entre los modulos M1-M6 de RoadGuard.

Todas las estructuras llevan marca temporal e ID de vehiculo, segun la
seccion 4.2 de la propuesta ("Los modulos se comunican mediante estructuras
de datos con marca temporal e ID de vehiculo").

Convencion de tiempo: `t` siempre esta en SEGUNDOS desde el inicio del video
y se deriva de los FPS reales del archivo. Las ventanas temporales de las
reglas (2 s, 5 s, 10 s) se evaluan sobre `t`, nunca sobre conteo de cuadros.

Convencion de unidades: distancias en metros, velocidades en m/s, tiempos en
segundos. Las magnitudes metricas son Optional porque M1 desactiva las
metricas basadas en distancia cuando falta calibracion (RF4, M1, Paso 5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# M1 - Ingesta y configuracion
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MetadatosVideo:
    """RF1. Resultado de validar el MP4 de entrada."""

    ruta: str
    ancho: int
    alto: int
    fps: float
    n_cuadros: int
    codec: str


@dataclass(frozen=True)
class Umbrales:
    """Umbrales configurables del motor de reglas (seccion 2.1, RF7-RF11).

    Los valores por defecto son los declarados en la propuesta. Son
    parametros, no limites legales (seccion 1.1).
    """

    # RF7 - Cercania peligrosa
    cercania_velocidad_min: float = 5.0      # m/s
    cercania_thw_max: float = 1.5            # s
    cercania_persistencia: float = 2.0       # s

    # RF8 - Zigzag
    zigzag_cambios_min: int = 2              # cambios completos
    zigzag_ventana: float = 10.0             # s

    # RF9 - Corte de carril
    corte_ventana_post_cambio: float = 2.0   # s
    corte_thw_max: float = 1.5               # s
    corte_ttc_max: float = 3.0               # s

    # RF10 - Puntaje de riesgo
    aporte_cercania: int = 40
    aporte_zigzag: int = 35
    aporte_corte: int = 50
    puntaje_maximo: int = 100
    vigencia_aporte: float = 5.0             # s

    # RF11 - Bandas de color
    banda_verde_max: int = 29
    banda_amarillo_max: int = 59


@dataclass(frozen=True)
class Homografia:
    """RF4. Correspondencias imagen <-> plano del camino (M1, M3).

    `puntos_imagen` y `puntos_camino` son listas paralelas de al menos 4
    pares. Si no se entregan, `disponible` es False y M1 debe desactivar
    toda metrica basada en distancia (Paso 5).
    """

    puntos_imagen: list[tuple[float, float]] = field(default_factory=list)
    puntos_camino: list[tuple[float, float]] = field(default_factory=list)

    @property
    def disponible(self) -> bool:
        return len(self.puntos_imagen) >= 4 and len(self.puntos_imagen) == len(
            self.puntos_camino
        )


@dataclass(frozen=True)
class Carril:
    """Limite de carril como poligono en coordenadas de imagen (RF4)."""

    indice: int
    poligono: list[tuple[float, float]]


@dataclass(frozen=True)
class Configuracion:
    """RF1. Configuracion de camara validada y normalizada por M1.

    Contiene region de interes, limites de carril, correspondencias para
    rectificacion de perspectiva, clases vehiculares y umbrales
    (seccion 1.3).
    """

    region_interes: list[tuple[float, float]]
    carriles: list[Carril]
    homografia: Homografia
    clases: list[str]
    umbrales: Umbrales
    confianza_min_deteccion: float = 0.25
    confianza_min_carril: float = 0.60


# ---------------------------------------------------------------------------
# M2 - Deteccion y seguimiento vehicular
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Caja:
    """Caja delimitadora en pixeles, esquina superior izq. / inferior der."""

    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def punto_calzada(self) -> tuple[float, float]:
        """Punto de contacto con la calzada: centro del borde inferior (M2)."""
        return ((self.x1 + self.x2) / 2.0, self.y2)


@dataclass(frozen=True)
class Deteccion:
    """RF2. Salida del detector antes de asociar identidad."""

    clase: str
    confianza: float
    caja: Caja


@dataclass(frozen=True)
class Track:
    """RF2, RF3. Salida de M2 por vehiculo y por cuadro.

    `id_vehiculo` es el ID persistente de ByteTrack y es la clave que une
    todas las estructuras posteriores.
    """

    id_vehiculo: int
    cuadro: int
    t: float
    clase: str
    confianza: float
    caja: Caja
    punto_calzada_px: tuple[float, float]


# ---------------------------------------------------------------------------
# M3 - Geometria vial y trayectorias
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EstadoCinematico:
    """RF4, RF5. Estado causal de un vehiculo en el instante `t`.

    Causalidad (RF5): solo puede construirse con informacion disponible hasta
    `t`. Nunca con cuadros futuros.

    `x_camino` es la coordenada longitudinal (sentido de avance) y `y_camino`
    la lateral, ambas en metros sobre el plano del camino. Son None cuando
    `calibrado` es False.
    """

    id_vehiculo: int
    cuadro: int
    t: float
    x_camino: Optional[float]
    y_camino: Optional[float]
    velocidad: Optional[float]
    carril: Optional[int]
    confianza_carril: float
    calibrado: bool


@dataclass(frozen=True)
class CambioCarril:
    """Cambio de carril COMPLETO y confirmado (Paso 4).

    Las oscilaciones sobre la linea y los cruces breves no generan esta
    estructura. `t_confirmacion` >= `t_cruce`: la diferencia es la latencia
    de decision introducida por la confirmacion de permanencia estable.
    """

    id_vehiculo: int
    carril_origen: int
    carril_destino: int
    t_cruce: float
    t_confirmacion: float


@dataclass(frozen=True)
class Relacion:
    """RF6. Relacion longitudinal predecesor/seguidor dentro de un carril.

    THW = distancia / velocidad del seguidor (M3).
    TTC solo se calcula con tasa de cierre positiva (M3); en caso contrario
    queda en None.
    """

    id_seguidor: int
    id_predecesor: Optional[int]
    cuadro: int
    t: float
    carril: Optional[int]
    distancia: Optional[float]
    thw: Optional[float]
    ttc: Optional[float]


# ---------------------------------------------------------------------------
# M4 - Motor de reglas y riesgo
# ---------------------------------------------------------------------------

class Regla(str, Enum):
    """Las tres conductas definidas en RF7, RF8 y RF9."""

    CERCANIA = "cercania_peligrosa"
    ZIGZAG = "zigzag"
    CORTE = "corte_de_carril"


class NivelRiesgo(str, Enum):
    """RF11. Bandas de color del puntaje de riesgo."""

    VERDE = "verde"
    AMARILLO = "amarillo"
    ROJO = "rojo"


@dataclass(frozen=True)
class Evento:
    """RF12 y seccion 2.5 (trazabilidad).

    Cada evento debe incluir vehiculo, intervalo, regla, variables medidas,
    umbrales y puntaje, para que la alerta sea auditable (seccion 1.4).

    `variables` guarda los valores que activaron la regla (p. ej. velocidad,
    distancia, THW, TTC) y `umbrales` los limites vigentes al evaluarla.
    """

    id_vehiculo: int
    regla: Regla
    t_inicio: float
    t_fin: float
    variables: dict[str, Optional[float]]
    umbrales: dict[str, float]
    aporte_puntaje: int
    id_relacionado: Optional[int] = None  # predecesor o vehiculo cortado


@dataclass(frozen=True)
class PuntajeRiesgo:
    """RF10, RF11. Puntaje temporal de un vehiculo en el instante `t`."""

    id_vehiculo: int
    t: float
    puntaje: int
    nivel: NivelRiesgo


# ---------------------------------------------------------------------------
# M5 / M6 - Salidas y metricas
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResumenVehiculo:
    """RF12. Una entrada del resumen JSON por vehiculo."""

    id_vehiculo: int
    clase: str
    t_primera_aparicion: float
    t_ultima_aparicion: float
    n_eventos: dict[str, int]
    puntaje_maximo: int
    nivel_maximo: NivelRiesgo


@dataclass(frozen=True)
class ResumenEjecucion:
    """RF12 y Paso 6: evidencia de reproducibilidad de la corrida."""

    video: str
    configuracion: str
    version_modelo: str
    fps_video: float
    fps_procesamiento: float
    n_cuadros_procesados: int
    calibrado: bool
    advertencias: list[str]
