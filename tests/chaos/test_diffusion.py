"""tests/chaos/test_diffusion.py - tarea 3.6, la difusion encadenada.

Aqui solo se prueba la etapa: la formula, que se deshace exactamente y
que la avalancha va hacia adelante y no hacia atras. El cifrado completo
(permutacion + las dos pasadas) esta en test_cipher.py.
"""

import numpy as np
import pytest
from chaos import deshacer_adelante, difundir_adelante


def _datos(n, semilla):
    return np.random.default_rng(semilla).integers(0, 256, n, dtype=np.uint8)


def test_la_formula_es_la_especificada():
    """c_i = p_i XOR k_i XOR c_{i-1}, con c_{-1} = iv. Calculado a mano
    sobre cuatro bytes para que el test no repita el codigo que prueba."""

    p = np.array([1, 2, 3, 4], dtype=np.uint8)
    k = np.array([10, 20, 30, 40], dtype=np.uint8)
    iv = 7

    c0 = 1 ^ 10 ^ 7
    c1 = 2 ^ 20 ^ c0
    c2 = 3 ^ 30 ^ c1
    c3 = 4 ^ 40 ^ c2

    np.testing.assert_array_equal(
        difundir_adelante(p, k, iv), np.array([c0, c1, c2, c3], dtype=np.uint8)
    )


@pytest.mark.parametrize("n", [1, 2, 3, 1000, 4096])
def test_round_trip_de_la_etapa(n):
    """Deshacer devuelve exactamente lo que entro. Bit a bit."""

    p, k = _datos(n, 1), _datos(n, 2)
    np.testing.assert_array_equal(
        deshacer_adelante(difundir_adelante(p, k, 99), k, 99), p
    )


def test_el_resultado_es_uint8():
    """Un float en el camino del XOR es un TypeError en el mejor caso y
    una conversion silenciosa en el peor."""

    p, k = _datos(64, 1), _datos(64, 2)
    assert difundir_adelante(p, k, 0).dtype == np.uint8
    assert deshacer_adelante(p, k, 0).dtype == np.uint8


def test_no_muta_las_entradas():
    """Operaciones in place sobre la entrada destruyen el original que el
    test de round-trip necesita para comparar."""

    p, k = _datos(256, 3), _datos(256, 4)
    copia_p, copia_k = p.copy(), k.copy()
    difundir_adelante(p, k, 5)
    deshacer_adelante(p, k, 5)
    np.testing.assert_array_equal(p, copia_p)
    np.testing.assert_array_equal(k, copia_k)


def test_la_avalancha_va_solo_hacia_adelante():
    """Cambiar p_j no toca ningun c_t con t < j, y toca TODOS los t >= j.

    Es la limitacion real que obliga a la segunda pasada del cifrado
    la avalancha es unidireccional, asi que
    cambiar el ULTIMO pixel solo afectaria al ultimo byte del cifrado.
    """
    n, j = 512, 300
    p, k = _datos(n, 5), _datos(n, 6)
    otro = p.copy()
    otro[j] ^= 1

    c1 = difundir_adelante(p, k, 11)
    c2 = difundir_adelante(otro, k, 11)
    distintos = np.flatnonzero(c1 != c2)

    np.testing.assert_array_equal(distintos, np.arange(j, n))

    # Y el ultimo byte solo se propaga a si mismo: 1 de 512 posiciones.
    ultimo = p.copy()
    ultimo[-1] ^= 1
    assert np.count_nonzero(difundir_adelante(ultimo, k, 11) != c1) == 1


def test_el_iv_forma_parte_de_la_cadena():
    """Dos IV distintos dan cifrados distintos, y deshacer con el IV
    equivocado no devuelve el original."""

    p, k = _datos(128, 7), _datos(128, 8)
    c = difundir_adelante(p, k, 0)
    assert not np.array_equal(c, difundir_adelante(p, k, 1))
    assert not np.array_equal(deshacer_adelante(c, k, 1), p)


@pytest.mark.parametrize("funcion", [difundir_adelante, deshacer_adelante])
def test_longitudes_distintas_dan_error_y_no_truncan(funcion):
    """Regenerar el keystream con distinta longitud desalinea el flujo
    desde el primer byte. Es uno de los tres errores tipicos de la tarea
    y tiene que doler, no truncar en silencio."""

    p, k = _datos(100, 9), _datos(64, 10)
    with pytest.raises(ValueError, match="64 bytes para 100"):
        funcion(p, k, 0)
