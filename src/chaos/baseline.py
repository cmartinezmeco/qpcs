"""src/chaos/baseline.py - AES-256-GCM y el flujo trivial de contraste.

Es la tesis del modulo (guia Fase 3, cap. 6.6): estas dos referencias se
miden con las mismas metricas que el esquema caotico. El resultado
esperado es que las tres columnas salgan iguales, lo que demuestra que
esas metricas no prueban seguridad, solo ausencia de defectos groseros.

De las dos, la importante es la SEGUNDA. Que AES pase las metricas se
puede leer como "AES es bueno"; que las pase tambien SHA256(clave ||
contador) usado como flujo -una construccion que nadie defenderia como
cifrado serio- cierra esa escapatoria y hace la conclusion inevitable.
Sin esa tercera columna, el lector puede pensar que el esquema caotico
"se acerca a AES".

Lo que la tabla NO puede ensenar y hay que escribir aparte: AES-256-GCM
tiene veinticinco anos de criptoanalisis publico, un proceso de
estandarizacion abierto y autenticacion (el tag de GCM); el esquema
caotico y el contador trivial no tienen nada de eso. Esa fila -"prueba de
seguridad: ninguna / si / ninguna"- es la unica de la tabla que separa
las tres columnas, y no sale de ninguna medida.

AES-GCM sale de la libreria `cryptography`, la misma que usa el modulo 2
para el cifrado hibrido (src/pqc/hybrid.py). Aqui no se implementa
criptografia a mano.
"""

from __future__ import annotations

import hashlib
import os

import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .types import Imagen

# AES-256: 32 bytes de clave. GCM: 12 bytes de nonce (96 bits, el tamano
# nativo; con cualquier otra longitud el estandar obliga a pasar el nonce
# por GHASH, mas lento y sin ninguna ventaja) y 16 de tag.
LONGITUD_CLAVE_AES = 32
LONGITUD_NONCE_AES = 12
LONGITUD_TAG_AES = 16

# Tamano del bloque del flujo trivial: SHA-256 produce 32 bytes por
# llamada.
_BLOQUE_SHA256 = 32


def cifrar_aes_gcm(img: Imagen, clave: bytes) -> tuple[Imagen, bytes, bytes]:
    """Cifra la imagen con AES-256-GCM.

    A diferencia del esquema caotico, usa un nonce fresco por llamada:
    dos cifrados de la misma imagen con la misma clave NO son iguales
    (contraste con la limitacion del cap. 6.6).

    El tag de 16 bytes se devuelve por separado y no concatenado a los
    datos por un motivo de medida: la tabla de metricas compara imagenes
    del MISMO tamano que el original, y GCM devuelve ciphertext||tag, 16
    bytes de mas que no son pixeles. Dejarlos dentro descuadraria la forma
    y contaminaria el histograma con 16 valores que no vienen del cifrado
    de la imagen.

    Que el tag exista es, ademas, la diferencia de fondo con las otras dos
    columnas de la tabla: AES-GCM autentica y el esquema caotico no.

    Args:
        img: imagen uint8, cualquier forma.
        clave: 32 bytes.

    Returns:
        (datos_cifrados_como_imagen, nonce, tag) para poder descifrar
        y para poder medir metricas sobre datos_cifrados_como_imagen.

    Raises:
        ValueError: si la clave no mide 32 bytes o la imagen no es uint8.
    """
    if len(clave) != LONGITUD_CLAVE_AES:
        raise ValueError(
            f"AES-256 necesita una clave de {LONGITUD_CLAVE_AES} bytes y se "
            f"han dado {len(clave)}"
        )
    if img.dtype != np.uint8:
        raise ValueError(f"la imagen debe ser uint8 y es {img.dtype}")

    nonce = os.urandom(LONGITUD_NONCE_AES)
    plano = np.ascontiguousarray(img)
    cifrado_con_tag = AESGCM(clave).encrypt(nonce, plano.tobytes(), None)

    cuerpo = cifrado_con_tag[:-LONGITUD_TAG_AES]
    tag = cifrado_con_tag[-LONGITUD_TAG_AES:]
    datos: Imagen = np.frombuffer(cuerpo, dtype=np.uint8).reshape(img.shape).copy()
    return datos, nonce, tag


def cifrar_flujo_trivial(img: Imagen, clave: bytes) -> Imagen:
    """XOR con SHA256(clave || contador) repetido. Deliberadamente
    simplista: nadie lo defenderia como cifrado serio. Sirve para
    demostrar que pasa las metricas igual de bien que AES y que el
    esquema caotico (cap. 6.6, tercera columna de la tabla).

    El flujo es la concatenacion de SHA256(clave || i) para i = 0, 1, 2...
    con el contador en 8 bytes big-endian, truncada al tamano de la
    imagen. No hay nonce, no hay encadenado, no hay autenticacion y el
    flujo no depende del texto plano: cifrar dos imagenes con la misma
    clave permite recuperar el XOR de las dos con una resta. Y aun asi da
    entropia ~7.997, correlacion ~0, NPCR ~99.61% y UACI ~33.46%.

    Esa es toda la leccion del modulo en una funcion de diez lineas.

    Args:
        img: imagen uint8, cualquier forma.
        clave: clave de cualquier longitud (va como prefijo del hash).

    Returns:
        La imagen cifrada, misma forma y dtype.

    Raises:
        ValueError: si la imagen no es uint8.
    """
    if img.dtype != np.uint8:
        raise ValueError(f"la imagen debe ser uint8 y es {img.dtype}")

    plano = np.ascontiguousarray(img).ravel()
    n_bloques = (plano.size + _BLOQUE_SHA256 - 1) // _BLOQUE_SHA256
    flujo = b"".join(
        hashlib.sha256(clave + i.to_bytes(8, "big")).digest() for i in range(n_bloques)
    )
    keystream = np.frombuffer(flujo, dtype=np.uint8)[: plano.size]
    cifrada: Imagen = (plano ^ keystream).reshape(img.shape)
    return cifrada
