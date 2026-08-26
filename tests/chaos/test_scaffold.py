"""tests/chaos/test_scaffold.py - el contrato de la API publica.

Si esto falla, alguien ha renombrado o quitado algo de __all__ sin
avisar al equipo. Lee los nombres desde chaos.__all__ en vez de
repetirlos a mano: escribir la lista dos veces permitiria justo el
fallo que este test deberia cazar.
"""

from __future__ import annotations

import chaos


def test_api_publica_existe():
    """Cada nombre declarado en __all__ debe ser accesible en el paquete."""
    for nombre in chaos.__all__:
        assert hasattr(chaos, nombre), f"falta {nombre} en la API publica"


def test_las_constantes_del_contrato_no_se_han_movido():
    """types.py no se exporta por __init__, pero sus constantes son el
    contrato mas importante del modulo (guia Fase 3, cap. 7.2). Este
    test fija sus valores para que un cambio accidental salte aqui.
    """
    from chaos.types import (
        ESCALA_BITS,
        PASO_RK4,
        SUBMUESTREO,
        TRANSITORIO,
        UMBRAL_LYAPUNOV,
    )

    assert TRANSITORIO == 1000
    assert SUBMUESTREO == 3
    assert PASO_RK4 == 0.01
    assert ESCALA_BITS == 4294967296.0
    assert UMBRAL_LYAPUNOV == 0.01


def test_lo_que_consumen_el_dashboard_y_los_scripts_es_publico():
    """La otra mitad del contrato de la API (tarea 3.9).

    No basta con que exista lo declarado en __all__: hace falta que este
    declarado lo que se usa desde FUERA del paquete. Estos son los nombres
    que importan la tercera pestana del dashboard y los tres scripts del
    modulo. Sin este test se puede renombrar cualquiera de ellos con la
    suite entera en verde y el dashboard roto, que es como la Fase 2
    descubrio que le faltaba media API publica.
    """
    consumidos_fuera = (
        # dashboard/qkd_app.py (pestana 3)
        "ClaveCaotica",
        "chi2_histograma",
        "cifrar_aes_gcm",
        "cifrar_flujo_trivial",
        "cifrar_imagen",
        "correlacion_adyacente",
        "descifrar_imagen",
        "entropia_esperada",
        "entropia_shannon",
        "imagen_de_prueba",
        "lyapunov_logistico",
        "permutacion_desde_orbita",
        # scripts/make_chaos_plots.py
        "orbita_logistica",
        "orbita_lorenz",
        # scripts/bench_chaos.py
        "deshacer_adelante",
        "difundir_adelante",
        "keystream",
        # scripts/check_chaos_determinism.py
        "keystream_logistico",
    )
    for nombre in consumidos_fuera:
        assert nombre in chaos.__all__, f"{nombre} se usa fuera pero no es publico"


def test_los_ayudantes_privados_que_se_usan_fuera_siguen_existiendo():
    """Deuda declarada, no escondida.

    Tres consumidores de fuera del paquete importan ayudantes PRIVADOS de
    cipher.py, y los tres con el mismo motivo: necesitan un estado
    intermedio que la API publica no devuelve.

      - _valores_de_permutacion: la receta de la orbita que alimenta a
        sigma. La usan el test de la avalancha, la figura 2 (que ensena la
        imagen permutada pero NO difundida) y la pestana del dashboard.
      - _material: el troceado del keystream en (k_ida, k_vuelta, iv, iv).
        La usa el banco de medidas para cronometrar cada etapa por
        separado.

    La alternativa era copiar la receta en cada sitio, y entonces una
    copia se separaria de la del cifrado sin que nadie lo notara: eso es
    peor, porque el sintoma seria una figura que miente, no un error.
    Este test deja la dependencia POR ESCRITO y falla el dia que alguien
    renombre uno de los dos, que es cuando hay que decidir si se
    promocionan a publicos o se actualizan los consumidores.
    """
    from chaos import cipher

    for ayudante in ("_valores_de_permutacion", "_material"):
        assert hasattr(cipher, ayudante), (
            f"cipher.{ayudante} lo usan el dashboard, las figuras o el "
            f"benchmark desde fuera del paquete"
        )
