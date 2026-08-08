# tests/pqc/test_shor.py (parte 2.2)
import numpy as np
import pytest
from pqc.shor import (
    c_amod15,
    circuito_orden_15,
    factorizar_15,
    histograma_fases_15,
    medir_fase_15,
    orden_desde_fase,
    qft_dagger,
)
from qiskit.quantum_info import Operator, Statevector

# Los seis coprimos con 15 y su orden real, calculado a mano una vez: es la
# tabla contra la que se contrasta lo que devuelve el modulo. El exponente del
# grupo (Z/15)* es 4, asi que ningun orden pasa de 4.
ORDENES = {2: 4, 4: 2, 7: 4, 8: 4, 11: 2, 13: 4}


def test_fase_es_multiplo_de_1_sobre_4_para_a7():
    """a=7 mod 15 tiene orden 4: las fases validas son 0, 1/4, 2/4, 3/4."""
    for seed in range(8):
        phi = medir_fase_15(a=7, rng=np.random.default_rng(seed), n_count=8)
        cercania = min(abs(phi - k / 4) for k in range(4))
        assert cercania < 1 / 16, f"fase {phi:.3f} lejos de k/4"


def test_shor_factoriza_15():
    """EL test del bloque Shor: 15 = 3 x 5 via busqueda de orden."""
    res = factorizar_15(np.random.default_rng(42))
    assert res.ok
    p, q = res.factores
    assert p * q == 15
    assert {p, q} == {3, 5}


@pytest.mark.parametrize("semilla", range(16))
def test_el_orden_que_publica_shor_es_el_orden_de_verdad(semilla):
    """El campo `orden` tiene que cumplir a^orden == 1 (mod 15). No es obvio.

    Sustituye a un test que calculaba el orden por su cuenta con pow() y gcd()
    y afirmaba un hecho de aritmetica modular: pasaba igual con src/pqc/shor.py
    vacio, porque no ejecutaba ni una linea del modulo.

    Lo que se comprueba ahora es la propiedad que de verdad se podia romper, y
    que estaba rota: las fracciones continuas sobre una fase s/r pueden
    devolver un DIVISOR de r en vez de r (con a=7 y fase 2/4 devuelven 2, no
    4), y la reduccion clasica factoriza igual, asi que el fallo no se veia en
    `factores` -solo en `orden`, que es lo que el dashboard pinta como "Orden r
    hallado" y lo que fija las lineas del histograma-.

    EL RANGO DE SEMILLAS NO ES DECORATIVO. Contra el codigo anterior, 45 de las
    200 primeras semillas (22%) publicaban un orden que no lo era, pero
    NINGUNA de las seis primeras: un barrido range(6) habria pasado en verde
    sobre el bug. range(16) incluye las semillas 9, 10, 12 y 13, que son las
    primeras que lo destapan. Al tocar este test, comprobar que sigue fallando
    contra la version sin `pow(a, r, N) != 1`.
    """
    res = factorizar_15(np.random.default_rng(semilla))
    assert res.ok
    assert pow(res.a, res.orden, 15) == 1, (
        f"orden={res.orden} no es el orden de a={res.a} mod 15 "
        f"(el real es {ORDENES[res.a]})"
    )
    assert res.orden == ORDENES[res.a]


def test_fracciones_continuas_recuperan_denominador():
    """fase = 3/4 debe dar r = 4 (denominador del convergente)."""
    assert orden_desde_fase(0.75, 15) == 4


def test_orden_desde_fase_devuelve_none_cuando_no_hay_denominador_util():
    """La rama que el llamador descarta: fase 0 (y fase 1/1) no dan orden.

    Es el `return r if r > 1 else None` de orden_desde_fase, que ningun test
    recorria. La fase 0 sale de verdad -es s=0, uno de cada r resultados del
    circuito-, asi que esta rama se ejecuta en cada ejecucion real de Shor.
    """
    assert orden_desde_fase(0.0, 15) is None
    assert orden_desde_fase(1.0, 15) is None
    assert orden_desde_fase(0.5, 15) == 2


def test_c_amod15_rechaza_una_base_que_no_es_coprima():
    """Con a no coprimo con 15 el oraculo no existe: error inmediato.

    Cubre tambien el centinela a=0 del camino de fracaso de factorizar_15: si
    alguien pinta ese 0 y lo devuelve al circuito, tiene que reventar aqui y no
    dibujar un histograma de mentira.
    """
    for a in (0, 3, 5, 6, 9, 10, 12, 14, 15):
        with pytest.raises(ValueError, match="coprimo"):
            c_amod15(a, 1)


