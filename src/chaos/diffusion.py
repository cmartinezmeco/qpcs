"""src/chaos/diffusion.py - difusion por XOR encadenado, ida y vuelta.

La difusion hacia adelante es intrinsecamente SECUENCIAL (cada byte
depende del anterior) y no se puede vectorizar. Deshacerla SI es
vectorizable, porque los c_{i-1} ya son la entrada conocida. Esa
asimetria es la razon de que descifrar sea mas rapido que cifrar en el
benchmark (guia Fase 3, cap. 5.3).
"""

from __future__ import annotations

from .types import Keystream


def difundir_adelante(p: Keystream, k: Keystream, iv: int) -> Keystream:
    """c_i = p_i XOR k_i XOR c_{i-1}, con c_{-1} = iv.

    Args:
        p: datos a difundir (texto plano permutado, aplanado).
        k: keystream, misma longitud que p.
        iv: byte inicial de la cadena, derivado de la clave.

    Returns:
        c: el resultado difundido, misma longitud que p.
    """
    raise NotImplementedError


def deshacer_adelante(c: Keystream, k: Keystream, iv: int) -> Keystream:
    """p_i = c_i XOR k_i XOR c_{i-1}. Inversa exacta de difundir_adelante.

    Vectorizable: c_{i-1} es la entrada, no hay que calcularla paso a paso.
    """
    raise NotImplementedError
