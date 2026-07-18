# tests/qkd/test_privacy.py — tests de la tarea 1.6 (amplificacion de
# privacidad: Toeplitz + longitud segura).

import numpy as np
import pytest
from qkd.privacy import binary_entropy, privacy_amplify, secure_key_length


def _mat(n: int, ell: int, seed_bits):
    """Construye la matriz de Toeplitz explicitamente.

    Solo para tests pequenos: valida bit a bit el camino rapido por FFT de
    privacy_amplify. (Con n = 10^5 esta matriz ocuparia ~1 GB: por eso el
    codigo de produccion usa matmul_toeplitz y nunca la construye.)
    """
    from scipy.linalg import toeplitz

    return toeplitz(seed_bits[:ell], seed_bits[ell - 1 :]).astype(np.uint8)


def test_fft_coincide_con_la_matriz_explicita():
    """El truco rapido debe dar EXACTAMENTE lo mismo que la definicion."""
    rng = np.random.default_rng(0)
    n, ell = 200, 80
    key = rng.integers(0, 2, n, dtype=np.uint8)
    seed = rng.integers(0, 2, n + ell - 1, dtype=np.uint8)
    esperado = (_mat(n, ell, seed) @ key) % 2
    np.testing.assert_array_equal(privacy_amplify(key, ell, seed), esperado)


def test_longitud_de_salida():
    rng = np.random.default_rng(1)
    key = rng.integers(0, 2, 1000, dtype=np.uint8)
    seed = rng.integers(0, 2, 1000 + 400 - 1, dtype=np.uint8)
    assert privacy_amplify(key, 400, seed).size == 400


def test_linealidad():
    """T(a xor b) = Ta xor Tb. Es una aplicacion lineal sobre GF(2)."""
    rng = np.random.default_rng(2)
    n, ell = 500, 200
    a = rng.integers(0, 2, n, dtype=np.uint8)
    b = rng.integers(0, 2, n, dtype=np.uint8)
    s = rng.integers(0, 2, n + ell - 1, dtype=np.uint8)
    izq = privacy_amplify(np.bitwise_xor(a, b), ell, s)
    der = np.bitwise_xor(privacy_amplify(a, ell, s), privacy_amplify(b, ell, s))
    np.testing.assert_array_equal(izq, der)


def test_avalancha():
    """Cambiar 1 bit de entrada cambia ~50% de los bits de salida.

    Tolerancia derivada: el numero de bits cambiados es ~binomial(ell, 1/2),
    sigma = sqrt(ell)/2, umbral 4 sigma.
    """
    rng = np.random.default_rng(3)
    n, ell = 2000, 800
    key = rng.integers(0, 2, n, dtype=np.uint8)
    seed = rng.integers(0, 2, n + ell - 1, dtype=np.uint8)
    otra = key.copy()
    otra[123] ^= 1
    d = np.count_nonzero(
        privacy_amplify(key, ell, seed) != privacy_amplify(otra, ell, seed)
    )
    sigma = np.sqrt(ell) / 2
    assert abs(d - ell / 2) < 4 * sigma


def test_umbral_de_seguridad():
    """Q > 11% => no hay clave. Es el resultado central de BB84: el 25% que
    produce Eve esta muy por encima de lo que el protocolo tolera."""
    assert secure_key_length(n=10_000, qber=0.25, leak_ec=3_000) == 0
    assert secure_key_length(n=10_000, qber=0.02, leak_ec=1_700) > 0


def test_h_de_11_por_ciento_es_medio():
    assert binary_entropy(0.110) == pytest.approx(0.5, abs=0.005)


def test_entropia_binaria_extremos():
    """h(0) = h(1) = 0 por convenio (limite de la formula); h(0.5) = 1."""
    assert binary_entropy(0.0) == 0.0
    assert binary_entropy(1.0) == 0.0
    assert binary_entropy(0.5) == pytest.approx(1.0)


def test_qber_50_por_ciento_sin_clave():
    """Caso borde de la tabla 5.1: Q = 0.5 => h(Q) = 1 => ell = 0 aunque no
    se haya filtrado ni un bit en la reconciliacion."""
    assert secure_key_length(n=50_000, qber=0.5, leak_ec=0) == 0


def test_semilla_de_longitud_mala():
    """Caso borde de la tabla 5.1: ValueError explicito, no resultado
    silencioso con una matriz mal formada."""
    rng = np.random.default_rng(4)
    key = rng.integers(0, 2, 100, dtype=np.uint8)
    seed = rng.integers(0, 2, 50, dtype=np.uint8)  # deberia ser 100+40-1=139
    with pytest.raises(ValueError):
        privacy_amplify(key, 40, seed)


def test_ell_no_positivo_devuelve_clave_vacia():
    """Con ell <= 0 la funcion devuelve un array vacio; el aborto explicito
    con motivo legible lo gestiona run_protocol (ver test_protocol.py)."""
    key = np.ones(100, dtype=np.uint8)
    out = privacy_amplify(key, 0, np.empty(0, dtype=np.uint8))
    assert out.size == 0
    assert out.dtype == np.uint8
