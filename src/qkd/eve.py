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
    Nota de diseño: esta funcion recibe alice_bases porque en la simulacion hay
    que calcular el resultado de la medida de Eve, no porque Eve las conozca.
    Eve NUNCA usa alice_bases para elegir su base: ver la linea de eve_bases.
    """
    n = alice_bits.size
    intercepted = rng.random(n) < rate # Máscara booleana de los fotones interceptados por Eve. Se genera un número en el intervalo [0, 1) y si es menor que rate, se considera interceptado. Esto asegura que la fracción de fotones interceptados sea aproximadamente rate.
    eve_bases = rng.integers(0, 2, size=n, dtype=np.uint8) # <- al azar, sin conocer alice_bases. Esto es lo que hace que el ataque sea imperfecto y genere errores.
    
    same = alice_bases == eve_bases # Posiciones donde las bases de Alice y Eve coinciden. En estas posiciones, Eve medirá el mismo bit que Alice. En las posiciones donde no coinciden, Eve medirá un bit aleatorio.
    coin = rng.integers(0, 2, size=n, dtype=np.uint8)
    eve_results = np.where(same, alice_bits, coin).astype(np.uint8) # En las posiciones donde las bases coinciden, Eve obtiene el bit de Alice; donde no, obtiene un bit aleatorio (simulando la medida en la base equivocada). Esto es lo que genera errores en el protocolo BB84 cuando Eve intercepta y reenvía los fotones.
    
    # Donde intercepta, Bob recibe (bit de Eve, base de Eve); donde no, el original
    out_bits = np.where(intercepted, eve_results, alice_bits).astype(np.uint8)
    out_bases = np.where(intercepted, eve_bases, alice_bases).astype(np.uint8)
    return out_bits, out_bases, intercepted.astype(np.uint8)
