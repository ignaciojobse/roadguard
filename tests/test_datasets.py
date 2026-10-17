"""T6. Conversion de highD y NGSIM al contrato de datos (seccion 2.4).

Casos minimos a cubrir:
  - highD: centro de caja, frameRate del registro, inversion del sentido
    para drivingDirection == 1 (x crece en el sentido de avance).
  - NGSIM: pies -> metros, filtro por ubicacion, duplicados descartados.
  - Ida y vuelta por el CSV intermedio sin perdida.
"""

from pathlib import Path

import pytest

from roadguard.m6_evaluacion.datasets import (
    PIE,
    cargar_highd,
    cargar_ngsim,
    guardar_estados_csv,
    leer_estados_csv,
    por_cuadro,
)


def _escribir(ruta: Path, texto: str) -> str:
    ruta.write_text(texto.strip() + "\n", encoding="utf-8")
    return str(ruta)


def test_highd(tmp_path: Path) -> None:
    tracks = _escribir(
        tmp_path / "01_tracks.csv",
        """
frame,id,x,y,width,height,xVelocity,yVelocity,laneId,thw
1,1,100.0,20.0,4.0,2.0,30.0,0.0,5,1.0
2,1,101.2,20.0,4.0,2.0,30.0,0.0,5,1.0
1,2,300.0,8.0,4.0,2.0,-25.0,0.0,2,0.0
2,2,299.0,8.0,4.0,2.0,-25.0,0.0,2,0.0
""",
    )
    meta = _escribir(tmp_path / "01_tracksMeta.csv", "id,drivingDirection\n1,2\n2,1")
    rec = _escribir(tmp_path / "01_recordingMeta.csv", "id,frameRate\n1,25")
    estados, fps = cargar_highd(tracks, meta, rec)
    assert fps == 25.0
    e = {(s.id_vehiculo, s.cuadro): s for s in estados}
    assert e[(1, 1)].x_camino == pytest.approx(102.0) and e[(1, 1)].velocidad == 30.0
    assert e[(1, 2)].t == pytest.approx(1 / 25)
    # sentido 1: x invertido, velocidad positiva y x creciente al avanzar
    assert e[(2, 1)].velocidad == 25.0
    assert e[(2, 2)].x_camino > e[(2, 1)].x_camino
    assert e[(2, 1)].carril == 2 and e[(2, 1)].calibrado


def test_ngsim(tmp_path: Path) -> None:
    ruta = _escribir(
        tmp_path / "ngsim.csv",
        """
Vehicle_ID,Frame_ID,Total_Frames,Global_Time,Local_X,Local_Y,v_Vel,Lane_ID,Location
1,10,3,1000,6.0,100.0,40.0,1,us-101
1,11,3,1100,6.0,104.0,40.0,1,us-101
1,11,3,1100,6.0,104.0,40.0,1,us-101
2,10,3,1000,18.0,50.0,30.0,2,us-101
9,10,3,1000,18.0,50.0,30.0,2,i-80
""",
    )
    estados, fps = cargar_ngsim(ruta, ubicacion="US-101")
    assert fps == 10.0
    assert len(estados) == 3  # duplicado e i-80 descartados
    e = {(s.id_vehiculo, s.cuadro): s for s in estados}
    assert e[(1, 10)].x_camino == pytest.approx(100 * PIE)
    assert e[(1, 10)].velocidad == pytest.approx(40 * PIE)
    assert e[(1, 11)].t == pytest.approx(0.1)
    assert e[(2, 10)].carril == 2


def test_ida_y_vuelta_csv(tmp_path: Path) -> None:
    ruta = _escribir(
        tmp_path / "ngsim.csv",
        "Vehicle_ID,Frame_ID,Global_Time,Local_X,Local_Y,v_Vel,Lane_ID\n1,1,0,6,100,40,1\n2,1,0,6,60,40,1\n1,2,100,6,104,40,1",
    )
    estados, _ = cargar_ngsim(ruta)
    salida = tmp_path / "estados.csv"
    guardar_estados_csv(estados, str(salida), {"fuente": "ngsim"})
    leidos, meta = leer_estados_csv(str(salida))
    assert leidos == estados
    assert meta == {"fuente": "ngsim"}
    cuadros = list(por_cuadro(leidos))
    assert [c for c, _, _ in cuadros] == [1, 2]
    assert [e.id_vehiculo for e in cuadros[0][2]] == [1, 2]
