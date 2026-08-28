"""tests/detector/test_carga.py - lectura de la senal de ruido de detector."""

from __future__ import annotations

import numpy as np
import pytest
from detector.carga import _ruido_potencia, cargar_muestra, senal_de_prueba


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


def test_senal_de_prueba_tiene_la_forma_del_contrato():
    """Comprobacion basica: tipo, forma, reproducibilidad con semilla."""
    senal, fs = senal_de_prueba(n=2**16, semilla=1)
    assert senal.dtype == np.int32
    assert senal.shape == (2**16,)
    assert fs > 0

    otra, _ = senal_de_prueba(n=2**16, semilla=1)
    np.testing.assert_array_equal(senal, otra)


def test_senal_de_prueba_semillas_distintas_dan_senales_distintas():
    """Si esto fallara, la semilla no estaria haciendo nada."""
    a, _ = senal_de_prueba(n=2**16, semilla=1)
    b, _ = senal_de_prueba(n=2**16, semilla=2)
    assert not np.array_equal(a, b)


def test_senal_de_prueba_tiene_el_pedestal_esperado():
    """La media debe caer cerca de 1000 (el pedestal fijado en el
    codigo), con margen para la varianza de una sola realizacion."""
    senal, _ = senal_de_prueba(n=2**18, semilla=42)
    assert 950 < senal.mean() < 1050


def test_ruido_potencia_alfa_cero_no_colorea():
    """Con alfa=0, _ruido_potencia no debe alterar la naturaleza blanca
    del ruido: sirve de caso de control para el test del 1/f."""
    rng = np.random.default_rng(7)
    resultado = _ruido_potencia(2**16, alfa=0.0, rng=rng)
    assert resultado.std() == pytest.approx(1.0, rel=0.05)


def test_ruido_potencia_alfa_positivo_decrece_con_la_frecuencia():
    """El test central de esta funcion: la PSD del ruido coloreado debe
    decrecer con la frecuencia. No comprueba el valor exacto de alfa
    (eso lo hace ajustar_alfa en la tarea 4.4): comprueba que la
    tendencia tiene el signo correcto, contra la teoria y no contra
    otra implementacion."""
    rng = np.random.default_rng(7)
    n = 2**16
    resultado = _ruido_potencia(n, alfa=1.0, rng=rng)

    psd = np.abs(np.fft.rfft(resultado)) ** 2
    freqs = np.fft.rfftfreq(n)
    mitad = len(freqs) // 2
    potencia_baja = psd[1:mitad].mean()
    potencia_alta = psd[mitad:].mean()
    assert potencia_baja > potencia_alta
