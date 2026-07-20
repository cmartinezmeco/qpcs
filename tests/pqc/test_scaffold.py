"""tests/pqc/test_scaffold.py - tarea 2.1.

Espejo de tests/qkd/test_scaffold.py: comprueba que el andamiaje del modulo 2
esta en su sitio antes de que nadie implemente nada. Dos cosas:

  1. Que la API publica del paquete `pqc` existe (si alguien renombra o borra
     algo sin avisar, este test se pone rojo).
  2. Que liboqs trae de verdad los mecanismos NIST que el modulo va a usar
     (ML-KEM-768, ML-DSA-65). Es la prueba real de que el Dockerfile compilo
     liboqs con lo que necesitamos.
"""

import oqs
import pqc


def test_api_publica_existe():
    nombres = (
        # classical (2.4)
        "rsa_generar",
        "rsa_cifrar_oaep",
        "rsa_descifrar_oaep",
        "rsa_firmar_pss",
        "rsa_verificar_pss",
        "x25519_generar",
        "x25519_intercambio",
        "ed25519_generar",
        "ed25519_firmar",
        "ed25519_verificar",
        # kem (2.5)
        "kem_generar",
        "kem_encapsular",
        "kem_desencapsular",
        # hybrid (2.5)
        "cifrar_mensaje",
        "descifrar_mensaje",
        # sig (2.6)
        "firmar",
        "verificar",
        # shor (2.2 / 2.3)
        "qft_dagger",
        "c_amod15",
        "circuito_orden_15",
        "medir_fase_15",
        "orden_desde_fase",
        "factorizar_15",
        # benchmark (2.7)
        "medir_kem",
        "medir_sig",
        "medir_classical",
        "tamanos_kem",
        "tamanos_sig",
    )
    for nombre in nombres:
        assert hasattr(pqc, nombre), f"falta {nombre} en la API publica de pqc"


def test_liboqs_trae_mecanismos_nist():
    """Los nombres FIPS 203/204 que usa el modulo tienen que estar en liboqs."""
    kems = oqs.get_enabled_kem_mechanisms()
    sigs = oqs.get_enabled_sig_mechanisms()
    assert "ML-KEM-768" in kems, "liboqs no expone ML-KEM-768 (FIPS 203)"
    assert "ML-DSA-65" in sigs, "liboqs no expone ML-DSA-65 (FIPS 204)"
    # NOTA sobre la nomenclatura (comprobado en liboqs 0.14.0, la que compila
    # el Dockerfile): esta version AUN expone los nombres pre-estandarizacion
    # "Kyber768" y "Dilithium3" como alias, conviviendo con los nombres NIST.
    # Es decir, liboqs NO nos obliga a usar la nomenclatura correcta: que en
    # NUESTRO codigo aparezca solo "ML-KEM-*"/"ML-DSA-*" (FIPS 203/204) y nunca
    # "Kyber"/"Dilithium" salvo como nota historica es una regla de REVIEW, no
    # algo que este test pueda derivar de los mecanismos habilitados. Si una
    # version futura de liboqs retirase los alias, los `in` de arriba seguirian
    # verdes (usamos los nombres NIST) y este comentario dejaria de aplicar.
