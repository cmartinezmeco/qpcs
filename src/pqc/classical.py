"""src/pqc/classical.py - tarea 2.4 (Marco). Cripto clasica de referencia.

La linea base contra la que se compara la PQC: RSA (OAEP para cifrar, PSS para
firmar) y curva eliptica (X25519 para intercambio de clave, Ed25519 para
firma). Todo se construye sobre la libreria `cryptography` (pyca), que trae
sus propios stubs de tipos, asi que no necesita override de mypy.

A diferencia de la parte Shor, aqui NO entra ningun np.random.Generator: las
claves las genera la propia `cryptography` con su CSPRNG interno y deben ser
impredecibles por seguridad. Los tests de la tarea 2.4 comprueban PROPIEDADES
(descifrar deshace cifrar, una firma valida verifica, una manipulada no), no
valores fijos.

Serializacion: las claves cruzan estas fronteras como bytes PEM/raw para que
`benchmark.py` y los tests midan tamanos reales sin acoplarse a los objetos de
`cryptography`.
"""

from __future__ import annotations


def rsa_generar(bits: int = 3072) -> tuple[bytes, bytes]:
    """Genera un par RSA y devuelve (clave_publica_pem, clave_privada_pem).

    3072 bits es el nivel de seguridad clasico ~128 bits, el comparable con
    ML-KEM-768 / ML-DSA-65 en las tablas del benchmark (tarea 2.7).
    """
    raise NotImplementedError


def rsa_cifrar_oaep(clave_publica_pem: bytes, mensaje: bytes) -> bytes:
    """Cifra `mensaje` con RSA-OAEP (padding probabilistico, SHA-256).

    OAEP y no PKCS#1 v1.5: este ultimo es vulnerable a Bleichenbacher. El
    mensaje debe caber en el modulo menos el overhead de OAEP.
    """
    raise NotImplementedError


def rsa_descifrar_oaep(clave_privada_pem: bytes, texto_cifrado: bytes) -> bytes:
    """Descifra un texto producido por `rsa_cifrar_oaep`. Inversa exacta."""
    raise NotImplementedError


def rsa_firmar_pss(clave_privada_pem: bytes, mensaje: bytes) -> bytes:
    """Firma `mensaje` con RSA-PSS (relleno probabilistico, SHA-256).

    PSS y no PKCS#1 v1.5 por la misma razon que OAEP: es la construccion con
    reduccion de seguridad demostrada.
    """
    raise NotImplementedError


def rsa_verificar_pss(clave_publica_pem: bytes, mensaje: bytes, firma: bytes) -> bool:
    """Verifica una firma RSA-PSS. True si es valida, False si no.

    La implementacion captura la InvalidSignature de `cryptography` y la
    convierte en False: nunca deja escapar la excepcion al llamador.
    """
    raise NotImplementedError


def x25519_generar() -> tuple[bytes, bytes]:
    """Genera un par X25519 y devuelve (clave_publica_raw, clave_privada_raw).

    Formato raw de 32 bytes (RFC 7748), no PEM: X25519 no tiene overhead de
    codificacion y asi el tamano que reporta el benchmark es el real.
    """
    raise NotImplementedError


def x25519_intercambio(clave_privada_raw: bytes, clave_publica_par_raw: bytes) -> bytes:
    """Diffie-Hellman sobre Curve25519: devuelve el secreto compartido (32 B).

    Es el analogo clasico del `kem_encapsular` de `kem.py`: ambos lados
    derivan el mismo secreto. En un canal real ese secreto pasa por un HKDF
    antes de usarse como clave simetrica (ver `hybrid.py`).
    """
    raise NotImplementedError


def ed25519_generar() -> tuple[bytes, bytes]:
    """Genera un par Ed25519 y devuelve (clave_publica_raw, clave_privada_raw).

    Formato raw de 32 bytes. Ed25519 es determinista (RFC 8032): la firma no
    consume aleatoriedad, asi que aqui tampoco entra ningun rng.
    """
    raise NotImplementedError


def ed25519_firmar(clave_privada_raw: bytes, mensaje: bytes) -> bytes:
    """Firma `mensaje` con Ed25519. Devuelve la firma de 64 bytes."""
    raise NotImplementedError


def ed25519_verificar(clave_publica_raw: bytes, mensaje: bytes, firma: bytes) -> bool:
    """Verifica una firma Ed25519. True si es valida, False si no.

    Como en `rsa_verificar_pss`, la InvalidSignature se traduce a False.
    """
    raise NotImplementedError
