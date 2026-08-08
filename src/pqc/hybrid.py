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

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .kem import kem_desencapsular, kem_encapsular
from .types import MensajeCifrado

# Etiqueta de dominio del HKDF: ata la clave derivada a ESTE uso concreto. Si
# el mismo secreto del KEM se reutilizase para otra cosa (autenticar, cifrar
# otro canal), un `info` distinto daria una clave independiente. Cambiarla
# rompe la compatibilidad con sobres ya cifrados, de ahi el sufijo de version.
#
# v2: el sobre paso a autenticar el campo `mecanismo` como AAD (ver
# cifrar_mensaje). Eso cambia el formato de hecho -un sobre v1 no descifra con
# v2 y al reves-, y un cambio de formato se marca subiendo la version del
# dominio, no dejandolo en silencio. En este proyecto no hay ni un sobre
# persistido (se cifra y se descifra dentro de la misma ejecucion), asi que la
# ruptura no cuesta nada; el numero esta para el dia que si cueste.
_INFO = b"qpcs-fase2-mlkem-aesgcm-v2"

# Mecanismos que se admiten dentro de un sobre. `mecanismo` es el UNICO campo
# del MensajeCifrado que el receptor tiene que INTERPRETAR antes de poder
# verificar nada -lo necesita para elegir con que KEM desencapsular-, y por eso
# es tambien el unico que un atacante puede usar para desviar el flujo del
# receptor. La lista es la familia ML-KEM al completo: es lo que `_INFO` dice
# que hay dentro del sobre y lo que ofrece el desplegable del dashboard.
MECANISMOS_ADMITIDOS = ("ML-KEM-512", "ML-KEM-768", "ML-KEM-1024")

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

    EL `mecanismo` VIAJA COMO AAD, no como None. Es la cabecera en claro del
    sobre: no se cifra (el receptor tiene que leerla para saber con que KEM
    desencapsular) pero SI se autentica, que es exactamente para lo que existe
    el campo de datos asociados de un AEAD. El argumento de que "no se puede
    autenticar porque hace falta antes de tener la clave" no se sostiene: el
    AAD se comprueba DENTRO de decrypt, o sea despues de desencapsular y
    derivar la clave, asi que leerlo antes y verificarlo despues no es
    circular, es el orden normal. Un campo que decide QUE ALGORITMO se usa y
    viaja sin autenticar es el patron de sustitucion de algoritmo de manual.
    """
    kem_ciphertext, secreto = kem_encapsular(clave_publica, mecanismo)
    nonce = os.urandom(_LONGITUD_NONCE)
    aead_ciphertext = AESGCM(_clave_aes(secreto)).encrypt(
        nonce, mensaje, mecanismo.encode()
    )
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

    Cubre los CUATRO tipos de manipulacion con el mismo error, InvalidTag:
      - Tocar el aead_ciphertext o el nonce: el tag de GCM no cuadra.
      - Tocar el kem_ciphertext: ML-KEM no protesta (rechazo implicito, ver
        `kem_desencapsular`), pero devuelve otro secreto, el HKDF da otra clave
        y el tag tampoco cuadra. Misma InvalidTag por otro camino.
      - Tocar el `mecanismo`: es el campo que hay que leer ANTES de poder
        verificar nada, asi que se trata aparte, en las dos guardas de abajo.

    POR QUE EL `mecanismo` NECESITA GUARDAS Y NO LE BASTA EL AAD. El AAD lo
    caza cuando el sobre llega hasta AES-GCM, pero un mecanismo manipulado no
    llega tan lejos: revienta antes, en el KEM, y cada valor revienta de una
    forma distinta. Medido sobre liboqs, sustituyendo el mecanismo de un sobre
    de ML-KEM-768:

      - "Kyber768-inventado" (no existe) -> MechanismNotSupportedError, al
        abrir el KEM.
      - "ML-KEM-512" (existe, mas pequeno) -> ValueError de ctypes: la clave
        privada de 2400 B no cabe en el buffer de 1632 B.
      - "ML-KEM-1024" (existe, mas grande) -> los buffers tragan, pero
        OQS_KEM_decaps devuelve fallo y liboqs-python levanta RuntimeError.

    Tres tipos de excepcion que ningun llamador espera de un sobre manipulado
    -el dashboard, por ejemplo, solo captura InvalidTag y se iba a traceback-,
    asi que las tres se traducen aqui a InvalidTag: un sobre que no se puede
    procesar es un sobre que no se autentica, y el llamador solo deberia tener
    que conocer un modo de fallo. Es tambien el motivo de que la lista blanca
    se compruebe ANTES de tocar liboqs: bytes de un atacante no deben llegar a
    decidir que mecanismo se instancia en la libreria C.

    Lo que NO se traduce: los errores de `cifrar_mensaje`. Alli un mecanismo
    mal escrito es un typo del programador y sigue explotando ruidosamente.
    """
    if sobre.mecanismo not in MECANISMOS_ADMITIDOS:
        raise InvalidTag(
            f"mecanismo no admitido en el sobre: {sobre.mecanismo!r} "
            f"(se esperaba uno de {list(MECANISMOS_ADMITIDOS)})"
        )
    try:
        secreto = kem_desencapsular(
            clave_privada, sobre.kem_ciphertext, sobre.mecanismo
        )
    except (ValueError, RuntimeError) as exc:
        # Material que no cuadra con el mecanismo declarado (ver el desglose de
        # arriba). Tambien cae aqui una clave privada truncada, que para el
        # caso es lo mismo: no descifra. Se acota a estos dos tipos y no a
        # Exception para no tragarse un bug de tipos del llamador, misma regla
        # que en `sig.verificar`.
        raise InvalidTag(
            f"el material no cuadra con el mecanismo declarado "
            f"({sobre.mecanismo}): sobre manipulado o clave equivocada"
        ) from exc
    return AESGCM(_clave_aes(secreto)).decrypt(
        sobre.nonce, sobre.aead_ciphertext, sobre.mecanismo.encode()
    )
