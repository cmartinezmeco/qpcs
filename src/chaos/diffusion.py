"""src/chaos/diffusion.py - difusion por XOR encadenado, ida y vuelta.

La difusion hacia adelante es intrinsecamente SECUENCIAL (cada byte
depende del anterior) y no se puede vectorizar. Deshacerla SI es
vectorizable, porque los c_{i-1} ya son la entrada conocida. Esa
asimetria es la razon de que descifrar sea mas rapido que cifrar en el
benchmark (guia Fase 3, cap. 5.3).

Por que encadenado y no un XOR simple: con c_i = p_i XOR k_i, cambiar un
pixel del plano cambia UN pixel del cifrado y NPCR saldria 1/M (0.0015 %)
en vez del 99.6 % que pide el criterio de cierre. El encadenado propaga
el cambio en avalancha hacia adelante. La pasada hacia atras (que el
orquestador construye con estas mismas dos funciones sobre el array
invertido, ver cipher.py) es lo que hace que la avalancha alcance tambien
al ULTIMO pixel.
"""

from __future__ import annotations

import numpy as np

from .types import Keystream


def difundir_adelante(p: Keystream, k: Keystream, iv: int) -> Keystream:
    """c_i = p_i XOR k_i XOR c_{i-1}, con c_{-1} = iv.

    Args:
        p: datos a difundir (texto plano permutado, aplanado).
        k: keystream, misma longitud que p.
        iv: byte inicial de la cadena, derivado de la clave.

    Returns:
        c: el resultado difundido, misma longitud que p.

    Raises:
        ValueError: si k es mas corto que p. Es el tercero de los errores
            tipicos de la tarea 3.6 (guia Fase 3, cap. 5.4): un keystream
            regenerado con otra longitud desalinea el flujo desde el primer
            byte, y truncar en silencio convertiria eso en ruido en vez de
            en un error.
    """
    if k.size != p.size:
        raise ValueError(
            f"keystream de {k.size} bytes para {p.size} datos: las longitudes "
            f"deben coincidir exactamente (la del cifrado se deriva de las "
            f"dimensiones, que viajan en ImagenCifrada)"
        )

    # SECUENCIAL por naturaleza: cada paso necesita el anterior. Si alguien
    # "lo vectoriza", esta calculando otra cosa. Se opera sobre listas de
    # int de Python y no sobre escalares de NumPy porque el bucle es el
    # cuello de botella del cifrado (512x512 son 262144 vueltas, y otras
    # tantas en la pasada de vuelta) y un escalar uint8 de NumPy cuesta un
    # orden de magnitud mas que un int por iteracion. El resultado es
    # identico bit a bit: XOR sobre enteros de 0..255 es exacto.
    # strict=True: las longitudes ya se han comprobado arriba, asi que
    # esto es un cinturon mas. Si alguna vez dejasen de coincidir, es
    # preferible una excepcion a un keystream truncado en silencio.
    p_lista = p.tolist()
    k_lista = k.tolist()
    salida = [0] * len(p_lista)
    anterior = int(iv) & 0xFF
    for i, (pi, ki) in enumerate(zip(p_lista, k_lista, strict=True)):
        anterior = pi ^ ki ^ anterior
        salida[i] = anterior
    return np.array(salida, dtype=np.uint8)


def deshacer_adelante(c: Keystream, k: Keystream, iv: int) -> Keystream:
    """p_i = c_i XOR k_i XOR c_{i-1}. Inversa exacta de difundir_adelante.

    Vectorizable: c_{i-1} es la entrada, no hay que calcularla paso a paso.
    De ahi que descifrar salga uno o dos ordenes de magnitud mas rapido que
    cifrar en el benchmark, y hay que decirlo en el README para que no
    parezca un error de medida (guia Fase 3, cap. 5.3).

    Args:
        c: datos difundidos.
        k: el MISMO keystream que se uso al difundir.
        iv: el MISMO byte inicial.

    Returns:
        p: los datos originales.

    Raises:
        ValueError: si k no tiene la longitud de c (mismo motivo que arriba).
    """
    if k.size != c.size:
        raise ValueError(
            f"keystream de {k.size} bytes para {c.size} datos: las longitudes "
            f"deben coincidir exactamente"
        )
    inicial = np.array([int(iv) & 0xFF], dtype=np.uint8)
    previos: Keystream = np.concatenate((inicial, c[:-1]))
    resultado: Keystream = c ^ k ^ previos
    return resultado
