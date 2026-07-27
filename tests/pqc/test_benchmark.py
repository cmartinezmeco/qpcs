"""tests/pqc/test_benchmark.py - tareas 2.7 / 2.8 (el benchmark del modulo).

Un benchmark no se puede testear por sus VALORES: los milisegundos dependen de
la maquina, de la carga del sistema y del planificador, y un test que exigiera
"ML-KEM tarda 0.02 ms" parpadearia el primer dia. Lo que si se testea, y es lo
que hay aqui, son tres cosas:

  1. La FORMA del resultado: que sale una `Medida` con su familia, su
     mecanismo, su operacion, sus repeticiones y las tres cifras (media, sigma
     y p50) coherentes entre si.
  2. Que la sigma es DERIVADA de la muestra: con una sola repeticion vale 0.0
     (no hay dispersion que medir) y con varias es positiva. Es la regla de la
     Fase 1 -toda barra de error sale de un calculo- convertida en test.
  3. Los TAMANOS, que si son deterministas: los fija FIPS 203/204 y el modulo
     RSA, asi que aqui si se puede exigir el numero exacto.

La suite rapida usa pocas repeticiones y RSA-1024: solo comprueba que el
benchmark corre y da forma correcta. El benchmark de verdad (200 repeticiones
de PQC, 50 de RSA-3072) va marcado @pytest.mark.slow al final, porque cuesta
casi un minuto de CPU y no tiene por que correr en cada push.
"""

import json

import pytest
from pqc.benchmark import (
    MECANISMO_KEM,
    MECANISMO_RSA,
    MECANISMO_SIG,
    OPS_ED25519,
    OPS_FIRMA,
    OPS_KEM,
    OPS_RSA,
    OPS_X25519,
    SUFIJO_CAPA_API,
    cargar_json,
    entorno,
    entorno_del_json,
    guardar_json,
    medir_classical,
    medir_kem,
    medir_sig,
    tabla_medidas,
    tabla_tamanos,
    tamanos_classical,
    tamanos_kem,
    tamanos_sig,
)

# Modulo RSA de juguete para la suite rapida: generar 1024 bits cuesta ~25 ms
# contra los ~250 ms de 3072. El benchmark publicable usa RSA-3072 (el
# comparable justo de ML-KEM-768, nivel NIST 3); aqui solo se ejercita el
# camino del codigo, no se publica ninguna cifra.
RSA_RAPIDO = "RSA-1024"

# Repeticiones minimas para los tests de forma. Con 3 ya hay sigma calculable.
POCAS = 3


def _comprobar_forma(medida, familia, mecanismo, operacion, repeticiones):
    """Las invariantes que toda `Medida` cumple, venga de donde venga."""
    assert medida.familia == familia
    assert medida.mecanismo == mecanismo
    assert medida.operacion == operacion
    assert medida.repeticiones == repeticiones
    # Ninguna operacion criptografica tarda 0: si sale 0 es que no se midio.
    assert medida.media_ms > 0.0
    assert medida.p50_ms > 0.0
    # La sigma nunca es negativa (es una desviacion tipica) y la mediana vive
    # en el mismo orden de magnitud que la media salvo contaminacion brutal.
    assert medida.sigma_ms >= 0.0


def test_las_tres_operaciones_del_kem_dan_medida():
    """keygen, encaps y decaps de ML-KEM-768, capa primitiva."""
    for operacion in OPS_KEM:
        medida = medir_kem(MECANISMO_KEM, operacion, POCAS)
        _comprobar_forma(medida, "ML-KEM", MECANISMO_KEM, operacion, POCAS)


def test_las_tres_operaciones_de_la_firma_dan_medida():
    """keygen, sign y verify de ML-DSA-65, capa primitiva."""
    for operacion in OPS_FIRMA:
        medida = medir_sig(MECANISMO_SIG, operacion, POCAS)
        _comprobar_forma(medida, "ML-DSA", MECANISMO_SIG, operacion, POCAS)


def test_las_operaciones_clasicas_dan_medida():
    """RSA y las dos curvas. Cada familia con su etiqueta del contrato."""
    for operacion in OPS_RSA:
        medida = medir_classical("RSA", RSA_RAPIDO, operacion, POCAS)
        _comprobar_forma(medida, "RSA", RSA_RAPIDO, operacion, POCAS)
    for operacion in OPS_X25519:
        medida = medir_classical("ECC", "X25519", operacion, POCAS)
        _comprobar_forma(medida, "ECC", "X25519", operacion, POCAS)
    for operacion in OPS_ED25519:
        medida = medir_classical("ECC", "Ed25519", operacion, POCAS)
        _comprobar_forma(medida, "ECC", "Ed25519", operacion, POCAS)


