"""Genera los YAML calibrados de las secuencias UA-DETRAC de la demo (M3).

Uso, desde la raiz del repo:

    python scripts/calibrar_ua_detrac.py                       # todas
    python scripts/calibrar_ua_detrac.py MVI_40243 MVI_40712   # solo esas

Escribe `configs/<secuencia>.yaml` y, si estan los cuadros en
`datos/ua-detrac/cuadros/<secuencia>/`, una imagen de verificacion en
`datos/ua-detrac/calibracion/<secuencia>.png` con la rejilla metrica, los
carriles y los puntos usados.

Los puntos de imagen se midieron detectando los trazos blancos (top-hat
sobre el gris) y promediando los extremos que coinciden entre cuadros: en
MVI_39271 sobre los cuadros 1, 300, 900 y 1150; en MVI_40714 sobre los
cuadros 1100, 1130 y 1150, cuando la cola ya se disolvio. Ver el PRD de
datos y evaluacion, seccion 7, y el ROADMAP para el estado de cada secuencia.
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
        "carril_0": "junto al bandejon",
        "notas": [
            "Confirmada: escala longitudinal (predice los trazos lejanos a ~5 px y da",
            "  60 km/h para un auto del cuadro 1 al 11).",
            "Candidata a validar: ancho de carril de 3,5 m (CJJ 37-2012; la camara",
            "  admite entre 3,0 y 3,5 m) y el carril junto al paradero, sin linea visible.",
        ],
    },
    "MVI_40714": {
        "descripcion": (
            "UA-DETRAC prueba, nublado, camara fija sobre una pasarela. Calzada "
            "izquierda, entre la vereda y la baranda central; el trafico avanza hacia "
            "la camara (de arriba hacia abajo en la imagen), en cola casi detenida "
            "hasta el cuadro ~1000."
        ),
        # L1: linea discontinua a la izquierda del carril de viraje (junto a la
        # baranda). Se ve un trazo completo (y 270-308) y el inicio del
        # siguiente (y 394); el resto sale de la imagen. S: linea continua al
        # otro lado del carril con flecha. Las dos son rectas con rms 0,25 px
        # entre y 270 y 540 y se cortan en el punto de fuga (514, -14).
        # Como S es continua, sus puntos se toman en las mismas filas que los
        # de L1: con la camara sin giro, las filas de la imagen son
        # transversales al camino, y la calibracion lo confirma (desfase de
        # S de 0,15 m). La linea R1, a la derecha de L1, no sirve: diverge
        # hacia la camara porque abre el carril de viraje.
        "lineas": [
            ([(485.9, 270.2), (482.2, 308.2), (473.7, 393.8)], 0.0),
            ([(397.3, 270.2), (381.7, 308.2), (346.6, 393.8)], 3.5),
        ],
        # Inicio y fin del trazo e inicio del siguiente. Con el punto de fuga,
        # la razon trazo/hueco en metros da 0,64: es la norma de 6 y 9 m
        # (0,67), no la de 2 y 4 m (0,5), que pondria el inicio del segundo
        # trazo 32 px mas abajo.
        "posiciones": [0.0, 6.0, 15.0],
        "fuente": "una linea continua y una discontinua",
        "trazo": 6.0,
        "hueco": 9.0,
        # Bordes laterales en metros, medidos sobre un fondo sin vehiculos
        # (mediana por pixel fuera de las cajas del XML): borde de la baranda
        # (-3,6), L1, S, la linea siguiente (6,6) y un carril estandar mas
        # hacia la vereda, donde los buses tapan las lineas. No se agrega un
        # quinto carril (hasta 13,6 m): no hay linea que lo respalde y sus
        # buses entran cortados por el borde de la imagen, lo que mueve el
        # punto de contacto de lado y dio 3 cortes de carril falsos.
        "bordes": [-3.6, 0.0, 3.5, 6.6, 10.1],
        # Desde donde la calle empieza a curvar (y ~200) hasta el borde
        # inferior de la imagen.
        "x": (-10.0, 24.0),
        "carril_0": "junto a la baranda central (viraje)",
        "verificacion": "img01130.jpg",
        "notas": [
            "Confirmada: patron de 6 m de trazo y 9 m de hueco (razon 0,64 con el",
            "  punto de fuga) y camara fisica coherente (focal 1121 px).",
            "Candidata a validar: ancho de carril de 3,5 m y el borde del carril",
            "  junto a la vereda (10,1 m), sin linea visible bajo los buses.",
        ],
    },
    "MVI_40742": {
        "descripcion": (
            "UA-DETRAC prueba, anochecer, camara fija. Calzada cercana, entre la "
            "baranda central y la baranda de la vereda; el trafico avanza de izquierda "
            "a derecha, acercandose a la camara. Buses detenidos tapan la calzada casi "
            "todo el clip."
        ),
        # Sin homografia (Paso 5): ninguna linea de esta calzada da trazos
        # repetibles entre cuadros, y las dos lineas que se ven completas son
        # continuas, asi que no hay escala longitudinal desde el pavimento. La
        # region y los carriles se trazan en pixeles como rayos desde el punto
        # de fuga comun de las lineas de la calzada (Hough sobre un fondo sin
        # vehiculos), dados por su pendiente (dy/dx) desde ese punto.
        "fuga": (-278.0, 91.0),
        # Borde bajo la baranda central (linea continua, 0,341), linea
        # continua entre los dos carriles (0,452) y baranda de la vereda
        # (0,621). Los bordes de la region se abren un poco hacia afuera
        # para no cortar el punto de contacto de los vehiculos junto a las
        # barandas. Ningun vehiculo del XML pisa la franja entre la baranda
        # central y la primera linea (pendientes 0,29 a 0,35): es banquina.
        "rayos": [0.335, 0.452, 0.625],
        "u": (0.0, 960.0),
        "carril_0": "junto a la baranda central",
        "verificacion": "img01655.jpg",
        "notas": [
            "Sin calibracion: distancia, THW y TTC no disponibles y sin eventos de",
            "  cercania ni corte (Paso 5). Se evalua percepcion y carril.",
            "Confirmada: dos carriles; los vehiculos del XML se agrupan a cada lado",
            "  de la linea continua central y ninguno pisa la banquina.",
        ],
    },
    "MVI_40243": {
        "descripcion": (
            "UA-DETRAC entrenamiento, nublado, camara fija sobre una autopista urbana. "
            "Calzada derecha, entre el bandejon central y la orilla; el trafico se aleja "
            "de la camara (de abajo hacia arriba en la imagen)."
        ),
        # Lineas discontinuas A (la primera junto al carril del bandejon) y B
        # (la siguiente), dos trazos cada una, medidos en el sentido de avance
        # (cercano a lejano) sobre un fondo sin vehiculos (mediana de 85
        # cuadros, top-hat). La tercera linea, C, no se usa para ajustar: es
        # el control independiente (cae a 7,4-7,8 m de A y sus trazos miden
        # 5,8 m con 9,5 m de hueco).
        "lineas": [
            ([(506.2, 411.2), (600.9, 319.0), (684.8, 237.8), (715.0, 208.0)], 0.0),
            ([(685.1, 410.7), (739.6, 317.4), (786.9, 236.4), (804.3, 205.6)], 3.75),
        ],
        # Autopista: 6 m de trazo y 9 m de hueco (GB 5768.3-2009) y carril de
        # 3,75 m (CJJ 37-2012, via rapida). Con 3,5 m la camara implicita no es
        # fisica cuando se agrega la linea C.
        "trazo": 6.0,
        "hueco": 9.0,
        # Linea de borde junto al bandejon (-4,1 m, medida), A, B, C y un
        # carril mas hasta la orilla, cortado por el borde de la imagen. Los
        # vehiculos del XML se agrupan en -1,7 / 1,9 / 5,5 / 8,3 m.
        "bordes": [-4.1, 0.0, 3.75, 7.5, 11.25],
        # De -5 a 70 m: a 65 km/h un auto tarda 4 s en cruzarlo. Con solo el
        # tramo de los trazos (35 m) lo cruzaba en menos de los 2 s de
        # persistencia de la cercania, y la regla nunca podia confirmarse. A
        # 70 m los carriles todavia miden ~40 px de ancho.
        "x": (-5.0, 70.0),
        "carril_0": "junto al bandejon central",
        "verificacion": "img00300.jpg",
        "notas": [
            "Confirmada: escala y patron de 6/9 m (la linea C, no usada, cae a 7,4-7,8 m",
            "  y sus trazos miden 5,8 y 9,5 m) y 63 km/h de mediana para los autos del XML.",
            "Candidata a validar: ancho de carril de 3,75 m (norma de via rapida).",
        ],
    },
    "MVI_40712": {
        "descripcion": (
            "UA-DETRAC prueba, nublado, camara fija sobre la misma pasarela que "
            "MVI_40714, con el encuadre levemente movido y trafico fluido. Calzada "
            "izquierda; el trafico avanza hacia la camara."
        ),
        # Los mismos puntos de MVI_40714 (L1 discontinua y S continua, en las
        # mismas filas), llevados a este encuadre con la homografia imagen a
        # imagen entre los dos fondos sin vehiculos (ORB + RANSAC, 228 pares,
        # error mediano 1,0 px). Se verifico que caen sobre las lineas pintadas.
        "lineas": [
            ([(488.9, 249.1), (484.7, 286.4), (475.0, 370.3)], 0.0),
            ([(400.5, 249.1), (384.6, 286.5), (348.7, 370.3)], 3.5),
        ],
        "posiciones": [0.0, 6.0, 15.0],
        "fuente": "una linea continua y una discontinua (transferidas de MVI_40714)",
        "trazo": 6.0,
        "hueco": 9.0,
        "bordes": [-3.6, 0.0, 3.5, 6.6, 10.1],
        "x": (-10.0, 24.0),
        "carril_0": "junto a la baranda central (viraje)",
        "verificacion": "img00300.jpg",
        "notas": [
            "Confirmada: misma camara que MVI_40714 (calibracion transferida con",
            "  error de registro de 1 px) y velocidades del XML coherentes con la via.",
            "Candidata a validar: ancho de carril de 3,5 m y el borde junto a la vereda.",
        ],
    },
}


def calibrar(nombre: str) -> tuple[dict, ResultadoCalibracion]:
    s = SECUENCIAS[nombre]
    posiciones = s.get("posiciones") or posiciones_trazos(
        len(s["lineas"][0][0]) // 2, s["trazo"], s["hueco"]
    )
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


def sin_calibrar(nombre: str) -> dict:
    """Region y carriles en pixeles, como rayos desde el punto de fuga."""
    s = SECUENCIAS[nombre]
    (fu, fv), (u0, u1) = s["fuga"], s["u"]

    def punto(u: float, pendiente: float) -> list[float]:
        return [round(u, 1), round(fv + pendiente * (u - fu), 1)]

    def cuadrilatero(p0: float, p1: float) -> list[list[float]]:
        return [punto(u0, p0), punto(u1, p0), punto(u1, p1), punto(u0, p1)]

    rayos = s["rayos"]
    return {
        "region_interes": cuadrilatero(rayos[0], rayos[-1]),
        "carriles": [
            {"indice": i, "poligono": cuadrilatero(a, b)}
            for i, (a, b) in enumerate(zip(rayos, rayos[1:]))
        ],
    }


def escribir_yaml(nombre: str, datos: dict, r: ResultadoCalibracion | None) -> Path:
    s = SECUENCIAS[nombre]
    plantilla = (RAIZ / "configs" / "camara_ejemplo.yaml").read_text(encoding="utf-8")
    cola = plantilla[plantilla.index("# Clases vehiculares") :]

    def puntos(lista, sangria):
        return "\n".join(f"{sangria}- [{p[0]:g}, {p[1]:g}]" for p in lista)

    carriles = "\n".join(
        f"  - indice: {c['indice']}\n    poligono:\n{puntos(c['poligono'], '      ')}"
        for c in datos["carriles"]
    )
    notas = "\n".join(f"#   {linea}" for linea in s["notas"])
    if r is None:
        calibracion = f"""# Sin calibracion (M3, RF4, Paso 5): no hay homografia. Region y carriles
