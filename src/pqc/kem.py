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
"""

from __future__ import annotations

import oqs


def abrir_kem(mecanismo: str = "ML-KEM-768") -> oqs.KeyEncapsulation:
    """Crea el objeto KEM de liboqs para `mecanismo`.

    El objeto oqs.KeyEncapsulation reserva memoria nativa (la clave secreta)
    que hay que liberar. Por eso SIEMPRE se usa como context manager y nunca
    se guarda mas alla del bloque `with`:

        with abrir_kem() as kem:
            clave_publica = kem.generate_keypair()
            ...  # todo el uso de la clave dentro del with

    Fuera del `with` el objeto ya ha liberado su clave secreta y usarlo es un
    error. `kem_generar` y `kem_encapsular` siguen exactamente este patron.
    """
    raise NotImplementedError


def kem_generar(mecanismo: str = "ML-KEM-768") -> tuple[bytes, bytes]:
    """Genera un par ML-KEM y devuelve (clave_publica, clave_privada).

    Implementacion (2.5):

        with abrir_kem(mecanismo) as kem:
            clave_publica = kem.generate_keypair()
            clave_privada = kem.export_secret_key()

    Se exportan a bytes DENTRO del `with` porque al salir el objeto libera la
    clave secreta nativa.
    """
    raise NotImplementedError


def kem_encapsular(
    clave_publica: bytes, mecanismo: str = "ML-KEM-768"
) -> tuple[bytes, bytes]:
    """Encapsula contra `clave_publica`. Devuelve (kem_ciphertext, secreto).

    Implementacion (2.5):

        with abrir_kem(mecanismo) as kem:
            kem_ciphertext, secreto = kem.encap_secret(clave_publica)

    El `secreto` es el material del que `hybrid.py` deriva (via HKDF) la clave
    AES-GCM; el `kem_ciphertext` viaja por el canal hasta el receptor.
    """
    raise NotImplementedError


def kem_desencapsular(
    clave_privada: bytes, kem_ciphertext: bytes, mecanismo: str = "ML-KEM-768"
) -> bytes:
    """Recupera el secreto compartido a partir del `kem_ciphertext`.

    Implementacion (2.5): el receptor abre un KEM importando su clave privada
    y llama a `decap_secret`. Debe devolver el MISMO secreto que obtuvo
    `kem_encapsular` (propiedad de correccion que testea la tarea 2.5).
    """
    raise NotImplementedError
