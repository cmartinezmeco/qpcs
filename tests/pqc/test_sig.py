"""tests/pqc/test_sig.py - tarea 2.6 (ML-DSA, firma post-cuantica real).

Firmar un mensaje de verdad con ML-DSA-65 y, sobre todo, comprobar que lo que
NO deberia verificar no verifica. Un test que solo firma y verifica no prueba
nada: lo pasaria igual una implementacion que devolviese True siempre. Por eso
los tres casos negativos (mensaje alterado, firma alterada, clave publica de
otro firmante) son el nucleo de este fichero.

Sin semilla, como toda la cripto real: propiedades, no valores fijos.
"""

import oqs
import pytest
from pqc.sig import abrir_firma, firmar, verificar
from pqc.types import ResultadoFirma

# Tamanos de ML-DSA-65 fijados por FIPS 204.
PK_65 = 1952
FIRMA_65 = 3309


def test_firma_valida_verifica():
    res = firmar(b"comunicado oficial QPCS", "ML-DSA-65")
    assert verificar(res)


def test_mensaje_manipulado_se_rechaza():
    """El test que de verdad prueba algo: alterar el mensaje invalida la firma.

    Se reconstruye el ResultadoFirma en vez de mutarlo (frozen=True).
    """
    res = firmar(b"transferir 100 euros", "ML-DSA-65")
    manipulado = ResultadoFirma(
        b"transferir 900 euros", res.firma, res.clave_publica, res.mecanismo
    )
    assert not verificar(manipulado)


def test_firma_manipulada_se_rechaza():
    """Un solo bit cambiado en la firma y deja de valer."""
    res = firmar(b"documento intacto", "ML-DSA-65")
    rota = ResultadoFirma(
        res.mensaje,
        bytes([res.firma[0] ^ 0x01]) + res.firma[1:],
        res.clave_publica,
        res.mecanismo,
    )
    assert not verificar(rota)


def test_firma_de_otra_clave_se_rechaza():
    """Una firma valida pero de OTRO firmante no cuela (round-trip cruzado).

    Cada llamada a `firmar` genera su propio par, asi que a y b tienen claves
    publicas distintas aunque el mensaje sea el mismo.
    """
    a = firmar(b"mismo mensaje", "ML-DSA-65")
    b = firmar(b"mismo mensaje", "ML-DSA-65")
    cruzado = ResultadoFirma(a.mensaje, a.firma, b.clave_publica, a.mecanismo)
    assert not verificar(cruzado)


def test_verificar_devuelve_false_y_no_lanza():
    """Ante una firma basura devuelve False, no una excepcion: el caso
    negativo es un resultado legitimo, no un error del programa."""
    res = firmar(b"mensaje", "ML-DSA-65")
    basura = ResultadoFirma(
        res.mensaje, b"\x00" * FIRMA_65, res.clave_publica, res.mecanismo
    )
    assert verificar(basura) is False


def test_firma_truncada_se_rechaza():
    """Caso borde: firma con longitud incorrecta. Tambien False, sin reventar."""
    res = firmar(b"mensaje", "ML-DSA-65")
    corta = ResultadoFirma(
        res.mensaje, res.firma[:-10], res.clave_publica, res.mecanismo
    )
    assert verificar(corta) is False


def test_tamanos_fips_204():
    """1952 B de clave publica y 3309 de firma en ML-DSA-65.

    Contrastar con los 32 + 64 de Ed25519 (test_classical.py): la firma
    post-cuantica pesa ~50 veces mas. Ese es el numero honesto que el
    benchmark de la tarea 2.7 tiene que poner sobre la mesa.
    """
    res = firmar(b"para medir", "ML-DSA-65")
    assert len(res.clave_publica) == PK_65
    assert len(res.firma) == FIRMA_65


def test_el_resultado_es_bytes_y_lleva_nomenclatura_nist():
    """Todo lo cripto es bytes (contrato de types.py) y el mecanismo se
    etiqueta con el nombre FIPS 204, nunca con "Dilithium3"."""
    res = firmar(b"mensaje", "ML-DSA-65")
    assert isinstance(res.firma, bytes)
    assert isinstance(res.clave_publica, bytes)
    assert res.mensaje == b"mensaje"
    assert res.mecanismo == "ML-DSA-65"


def test_firmar_no_oculta_el_mensaje():
    """Firmar NO es cifrar: el mensaje viaja en claro dentro del resultado.

    Es el malentendido numero uno de este bloque; el test lo deja escrito.
    Para ocultarlo esta el cifrado hibrido de test_hybrid.py.
    """
    mensaje = b"esto se lee sin ninguna clave"
    assert firmar(mensaje, "ML-DSA-65").mensaje == mensaje


def test_mecanismo_inexistente_falla_ruidosamente():
    """Nomenclatura pre-NIST o typo: error de liboqs inmediato."""
    with pytest.raises(oqs.MechanismNotSupportedError):
        firmar(b"mensaje", "Dilithium3-inventado")


def test_abrir_firma_es_context_manager():
    """Igual que abrir_kem: memoria C, siempre bajo `with`."""
    with abrir_firma("ML-DSA-65") as firmante:
        assert len(firmante.generate_keypair()) == PK_65
