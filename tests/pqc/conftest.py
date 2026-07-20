# tests/pqc/conftest.py
#
# Fixtures compartidas de la suite PQC (Fase 2). Misma politica anti-parpadeo
# que tests/qkd/conftest.py: semilla fija SIEMPRE, tolerancias derivadas,
# prohibido el retry.
#
# OJO - la semilla SOLO aplica a la parte Shor (src/pqc/shor.py):
#   - Shor es estocastico (elige la base `a` y muestrea shots del simulador) y
#     recibe un np.random.Generator EXPLICITO. Con semilla fija, misma fase y
#     mismo camino de factorizacion: los tests son deterministas.
#   - La cripto REAL (ML-KEM / ML-DSA / RSA / ECC) NO se siembra: liboqs y
#     `cryptography` generan sus claves con su propio CSPRNG y deben ser
#     impredecibles por seguridad (sembrarlas seria un fallo, no una feature).
#     Por eso esos tests se validan por PROPIEDADES (descifrar deshace cifrar,
#     una firma valida verifica y una manipulada no), nunca contra valores
#     fijos.

import numpy as np
import pytest

SEMILLA = 42


@pytest.fixture
def rng() -> np.random.Generator:
    """RNG determinista para la parte Shor. Nunca default_rng() sin semilla."""
    return np.random.default_rng(SEMILLA)
