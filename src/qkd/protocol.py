"""src/qkd/protocol.py — orquestador: ata la cadena entera de punta a punta."""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np

from .bb84 import run_bb84
from .privacy import privacy_amplify, secure_key_length
from .qber import estimate_qber
from .reconciliation import cascade
from .types import ProtocolResult, QberEstimate

logger = logging.getLogger(__name__)

# Umbral de seguridad de BB84 con post-procesado unidireccional
# (Shor-Preskill): h(Q) < 1/2 <=> Q < ~11%. Por encima, ni con
# reconciliacion ideal (f = 1) queda clave destilable.
QBER_THRESHOLD = 0.11

# Bits objetivo de muestra publica para estimar el QBER cuando no se pide
# una sample_fraction concreta. 800 basta para estabilizar la sigma
# binomial sin sacrificar demasiada clave final con N grandes (Gonzalo,
# tarea 2.x). Acotado entre 2% (N masivo) y 40% (N pequeño).
_MUESTRA_QBER_OBJETIVO = 800
_MUESTRA_FRACCION_MIN = 0.02
_MUESTRA_FRACCION_MAX = 0.40


def _fraccion_muestra_optima(sifted_len: int) -> float:
    """Fraccion de muestra que apunta a ~_MUESTRA_QBER_OBJETIVO bits.

    Se usa SOLO cuando el llamador no especifica sample_fraction: nunca
    sustituye un valor pedido explicitamente (lo necesitan intactos
    test_muestra_vacia_lanza_error y el slider del dashboard).
    """
    if sifted_len == 0:
        return 0.0
    fraccion = _MUESTRA_QBER_OBJETIVO / sifted_len
    return float(np.clip(fraccion, _MUESTRA_FRACCION_MIN, _MUESTRA_FRACCION_MAX))


def run_protocol(
    n_photons: int,
    rng: np.random.Generator,
    eve_rate: float = 0.0,
    noise: float = 0.0,
    sample_fraction: float | None = None,
    backend: Literal["qiskit", "numpy"] = "numpy",
) -> ProtocolResult:
    """Recorre la cadena completa: QRNG -> BB84 -> QBER -> Cascade -> privacidad.

    Aborta (final_key = None, abort_reason legible) en dos situaciones:
      1. El QBER medido supera el umbral del 11%: hay demasiado
         error/espionaje y la teoria dice que no hay clave destilable.
      2. La formula de la longitud segura da ell <= 0 (puede pasar con Q
         algo por debajo del umbral, porque el f_EC real de Cascade > 1
         filtra mas que la reconciliacion ideal que asume el umbral).
    """
    # --- 1-3. Preparacion, canal (con Eve opcional), medida y sifting ---
    sifted = run_bb84(
        n_photons=n_photons,
        rng=rng,
        eve_rate=eve_rate,
        noise=noise,
        backend=backend,
    )
    sifted_len = int(sifted.alice.size)

    # --- 4. Estimacion del QBER: si no se especifica sample_fraction, se
    # calcula automaticamente (ver _fraccion_muestra_optima); si se
    # especifica, se respeta tal cual.
    fraccion = (
        sample_fraction
        if sample_fraction is not None
        else _fraccion_muestra_optima(sifted_len)
    )
    est = estimate_qber(sifted, fraccion, rng)

    def _abort(reason: str) -> ProtocolResult:
        """Resultado de aborto homogeneo: sin clave, con motivo legible."""
        logger.debug("protocolo abortado: %s", reason)
        return ProtocolResult(
            n_photons=n_photons,
            sifted_len=sifted_len,
            qber=est,
            reconciliation=None,
            final_key=None,
            aborted=True,
            abort_reason=reason,
            secret_fraction=0.0,
        )

    # --- 5. Umbral: por encima del 11% se aborta, no se negocia ---
    if est.qber > QBER_THRESHOLD:
        return _abort(
            f"QBER = {est.qber:.1%} > umbral de seguridad "
            f"{QBER_THRESHOLD:.0%}: presencia de espia (o canal inservible)"
        )

    # --- 6. Reconciliacion (Cascade): igualar las claves contando fugas ---
    rec = cascade(est.remaining.alice, est.remaining.bob, est.qber, rng)
    if not rec.ok:
        # Con Q <= 10% y 4 pasadas no deberia ocurrir; si ocurre, mejor
        # abortar con motivo que devolver una "clave" con errores.
        return _abort("reconciliacion fallida: quedan errores tras Cascade")

    # --- 7. Amplificacion de privacidad (Toeplitz) ---
    n_rec = int(rec.bob.size)
    # MEJORA C1: se pasa la sigma de la estimacion del QBER para que la cota
    # de seguridad pueda usarla. n_sigma se deja en su valor por defecto (0),
    # asi que el resultado numerico es identico al de antes; lo que cambia es
    # que el dato deja de estar desconectado de la formula que lo necesita.
    ell = secure_key_length(
        n=n_rec, qber=est.qber, leak_ec=rec.leak_ec, sigma=est.sigma
    )
    if ell <= 0:
        # ell <= 0: Eve (canal + paridades) puede saber tanto como mide la
        # clave. No se devuelve una clave vacia en silencio: se aborta.
        return _abort(
            f"clave final de longitud {ell} <= 0 tras descontar "
            f"h(Q) y leak_ec = {rec.leak_ec}: no hay nada que destilar"
        )

    # La semilla de Toeplitz es publica y se elige al azar AHORA, despues de
    # que Eve haya obtenido toda su informacion (requisito del lemma).
    seed = rng.integers(0, 2, size=n_rec + ell - 1, dtype=np.uint8)
    final_key = privacy_amplify(rec.bob, ell, seed)

    return ProtocolResult(
        n_photons=n_photons,
        sifted_len=sifted_len,
        qber=est,
        reconciliation=rec,
        final_key=final_key,
        aborted=False,
        abort_reason=None,
        secret_fraction=ell / n_photons,
    )


def run_until_qber(
    n_photons: int,
    rng: np.random.Generator,
    eve_rate: float = 0.0,
    noise: float = 0.0,
    sample_fraction: float | None = None,
) -> QberEstimate:
    """Version corta de la cadena, solo hasta la estimacion del QBER.

    La usan los tests de la tarea 1.4, que no necesitan llegar hasta Cascade.
    Usa siempre el backend numpy: es el unico donde Eve (intercept-resend)
    esta modelada, y el unico viable en tiempo para los barridos de 40 000
    fotones que hacen estos tests (ver run_bb84 en bb84.py).

    Si no se especifica sample_fraction, se calcula automaticamente (ver
    _fraccion_muestra_optima); si se especifica, se respeta tal cual.
    """
    sifted = run_bb84(
        n_photons=n_photons,
        rng=rng,
        eve_rate=eve_rate,
        noise=noise,
        backend="numpy",
    )
    sifted_len = int(sifted.alice.size)
    fraccion = (
        sample_fraction
        if sample_fraction is not None
        else _fraccion_muestra_optima(sifted_len)
    )
    return estimate_qber(sifted, fraccion, rng)
