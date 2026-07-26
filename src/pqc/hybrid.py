"""src/pqc/hybrid.py - tarea 2.5 (Marco). Cifrado hibrido real (KEM + AEAD).

Un KEM (ver `kem.py`) solo acuerda un secreto corto; no cifra mensajes. El
esquema hibrido estandar convierte ese secreto en cifrado autenticado de
longitud arbitraria:

    1. KEM:      encapsular contra la clave publica -> (kem_ciphertext, secreto)
    2. HKDF:     derivar del `secreto` una clave AES de 256 bits (SHA-256)
    3. AES-GCM:  cifrar el mensaje con esa clave y un nonce fresco -> tag+cipher

El receptor desencapsula el `kem_ciphertext` con su clave privada, repite el
HKDF y descifra. El resultado empaquetado es un `MensajeCifrado` (ver
`types.py`): kem_ciphertext + nonce + aead_ciphertext + mecanismo.

Es "hibrido" en el sentido KEM+simetrico; combinarlo ademas con un KEM clasico
(X25519) para defensa en profundidad seria una capa extra fuera del alcance de
esta tarea. HKDF y AES-GCM salen de la libreria `cryptography`.
"""

from __future__ import annotations

import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .kem import kem_desencapsular, kem_encapsular
from .types import MensajeCifrado

# Etiqueta de dominio del HKDF: ata la clave derivada a ESTE uso concreto. Si
# el mismo secreto del KEM se reutilizase para otra cosa (autenticar, cifrar
# otro canal), un `info` distinto daria una clave independiente. Cambiarla
# rompe la compatibilidad con sobres ya cifrados, de ahi el sufijo de version.
_INFO = b"qpcs-fase2-mlkem-aesgcm-v1"

# AES-256-GCM: 32 bytes de clave y 12 de nonce. Los 12 no son un capricho, son
# el tamano nativo de GCM (96 bits): con cualquier otra longitud el estandar
# obliga a pasar el nonce por GHASH, mas lento y sin ninguna ventaja.
_LONGITUD_CLAVE = 32
_LONGITUD_NONCE = 12


def _clave_aes(secreto: bytes) -> bytes:
    """Deriva la clave AES-256 del secreto compartido del KEM (HKDF-SHA256).

    Por que no usar los 32 bytes del KEM directamente como clave AES: el
    secreto de ML-KEM es uniforme, si, pero el KDF es la pieza que fija el
    dominio (`_INFO`) y la que dejaria derivar varias claves independientes
    del mismo secreto. Es lo que hace TLS y cuesta microsegundos.

    salt=None: HKDF usa entonces un salt de ceros, que es exactamente lo
    correcto cuando la entrada ya es una clave uniforme y no una contrasena.
    """
    return HKDF(
        algorithm=hashes.SHA256(),
        length=_LONGITUD_CLAVE,
        salt=None,
        info=_INFO,
    ).derive(secreto)


def cifrar_mensaje(
    clave_publica: bytes, mensaje: bytes, mecanismo: str = "ML-KEM-768"
) -> MensajeCifrado:
    """Cifra `mensaje` para el titular de `clave_publica` (ML-KEM).

    Encadena kem_encapsular -> HKDF-SHA256 sobre el secreto -> AES-256-GCM con
    nonce aleatorio de 12 bytes, y empaqueta todo en un `MensajeCifrado`.

    El nonce NUNCA se reutiliza con la misma clave: sale de os.urandom(12) en
    cada llamada y, ademas, cada llamada encapsula de nuevo y por tanto deriva
    una clave AES distinta. Repetir nonce y clave a la vez en GCM no filtra un
    mensaje: filtra la clave de autenticacion y permite falsificar tags. Es el
    fallo clasico de este patron, y por eso aqui no hay ningun valor constante.

    A diferencia de RSA-OAEP (limitado a 318 bytes con 3072 bits, ver
    `classical.rsa_cifrar_oaep`), aqui el mensaje puede tener cualquier tamano:
    lo cifra AES, no el algoritmo asimetrico. Esa es toda la gracia del hibrido.
    """
    kem_ciphertext, secreto = kem_encapsular(clave_publica, mecanismo)
    nonce = os.urandom(_LONGITUD_NONCE)
    # None como datos asociados: no hay cabecera en claro que autenticar. El
    # mecanismo viaja en el dataclass, pero no se pasa como AAD porque el
    # receptor ya lo necesita ANTES para elegir con que KEM desencapsular.
    aead_ciphertext = AESGCM(_clave_aes(secreto)).encrypt(nonce, mensaje, None)
    return MensajeCifrado(kem_ciphertext, nonce, aead_ciphertext, mecanismo)


def descifrar_mensaje(clave_privada: bytes, sobre: MensajeCifrado) -> bytes:
    """Descifra un `MensajeCifrado` producido por `cifrar_mensaje`.

    Deshace la cadena: kem_desencapsular del `sobre.kem_ciphertext` con la
    clave privada -> mismo HKDF -> AES-256-GCM descifra y verifica el tag. Si
    el tag no cuadra (mensaje manipulado) AES-GCM lanza y no se devuelve texto
    en claro: es la garantia de autenticidad del AEAD.

    Esa excepcion, `InvalidTag`, es el resultado esperado del test de
    manipulacion y NO se captura aqui a proposito: devolver None o basura ante
    un mensaje alterado convertiria un fallo de seguridad en algo que el
    llamador puede ignorar por descuido.

    Cubre los dos tipos de manipulacion con el mismo mecanismo:
      - Tocar el aead_ciphertext o el nonce: el tag de GCM no cuadra.
      - Tocar el kem_ciphertext: ML-KEM no protesta (rechazo implicito, ver
        `kem_desencapsular`), pero devuelve otro secreto, el HKDF da otra clave
        y el tag tampoco cuadra. Misma InvalidTag por otro camino.
    """
    secreto = kem_desencapsular(clave_privada, sobre.kem_ciphertext, sobre.mecanismo)
    return AESGCM(_clave_aes(secreto)).decrypt(sobre.nonce, sobre.aead_ciphertext, None)