# son rayos desde el punto de fuga {s['fuga']} con pendientes {s['rayos']}."""
        region = "# Region de interes: poligono en coordenadas de imagen (px), entre los\n# bordes exteriores de la calzada y todo el ancho de la imagen."
        bordes = f"# Carriles: poligonos en px entre rayos consecutivos. Carril 0 {s['carril_0']}."
        homografia = ""
    else:
        calibracion = f"""# Calibracion (M3, RF4): homografia desde {s.get('fuente', 'dos lineas discontinuas')} de
# {s['trazo']:g} m de trazo y {s['hueco']:g} m de hueco, separadas por un carril de
# {s['lineas'][1][1] - s['lineas'][0][1]:g} m. Ejes: x en el sentido de avance, y lateral, en metros.
#   Error de reproyeccion: RMSE {r.rmse:.2f} m, maximo {r.error_maximo:.2f} m.
#   Desfase entre los trazos de las dos lineas: {r.desfases[1]:.2f} m.
#   Camara implicita: focal {r.focal_px:.0f} px, inconsistencia {r.inconsistencia:.2f}."""
        region = f"""# Region de interes: poligono en coordenadas de imagen (px), x de {s['x'][0]:g} a
# {s['x'][1]:g} m y todo el ancho de la calzada."""
        bordes = f"""# Carriles: poligonos en px, construidos desde sus bordes en metros
# {s['bordes']}. Carril 0 {s['carril_0']}."""
        homografia = f"""# Correspondencias imagen <-> camino (metros).
homografia:
  puntos_imagen:
{puntos(datos['homografia']['puntos_imagen'], '    ')}
  puntos_camino:
{puntos(datos['homografia']['puntos_camino'], '    ')}

"""
    texto = f"""# Configuracion de camara de RoadGuard (RF1): {nombre}.
#
# Generado por scripts/calibrar_ua_detrac.py; no editar a mano, cambiar los
# puntos en el script y volver a generarlo.
#
{calibracion}
# Estado de cada dato:
{notas}
# Los umbrales NO constituyen limites legales (seccion 1.1).

camara:
  nombre: {nombre}
  descripcion: >-
    {s['descripcion']}

{region}
region_interes:
{puntos(datos['region_interes'], '  ')}

{bordes}
carriles:
{carriles}

{homografia}{cola}"""
    ruta = RAIZ / "configs" / f"{nombre}.yaml"
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def imagen_de_verificacion(nombre: str, datos: dict, r: ResultadoCalibracion | None) -> None:
    import cv2

    s = SECUENCIAS[nombre]
    if "verificacion" in s:
        cuadros = [RAIZ / "datos" / "ua-detrac" / nombre / s["verificacion"]]
    else:
        cuadros = sorted((RAIZ / "datos" / "ua-detrac" / "cuadros" / nombre).glob("img*.jpg"))
    if not cuadros or not cuadros[0].exists():
        return
    im = cv2.imread(str(cuadros[0]))
    if r is not None:
        x0, x1 = s["x"]
        for x in np.arange(np.ceil(x0 / 5) * 5, x1 + 0.1, 5.0):
            pts = proyectar_a_imagen(r.homografia, [(x, y) for y in (s["bordes"][0], s["bordes"][-1])])
            cv2.line(im, *[tuple(np.int32(p)) for p in pts], (255, 200, 0), 1)
    for c in datos["carriles"]:
        cv2.polylines(im, [np.int32(c["poligono"])], True, (0, 255, 255), 1)
    for p in datos.get("homografia", {}).get("puntos_imagen", []):
        cv2.circle(im, tuple(np.int32(p)), 4, (0, 0, 255), -1)
    destino = RAIZ / "datos" / "ua-detrac" / "calibracion"
    destino.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(destino / f"{nombre}.png"), im)


def main(argv: list[str] | None = None) -> None:
    """Sin argumentos genera todas las secuencias; con nombres, solo esas."""
    from roadguard.m1_ingesta.config import cargar_configuracion

    pedidas = argv if argv is not None else sys.argv[1:]
    for nombre, s in SECUENCIAS.items():
        if pedidas and nombre not in pedidas:
            continue
        if "rayos" in s:
            datos, r = sin_calibrar(nombre), None
        else:
            datos, r = calibrar(nombre)
        ruta = escribir_yaml(nombre, datos, r)
        cargar_configuracion(str(ruta))  # valida el YAML con M1
        imagen_de_verificacion(nombre, datos, r)
        if r is None:
            print(f"{nombre}: {ruta.relative_to(RAIZ)}  sin calibracion (Paso 5)")
        else:
            print(
                f"{nombre}: {ruta.relative_to(RAIZ)}  RMSE {r.rmse:.2f} m  "
                f"desfase {r.desfases[1]:.2f} m  focal {r.focal_px:.0f} px"
            )


if __name__ == "__main__":
    main()
