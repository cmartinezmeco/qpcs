# tests/qkd/test_reconciliation.py — tests de la tarea 1.5 (Cascade).
#
# Nota para el equipo: binary_entropy no vive en qkd.utils, que es donde
# uno la buscaria por costumbre, sino en qkd/privacy.py, y asi la exporta
# la API publica. Importamos de ahi.

import numpy as np
import pytest
from qkd.privacy import binary_entropy
from qkd.reconciliation import ParityOracle, _binary, _local_parity, cascade


def _par(n: int, q: float, seed: int):
    """Par de claves de n bits que difieren en una fraccion ~q de posiciones.

    Simula la salida de la tarea 1.4 (clave cribada tras descartar la
    muestra del QBER) sin tener que correr BB84 entero: para probar Cascade
    solo importa el patron de errores, no de donde salio.
    """
    rng = np.random.default_rng(seed)
    alice = rng.integers(0, 2, n, dtype=np.uint8)
    flips = rng.random(n) < q
    bob = np.bitwise_xor(alice, flips.astype(np.uint8))
    return alice, bob, rng


@pytest.mark.parametrize("q", [0.01, 0.02, 0.05, 0.08, 0.10])
def test_cascade_iguala_las_claves(q):
    """El criterio central: al salir, bob == alice, para todo Q operativo."""
    alice, bob, rng = _par(10_000, q, seed=42)
    r = cascade(alice, bob, qber=q, rng=rng)
    np.testing.assert_array_equal(r.alice, r.bob)
    assert r.ok


@pytest.mark.parametrize("q", [0.02, 0.05])
def test_eficiencia_razonable(q):
    """f_EC entre 1.0 y 1.4. Por debajo de 1.0 se viola Shannon: es un bug.

    (El limite teorico de Slepian-Wolf es n*h(Q) bits; Cascade se queda un
    10-20% por encima, de ahi el rango.)
    """
    alice, bob, rng = _par(20_000, q, seed=7)
    r = cascade(alice, bob, qber=q, rng=rng)
    f = r.leak_ec / (alice.size * binary_entropy(q))
    assert 1.0 <= f <= 1.4, f"f_EC={f:.3f} fuera de rango"


def test_sin_errores_no_corrige_nada():
    alice, _, rng = _par(5_000, 0.0, seed=1)
    r = cascade(alice, alice.copy(), qber=0.01, rng=rng)
    assert r.corrected == 0
    assert r.leak_ec > 0  # aun asi se pagan las paridades de descubrimiento
    assert r.ok


def test_el_oraculo_cuenta_todo():
    """leak_ec no puede ser 0 ni un numero redondo sospechoso."""
    alice, bob, rng = _par(5_000, 0.03, seed=3)
    r = cascade(alice, bob, qber=0.03, rng=rng)
    # Como minimo, las paridades de descubrimiento de la pasada 1:
    # n / k1 bloques con k1 = ceil(0.73 / Q).
    assert r.leak_ec >= 5_000 / int(np.ceil(0.73 / 0.03))


def test_qber_cero_exacto_no_diverge():
    """Caso borde: Q = 0 exacto => k1 acotado (no division
    por cero) y Cascade termina con las claves intactas."""
    alice, _, rng = _par(2_000, 0.0, seed=5)
    r = cascade(alice, alice.copy(), qber=0.0, rng=rng)
    assert r.ok
    assert r.corrected == 0


def test_claves_vacias():
    """Caso borde: n = 0 no lanza excepcion y sale ok."""
    empty = np.empty(0, dtype=np.uint8)
    r = cascade(empty, empty.copy(), qber=0.02, rng=np.random.default_rng(0))
    assert r.ok
    assert r.corrected == 0


def test_no_muta_las_entradas():
    """El contrato de types.py es frozen: cascade devuelve copias y no toca
    los arrays originales (bug clasico: corregir bob in place)."""
    alice, bob, rng = _par(5_000, 0.03, seed=9)
    bob_original = bob.copy()
    cascade(alice, bob, qber=0.03, rng=rng)
    np.testing.assert_array_equal(bob, bob_original)


