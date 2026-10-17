"""RF7. Pendiente: implementar junto con m4_reglas/cercania.py.

Casos minimos a cubrir:
  - Activa con v > 5 m/s y THW < 1,5 s sostenidos 2 s o mas.
  - No activa si la persistencia es menor a 2 s.
  - No activa si la velocidad del seguidor es <= 5 m/s.
  - No activa si THW es None (sin calibracion, Paso 5).
  - No duplica el evento mientras la condicion sigue activa (M4).
"""

import pytest

pytestmark = pytest.mark.skip(reason="RF7 pendiente de implementacion")
