"""RF6. Pendiente: implementar junto con m3_geometria/relaciones.py.

Casos minimos a cubrir:
  - THW = distancia / velocidad del seguidor.
  - TTC solo se calcula con tasa de cierre positiva; si no, None.
  - Division invalida o ausencia de predecesor -> None (Paso 3).
  - Sin calibracion, distancia, THW y TTC quedan en None (Paso 5).
"""

import pytest

pytestmark = pytest.mark.skip(reason="RF6 pendiente de implementacion")
