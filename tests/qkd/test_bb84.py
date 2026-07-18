# tests/qkd/test_bb84.py

import numpy as np
from qkd.bb84 import run_bb84


def test_sin_eve_sin_ruido_las_claves_son_identicas():
    """El test más importante del módulo. Si esto falla, nada más importa."""
    r = run_bb84(n_photons=5_000, rng=np.random.default_rng(42))
    np.testing.assert_array_equal(r.alice, r.bob)


def test_sifting_conserva_la_mitad():
    """Longitud ~ N/2 con sigma = sqrt(N)/2. Tolerancia = 4 sigma, derivada."""
    n = 10_000
    r = run_bb84(n_photons=n, rng=np.random.default_rng(0))
    assert abs(r.alice.size - n / 2) < 4 * np.sqrt(n) / 2


def test_casos_borde():
    assert run_bb84(0, np.random.default_rng(0)).alice.size == 0
    assert run_bb84(1, np.random.default_rng(0)).alice.size in (0, 1)


def test_backends_coinciden():
    """qiskit vs numpy: mismas estadísticas, misma física."""
    kw = dict(n_photons=2_000, noise=0.0)
    a = run_bb84(**kw, rng=np.random.default_rng(1), backend="numpy")
    b = run_bb84(**kw, rng=np.random.default_rng(1), backend="qiskit")
    np.testing.assert_array_equal(a.alice, a.bob)
    np.testing.assert_array_equal(b.alice, b.bob)
    assert abs(a.alice.size - b.alice.size) < 4 * np.sqrt(2_000) / 2
