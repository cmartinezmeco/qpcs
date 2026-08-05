# tests/qkd/test_eve_qber.py

import numpy as np
import pytest
from qkd.bb84 import run_bb84
from qkd.protocol import run_until_qber
from qkd.qber import estimate_qber


def test_qber_converge_a_25_por_ciento():
    """Intercept-resend total: Q -> 1/4. La tolerancia sale de la binomial."""
    est = run_until_qber(n_photons=40_000, eve_rate=1.0, rng=np.random.default_rng(42))

    m = est.n_sample
    sigma = np.sqrt(0.25 * 0.75 / m)
    assert (
        abs(est.qber - 0.25) < 4 * sigma
    ), f"Q={est.qber:.4f}, esperado 0.25 +- {4 * sigma:.4f}"


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


@pytest.mark.parametrize("ruido", [0.0, 0.01, 0.02, 0.05])
def test_qber_sigue_al_ruido_del_canal(ruido, sigma_qber):
    """Sin Eve, el QBER medido es el ruido inyectado: Q = noise.

    MEJORA B1: el parametro `noise` atraviesa toda la cadena (_bob_measures
    lo inyecta, run_bb84 y run_protocol lo exponen, el dashboard tiene su
    slider y la figura del embudo se genera con ruido 0.02) pero NO tenia ni
    un solo test. Es exactamente el escenario del bug de "Eve escrita pero
    desenchufada del canal", que se cazo porque habia un test que exigia la
    relacion cuantitativa Q(p) = p/4: si el ruido se desconectara del canal,
    hasta ahora nada en la suite lo habria detectado.

    Cada bit de Bob se voltea con probabilidad `noise` (bb84._bob_measures),
    asi que sobre las posiciones cribadas y sin espia el QBER esperado es el
    propio `noise`. Tolerancia derivada de la binomial de la muestra (4
    sigma), nunca a ojo.
    """
    est = run_until_qber(
        n_photons=40_000, eve_rate=0.0, noise=ruido, rng=np.random.default_rng(23)
    )
    tolerancia = 4 * sigma_qber(ruido, est.n_sample)
    assert abs(est.qber - ruido) <= tolerancia, (
        f"Q={est.qber:.4f} con noise={ruido}, esperado {ruido} " f"+- {tolerancia:.4f}"
    )


def test_la_muestra_se_descarta():
    """Bug clásico: estimar el QBER y seguir usando los bits publicados.

    MEJORA D6 (cierra I5): la segunda asercion de este test comparaba una
    expresion CONSIGO MISMA (`x + y == approx(x + y)`), asi que pasaba
    siempre, con independencia de que el codigo fuera correcto. Se sustituye
    por una comparacion real contra el tamano esperado de `remaining`, lo que
    obliga a construir el sifting aparte para conocer la longitud cribada.
    """
    rng = np.random.default_rng(2)
    sifted = run_bb84(n_photons=10_000, eve_rate=0.0, rng=rng)
    est = estimate_qber(sifted, 0.2, rng)

    assert est.remaining.alice.size == est.remaining.bob.size
    # Lo que queda es EXACTAMENTE la clave cribada menos los bits publicados.
    assert est.remaining.alice.size == sifted.alice.size - est.n_sample
    # Y los indices tambien se recortan: ninguna posicion muestreada
    # sobrevive en la clave que sigue adelante.
    assert est.remaining.indices.size == est.remaining.alice.size
    assert set(est.remaining.indices).issubset(set(sifted.indices))