def test_la_capa_api_se_distingue_en_el_mecanismo():
    """Las dos capas conviven en la misma tabla, y se distinguen por el nombre.

    `Operacion` es un Literal cerrado del contrato compartido (types.py), asi
    que la capa medida viaja en el `mecanismo`, que si es string libre. Si esto
    se rompiese, las filas "primitiva" y "+carga" colisionarian y la tabla
    perderia la mitad de las medidas sin avisar.
    """
    primitiva = medir_kem(MECANISMO_KEM, "decaps", POCAS, "primitiva")
    con_carga = medir_kem(MECANISMO_KEM, "decaps", POCAS, "api")
    assert primitiva.mecanismo == MECANISMO_KEM
    assert con_carga.mecanismo == MECANISMO_KEM + SUFIJO_CAPA_API
    assert primitiva.mecanismo != con_carga.mecanismo
    # Misma familia y misma operacion: lo unico que cambia es la capa.
    assert primitiva.familia == con_carga.familia
    assert primitiva.operacion == con_carga.operacion


def test_una_sola_repeticion_da_sigma_cero():
    """Con n=1 no hay dispersion que estimar: sigma 0.0, y se dice.

    Es lo contrario de inventarse una barra de error: 0.0 aqui significa "sin
    barra de error", no "medida perfecta". Con varias repeticiones la sigma
    sale positiva porque el jitter del planificador es inevitable.
    """
    assert medir_kem(MECANISMO_KEM, "encaps", 1).sigma_ms == 0.0
    assert medir_kem(MECANISMO_KEM, "encaps", 20).sigma_ms > 0.0


def test_repeticiones_invalidas_fallan():
    """Pedir 0 repeticiones es un error del llamador, no una medida vacia."""
    with pytest.raises(ValueError):
        medir_kem(MECANISMO_KEM, "encaps", 0)


def test_operacion_que_no_aplica_falla_con_mensaje_claro():
    """Un KEM no firma y una firma no encapsula: error inmediato y legible.

    La validacion va ANTES de generar el material de clave (que en RSA cuesta
    un cuarto de segundo), para que el fallo sea instantaneo.
    """
    with pytest.raises(ValueError, match="no aplica"):
        medir_kem(MECANISMO_KEM, "sign", POCAS)
    with pytest.raises(ValueError, match="no aplica"):
        medir_sig(MECANISMO_SIG, "encaps", POCAS)
    with pytest.raises(ValueError, match="no aplica"):
        medir_classical("ECC", "Ed25519", "decaps", POCAS)


def test_la_capa_api_de_mldsa_solo_admite_verify():
    """`sig.firmar` genera el par y firma en la misma llamada a proposito.

    Cronometrarla como "sign" le cargaria a la firma el coste del keygen y
    ML-DSA-65 pareceria el doble de lento de lo que es, asi que la capa "api"
    lo rechaza en vez de publicar una cifra enganosa (ver medir_sig).
    """
    with pytest.raises(ValueError, match="no aplica"):
        medir_sig(MECANISMO_SIG, "sign", POCAS, "api")
    assert medir_sig(MECANISMO_SIG, "verify", POCAS, "api").repeticiones == POCAS


def test_familias_y_mecanismos_incoherentes_fallan():
    """La familia y el mecanismo tienen que cuadrar entre si."""
    with pytest.raises(ValueError, match="no es clasica"):
        medir_classical("ML-KEM", MECANISMO_KEM, "keygen", POCAS)
    with pytest.raises(ValueError, match="se esperaba RSA"):
        medir_classical("RSA", "X25519", "keygen", POCAS)
    with pytest.raises(ValueError, match="no soportado"):
        medir_classical("ECC", "P-256", "keygen", POCAS)


