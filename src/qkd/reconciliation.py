"""src/qkd/reconciliation.py — tarea 1.5 (Marco). Cascade + contador de fugas.

Reconciliacion de claves: Alice y Bob salen de la tarea 1.4 con dos cadenas
que difieren en una fraccion Q de posiciones y las igualan hablando por un
canal publico que Eve escucha entero. Cada bit publicado se cuenta en el
ParityOracle (leak_ec) porque despues se resta de la clave final (tarea 1.6).

Referencia: G. Brassard y L. Salvail, "Secret-key reconciliation by public
discussion", EUROCRYPT '93 (el algoritmo Cascade original).
"""

from __future__ import annotations

import logging

import numpy as np
import numpy.typing as npt

from .privacy import binary_entropy
from .types import Bits, ReconciliationResult

logger = logging.getLogger(__name__)

# Alias local: un bloque es un array de indices (posiciones de la clave).
IndexArray = npt.NDArray[np.int64]


class ParityOracle:
    """Canal publico de Alice hacia Bob. La UNICA forma de mirar su clave.

    Cada consulta = 1 bit publicado = 1 bit que Eve conoce = 1 bit menos de
    clave final. El contador `leaked` es la razon de ser de esta clase:
    leak_ec no se estima "a ojo", se cuenta aqui, bit a bit.

    Defensa estructural contra el "Cascade que hace trampa": en la simulacion
    las dos claves estan en memoria y mirar alice[i] directamente seria una
    linea. Encapsulando la clave de Alice aqui, cascade() solo puede saber de
    ella lo que pregunte por paridades, exactamente igual que en el protocolo
    real. Regla de revision del PR: la palabra "alice" no puede aparecer en
    cascade() salvo para construir este oraculo (y el array_equal final, que
    solo simula la verificacion de exito y no publica nada).
    """

    def __init__(self, alice_key: Bits) -> None:
        # Privado: NADIE fuera de esta clase lo toca.
        self._key = alice_key
        self.leaked = 0

    def parity(self, idx: IndexArray) -> int:
        """Paridad de alice[idx]. Cuesta exactamente 1 bit de fuga."""
        self.leaked += 1
        if idx.size == 0:
            return 0
        return int(np.bitwise_xor.reduce(self._key[idx]))


def _local_parity(bob: Bits, idx: IndexArray) -> int:
    """Paridad de los bits del PROPIO Bob. Es gratis: no pasa por el canal."""
    if idx.size == 0:
        return 0
    return int(np.bitwise_xor.reduce(bob[idx]))


def _binary(oracle: ParityOracle, bob: Bits, idx: IndexArray) -> int:
    """Busqueda binaria (BINARY) de UN error en un bloque de paridad impar.

    Invariante: idx contiene un numero impar de errores.
    Coste: ceil(log2(len(idx))) bits de fuga (una paridad por nivel; la
    paridad de la otra mitad se deduce gratis de la del bloque entero).
    Devuelve la posicion (absoluta) del error encontrado.
    """
    while idx.size > 1:
        half = idx.size // 2
        left = idx[:half]
        if oracle.parity(left) != _local_parity(bob, left):
            idx = left  # el error impar esta en la mitad izquierda
        else:
            idx = idx[half:]  # ... o en la derecha
    return int(idx[0])


