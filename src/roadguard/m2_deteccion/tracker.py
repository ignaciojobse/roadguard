"""M2 - Seguimiento multiobjeto con ByteTrack (RF3).

Implementacion propia del algoritmo de ByteTrack (Zhang et al., 2022) sobre
NumPy y SciPy, para que el seguimiento sea independiente del detector y
se pueda probar con detecciones sinteticas:

1. Prediccion de todos los tracks con un filtro de Kalman de velocidad
   constante en (cx, cy, aspecto, alto).
2. Primera asociacion: detecciones de confianza alta contra tracks activos y
   perdidos, por IoU ponderado por confianza.
3. Segunda asociacion: detecciones de confianza baja contra los tracks
   activos que quedaron sin pareja (recupera vehiculos parcialmente
   ocluidos).
4. Tracks nuevos sin confirmar: se confirman si vuelven a asociarse en el
   cuadro siguiente.
5. Tracks no asociados pasan a perdidos y se eliminan tras `buffer`
   segundos sin observacion. Mientras estan perdidos conservan su ID, lo que
   cubre las oclusiones breves (RF3).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

import numpy as np
from scipy.optimize import linear_sum_assignment

from roadguard.tipos import Caja, Deteccion, Track

_SEGUIDO, _PERDIDO, _ELIMINADO = "seguido", "perdido", "eliminado"


class _Kalman:
    """Filtro de Kalman en (cx, cy, a, h, vcx, vcy, va, vh), como ByteTrack."""

    _peso_pos = 1.0 / 20
    _peso_vel = 1.0 / 160

    def __init__(self) -> None:
        self.F = np.eye(8)
        for i in range(4):
            self.F[i, 4 + i] = 1.0
        self.H = np.eye(4, 8)

    def iniciar(self, z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        media = np.r_[z, np.zeros(4)]
        h = z[3]
        std = [
            2 * self._peso_pos * h, 2 * self._peso_pos * h, 1e-2, 2 * self._peso_pos * h,
            10 * self._peso_vel * h, 10 * self._peso_vel * h, 1e-5, 10 * self._peso_vel * h,
        ]
        return media, np.diag(np.square(std))

    def predecir(self, media: np.ndarray, cov: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        h = media[3]
        std = [
            self._peso_pos * h, self._peso_pos * h, 1e-2, self._peso_pos * h,
            self._peso_vel * h, self._peso_vel * h, 1e-5, self._peso_vel * h,
        ]
        Q = np.diag(np.square(std))
        return self.F @ media, self.F @ cov @ self.F.T + Q

    def corregir(self, media: np.ndarray, cov: np.ndarray, z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        h = media[3]
        R = np.diag(np.square([self._peso_pos * h, self._peso_pos * h, 1e-1, self._peso_pos * h]))
        S = self.H @ cov @ self.H.T + R
        K = np.linalg.solve(S, (cov @ self.H.T).T).T
        media = media + K @ (z - self.H @ media)
        cov = cov - K @ S @ K.T
        return media, cov


def _caja_a_xyah(c: Caja) -> np.ndarray:
    w, h = c.x2 - c.x1, c.y2 - c.y1
    return np.array([c.x1 + w / 2, c.y1 + h / 2, w / max(h, 1e-6), h], dtype=float)


def _xyah_a_caja(m: np.ndarray) -> Caja:
    cx, cy, a, h = m[:4]
    w = a * h
    return Caja(float(cx - w / 2), float(cy - h / 2), float(cx + w / 2), float(cy + h / 2))


class _Pista:
    def __init__(self, det: Deteccion, kalman: _Kalman, t: float) -> None:
        self.id: Optional[int] = None
        self.media, self.cov = kalman.iniciar(_caja_a_xyah(det.caja))
        self.estado = _SEGUIDO
        self.confirmada = False
        self.confianza = det.confianza
        self.t_ultimo = t
        self.votos: dict[str, float] = defaultdict(float)
        self.votos[det.clase] += det.confianza

    @property
    def caja(self) -> Caja:
        return _xyah_a_caja(self.media)

    @property
    def clase(self) -> str:
        return max(self.votos.items(), key=lambda kv: kv[1])[0]

    def actualizar(self, det: Deteccion, kalman: _Kalman, t: float) -> None:
        self.media, self.cov = kalman.corregir(self.media, self.cov, _caja_a_xyah(det.caja))
        self.estado = _SEGUIDO
        self.confirmada = True
        self.confianza = det.confianza
        self.t_ultimo = t
        self.votos[det.clase] += det.confianza


def _iou(a: list[Caja], b: list[Caja]) -> np.ndarray:
    if not a or not b:
        return np.zeros((len(a), len(b)))
    A = np.array([[c.x1, c.y1, c.x2, c.y2] for c in a])
    B = np.array([[c.x1, c.y1, c.x2, c.y2] for c in b])
    ix1 = np.maximum(A[:, None, 0], B[None, :, 0])
    iy1 = np.maximum(A[:, None, 1], B[None, :, 1])
    ix2 = np.minimum(A[:, None, 2], B[None, :, 2])
    iy2 = np.minimum(A[:, None, 3], B[None, :, 3])
    inter = np.clip(ix2 - ix1, 0, None) * np.clip(iy2 - iy1, 0, None)
    area_a = (A[:, 2] - A[:, 0]) * (A[:, 3] - A[:, 1])
    area_b = (B[:, 2] - B[:, 0]) * (B[:, 3] - B[:, 1])
    union = area_a[:, None] + area_b[None, :] - inter
    return np.where(union > 0, inter / np.maximum(union, 1e-12), 0.0)


def _asociar(
    pistas: list[_Pista], dets: list[Deteccion], umbral_costo: float, fusionar: bool
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Asignacion hungara sobre costo 1 - IoU (opcionalmente * confianza)."""
    if not pistas or not dets:
        return [], list(range(len(pistas))), list(range(len(dets)))
    iou = _iou([p.caja for p in pistas], [d.caja for d in dets])
    if fusionar:
        iou = iou * np.array([d.confianza for d in dets])[None, :]
    costo = 1.0 - iou
    costo_resuelto = np.where(costo > umbral_costo, 1e6, costo)
    filas, cols = linear_sum_assignment(costo_resuelto)
    pares = [(r, c) for r, c in zip(filas, cols) if costo[r, c] <= umbral_costo]
    usadas_p = {r for r, _ in pares}
    usadas_d = {c for _, c in pares}
    return (
        pares,
        [i for i in range(len(pistas)) if i not in usadas_p],
        [j for j in range(len(dets)) if j not in usadas_d],
    )


