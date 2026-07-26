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

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa, x25519

# Los dos rellenos, fijados UNA sola vez para que quien cifra y quien descifra
# (y el benchmark de la tarea 2.7) usen exactamente los mismos parametros: un
# OAEP con distinto hash en cada lado no descifra. Son objetos de valor sin
# estado interno, asi que compartirlos entre llamadas es seguro.
#
# OAEP para cifrar y PSS para firmar, NUNCA PKCS#1 v1.5: el v1.5 de cifrado es
# vulnerable a Bleichenbacher (oraculo de relleno) y el de firma no tiene
# reduccion de seguridad demostrada. Los dos modernos son probabilisticos, de
# ahi que cifrar o firmar dos veces el mismo mensaje de resultados distintos
# (hay un test que lo comprueba: es la propiedad, no un efecto raro).
_OAEP = padding.OAEP(
    mgf=padding.MGF1(algorithm=hashes.SHA256()),
    algorithm=hashes.SHA256(),
    label=None,
)
_PSS = padding.PSS(
    mgf=padding.MGF1(algorithm=hashes.SHA256()),
    salt_length=padding.PSS.MAX_LENGTH,
)


def _cargar_rsa_publica(clave_publica_pem: bytes) -> rsa.RSAPublicKey:
    """Deserializa una clave publica RSA en PEM y comprueba que lo es.

    `load_pem_public_key` devuelve la union de todos los tipos de clave que
    entiende `cryptography` (RSA, EC, Ed25519...). El isinstance estrecha ese
    tipo para mypy --strict y, de paso, convierte "me han pasado una clave
    Ed25519 por error" en un TypeError legible en vez de un AttributeError
    tres llamadas mas abajo.
    """
    clave = serialization.load_pem_public_key(clave_publica_pem)
    if not isinstance(clave, rsa.RSAPublicKey):
        raise TypeError("se esperaba una clave publica RSA en PEM")
    return clave


def _cargar_rsa_privada(clave_privada_pem: bytes) -> rsa.RSAPrivateKey:
    """Deserializa una clave privada RSA en PEM (sin cifrar). Ver el gemelo.

    password=None porque estas claves viven en memoria durante un benchmark,
    no en disco: cifrar el PEM aqui daria una falsa sensacion de custodia. La
    gestion de claves persistente esta explicitamente fuera de la Fase 2.
    """
    clave = serialization.load_pem_private_key(clave_privada_pem, password=None)
    if not isinstance(clave, rsa.RSAPrivateKey):
        raise TypeError("se esperaba una clave privada RSA en PEM")
    return clave


def rsa_generar(bits: int = 3072) -> tuple[bytes, bytes]:
    """Genera un par RSA y devuelve (clave_publica_pem, clave_privada_pem).

    3072 bits es el nivel de seguridad clasico ~128 bits, el comparable con
    ML-KEM-768 / ML-DSA-65 en las tablas del benchmark (tarea 2.7). Comparar
    RSA-2048 (~112 bits) contra ML-KEM-768 (nivel NIST 3) seria comparar peras
    con manzanas y regalarle ventaja a RSA en los tiempos.

    El exponente publico es 65537: el estandar de facto (primo de Fermat F4,
    con solo dos bits a 1, asi que cifrar y verificar son baratos) y el unico
    valor que `cryptography` recomienda sin reservas.
    """
    privada = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    # SubjectPublicKeyInfo / PKCS#8: los formatos PEM canonicos, los que
    # interoperan con OpenSSL y los que hacen que len(pem) sea un tamano
    # comparable en el benchmark.
    clave_publica_pem = privada.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    clave_privada_pem = privada.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return clave_publica_pem, clave_privada_pem


def rsa_cifrar_oaep(clave_publica_pem: bytes, mensaje: bytes) -> bytes:
    """Cifra `mensaje` con RSA-OAEP (padding probabilistico, SHA-256).

    OAEP y no PKCS#1 v1.5: este ultimo es vulnerable a Bleichenbacher. El
    mensaje debe caber en el modulo menos el overhead de OAEP.

    Ese limite es duro y es la razon de ser de los KEM: con RSA-3072 caben
    k - 2*hLen - 2 = 384 - 64 - 2 = 318 bytes y ni uno mas; pasarse levanta
    ValueError (lo cubre un test). Para mensajes de verdad se usa el patron
    hibrido, exactamente igual que ML-KEM en `hybrid.py`.
    """
    return _cargar_rsa_publica(clave_publica_pem).encrypt(mensaje, _OAEP)


def rsa_descifrar_oaep(clave_privada_pem: bytes, texto_cifrado: bytes) -> bytes:
    """Descifra un texto producido por `rsa_cifrar_oaep`. Inversa exacta."""
    return _cargar_rsa_privada(clave_privada_pem).decrypt(texto_cifrado, _OAEP)


