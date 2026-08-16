"""src/chaos/permutation.py - permutacion de pixeles por ordenamiento.

kind="stable" es OBLIGATORIO en cualquier argsort de este fichero, no una
preferencia de estilo: el introsort por defecto de NumPy no garantiza el
mismo orden ante valores empatados de la orbita. Los empates son
improbables (~5e-7 por imagen de 256x256, por la paradoja del cumpleanos)
pero no imposibles, y uno solo hace el cifrado irreversible en otra
version de NumPy (guia Fase 3, cap. 5.2).
"""

from __future__ import annotations

from .types import Orbita, Permutacion


def permutacion_desde_orbita(orb: Orbita, m: int) -> Permutacion:
    """Permutacion de m elementos por ordenamiento por indice.

    Args:
        orb: orbita de la que sacar los valores a ordenar. Debe tener
            al menos m elementos.
        m: numero de elementos a permutar (alto * ancho de la imagen).

    Returns:
        Array int64 de longitud m: sigma tal que orb[:m][sigma] esta
        ordenado. kind="stable" es obligatorio.
    """
    raise NotImplementedError


def invertir_permutacion(sigma: Permutacion) -> Permutacion:
    """Inversa de una permutacion, sin bucles, en O(m).

    Args:
        sigma: la permutacion a invertir.

    Returns:
        sigma_inv tal que sigma_inv[sigma[i]] == i para todo i.
    """
    raise NotImplementedError