class SeguidorByteTrack:
    """Asigna un ID persistente a cada vehiculo (RF3).

    Debe mantener el ID mientras el vehiculo sea observable, incluyendo
    oclusiones breves, y administrar apariciones/desapariciones (M2).
    Asocia por confianza, movimiento y solapamiento.

    Parametros por defecto: los del articulo original de ByteTrack
    (umbral alto 0,5; nuevo track 0,6; asociaciones 0,8 / 0,5 / 0,7) con
    `buffer` expresado en segundos (30 cuadros a 30 FPS).
    """

    def __init__(
        self,
        fps: float,
        umbral_alto: float = 0.5,
        umbral_bajo: float = 0.1,
        umbral_nuevo: float = 0.6,
        buffer: float = 1.0,
        costo_max_primera: float = 0.8,
        costo_max_segunda: float = 0.5,
        costo_max_sin_confirmar: float = 0.7,
    ) -> None:
        if fps <= 0:
            raise ValueError("fps debe ser positivo")
        self.fps = fps
        self.umbral_alto = umbral_alto
        self.umbral_bajo = umbral_bajo
        self.umbral_nuevo = umbral_nuevo
        self.buffer = buffer
        self.costo_max_primera = costo_max_primera
        self.costo_max_segunda = costo_max_segunda
        self.costo_max_sin_confirmar = costo_max_sin_confirmar
        self._kalman = _Kalman()
        self._pistas: list[_Pista] = []
        self._siguiente_id = 1
        self._primer_cuadro = True

    def actualizar(
        self, detecciones: list[Deteccion], cuadro: int, t: float
    ) -> list[Track]:
        """Actualiza el estado del tracker y devuelve los tracks vivos."""
        k = self._kalman
        altas = [d for d in detecciones if d.confianza >= self.umbral_alto]
        bajas = [d for d in detecciones if self.umbral_bajo <= d.confianza < self.umbral_alto]

        for p in self._pistas:
            if p.estado != _SEGUIDO:
                p.media[7] = 0.0  # ByteTrack: sin crecimiento de alto en perdidos
            p.media, p.cov = k.predecir(p.media, p.cov)

        confirmadas = [p for p in self._pistas if p.confirmada]
        sin_confirmar = [p for p in self._pistas if not p.confirmada]

        # 1) confianza alta contra tracks activos y perdidos
        pares, libres_p, libres_d = _asociar(confirmadas, altas, self.costo_max_primera, True)
        for i, j in pares:
            confirmadas[i].actualizar(altas[j], k, t)

        # 2) confianza baja contra activos sin pareja (oclusion parcial)
        restantes = [confirmadas[i] for i in libres_p if confirmadas[i].estado == _SEGUIDO]
        pares2, libres2, _ = _asociar(restantes, bajas, self.costo_max_segunda, False)
        for i, j in pares2:
            restantes[i].actualizar(bajas[j], k, t)
        for i in libres2:
            restantes[i].estado = _PERDIDO

        # 3) tracks nuevos sin confirmar contra altas sobrantes
        altas_libres = [altas[j] for j in libres_d]
        pares3, libres3, libres_d3 = _asociar(
            sin_confirmar, altas_libres, self.costo_max_sin_confirmar, True
        )
        for i, j in pares3:
            sin_confirmar[i].actualizar(altas_libres[j], k, t)
            sin_confirmar[i].id = self._nuevo_id()
        for i in libres3:
            sin_confirmar[i].estado = _ELIMINADO

        # 4) apariciones
        for j in libres_d3:
            det = altas_libres[j]
            if det.confianza < self.umbral_nuevo:
                continue
            pista = _Pista(det, k, t)
            if self._primer_cuadro:
                pista.confirmada = True
                pista.id = self._nuevo_id()
            self._pistas.append(pista)

        # 5) desapariciones
        for p in self._pistas:
            if p.estado == _PERDIDO and t - p.t_ultimo > self.buffer:
                p.estado = _ELIMINADO
        self._pistas = [p for p in self._pistas if p.estado != _ELIMINADO]
        self._primer_cuadro = False

        salida: list[Track] = []
        for p in self._pistas:
            if p.confirmada and p.estado == _SEGUIDO and p.t_ultimo == t:
                caja = p.caja
                salida.append(
                    Track(
                        id_vehiculo=p.id,
                        cuadro=cuadro,
                        t=t,
                        clase=p.clase,
                        confianza=p.confianza,
                        caja=caja,
                        punto_calzada_px=caja.punto_calzada,
                    )
                )
        return salida

    def _nuevo_id(self) -> int:
        i = self._siguiente_id
        self._siguiente_id += 1
        return i
