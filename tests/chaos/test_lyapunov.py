def test_lyapunov_de_r4_es_ln2():
    """El valor exacto, no una referencia. Tolerancia DERIVADA del
    error estandar que devuelve el propio diagnostico."""
    
    d = lyapunov_logistico(0.4, 4.0, n=200_000)
    assert abs(d.lyapunov - np.log(2.0)) < 4 * d.sigma

@pytest.mark.parametrize("r,esperado_caotico", [
    (2.5, False), # punto fijo
    (3.2, False), # periodo 2
    (3.5, False), # periodo 4
    (3.83, False), # LA VENTANA DE PERIODO 3 dentro del caos
    (3.9, True),
    (4.0, True),
])

def test_detecta_el_regimen(r, esperado_caotico):
    """El test que justifica la existencia de esta tarea: r = 3.83 esta
    DENTRO del rango caotico nominal (3.57, 4] y sin embargo NO es
    caotico. Un modulo que solo comprobara el rango lo aceptaria."""

    assert lyapunov_logistico(0.4, r).es_caotico == esperado_caotico

def test_lorenz_espectro_suma_la_divergencia():
    """lambda_1 + lambda_2 + lambda_3 = -(sigma + 1 + beta) = -13.667.
    Verificacion independiente y gratis del integrador (cap. 3.3)."""

    l1, l2, l3 = espectro_lyapunov_lorenz()
    assert abs((l1 + l2 + l3) + (LORENZ_SIGMA + 1 + LORENZ_BETA)) < 0.5
    assert abs(l1 - 0.906) < 0.05
    assert abs(l2) < 0.05