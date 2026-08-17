def test_vector_de_prueba():
    """EL test del modulo. Si esto falla en el contenedor y pasa en
    local, el determinismo esta roto y nada mas importa."""

    v = json.loads(Path("vectors/keystream_v1.json").read_text())
    ks = keystream_logistico(ClaveCaotica(**v["clave"], sistema="logistico"),
                             1_000_000)
    assert ks[:64].tobytes().hex() == v["primeros_64_bytes_hex"]
    assert hashlib.sha256(ks.tobytes()).hexdigest() == v["sha256_de_1e6_bytes"]

def test_la_cuantizacion_ingenua_falla_el_chi2():
    """Demuestra que la decision de diseno sirve. Sin este test, el
    codigo malo pasaria igual el test de arriba."""

    orb = orbita_logistica(0.4, 4.0, 100_000)
    ingenua = (orb * 256).astype(np.uint8) # bits ALTOS
    buena = ((orb * ESCALA_BITS).astype(np.uint64) & 0xFF).astype(np.uint8)
    assert chi2_histograma(ingenua) > 293.25 # RECHAZA uniformidad
    assert chi2_histograma(buena) < 293.25 # no la rechaza

def test_sensibilidad_a_la_clave():
    """1e-15 en x0 => keystreams sin relacion. Es el Lyapunov en accion."""

    a = keystream_logistico(ClaveCaotica("logistico", 0.4, r=3.99), 10_000)
    b = keystream_logistico(ClaveCaotica("logistico", 0.4 + 1e-15, r=3.99), 10_000)
    coincidencias = np.count_nonzero(a == b)
    esperado = 10_000 / 256
    sigma = np.sqrt(esperado * (1 - 1/256))
    assert abs(coincidencias - esperado) < 4 * sigma

def test_ciclo_medido_y_publicado():
    """Floyd sobre la orbita. No exige un minimo: MIDE y avisa."""

    ciclo = detectar_ciclo(ClaveCaotica("logistico", 0.4, r=3.99))
    assert ciclo is None or ciclo > 1_000_000