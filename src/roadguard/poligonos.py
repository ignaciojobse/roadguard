"""Geometria plana compartida: poligonos en coordenadas de imagen."""

from __future__ import annotations


def area_poligono(poligono: list[tuple[float, float]]) -> float:
    """Area absoluta por la formula del zapato."""
    s = 0.0
    n = len(poligono)
    for i in range(n):
        x1, y1 = poligono[i]
        x2, y2 = poligono[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def punto_en_poligono(p: tuple[float, float], poligono: list[tuple[float, float]]) -> bool:
    """Ray casting; los puntos sobre el borde cuentan como dentro."""
    x, y = p
    n = len(poligono)
    dentro = False
    for i in range(n):
        x1, y1 = poligono[i]
        x2, y2 = poligono[(i + 1) % n]
        if _sobre_segmento(p, (x1, y1), (x2, y2)):
            return True
        if (y1 > y) != (y2 > y):
            x_int = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_int:
                dentro = not dentro
    return dentro


def _sobre_segmento(p, a, b, tol: float = 1e-9) -> bool:
    cruz = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    if abs(cruz) > tol * max(1.0, abs(b[0] - a[0]) + abs(b[1] - a[1])):
        return False
    return (
        min(a[0], b[0]) - tol <= p[0] <= max(a[0], b[0]) + tol
        and min(a[1], b[1]) - tol <= p[1] <= max(a[1], b[1]) + tol
    )
