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

    QUE SE CAPTURA Y QUE NO. liboqs devuelve False por su cuenta ante un
    mensaje alterado, una firma alterada, una firma truncada o una clave
    publica mas corta de la cuenta (esa la rellena de ceros). Lo unico que
    LANZA es un error de LONGITUD: `verify` mete la clave publica en un buffer
    de tamano fijo (1952 B en ML-DSA-65), asi que una clave mas larga hace
    saltar el ValueError de ctypes. Eso sigue siendo "esta firma no verifica",
    no un fallo del programa, y por eso se traduce a False; el RuntimeError
    cubre los fallos internos de la libreria C.

    Lo que ya NO se captura es `Exception` a secas, que es lo que habia aqui:
    tragaba tambien el TypeError de pasar un `str` donde va `bytes` y lo
    convertia en "firma invalida", escondiendo un error de tipos del llamador
    detras de un resultado criptografico que parece legitimo. Un bug de tipos
    tiene que explotar.

    El `abrir_firma` queda FUERA del try a proposito: un mecanismo inexistente
    si debe explotar, porque es un error de programacion, no una firma
    invalida.
    """
    with abrir_firma(resultado.mecanismo) as verificador:
        try:
            return bool(
                verificador.verify(
                    resultado.mensaje, resultado.firma, resultado.clave_publica
                )
            )
        except (ValueError, RuntimeError):
            return False
