# tests/qkd/test_protocol.py — el test de integracion de la tarea 1.7:
# la cadena completa QRNG -> BB84 -> QBER -> Cascade -> privacidad.

import numpy as np
import pytest
from qkd.privacy import secure_key_length
from qkd.protocol import QBER_THRESHOLD, run_protocol


def test_cadena_completa_sin_eve(sigma_qber):
    """De 10^5 fotones a una clave secreta. Es EL test del modulo.

    MEJORA B4: la comprobacion del rendimiento era una banda a ojo
    (0.15 < secret_fraction < 0.40, un factor 2.7 de anchura) que chocaba con
    la regla de oro "las tolerancias se derivan, no se inventan": pasaria
    aunque la amplificacion de privacidad regalase o perdiese miles de bits.
    Se sustituye por la IDENTIDAD de la formula de la longitud segura,
    evaluada con el Q medido y el leak_ec realmente publicado -no es una
    estadistica, tiene que cuadrar exactamente-, y la banda ancha se deja
    solo donde corresponde: sobre el QBER medido, que si es estadistico.
    """
    ruido = 0.02
    r = run_protocol(
        n_photons=100_000, eve_rate=0.0, noise=ruido, rng=np.random.default_rng(42)
    )
    assert not r.aborted
    assert r.final_key is not None
    assert r.final_key.size > 0
    assert r.reconciliation is not None

    # Lo estadistico: el QBER medido sigue al ruido inyectado (4 sigma).
    assert abs(r.qber.qber - ruido) <= 4 * sigma_qber(ruido, r.qber.n_sample)

    # Lo exacto: ell = n(1 - h(Q)) - leak_ec - 2 log2(1/eps), evaluada con las
    # cifras que devuelve la propia ejecucion. Verifica la formula de punta a
    # punta (hasta ahora solo estaba testeada en unidad).
    ell_esperado = secure_key_length(
        n=int(r.reconciliation.bob.size),
        qber=r.qber.qber,
        leak_ec=r.reconciliation.leak_ec,
    )
    assert r.final_key.size == ell_esperado


def test_cadena_completa_con_eve_aborta():
    """Con Eve al 100% el QBER es 25% > 11%: no hay clave. Punto."""
    r = run_protocol(
        n_photons=50_000, eve_rate=1.0, noise=0.0, rng=np.random.default_rng(42)
    )
    assert r.aborted
    assert r.final_key is None
    assert "QBER" in r.abort_reason


@pytest.mark.parametrize("p", [0.0, 0.2, 0.42, 0.6, 0.8, 1.0])
def test_barrido_de_eve(p):
    """Q(p) = p/4, y el protocolo aborta exactamente cuando no puede
    destilar clave.

    Nota honesta para el equipo (difiere de la version idealizada de la
    guia): el umbral del 11% asume reconciliacion IDEAL (f = 1). Con el
    f_EC real de Cascade (~1.15-1.2 medido en test_eficiencia_razonable),
    justo bajo el umbral la formula
    ell = n(1 - h(Q)) - leak_ec - 2 log2(1/eps) puede salir <= 0 y el
    protocolo aborta por longitud de clave, no por QBER. Es el
    comportamiento correcto: la formula absorbe la ineficiencia de la
    reconciliacion sin mentir (misma logica que el plan B de la seccion
    5.5.7 de la guia).

    p = 0.42 (no 0.4) desde la optimizacion de sample_fraction (tarea
    2.x, Gonzalo): al sacrificar menos bits en la muestra del QBER (~800
    en vez de 0.2*sifted_len), queda mas clave real disponible y el caso
    limite se desplaza. Se comprobo con un barrido fino (0.38 a 0.46,
    misma semilla) que en p = 0.4 y 0.38 ya SALE clave (ell > 0) y que
    el aborto por longitud reaparece a partir de p ~ 0.42; es una
    consecuencia esperada de la mejora, no una regresion.
    """
    r = run_protocol(
        n_photons=40_000, eve_rate=p, noise=0.0, rng=np.random.default_rng(1)
    )
    # La fisica: el QBER medido sigue Q = p/4 dentro de 4 sigma.
    assert r.qber.qber == pytest.approx(p / 4, abs=4 * r.qber.sigma + 0.003)

    if p / 4 > QBER_THRESHOLD:
        # Por encima del umbral teorico: aborta siempre, y por el QBER.
        assert r.aborted
        assert "QBER" in (r.abort_reason or "")
        assert r.final_key is None
    elif p == 0.42:
        # Zona limite (Q ~ 9%): aborta por ell <= 0, con motivo legible
        # que lo distingue del aborto por umbral.
        assert r.aborted
        assert "clave" in (r.abort_reason or "")
        assert r.final_key is None
    else:
        # Comodo por debajo del umbral: sale clave.
        assert not r.aborted
        assert r.final_key is not None
        assert r.final_key.size > 0


def test_abortado_no_deja_rastros():
    """Cuando aborta: final_key is None, abort_reason poblado y
    secret_fraction = 0 (caso ell <= 0 de la tabla de casos borde 5.1)."""
    r = run_protocol(
        n_photons=50_000, eve_rate=1.0, noise=0.0, rng=np.random.default_rng(3)
    )
    assert r.aborted
    assert r.final_key is None
    assert r.abort_reason  # poblado, no None ni cadena vacia
    assert r.secret_fraction == 0.0


def test_muestra_vacia_lanza_error():
    """Caso borde de la tabla 5.1: s = 0 => ValueError explicito desde
    estimate_qber, no una division por cero silenciosa."""
    with pytest.raises(ValueError):
        run_protocol(n_photons=1_000, rng=np.random.default_rng(0), sample_fraction=0.0)


def test_el_balance_de_bits_cuadra():
    """Coherencia interna del resultado: sifted = muestra + reconciliada, y
    la clave final mide ell = secret_fraction * n_photons."""
    r = run_protocol(
        n_photons=40_000, eve_rate=0.0, noise=0.02, rng=np.random.default_rng(11)
    )
    assert not r.aborted
    assert r.reconciliation is not None
    assert r.final_key is not None
    # Los bits sacrificados para el QBER + los que entran a Cascade deben
    # sumar la clave cribada completa.
    assert r.qber.n_sample + r.reconciliation.bob.size == r.sifted_len
    # La fraccion secreta es exactamente ell / n_photons.
    assert r.final_key.size == pytest.approx(r.secret_fraction * r.n_photons)