@pytest.mark.parametrize("a", sorted(ORDENES))
def test_c_amod15_implementa_a_elevado_a_power_no_a_2_elevado_a_power(a):
    """El exponente que documenta el docstring, comprobado sobre la unitaria.

    Se compara la puerta con la permutacion clasica |y> -> |a^power * y mod 15>
    sobre los estados 1..14, que es lo que tiene que hacer. Si alguien
    "arreglara" el docstring cambiando el cuerpo a range(2**power), este test
    lo caza.

    De paso fija la identidad que hace barato el circuito: power y power % 4
    dan la MISMA puerta, porque el bloque cumple BLOQUE^4 = I. Sin ella,
    circuito_orden_15 construiria 255 copias del bloque en vez de 3.
    """
    for power in (1, 2, 3, 4, 5, 8, 128):
        puerta = c_amod15(a, power)
        # Puerta controlada de 5 qubits: el control que anade .control() es el
        # qubit 0 y los 4 de trabajo son los qubits 1..4. Las etiquetas de
        # Qiskit son big-endian (qubit4..qubit0), de ahi el "1" pegado al
        # final: es el control activado.
        for y in range(1, 15):
            esperado = pow(a, power, 15) * y % 15
            salida = Statevector.from_label(f"{y:04b}1").evolve(puerta)
            destino = Statevector.from_label(f"{esperado:04b}1")
            assert abs(complex(salida.inner(destino))) == pytest.approx(
                1.0
            ), f"a={a} power={power}: |{y}> no va a |{esperado}>"
        # Con el control a 0 la puerta no toca el registro de trabajo.
        sin_control = Statevector.from_label("00100")
        assert abs(
            complex(sin_control.evolve(puerta).inner(sin_control))
        ) == pytest.approx(1.0)
        assert np.allclose(Operator(puerta).data, Operator(c_amod15(a, power % 4)).data)


def test_qft_dagger_es_la_inversa_de_la_qft():
    """QFT^dagger deshace la QFT: el producto de las dos es la identidad.

    `qft_dagger` no la llamaba ningun test directamente, pese a ser la mitad de
    la estimacion de fase (la que lleva la fase de las amplitudes al registro
    de conteo). Se contrasta contra la QFT de la libreria de Qiskit, no contra
    otra implementacion nuestra.
    """
    from qiskit.circuit.library import QFT

    for n in (2, 3, 4):
        producto = Operator(QFT(n)) @ Operator(qft_dagger(n))
        assert np.allclose(producto.data, np.eye(2**n))


def test_circuito_orden_15_tiene_la_forma_de_la_estimacion_de_fase():
    """n_count qubits de conteo + 4 de trabajo, y n_count bits clasicos."""
    for n_count in (4, 8):
        qc = circuito_orden_15(7, n_count)
        assert qc.num_qubits == n_count + 4
        assert qc.num_clbits == n_count
        # Una medida por qubit de conteo, ni una mas.
        medidas = [inst for inst in qc.data if inst.operation.name == "measure"]
        assert len(medidas) == n_count


def test_factorizar_15_sin_intentos_devuelve_los_centinelas_del_fracaso():
    """El camino de fracaso, que ningun test recorria.

    Con max_intentos=0 el bucle no se ejecuta y se cae directo al return del
    fracaso. Lo que se fija es el CONTRATO de esos campos (ver el docstring de
    FactorizacionShor): con ok=False no son medidas, son centinelas, y `a=0` en
    particular no es una base valida. Quien los pinte sin mirar `ok` ensena
    ceros como si fueran resultados.
    """
    res = factorizar_15(np.random.default_rng(0), max_intentos=0)
    assert res.ok is False
    assert res.factores == (1, 15)
    assert (res.a, res.orden, res.fase_medida) == (0, 0, 0.0)


def test_histograma_de_fases_cae_en_los_multiplos_de_1_sobre_r():
    """El muestreo con muchos disparos que consumen la figura 3 y el dashboard.

    Con a=7 (orden 4) toda la masa tiene que caer en 0, 1/4, 2/4 y 3/4, y las
    cuentas tienen que sumar los disparos pedidos. Es la version comprobable de
    lo que la figura ensena a ojo.
    """
    histograma = histograma_fases_15(7, np.random.default_rng(42), n_count=8, shots=512)
    assert sum(histograma.values()) == 512
    assert set(histograma) == {0.0, 0.25, 0.5, 0.75}
    # Misma semilla, mismo histograma: es simulacion sembrada, no cripto real.
    assert histograma == histograma_fases_15(
        7, np.random.default_rng(42), n_count=8, shots=512
    )
