# tests/qkd/test_qrng.py

import numpy as np
from qkd.qrng import QRNG


def test_forma_y_dominio():
    bits = QRNG(seed=42).random_bits(1000)
    assert bits.shape == (1000,)
    assert bits.dtype == np.uint8
    assert set(np.unique(bits)) <= {0, 1}


def test_longitud_no_multiplo_del_bloque():
    """Caso borde clasico: n no divisible por qubits_per_circuit."""
    assert QRNG(qubits_per_circuit=16, seed=1).random_bits(17).shape == (17,)
    assert QRNG(seed=1).random_bits(0).shape == (0,)


def test_monobit_dentro_de_4_sigma():
    """Test monobit del NIST: z = (ceros - unos) / sqrt(n) ~ N(0,1)."""
    n = 20_000
    bits = QRNG(seed=7).random_bits(n)
    z = abs(2 * bits.sum() - n) / np.sqrt(n)
    assert z < 4.0, f"sesgo detectado: z={z:.2f}"


def test_reproducible_con_semilla():
    a = QRNG(seed=123).random_bits(500)
    b = QRNG(seed=123).random_bits(500)
    np.testing.assert_array_equal(a, b)
