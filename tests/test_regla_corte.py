"""RF9. Pendiente: implementar junto con m4_reglas/corte.py.

Casos minimos a cubrir:
  - Activa si el nuevo seguidor tiene THW < 1,5 s dentro de 2 s del cambio.
  - Activa si el nuevo seguidor tiene TTC < 3 s dentro de 2 s del cambio.
  - No activa si la condicion ocurre despues de los 2 s.
  - No activa si no hay nuevo seguidor (ausencia de predecesor, Paso 3).
"""

import pytest

pytestmark = pytest.mark.skip(reason="RF9 pendiente de implementacion")
