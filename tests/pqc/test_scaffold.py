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
    """Toda la superficie declarada existe, y `__all__` no miente.

    La lista de nombres NO se repite aqui a mano: se lee de `pqc.__all__`, que
    es el sitio donde el modulo declara su frontera. Escribirla dos veces
    permitia justo el fallo que este test deberia cazar -que la frontera
    declarada y la real se separen- y ademas dejaba fuera nueve nombres que el
    dashboard y las figuras si importaban.
    """
    assert pqc.__all__, "pqc.__all__ esta vacio"
    for nombre in pqc.__all__:
        assert hasattr(pqc, nombre), f"falta {nombre} en la API publica de pqc"


def test_lo_que_consumen_el_dashboard_y_las_figuras_es_publico():
    """Los nombres que se importan desde FUERA del paquete estan en __all__.

    Es la otra mitad del contrato: no basta con que exista lo declarado, hace
    falta que este declarado lo que se usa. Estos son los nombres que
    dashboard/qkd_app.py y scripts/make_pqc_plots.py importan de `pqc.*`; antes
    ninguno estaba en __all__ y se podia renombrar cualquiera de ellos con la
    suite en verde y el dashboard roto.
    """
    consumidos_fuera = (
        # dashboard/qkd_app.py
        "RUTA_JSON",
        "SUFIJO_CAPA_API",
        "cargar_json",
        "entorno_del_json",
        "MECANISMOS_ADMITIDOS",
        "cifrar_mensaje",
        "descifrar_mensaje",
        "kem_generar",
        "factorizar_15",
        "histograma_fases_15",
        "firmar",
        "verificar",
        # scripts/make_pqc_plots.py
        "guardar_json",
        "tabla_medidas",
        "tabla_tamanos",
        "circuito_orden_15",
        # tests/pqc
        "abrir_kem",
        "abrir_firma",
    )
    for nombre in consumidos_fuera:
        assert nombre in pqc.__all__, f"{nombre} se usa fuera pero no es publico"


def test_liboqs_trae_mecanismos_nist():
    """Los nombres FIPS 203/204 que usa el modulo tienen que estar en liboqs."""
    kems = oqs.get_enabled_kem_mechanisms()
    sigs = oqs.get_enabled_sig_mechanisms()
    assert "ML-KEM-768" in kems, "liboqs no expone ML-KEM-768 (FIPS 203)"
    assert "ML-DSA-65" in sigs, "liboqs no expone ML-DSA-65 (FIPS 204)"
    # NOTA sobre la nomenclatura. El Dockerfile compila liboqs 0.16.0 (ver
    # Dockerfile y requirements.txt: liboqs-python==0.16.0); la observacion que
    # sigue se comprobo sobre la 0.14.0, que es la que compilaba entonces y la
    # que puede seguir habiendo en un venv local antiguo. Aquella version AUN
    # exponia los nombres pre-estandarizacion "Kyber768" y "Dilithium3" como
    # alias, conviviendo con los nombres NIST.
    # Es decir, liboqs NO nos obliga a usar la nomenclatura correcta: que en
    # NUESTRO codigo aparezca solo "ML-KEM-*"/"ML-DSA-*" (FIPS 203/204) y nunca
    # "Kyber"/"Dilithium" salvo como nota historica es una regla de REVIEW, no
    # algo que este test pueda derivar de los mecanismos habilitados. Si una
    # version futura de liboqs retirase los alias, los `in` de arriba seguirian
    # verdes (usamos los nombres NIST) y este comentario dejaria de aplicar.
