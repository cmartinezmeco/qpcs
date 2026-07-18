# tests/qkd/test_eve_qber.py

import numpy as np
import pytest
from qkd.protocol import run_until_qber


def test_qber_converge_a_25_por_ciento():
    """Intercept-resend total: Q -> 1/4. La tolerancia sale de la binomial."""
    est = run_until_qber(n_photons=40_000, eve_rate=1.0, rng=np.random.default_rng(42))

    m = est.n_sample
    sigma = np.sqrt(0.25 * 0.75 / m)
    assert abs(est.qber - 0.25) < 4 * sigma, (
        f"Q={est.qber:.4f}, esperado 0.25 +- {4 * sigma:.4f}"
    )


@pytest.mark.parametrize("p", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_qber_es_lineal_en_p(p):
    """Q(p) = p/4 para todo p. Es la predicción teórica completa."""
    est = run_until_qber(n_photons=40_000, eve_rate=p, rng=np.random.default_rng(7))
    esperado = p / 4
    sigma = np.sqrt(max(esperado * (1 - esperado), 1e-9) / est.n_sample)
    assert abs(est.qber - esperado) < 4 * sigma + 0.002


def test_sin_eve_qber_es_cero():
    est = run_until_qber(n_photons=10_000, eve_rate=0.0, rng=np.random.default_rng(1))
    assert est.qber == 0.0


def test_la_muestra_se_descarta():
    """Bug clásico: estimar el QBER y seguir usando los bits publicados."""
    est = run_until_qber(n_photons=10_000, eve_rate=0.0, rng=np.random.default_rng(2))
    assert est.remaining.alice.size == est.remaining.bob.size
    assert est.remaining.alice.size + est.n_sample == pytest.approx(est.remaining.alice.size + est.n_sample)
