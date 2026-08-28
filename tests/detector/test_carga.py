"""tests/detector/test_carga.py - lectura de la senal de ruido de detector."""

from __future__ import annotations

import numpy as np
import pytest
from detector.carga import cargar_muestra


def test_carga_el_subconjunto_versionado():
    """El fichero real del repo carga sin red y con la forma esperada."""
    senal, fs = cargar_muestra()
    assert senal.dtype == np.int32
    assert senal.ndim == 1
    assert senal.size > 100_000
    assert fs > 0


def test_fichero_ausente_da_error_util():
    """El mensaje dice DONDE mirar (data/FUENTE.md), no solo que falta."""
    with pytest.raises(FileNotFoundError, match="FUENTE.md"):
        cargar_muestra("data/esto_no_existe.npz")


def test_la_senal_no_esta_degenerada():
    """Comprobacion de cordura: ni plana ni con NaN. Si esto falla, el
    subconjunto que se genero esta corrupto o mal filtrado."""
    senal, _ = cargar_muestra()
    assert senal.std() > 0
    assert not np.any(np.isnan(senal.astype(np.float64)))
    assert senal.min() >= 0
