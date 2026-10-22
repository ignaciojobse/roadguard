"""Genera los YAML calibrados de las secuencias UA-DETRAC de la demo (M3).

Uso, desde la raiz del repo:

    python scripts/calibrar_ua_detrac.py

Escribe `configs/<secuencia>.yaml` y, si estan los cuadros en
`datos/ua-detrac/cuadros/<secuencia>/`, una imagen de verificacion en
`datos/ua-detrac/calibracion/<secuencia>.png` con la rejilla metrica, los
carriles y los puntos usados.

Los puntos de imagen se midieron sobre los cuadros 1, 300, 900 y 1150 de
cada secuencia, detectando los trazos blancos (top-hat sobre el gris) y
promediando los extremos que coinciden entre cuadros. Ver el PRD de datos y
evaluacion, seccion 7, y el ROADMAP para el estado de cada secuencia.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from roadguard.m1_ingesta.config import configuracion_desde_dict  # noqa: E402
from roadguard.m3_geometria.calibracion import (  # noqa: E402
    LineaDiscontinua,
    ResultadoCalibracion,
    calibrar_lineas,
    carriles_desde_metros,
    posiciones_trazos,
    proyectar_a_imagen,
)

TAMANO = (960, 540)

SECUENCIAS = {
    "MVI_39271": {
        "descripcion": (
            "UA-DETRAC prueba, dia soleado, camara fija. Calzada cercana (entre el "
            "paradero de buses y el bandejon); el trafico avanza de derecha a izquierda, "
            "acercandose a la camara."
        ),
        # Linea discontinua inferior (junto al bandejon) y superior, cada una con
        # dos trazos medidos en el sentido de avance: lejano (derecha) a cercano.
        "lineas": [
            ([(637, 338), (543, 361), (349, 410), (161, 455)], 0.0),
            ([(560, 328), (463, 348), (255, 396), (69, 435)], 3.5),
        ],
        # GB 5768.3-2009, via de 60 km/h o mas: 6 m de trazo y 9 m de hueco.
        "trazo": 6.0,
        "hueco": 9.0,
        # Bordes laterales en metros: borde del bandejon, las dos lineas, un
        # carril estandar mas y la vereda del paradero.
        "bordes": [-3.3, 0.0, 3.5, 7.0, 13.2],
        # Tramo longitudinal donde los trazos todavia se distinguen.
        "x": (-25.0, 25.0),
    },
}


def calibrar(nombre: str) -> tuple[dict, ResultadoCalibracion]:
    s = SECUENCIAS[nombre]
    posiciones = posiciones_trazos(len(s["lineas"][0][0]) // 2, s["trazo"], s["hueco"])
    lineas = [LineaDiscontinua(pts, posiciones, lateral) for pts, lateral in s["lineas"]]
    r = calibrar_lineas(lineas, TAMANO)
    x0, x1 = s["x"]
    carriles = carriles_desde_metros(r.homografia, x0, x1, s["bordes"])
    region = proyectar_a_imagen(
        r.homografia,
        [(x0, s["bordes"][0]), (x1, s["bordes"][0]), (x1, s["bordes"][-1]), (x0, s["bordes"][-1])],
    )
    datos = {
        "region_interes": [[round(u, 1), round(v, 1)] for u, v in region],
        "carriles": [
            {"indice": c.indice, "poligono": [list(p) for p in c.poligono]} for c in carriles
        ],
        "homografia": {
            "puntos_imagen": [list(p) for p in r.homografia.puntos_imagen],
            "puntos_camino": [list(p) for p in r.homografia.puntos_camino],
        },
    }
    return datos, r


def escribir_yaml(nombre: str, datos: dict, r: ResultadoCalibracion) -> Path:
    s = SECUENCIAS[nombre]
    plantilla = (RAIZ / "configs" / "camara_ejemplo.yaml").read_text(encoding="utf-8")
    cola = plantilla[plantilla.index("# Clases vehiculares") :]

    def puntos(lista, sangria):
        return "\n".join(f"{sangria}- [{p[0]:g}, {p[1]:g}]" for p in lista)

    carriles = "\n".join(
        f"  - indice: {c['indice']}\n    poligono:\n{puntos(c['poligono'], '      ')}"
        for c in datos["carriles"]
    )
    texto = f"""# Configuracion de camara de RoadGuard (RF1): {nombre}.
