"""src/chaos/permutation.py - permutacion de pixeles por ordenamiento.

kind="stable" es OBLIGATORIO en cualquier argsort de este fichero, no una
preferencia de estilo: el introsort por defecto de NumPy no garantiza el
mismo orden ante valores empatados de la orbita. Los empates son
improbables (~5e-7 por imagen de 256x256, por la paradoja del cumpleanos)
pero no imposibles, y uno solo hace el cifrado irreversible en otra
version de NumPy.
"""

from __future__ import annotations

import numpy as np

from .types import Orbita, Permutacion


def permutacion_desde_orbita(orb: Orbita, m: int) -> Permutacion:
    """Permutacion de m elementos por ordenamiento por indice.

    Se ordenan los m primeros valores de la orbita y la permutacion es el
    vector de indices que produce ese orden. Es la alternativa al mapa del
    gato de Arnold que usa casi toda la literatura, y se elige por dos
    motivos concretos:

      1. Arnold exige imagenes CUADRADAS; esto acepta cualquier forma.
      2. Arnold es periodico con periodo corto (192 para N=256): iterarlo
         192 veces devuelve la imagen original SIN la clave. El periodo de
         esta permutacion es el de la orbita subyacente, no un numero
         pequeno derivado de la geometria.

    Args:
        orb: orbita de la que sacar los valores a ordenar. Debe tener
            al menos m elementos.
        m: numero de elementos a permutar (alto * ancho de la imagen).

    Returns:
        Array int64 de longitud m: sigma tal que orb[:m][sigma] esta
        ordenado. kind="stable" es obligatorio.

    Raises:
        ValueError: si la orbita tiene menos de m valores. Truncar en
            silencio daria una permutacion mas corta que la imagen y el
            cifrado seria irreversible sin avisar, que es el fallo
            silencioso al que este modulo tiene que tener mas respeto.
    """
    if orb.size < m:
        raise ValueError(
            f"la orbita tiene {orb.size} valores y hacen falta {m}: "
            f"generar mas orbita, nunca truncar la permutacion"
        )
    # kind="stable" (ver el docstring del modulo). No es una preferencia.
    return np.argsort(orb[:m], kind="stable").astype(np.int64)


def invertir_permutacion(sigma: Permutacion) -> Permutacion:
    """Inversa de una permutacion, sin bucles, en O(m).

    El truco es la asignacion indexada: colocar i en la posicion sigma[i]
    es exactamente la definicion de la inversa, y NumPy lo hace de una
    pasada. Con la convencion de aplicacion `permutada = plano[sigma]`,
    deshacerla es `plano = permutada[sigma_inv]`.

    Args:
        sigma: la permutacion a invertir.

    Returns:
        sigma_inv tal que sigma_inv[sigma[i]] == i para todo i.
    """
    inv: Permutacion = np.empty_like(sigma)
    inv[sigma] = np.arange(sigma.size, dtype=np.int64)
    return inv