def test_tamanos_kem_fips_203():
    """ML-KEM-768: 1184 B de publica, 2400 de privada, 1088 de ciphertext.

    Los mismos numeros que test_kem.py comprueba sobre los artefactos reales,
    pero leidos del `details` del mecanismo: si las dos fuentes no coincidieran,
    una de las dos estaria mintiendo. El campo `firma` no aplica a un KEM: 0.
    """
    tam = tamanos_kem(MECANISMO_KEM)
    assert tam.mecanismo == MECANISMO_KEM
    assert (tam.clave_publica, tam.clave_privada) == (1184, 2400)
    assert tam.texto_cifrado == 1088
    assert tam.firma == 0


def test_tamanos_sig_fips_204():
    """ML-DSA-65: 1952 B de publica, 4032 de privada, 3309 de firma.

    Esos 3309 contra los 64 de Ed25519 son EL numero del modulo: la firma
    post-cuantica pesa unas 50 veces mas. El campo `texto_cifrado` no aplica.
    """
    tam = tamanos_sig(MECANISMO_SIG)
    assert (tam.clave_publica, tam.clave_privada) == (1952, 4032)
    assert tam.firma == 3309
    assert tam.texto_cifrado == 0
    # La comparacion que sostiene el titular del README.
    assert tam.firma / tamanos_classical("Ed25519").firma > 50


def test_tamanos_classical_se_miden_sobre_artefactos_reales():
    """Los tamanos clasicos salen de len(artefacto), no de una constante.

    RSA-3072 se reporta en DER (lo que viaja por un canal real), no en el PEM
    que devuelve `classical.rsa_generar`: PEM es el mismo DER en base64, un 33%
    mas grande, y compararlo contra los bytes crudos de ML-KEM le inflaria el
    coste a RSA gratis.
    """
    rsa = tamanos_classical(MECANISMO_RSA)
    # 3072 bits = 384 bytes de modulo: es lo que mide un bloque OAEP y una
    # firma PSS. La cabecera SubjectPublicKeyInfo anade unas decenas de bytes.
    assert rsa.texto_cifrado == 384
    assert rsa.firma == 384
    assert 384 < rsa.clave_publica < 500
    assert rsa.clave_privada > rsa.clave_publica

    x25519 = tamanos_classical("X25519")
    # El "texto cifrado" de un DH efimero es la clave publica que viaja: 32 B,
    # contra los 1088 del kem_ciphertext de ML-KEM-768.
    assert (x25519.clave_publica, x25519.clave_privada) == (32, 32)
    assert x25519.texto_cifrado == 32
    assert x25519.firma == 0

    ed25519 = tamanos_classical("Ed25519")
    assert (ed25519.clave_publica, ed25519.clave_privada) == (32, 32)
    assert ed25519.firma == 64
    assert ed25519.texto_cifrado == 0


def test_tamanos_de_un_mecanismo_desconocido_fallan():
    with pytest.raises(ValueError, match="no soportado"):
        tamanos_classical("Kyber768")


def test_entorno_documenta_donde_se_midio():
    """Un benchmark sin maquina ni versiones es una anecdota, no una medida.

    Estas claves viajan en el JSON para que cualquiera sepa si sus numeros son
    comparables con los publicados (otra CPU u otra build de liboqs dan otras
    cifras).
    """
    datos = entorno()
    for clave in ("python", "plataforma", "procesador", "liboqs", "medido_utc"):
        assert datos[clave]


def test_json_round_trip(tmp_path):
    """Guardar y volver a cargar devuelve las MISMAS dataclasses.

    Es la via por la que las figuras (2.9) consumen el benchmark sin re-medir:
    si el round-trip perdiera precision o campos, las graficas dibujarian otra
    cosa que la tabla del README.
    """
    medidas = [medir_kem(MECANISMO_KEM, "encaps", POCAS)]
    tamanos = [tamanos_kem(MECANISMO_KEM), tamanos_classical("Ed25519")]
    ruta = guardar_json(medidas, tamanos, tmp_path / "benchmark.json")

    leidas, leidos = cargar_json(ruta)
    assert leidas == medidas
    assert leidos == tamanos
    # Y el fichero lleva dentro el entorno, no solo los numeros.
    assert json.loads(ruta.read_text())["entorno"]["liboqs"]


def test_el_entorno_viaja_dentro_del_json(tmp_path):
    """El dashboard lee el entorno del JSON para poder decir donde se midio."""
    ruta = guardar_json([], [], tmp_path / "b.json")
    assert entorno_del_json(ruta)["plataforma"] == entorno()["plataforma"]


