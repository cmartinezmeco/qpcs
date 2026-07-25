# tests/pqc/test_shor.py (parte 2.2)
from math import gcd

import numpy as np
from pqc.shor import factorizar_15, medir_fase_15, orden_desde_fase


def test_fase_es_multiplo_de_1_sobre_4_para_a7():
    """a=7 mod 15 tiene orden 4: las fases validas son 0, 1/4, 2/4, 3/4."""
    for seed in range(8):
        phi = medir_fase_15(a=7, rng=np.random.default_rng(seed), n_count=8)
        cercania = min(abs(phi - k / 4) for k in range(4))
        assert cercania < 1 / 16, f"fase {phi:.3f} lejos de k/4"


def test_shor_factoriza_15():
    """EL test del bloque Shor: 15 = 3 x 5 via busqueda de orden."""
    res = factorizar_15(np.random.default_rng(42))
    assert res.ok
    p, q = res.factores
    assert p * q == 15
    assert {p, q} == {3, 5}


def test_reduccion_es_correcta_para_todo_a():
    """La aritmetica clasica: si r es el orden real, salen factores."""
    N = 15
    for a in (2, 4, 7, 8, 11, 13):
        r = next(k for k in range(1, N) if pow(a, k, N) == 1)
        if r % 2 == 0 and pow(a, r // 2, N) != N - 1:
            x = pow(a, r // 2, N)
            assert 1 < gcd(x - 1, N) < N or 1 < gcd(x + 1, N) < N


def test_fracciones_continuas_recuperan_denominador():
    """fase = 3/4 debe dar r = 4 (denominador del convergente)."""
    assert orden_desde_fase(0.75, 15) == 4