def rsa_firmar_pss(clave_privada_pem: bytes, mensaje: bytes) -> bytes:
    """Firma `mensaje` con RSA-PSS (relleno probabilistico, SHA-256).

    PSS y no PKCS#1 v1.5 por la misma razon que OAEP: es la construccion con
    reduccion de seguridad demostrada.

    salt_length=MAX_LENGTH es el maximo que cabe en el modulo, que es lo que
    recomienda la RFC 8017 cuando no hay que interoperar con nada heredado.
    """
    return _cargar_rsa_privada(clave_privada_pem).sign(mensaje, _PSS, hashes.SHA256())


def rsa_verificar_pss(clave_publica_pem: bytes, mensaje: bytes, firma: bytes) -> bool:
    """Verifica una firma RSA-PSS. True si es valida, False si no.

    La implementacion captura la InvalidSignature de `cryptography` y la
    convierte en False: nunca deja escapar la excepcion al llamador.

    Asi la firma clasica y la post-cuantica (`sig.verificar`) tienen la misma
    forma -bool- y el benchmark puede cronometrarlas con el mismo codigo. Solo
    se captura InvalidSignature: un PEM corrupto sigue siendo un TypeError o
    un ValueError ruidoso, que es un fallo del llamador, no una firma invalida.
    """
    try:
        _cargar_rsa_publica(clave_publica_pem).verify(
            firma, mensaje, _PSS, hashes.SHA256()
        )
    except InvalidSignature:
        return False
    return True


def x25519_generar() -> tuple[bytes, bytes]:
    """Genera un par X25519 y devuelve (clave_publica_raw, clave_privada_raw).

    Formato raw de 32 bytes (RFC 7748), no PEM: X25519 no tiene overhead de
    codificacion y asi el tamano que reporta el benchmark es el real. Ese 32
    contra los 1184 de ML-KEM-768 es justo el precio en bytes de la migracion
    post-cuantica que la tabla de la tarea 2.7 tiene que ensenar.
    """
    privada = x25519.X25519PrivateKey.generate()
    clave_publica_raw = privada.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    clave_privada_raw = privada.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return clave_publica_raw, clave_privada_raw


def x25519_intercambio(clave_privada_raw: bytes, clave_publica_par_raw: bytes) -> bytes:
    """Diffie-Hellman sobre Curve25519: devuelve el secreto compartido (32 B).

    Es el analogo clasico del `kem_encapsular` de `kem.py`: ambos lados
    derivan el mismo secreto. En un canal real ese secreto pasa por un HKDF
    antes de usarse como clave simetrica (ver `hybrid.py`).

    La simetria es la propiedad que lo define y la que testeamos: intercambio
    (priv_a, pub_b) == intercambio(priv_b, pub_a). La diferencia con un KEM es
    que aqui los dos lados aportan una clave; en ML-KEM el emisor solo necesita
    la publica del receptor.
    """
    privada = x25519.X25519PrivateKey.from_private_bytes(clave_privada_raw)
    publica_par = x25519.X25519PublicKey.from_public_bytes(clave_publica_par_raw)
    return privada.exchange(publica_par)


def ed25519_generar() -> tuple[bytes, bytes]:
    """Genera un par Ed25519 y devuelve (clave_publica_raw, clave_privada_raw).

    Formato raw de 32 bytes. Ed25519 es determinista (RFC 8032): la firma no
    consume aleatoriedad, asi que aqui tampoco entra ningun rng.
    """
    privada = ed25519.Ed25519PrivateKey.generate()
    clave_publica_raw = privada.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    clave_privada_raw = privada.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return clave_publica_raw, clave_privada_raw


def ed25519_firmar(clave_privada_raw: bytes, mensaje: bytes) -> bytes:
    """Firma `mensaje` con Ed25519. Devuelve la firma de 64 bytes.

    Esos 64 bytes son la referencia clasica del titular del modulo: una firma
    ML-DSA-65 ocupa 3309, unas 50 veces mas (ver `tamanos_sig` en 2.7).
    """
    privada = ed25519.Ed25519PrivateKey.from_private_bytes(clave_privada_raw)
    return privada.sign(mensaje)


def ed25519_verificar(clave_publica_raw: bytes, mensaje: bytes, firma: bytes) -> bool:
    """Verifica una firma Ed25519. True si es valida, False si no.

    Como en `rsa_verificar_pss`, la InvalidSignature se traduce a False.
    """
    publica = ed25519.Ed25519PublicKey.from_public_bytes(clave_publica_raw)
    try:
        publica.verify(firma, mensaje)
    except InvalidSignature:
        return False
    return True
