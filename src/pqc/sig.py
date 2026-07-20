"""src/pqc/sig.py - tarea 2.6 (Marco). ML-DSA en crudo via liboqs.

ML-DSA (FIPS 204, antes "Dilithium") es el esquema de firma post-cuantico
basado en reticulos. Firma un mensaje con la clave privada y cualquiera lo
verifica con la publica. Este modulo expone la version cruda via liboqs.

Convencion NIST: SIEMPRE "ML-DSA-65", nunca "Dilithium3". El objeto
oqs.Signature, como el KEM, se usa SIEMPRE como context manager (ver
`abrir_firma`).

Sin np.random.Generator: liboqs firma con su propio CSPRNG interno (ML-DSA usa
aleatoriedad "hedged" por defecto) y las claves deben ser impredecibles. Los
tests (tarea 2.6) comprueban propiedades: una firma valida verifica, una firma
o un mensaje manipulados NO verifican.
"""

from __future__ import annotations

import oqs

from .types import ResultadoFirma


def abrir_firma(mecanismo: str = "ML-DSA-65") -> oqs.Signature:
    """Crea el objeto de firma de liboqs para `mecanismo`.

    Igual que `abrir_kem` en `kem.py`: reserva memoria nativa para la clave
    secreta y SIEMPRE se usa como context manager, nunca se guarda fuera del
    bloque `with`:

        with abrir_firma() as firmante:
            clave_publica = firmante.generate_keypair()
            firma = firmante.sign(mensaje)
    """
    raise NotImplementedError


def firmar(mensaje: bytes, mecanismo: str = "ML-DSA-65") -> ResultadoFirma:
    """Genera un par ML-DSA fresco, firma `mensaje` y empaqueta el resultado.

    Implementacion (2.6):

        with abrir_firma(mecanismo) as firmante:
            clave_publica = firmante.generate_keypair()
            firma = firmante.sign(mensaje)

    Devuelve un `ResultadoFirma` (mensaje + firma + clave_publica + mecanismo)
    para que `verificar` sea autocontenido y el benchmark (2.7) mida el tamano
    real de la firma.
    """
    raise NotImplementedError


def verificar(resultado: ResultadoFirma) -> bool:
    """Verifica un `ResultadoFirma`. True si la firma es valida, False si no.

    Implementacion (2.6): abre un verificador ML-DSA (sin clave secreta) y
    comprueba `resultado.firma` sobre `resultado.mensaje` con
    `resultado.clave_publica`. Un mensaje o una firma alterados dan False.
    """
    raise NotImplementedError