def _cascade_ingenua(alice, bob, qber, rng, n_passes=4):
    """Cascade con busqueda LINEAL del bloque, para contrastar (MEJORA B3).

    Reproduce paso a paso el algoritmo de qkd.reconciliation.cascade con una
    unica diferencia: donde la implementacion real consulta la tabla
    precomputada `block_of_by_pass[pj][pos]` (O(1)), esta recorre los bloques
    de la pasada buscando cual contiene la posicion (`pos in bloque`, O(k)),
    que es la version ingenua O(n^2) que la optimizacion sustituyo.

    Todo lo demas es identico, INCLUIDO el consumo del rng (las mismas
    permutaciones en el mismo orden), asi que ambas rutas tienen que producir
    exactamente la misma clave corregida y el mismo leak_ec.
    """
    n = bob.size
    bob = bob.copy()
    oracle = ParityOracle(alice)

    q = max(qber, 1e-3)
    k = max(2, int(np.ceil(0.73 / q)))

    blocks_by_pass = []
    alice_parity_by_pass = []
    corrected = 0

    for p in range(n_passes):
        if p == 0:
            perm = np.arange(n, dtype=np.int64)
        else:
            perm = rng.permutation(n).astype(np.int64)
        blocks = [perm[i : i + k] for i in range(0, n, k)]
        parities = [oracle.parity(b) for b in blocks]

        blocks_by_pass.append(blocks)
        alice_parity_by_pass.append(parities)

        pending = [
            (p, j) for j, b in enumerate(blocks) if parities[j] != _local_parity(bob, b)
        ]

        while pending:
            pending.sort(key=lambda pj: blocks_by_pass[pj[0]][pj[1]].size)
            pi, bi = pending.pop(0)
            block = blocks_by_pass[pi][bi]

            if alice_parity_by_pass[pi][bi] == _local_parity(bob, block):
                continue

            pos = _binary(oracle, bob, block)
            bob[pos] ^= 1
            corrected += 1

            for pj in range(len(blocks_by_pass)):
                if pj == pi:
                    continue
                # LA diferencia: busqueda lineal en vez de la tabla O(1).
                for jj, candidato in enumerate(blocks_by_pass[pj]):
                    if pos in candidato:
                        pending.append((pj, jj))
                        break

        k *= 2

    return bob, oracle.leaked, corrected


@pytest.mark.parametrize("q", [0.02, 0.05])
def test_block_of_coincide_con_la_busqueda_ingenua(q):
    """La tabla precomputada da EXACTAMENTE lo mismo que buscar a pelo.

    MEJORA B3: de las tres optimizaciones del modulo, dos ya tenian un test
    que las vigilaba (los dos backends del canal en test_backends_coinciden y
    el Toeplitz por FFT frente a la matriz explicita). La tercera
    -block_of_by_pass, que baja el backtracking del efecto cascada de O(n^2) a
    O(1)- no tenia ninguno, y un fallo ahi no rompe la correccion de forma
    visible: cascade seguiria igualando las claves por otras pasadas y solo
    se notaria como un f_EC mas alto, dentro del rango [1.0, 1.4] que tolera
    test_eficiencia_razonable. Este test cierra ese hueco con el mismo patron
    que el de la FFT: optimizacion contra definicion, bit a bit.
    """
    alice, bob, _ = _par(4_000, q, seed=17)

    # Dos generadores con la MISMA semilla: las permutaciones de las pasadas
    # son identicas en ambas rutas, asi que la comparacion es limpia.
    r_real = cascade(alice, bob, qber=q, rng=np.random.default_rng(101))
    bob_ingenua, leak_ingenua, corrected_ingenua = _cascade_ingenua(
        alice, bob, qber=q, rng=np.random.default_rng(101)
    )

    np.testing.assert_array_equal(r_real.bob, bob_ingenua)
    assert r_real.leak_ec == leak_ingenua
    assert r_real.corrected == corrected_ingenua


def test_el_oraculo_cobra_cada_consulta():
    """Cada llamada a parity() suma exactamente 1 al contador de fugas."""
    key = np.array([1, 0, 1, 1], dtype=np.uint8)
    oracle = ParityOracle(key)
    assert oracle.leaked == 0
    assert oracle.parity(np.array([0, 1, 2], dtype=np.int64)) == 0  # 1^0^1
    assert oracle.parity(np.array([2, 3], dtype=np.int64)) == 0  # 1^1
    assert oracle.parity(np.array([3], dtype=np.int64)) == 1
    assert oracle.leaked == 3
