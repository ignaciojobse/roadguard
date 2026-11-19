"""Orquestacion geometrica M3 por ejecucion y por cuadro."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional

from roadguard.m3_geometria.apoyo import estimar_apoyo_longitudinal
from roadguard.m3_geometria.carriles import DetectorCambioCarril
from roadguard.m3_geometria.homografia import ProyectorCamino
from roadguard.m3_geometria.movimiento import CompensadorCamara, MovimientoCamara
from roadguard.m3_geometria.relaciones import calcular_relaciones
from roadguard.m3_geometria.trayectorias import HistorialCausal
from roadguard.poligonos import punto_en_poligono
from roadguard.tipos import (
    Carril, CambioCarril, Configuracion, Deteccion, EstadoCinematico, Relacion, Track,
)


@dataclass
class DiagnosticosGeometria:
    validos: int = 0
    invalidos: int = 0
    residuo_maximo: Optional[float] = None
    fallo_actual: Optional[str] = None
    ultimo_fallo: Optional[str] = None
    fallos_apoyo: int = 0


@dataclass
class ResultadoGeometria:
    tracks: list[Track]
    estados: list[EstadoCinematico]
    relaciones: list[Relacion]
    cambios: list[CambioCarril]
    carriles_actuales: list[Carril]
    movimiento: Optional[MovimientoCamara]
    diagnosticos: DiagnosticosGeometria
    reinicios: list[int] = field(default_factory=list)
    observaciones_baja_confianza: int = 0
    cajas_recortadas: int = 0


class ProcesadorGeometria:
    """Estado M3 aislado a una ejecucion; detector/tracker permanecen en M2."""

    def __init__(self, cfg: Configuracion, fps: float, *,
                 compensar_camara: Optional[bool] = None,
                 metodo_apoyo: Optional[str] = None) -> None:
        compensar_camara = (cfg.procesamiento_geometria.compensar_camara
                            if compensar_camara is None else compensar_camara)
        metodo_apoyo = cfg.procesamiento_geometria.metodo_apoyo if metodo_apoyo is None else metodo_apoyo
        if metodo_apoyo not in {"centro_inferior", "longitudinal"}:
            raise ValueError("metodo_apoyo debe ser 'centro_inferior' o 'longitudinal'")
        self.cfg = cfg
        self.proyector = ProyectorCamino(cfg.homografia)
        if metodo_apoyo == "longitudinal" and not self.proyector.disponible:
            raise ValueError("El apoyo longitudinal requiere una homografia/proyector disponible")
        self.metodo_apoyo = metodo_apoyo
        self.compensador = CompensadorCamara(cfg.region_interes) if compensar_camara else None
        self.historial = HistorialCausal(fps, self.proyector, cfg.carriles,
                                         confianza_min_carril=cfg.confianza_min_carril)
        self.cambios_carril = DetectorCambioCarril(0.0, cfg.permanencia_cambio_carril)
        self.diagnosticos = DiagnosticosGeometria()
        self.movimiento: Optional[MovimientoCamara] = None
        self.carriles_actuales = list(cfg.carriles)

    def preparar_cuadro(self, imagen: object) -> None:
        if self.compensador is None:
            self.movimiento = None
            self.carriles_actuales = list(self.cfg.carriles)
            return
        self.movimiento = self.compensador.actualizar(imagen)
        if self.movimiento.valido:
            self.diagnosticos.validos += 1
            self.diagnosticos.fallo_actual = None
            residuo = self.movimiento.residuo_mediano
            if residuo is not None:
                d = self.diagnosticos
                d.residuo_maximo = max(d.residuo_maximo or 0.0, residuo)
            self.carriles_actuales = self._transformar_carriles(self.movimiento)
        else:
            self.diagnosticos.invalidos += 1
            self.diagnosticos.fallo_actual = self.movimiento.motivo or "transformacion no disponible"
            self.diagnosticos.ultimo_fallo = self.diagnosticos.fallo_actual
            self.carriles_actuales = []

    def filtrar_detecciones(self, detecciones: list[Deteccion]) -> list[Deteccion]:
        """Gate conservador: interseccion del bbox con ROI actual; no decide elegibilidad."""
        if self.compensador is not None and (self.movimiento is None or not self.movimiento.valido):
            return detecciones
        roi = self.cfg.region_interes
        if self.movimiento is not None:
            roi_actual = self.movimiento.transformar_puntos_referencia_a_actual(roi)
            if roi_actual is None:
                return detecciones
            roi = roi_actual
        x_min = min(x for x, _ in roi)
        x_max = max(x for x, _ in roi)
        y_min = min(y for _, y in roi)
        y_max = max(y for _, y in roi)
        salida = []
        for d in detecciones:
            x1, y1, x2, y2 = d.caja.x1, d.caja.y1, d.caja.x2, d.caja.y2
            # Rectangular envelope overlap is deliberately conservative. The
            # definitive support-point membership check happens in M3 below.
            if x2 >= x_min and x1 <= x_max and y2 >= y_min and y1 <= y_max:
                salida.append(d)
        return salida

    def procesar_tracks(self, tracks: list[Track], cuadro: int, t: float,
                        imagen: object) -> ResultadoGeometria:
        disponibles = self.compensador is None or (self.movimiento is not None and self.movimiento.valido)
        self.cambios_carril.interrumpir_ausentes({x.id_vehiculo for x in tracks})
        estados, cambios, tracks_salida = [], [], []
        alto, ancho = imagen.shape[:2]
        for track in tracks:
            punto = track.punto_calzada_px
            if disponibles and self.movimiento is not None:
                punto = self.movimiento.transformar_punto_actual_a_referencia(punto)
            if disponibles and self.metodo_apoyo == "longitudinal":
                punto = estimar_apoyo_longitudinal(
                    track.caja, self.proyector,
                    self.movimiento.actual_a_referencia if self.movimiento is not None else None)
                if punto is None:
                    self.diagnosticos.fallos_apoyo += 1
            roi_valido = punto is not None and punto_en_poligono(punto, self.cfg.region_interes)
            estado = self.historial.actualizar(
                track, (ancho, alto), punto_referencia=punto,
                geometria_disponible=bool(disponibles and roi_valido))
            punto_actual = None
            if disponibles and punto is not None:
                punto_actual = self.movimiento.transformar_puntos_referencia_a_actual([punto])[0] if self.movimiento else punto
            tracks_salida.append(replace(track, punto_calzada_px=punto_actual) if punto_actual else track)
            estados.append(estado)
            cambio = self.cambios_carril.actualizar(track.id_vehiculo, estado.carril, t, estado.confianza_carril)
            if cambio is not None:
                cambios.append(cambio)
        for ident in self.historial.purgar(t):
            self.cambios_carril.olvidar(ident)
        if not disponibles:
            cambios = []
        relaciones = calcular_relaciones(estados, cuadro, t)
        return ResultadoGeometria(tracks_salida, estados, relaciones, cambios, list(self.carriles_actuales),
                                  self.movimiento, replace(self.diagnosticos), list(self.historial.reinicios),
                                  self.historial.observaciones_baja_confianza, self.historial.cajas_recortadas)

    def _transformar_carriles(self, movimiento: MovimientoCamara) -> list[Carril]:
        salida = []
        for carril in self.cfg.carriles:
            puntos = movimiento.transformar_puntos_referencia_a_actual(carril.poligono)
            if puntos is None:
                return []
            salida.append(Carril(carril.indice, puntos))
        return salida