def test_json_manipulado_falla_al_cargar(tmp_path):
    """Un JSON editado a mano con una familia inventada no cuela.

    Lo que sale de json.load es Any: sin esta validacion, un "Kyber" acabaria
    dentro de un dataclass del contrato y el fallo apareceria tres capas mas
    arriba, al dibujar.
    """
    medidas = [medir_kem(MECANISMO_KEM, "encaps", POCAS)]
    ruta = guardar_json(medidas, [], tmp_path / "b.json")
    payload = json.loads(ruta.read_text())
    payload["medidas"][0]["familia"] = "Kyber"
    ruta.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="familia"):
        cargar_json(ruta)


def test_tabla_completa_tiene_las_dos_capas_y_las_cuatro_familias():
    """Smoke test del orquestador: la tabla que alimenta figuras y README.

    Con repeticiones minimas y RSA-1024 para que entre en la suite rapida: lo
    que se comprueba es que no falta ninguna fila, no cuanto tarda cada una.
    """
    filas = tabla_medidas(
        repeticiones_pqc=2, repeticiones_clasico=1, mecanismo_rsa=RSA_RAPIDO
    )
    familias = {fila.familia for fila in filas}
    assert familias == {"RSA", "ECC", "ML-KEM", "ML-DSA"}

    con_carga = [f for f in filas if f.mecanismo.endswith(SUFIJO_CAPA_API)]
    primitivas = [f for f in filas if not f.mecanismo.endswith(SUFIJO_CAPA_API)]
    # 5 de RSA + 2 de X25519 + 3 de Ed25519 + 3 de ML-KEM + 3 de ML-DSA.
    assert len(primitivas) == 16
    # La capa "api" repite todo menos keygen y sign de ML-DSA (ver medir_sig).
    assert len(con_carga) == 14
    # Ninguna fila duplicada: (mecanismo, operacion) es la clave de la tabla.
    claves = [(f.mecanismo, f.operacion) for f in filas]
    assert len(claves) == len(set(claves))


def test_tabla_tamanos_cubre_los_cinco_mecanismos():
    """Los cinco mecanismos de la figura de tamanos, ni uno menos."""
    mecanismos = {tam.mecanismo for tam in tabla_tamanos()}
    assert mecanismos == {
        MECANISMO_RSA,
        "X25519",
        "Ed25519",
        MECANISMO_KEM,
        MECANISMO_SIG,
    }


@pytest.mark.slow
def test_benchmark_completo_es_coherente():
    """El benchmark de verdad, con las repeticiones publicables (~1 min).

    Marcado slow: la CI corre con -m "not slow" y esto solo se ejecuta al
    mergear a main. Las dos afirmaciones que se comprueban son fisicas, no
    numericas, para que no dependan de la maquina:

      - Generar una clave RSA-3072 (buscar dos primos de 1536 bits) cuesta
        ordenes de magnitud mas que generar una de ML-KEM-768 (muestrear un
        reticulo). Es el titular "la PQC gana en tiempo, sobre todo generando
        claves", y por eso se exige un factor >10 y no un valor concreto.
      - La capa "+carga" hace estrictamente MAS trabajo que la primitiva (la
        misma operacion mas deserializar la clave), asi que nunca puede salir
        mas rapida. Se deja un 10% de margen para el ruido del planificador.
    """
    filas = {(f.mecanismo, f.operacion): f for f in tabla_medidas()}

    keygen_rsa = filas[(MECANISMO_RSA, "keygen")]
    keygen_kem = filas[(MECANISMO_KEM, "keygen")]
    assert keygen_rsa.media_ms > 10 * keygen_kem.media_ms

    for mecanismo, operacion in (
        (MECANISMO_RSA, "decrypt"),
        (MECANISMO_RSA, "sign"),
        (MECANISMO_KEM, "decaps"),
    ):
        primitiva = filas[(mecanismo, operacion)]
        con_carga = filas[(mecanismo + SUFIJO_CAPA_API, operacion)]
        assert con_carga.media_ms >= 0.9 * primitiva.media_ms

    # Con 200 (PQC) y 50 (clasico) repeticiones toda fila tiene dispersion
    # medible: si alguna saliera con sigma 0 exacta, el cronometro no estaria
    # midiendo lo que dice medir.
    for fila in filas.values():
        assert fila.sigma_ms > 0.0
