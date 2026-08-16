"""src/chaos/baseline.py - AES-256-GCM y el flujo trivial de contraste.

Es la tesis del modulo (guia Fase 3, cap. 6.6): estas dos referencias se
miden con las mismas metricas que el esquema caotico. El resultado
esperado es que las tres columnas salgan iguales, lo que demuestra que
esas metricas no prueban seguridad, solo ausencia de defectos groseros.
"""

from __future__ import annotations

from .types import Imagen


def cifrar_aes_gcm(img: Imagen, clave: bytes) -> tuple[Imagen, bytes, bytes]:
    """Cifra la imagen con AES-256-GCM.

    A diferencia del esquema caotico, usa un nonce fresco por llamada:
    dos cifrados de la misma imagen con la misma clave NO son iguales
    (contraste con la limitacion del cap. 6.6).

    Args:
        img: imagen uint8, cualquier forma.
        clave: 32 bytes.

    Returns:
        (datos_cifrados_como_imagen, nonce, tag) para poder descifrar
        y para poder medir metricas sobre datos_cifrados_como_imagen.
    """
    raise NotImplementedError


def cifrar_flujo_trivial(img: Imagen, clave: bytes) -> Imagen:
    """XOR con SHA256(clave || contador) repetido. Deliberadamente
    simplista: nadie lo defenderia como cifrado serio. Sirve para
    demostrar que pasa las metricas igual de bien que AES y que el
    esquema caotico (cap. 6.6, tercera columna de la tabla).
    """
    raise NotImplementedError