def cascade(
    alice: Bits, bob: Bits, qber: float, rng: np.random.Generator, n_passes: int = 4
) -> ReconciliationResult:
    """Reconciliacion Cascade (Brassard & Salvail, 1993).

    Tamano de bloque inicial k1 ~ 0.73/Q (regla empirica del articulo
    original), doblado en cada pasada con una permutacion publica nueva.
    Cuando se corrige un bit, los bloques de pasadas anteriores que lo
    contenian pasan a tener un numero impar de errores y se vuelven
    localizables sin gastar paridades nuevas de descubrimiento: es el
    "efecto cascada" que da nombre al algoritmo.

    Eficiencia esperada f_EC = leak_ec / (n * h(Q)) ~ 1.1-1.2 (se loguea al
    final; si sale < 1.0 hay un bug porque violaria el limite de Shannon).
    """
    n = bob.size
    # Los dataclasses del contrato son frozen: trabajamos sobre una copia de
    # la clave de Bob y devolvemos, nunca mutamos los arrays de entrada.
    bob = bob.copy()
    # Unica aparicion permitida de la clave de Alice: construir el oraculo.
    oracle = ParityOracle(alice)

    q = max(qber, 1e-3)  # evita k1 -> infinito si Q = 0
    k = max(2, int(np.ceil(0.73 / q)))

    # Estado acumulado por pasada, necesario para el efecto cascada:
    #   blocks_by_pass[p]   -> lista de bloques (arrays de indices).
    #   block_of_by_pass[p] -> block_of[pos] = indice del bloque de la pasada
    #       p que contiene la posicion pos. Precomputarlo cuesta O(n) por
    #       pasada y hace el backtracking O(1). (La alternativa ingenua
    #       "if pos in bloque" es O(k) dentro de dos bucles: el algoritmo se
    #       vuelve O(n^2) y con n = 40 000 no termina. Ver seccion 5.5.4 de
    #       la guia: la version que se mergea lleva block_of.)
    #   alice_parity_by_pass[p][j] -> paridad que Alice YA publico del bloque
    #       j. Se cachea para re-comprobar bloques sin volver a preguntar al
    #       oraculo: la paridad ya es publica, re-preguntar contaria fugas
    #       que no existen.
    blocks_by_pass: list[list[IndexArray]] = []
    block_of_by_pass: list[IndexArray] = []
    alice_parity_by_pass: list[list[int]] = []

    corrected = 0

    for p in range(n_passes):
        # Pasada 0 en orden natural; las siguientes barajan con una
        # permutacion publica para que dos errores que caian en el mismo
        # bloque (y se escondian mutuamente en la paridad) se separen.
        if p == 0:
            perm = np.arange(n, dtype=np.int64)
        else:
            perm = rng.permutation(n).astype(np.int64)
        blocks = [perm[i : i + k] for i in range(0, n, k)]

        block_of = np.empty(n, dtype=np.int64)
        for j, b in enumerate(blocks):
            block_of[b] = j

        # Descubrimiento: Alice publica la paridad de cada bloque de esta
        # pasada (1 bit de fuga por bloque, contado por el oraculo).
        parities = [oracle.parity(b) for b in blocks]

        blocks_by_pass.append(blocks)
        block_of_by_pass.append(block_of)
        alice_parity_by_pass.append(parities)

        # Cola de bloques con paridad discordante: pares (pasada, bloque).
        # Arranca con los discordantes de ESTA pasada; el efecto cascada ira
        # anadiendo bloques de pasadas anteriores.
        pending: list[tuple[int, int]] = [
            (p, j) for j, b in enumerate(blocks) if parities[j] != _local_parity(bob, b)
        ]

        while pending:
            # Heuristica estandar: atacar siempre el bloque mas pequeno
            # (BINARY mas barato: los bloques de pasadas tempranas son los
            # mas cortos).
            pending.sort(key=lambda pj: blocks_by_pass[pj[0]][pj[1]].size)
            pi, bi = pending.pop(0)
            block = blocks_by_pass[pi][bi]

            # Re-comprobacion GRATIS con la paridad cacheada: una correccion
            # posterior a su encolado puede haber dejado este bloque otra
            # vez con paridad par (0, 2... errores). Si ya cuadra, no hay
            # error impar que buscar y BINARY no aplica.
            if alice_parity_by_pass[pi][bi] == _local_parity(bob, block):
                continue

            pos = _binary(oracle, bob, block)
            bob[pos] ^= 1
            corrected += 1

            # --- EFECTO CASCADA ---
            # El bloque de cada OTRA pasada que contiene pos tenia la
            # paridad cuadrada con un numero par de errores; al eliminar
            # uno, ahora tiene un numero impar: hay al menos otro error ahi
            # dentro y es localizable sin paridades nuevas de
            # descubrimiento. Se encola y la re-comprobacion de arriba
            # filtra los que ya esten resueltos cuando les llegue el turno.
            for pj in range(len(blocks_by_pass)):
                if pj == pi:
                    continue
                pending.append((pj, int(block_of_by_pass[pj][pos])))

        k *= 2  # bloques del doble de tamano en la siguiente pasada

    # Verificacion final. En el protocolo real esto se haria comparando un
    # hash por el canal publico; en la simulacion basta comparar arrays (no
    # publica nada y no cuenta como fuga).
    ok = bool(np.array_equal(alice, bob))

    # La metrica de calidad de la tarea (seccion 5.5.5): f_EC = leak/(n h(Q)).
    # ~1.1-1.2 excelente; ~1.5 mal afinado; < 1 imposible (Shannon) = bug.
    # Convencion del equipo: logging, nada de print.
    h = binary_entropy(qber)
    if n > 0 and h > 0.0:
        logger.debug(
            "cascade: n=%d Q=%.4f passes=%d corrected=%d leak_ec=%d f_EC=%.3f",
            n,
            qber,
            n_passes,
            corrected,
            oracle.leaked,
            oracle.leaked / (n * h),
        )

    return ReconciliationResult(
        alice=alice,
        bob=bob,
        leak_ec=oracle.leaked,
        n_passes=n_passes,
        corrected=corrected,
        ok=ok,
        # MEJORA D1: se propaga el QBER al resultado. Es el mismo valor que
        # ya se usa arriba para el log de f_EC; guardarlo hace implementable
        # la property ReconciliationResult.efficiency.
        qber=qber,
    )
