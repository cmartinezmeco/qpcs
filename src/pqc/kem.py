"""src/pqc/kem.py - tarea 2.5 (Marco). ML-KEM en crudo via liboqs.

KEM = Key Encapsulation Mechanism. ML-KEM (FIPS 203, antes "Kyber") es el
mecanismo post-cuantico de acuerdo de clave: el emisor "encapsula" un secreto
contra la clave publica del receptor y obtiene (ciphertext, secreto); el
receptor "desencapsula" el ciphertext con su clave privada y recupera el mismo
secreto. Este modulo expone la version CRUDA (solo el KEM); el sobre completo
KEM + HKDF + AES-GCM vive en `hybrid.py`.

Convencion de nomenclatura NIST: SIEMPRE "ML-KEM-768", nunca "Kyber768". Ver
`abrir_kem` para el patron de context manager, que es OBLIGATORIO.

Aqui no entra ningun np.random.Generator: liboqs usa su propio CSPRNG y las
claves deben ser impredecibles. Los tests (tarea 2.5) validan la propiedad de
correccion (el secreto encapsulado coincide con el desencapsulado), no valores
fijos sembrados.

Todo lo que sale de liboqs se sella con bytes(...) antes de devolverlo: `oqs`
esta en los overrides de ignore_missing_imports del pyproject, asi que para
mypy --strict cualquier valor que venga de ahi es Any y contaminaria el tipo
de retorno de estas funciones.
"""

from __future__ import annotations

import oqs


def abrir_kem(
    mecanismo: str = "ML-KEM-768", clave_privada: bytes | None = None
) -> oqs.KeyEncapsulation:
    """Crea el objeto KEM de liboqs para `mecanismo`.

    El objeto oqs.KeyEncapsulation reserva memoria nativa (la clave secreta)
    que hay que liberar. Por eso SIEMPRE se usa como context manager y nunca
    se guarda mas alla del bloque `with`:

        with abrir_kem() as kem:
            clave_publica = kem.generate_keypair()
            ...  # todo el uso de la clave dentro del with

    Fuera del `with` el objeto ya ha liberado su clave secreta y usarlo es un
    error. `kem_generar` y `kem_encapsular` siguen exactamente este patron.

    `clave_privada` es el unico anadido de la tarea 2.5 sobre la firma del
    esqueleto: liboqs IMPORTA la clave secreta al construir el objeto, no
    despues, asi que el receptor de `kem_desencapsular` no tiene otra forma de
    recuperar su par. Con el valor por defecto (None) el comportamiento es el
    de siempre: un KEM sin clave, listo para generar un par o para encapsular
    contra la publica de otro.

    Un mecanismo mal escrito ("Kyber768", un typo) revienta aqui con
    MechanismNotSupportedError de liboqs: error ruidoso e inmediato, nunca un
    fallo silencioso mas abajo.
    """
    return oqs.KeyEncapsulation(mecanismo, clave_privada)


def kem_generar(mecanismo: str = "ML-KEM-768") -> tuple[bytes, bytes]:
    """Genera un par ML-KEM y devuelve (clave_publica, clave_privada).

    Las dos claves se exportan a bytes DENTRO del `with`: al salir, el objeto
    libera la memoria nativa donde vive la clave secreta, y leerla despues es
    un uso-despues-de-liberar. Devolverlas como bytes -y no el objeto vivo de
    liboqs- es lo que permite que el par sobreviva al bloque y que el receptor
    lo reabra luego en `kem_desencapsular`.

    Con ML-KEM-768: 1184 bytes de clave publica y 2400 de privada (FIPS 203).
    """
    with abrir_kem(mecanismo) as kem:
        clave_publica = kem.generate_keypair()
        clave_privada = kem.export_secret_key()
        return bytes(clave_publica), bytes(clave_privada)


def kem_encapsular(
    clave_publica: bytes, mecanismo: str = "ML-KEM-768"
) -> tuple[bytes, bytes]:
    """Encapsula contra `clave_publica`. Devuelve (kem_ciphertext, secreto).

    El `secreto` es el material del que `hybrid.py` deriva (via HKDF) la clave
    AES-GCM; el `kem_ciphertext` viaja por el canal hasta el receptor.

    El emisor solo necesita la clave publica del receptor: no aporta un par
    propio (esa es la diferencia con el Diffie-Hellman de `x25519_intercambio`,
    donde los dos lados ponen clave). Cada llamada produce un secreto nuevo e
    independiente aunque la clave publica sea la misma, porque el secreto lo
    genera el propio encapsulamiento, no un acuerdo entre claves fijas.

    Con ML-KEM-768: 1088 bytes de ciphertext y 32 de secreto compartido.
    """
    with abrir_kem(mecanismo) as kem:
        kem_ciphertext, secreto = kem.encap_secret(clave_publica)
        return bytes(kem_ciphertext), bytes(secreto)


def kem_desencapsular(
    clave_privada: bytes, kem_ciphertext: bytes, mecanismo: str = "ML-KEM-768"
) -> bytes:
    """Recupera el secreto compartido a partir del `kem_ciphertext`.

    El receptor reabre su KEM importando la clave privada que le devolvio
    `kem_generar` y desencapsula. Debe devolver el MISMO secreto que obtuvo
    `kem_encapsular` (propiedad de correccion que testea la tarea 2.5).

    OJO con lo que esta funcion NO hace: si el ciphertext viene manipulado,
    ML-KEM no lanza ningun error, devuelve un secreto de 32 bytes DISTINTO. Es
    el "rechazo implicito" de la construccion Fujisaki-Okamoto que le da la
    seguridad IND-CCA: fallar de forma distinguible seria un oraculo para el
    atacante. La manipulacion se detecta una capa mas arriba, cuando el tag de
    AES-GCM no cuadra con esa clave equivocada (ver `hybrid.descifrar_mensaje`).
    """
    with abrir_kem(mecanismo, clave_privada) as kem:
        return bytes(kem.decap_secret(kem_ciphertext))
