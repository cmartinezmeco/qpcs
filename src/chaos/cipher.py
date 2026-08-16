"""src/chaos/cipher.py - orquestador: cifrar_imagen / descifrar_imagen.

Ata la cadena completa: keystream -> permutacion -> difusion (ida y
vuelta). El descifrado invierte las etapas EN ORDEN INVERSO: la
composicion de funciones se deshace al reves (guia Fase 3, cap. 5.4).

Este modulo NO usa np.random en ningun sitio: el cifrado es enteramente
determinista a partir de la clave. Si aparece un np.random aqui, es un bug.
"""

from __future__ import annotations

from .types import ClaveCaotica, Imagen, ImagenCifrada


def cifrar_imagen(img: Imagen, clave: ClaveCaotica) -> ImagenCifrada:
    """Cifra una imagen en escala de grises con la clave dada.

    Cadena: generar keystream -> permutar -> difundir hacia adelante ->
    difundir hacia atras (para que la avalancha cubra tambien el ultimo
    pixel, ver guia Fase 3 cap. 5.3).

    Args:
        img: imagen uint8, cualquier forma (alto, ancho).
        clave: la clave caotica, logistica o Lorenz.

    Returns:
        ImagenCifrada con los datos cifrados y los metadatos necesarios
        para descifrar (forma, sistema, iv, hash del plano).
    """
    raise NotImplementedError


def descifrar_imagen(cifrada: ImagenCifrada, clave: ClaveCaotica) -> Imagen:
    """Descifra una ImagenCifrada con la clave dada.

    Debe ser EXACTAMENTE la inversa de cifrar_imagen: deshacer difusion
    hacia atras, deshacer difusion hacia adelante, aplicar la permutacion
    inversa. Ese orden, y no otro.

    Args:
        cifrada: el resultado de cifrar_imagen.
        clave: debe coincidir con clave.sistema usado al cifrar.

    Returns:
        La imagen original, uint8, bit a bit identica si la clave es correcta.
    """
    raise NotImplementedError
