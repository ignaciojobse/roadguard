import subprocess
import sys
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]


def test_demo_cercania_reporta_escenarios_y_evento_cerrado():
    resultado = subprocess.run(
        [sys.executable, "scripts/demo_cercania.py"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "DEMO SINTETICA / EXPERIMENTAL" in resultado.stdout
    assert "cercania 1.9 s: esperados=0, cerrados=0 — OK" in resultado.stdout
    assert "cercania sostenida 3.0 s: esperados=1, cerrados=1 — OK" in resultado.stdout
    assert "confirmacion=2.0s" in resultado.stdout
    assert "intervalo=[0.0, 3.0]s" in resultado.stdout
    assert "interrumpida antes de 2 s: esperados=0, cerrados=0 — OK" in resultado.stdout
    assert "sin calibracion: esperados=0, cerrados=0 — OK" in resultado.stdout
    assert "advertencia: RF7 no evaluable" in resultado.stdout
    assert "t=1.9s: sin alerta confirmada" in resultado.stdout
    assert "t=2.0s: activa" in resultado.stdout
    assert "t=3.0s: activa" in resultado.stdout
    assert "fin de entrada: cerrada" in resultado.stdout


def test_demo_cercania_es_determinista():
    comando = [sys.executable, "scripts/demo_cercania.py"]
    primero = subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True, check=False)
    segundo = subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True, check=False)
    assert primero.returncode == segundo.returncode == 0
    assert primero.stdout == segundo.stdout
