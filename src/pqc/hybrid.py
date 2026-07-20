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

from .types import MensajeCifrado


def cifrar_mensaje(
    clave_publica: bytes, mensaje: bytes, mecanismo: str = "ML-KEM-768"
) -> MensajeCifrado:
    """Cifra `mensaje` para el titular de `clave_publica` (ML-KEM).

    Implementacion (2.5): kem_encapsular -> HKDF-SHA256 sobre el secreto ->
    AES-256-GCM con nonce aleatorio de 12 bytes. Empaqueta todo en un
    `MensajeCifrado`. El nonce NUNCA se reutiliza con la misma clave (cada
    llamada deriva clave+nonce nuevos).
    """
    raise NotImplementedError


def descifrar_mensaje(clave_privada: bytes, sobre: MensajeCifrado) -> bytes:
    """Descifra un `MensajeCifrado` producido por `cifrar_mensaje`.

    Implementacion (2.5): kem_desencapsular del `sobre.kem_ciphertext` con la
    clave privada -> mismo HKDF -> AES-256-GCM descifra y verifica el tag. Si
    el tag no cuadra (mensaje manipulado) AES-GCM lanza y no se devuelve texto
    en claro: es la garantia de autenticidad del AEAD.
    """
    raise NotImplementedError
