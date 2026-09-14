"""src/qkd/eve.py — tarea 1.4 (Gonzalo). Espia intercept-resend."""

from __future__ import annotations

import numpy as np

from .types import Bases, Bits


def intercept_resend(
    alice_bits: Bits, alice_bases: Bases, rate: float, rng: np.random.Generator
) -> tuple[Bits, Bases, Bits]:
    """Ataque intercept-resend sobre una fraccion `rate` de los fotones.
    Devuelve (bits_reenviados, bases_reenviadas, mascara_interceptados).
    El estado que llega a Bob es el que Eve reenvio, en LA BASE DE EVE.
    Nota de diseno: esta funcion recibe alice_bases porque en la simulacion hay
    que calcular el resultado de la medida de Eve, no porque Eve las conozca.
    Eve NUNCA usa alice_bases para elegir su base: ver la linea de eve_bases.
    """
    n = alice_bits.size
    # Mascara booleana de los fotones interceptados por Eve: se genera un
    # numero en [0, 1) y si es menor que rate, se considera interceptado.
    # Asegura que la fraccion interceptada sea aproximadamente rate.
    intercepted = rng.random(n) < rate
    # Al azar, sin conocer alice_bases: esto hace que el ataque sea
    # imperfecto y genere errores.
    eve_bases = rng.integers(0, 2, size=n, dtype=np.uint8)

    # Posiciones donde las bases de Alice y Eve coinciden. Ahi Eve mide el
    # mismo bit que Alice; donde no coinciden, Eve mide un bit aleatorio.
    same = alice_bases == eve_bases
    coin = rng.integers(0, 2, size=n, dtype=np.uint8)
    # Si las bases coinciden, Eve obtiene el bit de Alice; si no, un bit
    # aleatorio (mide en la base equivocada). Esto genera los errores del
    # protocolo BB84 cuando Eve intercepta y reenvia los fotones.
    eve_results = np.where(same, alice_bits, coin).astype(np.uint8)

    # Donde intercepta, Bob recibe (bit de Eve, base de Eve); donde no, el original
    out_bits = np.where(intercepted, eve_results, alice_bits).astype(np.uint8)
    out_bases = np.where(intercepted, eve_bases, alice_bases).astype(np.uint8)
    return out_bits, out_bases, intercepted.astype(np.uint8)