#
# Generado por scripts/calibrar_ua_detrac.py; no editar a mano, cambiar los
# puntos en el script y volver a generarlo.
#
# Calibracion (M3, RF4): homografia desde dos lineas discontinuas de
# {s['trazo']:g} m de trazo y {s['hueco']:g} m de hueco, separadas por un carril de
# {s['lineas'][1][1] - s['lineas'][0][1]:g} m. Ejes: x en el sentido de avance, y lateral, en metros.
#   Error de reproyeccion: RMSE {r.rmse:.2f} m, maximo {r.error_maximo:.2f} m.
#   Desfase entre los trazos de las dos lineas: {r.desfases[1]:.2f} m.
#   Camara implicita: focal {r.focal_px:.0f} px, inconsistencia {r.inconsistencia:.2f}.
# Estado de cada dato:
#   Confirmada: escala longitudinal (predice los trazos lejanos a ~5 px y da
#     60 km/h para un auto del cuadro 1 al 11).
#   Candidata a validar: ancho de carril de 3,5 m (CJJ 37-2012; la camara
#     admite entre 3,0 y 3,5 m) y el carril junto al paradero, sin linea visible.
# Los umbrales NO constituyen limites legales (seccion 1.1).

camara:
  nombre: {nombre}
  descripcion: >-
    {s['descripcion']}

# Region de interes: poligono en coordenadas de imagen (px), x de {s['x'][0]:g} a
# {s['x'][1]:g} m y todo el ancho de la calzada.
region_interes:
{puntos(datos['region_interes'], '  ')}

# Carriles: poligonos en px, construidos desde sus bordes en metros
# {s['bordes']}. Carril 0 junto al bandejon.
carriles:
{carriles}

# Correspondencias imagen <-> camino (metros).
homografia:
  puntos_imagen:
{puntos(datos['homografia']['puntos_imagen'], '    ')}
  puntos_camino:
{puntos(datos['homografia']['puntos_camino'], '    ')}

{cola}"""
    ruta = RAIZ / "configs" / f"{nombre}.yaml"
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def imagen_de_verificacion(nombre: str, datos: dict, r: ResultadoCalibracion) -> None:
    import cv2

    cuadros = sorted((RAIZ / "datos" / "ua-detrac" / "cuadros" / nombre).glob("img*.jpg"))
    if not cuadros:
        return
    s = SECUENCIAS[nombre]
    im = cv2.imread(str(cuadros[0]))
    x0, x1 = s["x"]
    for x in np.arange(np.ceil(x0 / 5) * 5, x1 + 0.1, 5.0):
        pts = proyectar_a_imagen(r.homografia, [(x, y) for y in (s["bordes"][0], s["bordes"][-1])])
        cv2.line(im, *[tuple(np.int32(p)) for p in pts], (255, 200, 0), 1)
    for c in datos["carriles"]:
        cv2.polylines(im, [np.int32(c["poligono"])], True, (0, 255, 255), 1)
    for p in datos["homografia"]["puntos_imagen"]:
        cv2.circle(im, tuple(np.int32(p)), 4, (0, 0, 255), -1)
    destino = RAIZ / "datos" / "ua-detrac" / "calibracion"
    destino.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(destino / f"{nombre}.png"), im)


def main() -> None:
    for nombre in SECUENCIAS:
        datos, r = calibrar(nombre)
        ruta = escribir_yaml(nombre, datos, r)
        from roadguard.m1_ingesta.config import cargar_configuracion

        cargar_configuracion(str(ruta))  # valida el YAML con M1
        imagen_de_verificacion(nombre, datos, r)
        print(
            f"{nombre}: {ruta.relative_to(RAIZ)}  RMSE {r.rmse:.2f} m  "
            f"desfase {r.desfases[1]:.2f} m  focal {r.focal_px:.0f} px"
        )


if __name__ == "__main__":
    main()
