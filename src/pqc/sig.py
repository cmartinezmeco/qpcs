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

Firmar NO es cifrar: el mensaje viaja en claro dentro del `ResultadoFirma`. La
firma prueba quien lo emitio y que nadie lo ha tocado, no lo oculta. Para
ocultarlo esta `hybrid.py`.
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

    A diferencia de `abrir_kem`, aqui no hace falta importar clave privada
    alguna: `firmar` genera su par y lo consume en el acto, y `verificar` solo
    necesita la publica, que se pasa como argumento a verify().

    Un mecanismo mal escrito ("Dilithium3") levanta MechanismNotSupportedError
    de liboqs: falla ruidosamente y en el sitio.
    """
    return oqs.Signature(mecanismo)


def firmar(mensaje: bytes, mecanismo: str = "ML-DSA-65") -> ResultadoFirma:
    """Genera un par ML-DSA fresco, firma `mensaje` y empaqueta el resultado.

    Devuelve un `ResultadoFirma` (mensaje + firma + clave_publica + mecanismo)
    para que `verificar` sea autocontenido y el benchmark (2.7) mida el tamano
    real de la firma.

    La clave privada NUNCA sale de esta funcion: nace y muere dentro del
    `with`, que es justo lo que se quiere de una clave de firma. Como cada
    llamada genera un par nuevo, dos firmas del mismo mensaje llevan claves
    publicas distintas y ninguna verifica contra la de la otra (esa es la
    trampa que caza el test de firma cruzada).

    Con ML-DSA-65: 1952 bytes de clave publica y 3309 de firma. Frente a los
    64 bytes de una firma Ed25519, unas 50 veces mas: el precio real de la
    migracion, que la tabla de la tarea 2.7 pone encima de la mesa.
    """
    with abrir_firma(mecanismo) as firmante:
        clave_publica = firmante.generate_keypair()
        firma = firmante.sign(mensaje)
        # bytes(...) explicito: `oqs` no publica stubs (ver pyproject), asi que
        # para mypy --strict todo lo que sale de liboqs es Any y contaminaria
        # los campos del dataclass.
        return ResultadoFirma(mensaje, bytes(firma), bytes(clave_publica), mecanismo)


def verificar(resultado: ResultadoFirma) -> bool:
    """Verifica un `ResultadoFirma`. True si la firma es valida, False si no.

    Abre un verificador ML-DSA (sin clave secreta: verify() solo usa la
    publica) y comprueba `resultado.firma` sobre `resultado.mensaje` con
    `resultado.clave_publica`. Un mensaje, una firma o una clave publica
    alterados dan False.

    False y no excepcion: el caso negativo es un resultado legitimo de la
    operacion, no un error del programa. Asi `verificar` tiene la misma forma
    que `classical.rsa_verificar_pss` y el benchmark las cronometra igual.

    liboqs 0.14/0.16 ya devuelve False en todos esos casos (comprobado, tambien
    con firma truncada y clave publica de longitud incorrecta), pero el try
    envuelve la llamada para que el contrato "verificar no lanza" no dependa de
    la version de la libreria C. El `abrir_firma` queda FUERA del try a
    proposito: un mecanismo inexistente si debe explotar, porque es un error de
    programacion, no una firma invalida.
    """
    with abrir_firma(resultado.mecanismo) as verificador:
        try:
            return bool(
                verificador.verify(
                    resultado.mensaje, resultado.firma, resultado.clave_publica
                )
            )
        except Exception:
            return False
