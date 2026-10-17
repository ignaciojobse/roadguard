"""Fixtures compartidas de las pruebas unitarias de reglas (M6)."""

import pytest

from roadguard.tipos import Umbrales


@pytest.fixture
def umbrales() -> Umbrales:
    """Umbrales por defecto declarados en la propuesta (RF7-RF11)."""
    return Umbrales()
