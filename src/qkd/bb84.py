"""src/qkd/bb84.py — tarea 1.3 (Gonzalo). Nucleo BB84 sin Eve."""

from __future__ import annotations

from typing import Literal

import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

from .eve import intercept_resend
from .types import Bases, Bits, SiftedKeys


def _bob_measures(
    alice_bits: Bits,
    alice_bases: Bases,
    bob_bases: Bases,
    rng: np.random.Generator,
    noise: float = 0.0,
) -> Bits:
    """Resultado de Bob (Backend NumPy)."""
    same = alice_bases == bob_bases  # Posiciones donde las bases coinciden
    # Bits aleatorios para las posiciones donde las bases no coinciden.
    coin = rng.integers(0, 2, size=alice_bits.size, dtype=np.uint8)
    # Si las bases coinciden, Bob obtiene el bit de Alice; si no, uno
    # aleatorio.
    bits = np.where(same, alice_bits, coin).astype(np.uint8)

    if noise > 0.0:
        # Aplica ruido a los bits de Bob: cada bit tiene una probabilidad
        # "noise" de ser volteado (0 -> 1 o 1 -> 0).
        flips = rng.random(bits.size) < noise
        bits = np.bitwise_xor(bits, flips.astype(np.uint8))

    return bits


def _block_circuit(
    k: int, alice_bits: Bits, alice_bases: Bases, bob_bases: Bases
) -> QuantumCircuit:
    """Construye un unico circuito para un lote (bloque) de k fotones a la vez.

    Aplica las operaciones qubit a qubit dentro del mismo registro.
    """
    qc = QuantumCircuit(k, k)

    for i in range(k):
        # Alice prepara el qubit i
        if alice_bits[i] == 1:
            # Puerta NOT cuantica: |0> <-> |1> si el bit de Alice es 1.
            qc.x(i)
        if alice_bases[i] == 1:  # Base X
            # Puerta de Hadamard: cambia la base de Z a X y viceversa si
            # la base de Alice es 1.
            qc.h(i)

    # Prohibe al simulador fusionar o reordenar las compuertas de Alice
    # con las de Bob.
    qc.barrier()
    # --- Canal (Eve solo se modela en el backend numpy, ver run_bb84) ---
    qc.barrier()

    for i in range(k):
        # Bob mide el qubit i
        if bob_bases[i] == 1:
            # Si Bob mide en la base X (bit = 1), tiene que deshacer
            # matematicamente esa base con una Hadamard antes de medir.
            qc.h(i)
        # Destruye el qubit i (la superposicion) y almacena el resultado
        # en el bit clasico i.
        qc.measure(i, i)

    return qc


def sift(
    alice_bits: Bits, alice_bases: Bases, bob_bits: Bits, bob_bases: Bases
) -> SiftedKeys:
    """Descarta las posiciones con bases distintas."""
    keep = np.flatnonzero(alice_bases == bob_bases)
    # Forzamos .copy() explicito para asegurar que Cascade no mute los
    # arrays originales.
    return SiftedKeys(
        alice=alice_bits[keep].copy(),
        bob=bob_bits[keep].copy(),
        indices=keep.copy(),
        n_sent=alice_bits.size,
    )


def run_bb84(
    n_photons: int,
    rng: np.random.Generator,
    eve_rate: float = 0.0,
    noise: float = 0.0,
    backend: Literal["qiskit", "numpy"] = "numpy",
    k: int = 16,  # Tamaño del lote, por defecto 16 como en QRNG
) -> SiftedKeys:
    """Ejecuta el protocolo BB84 procesando en lotes de k qubits si usa
    Qiskit y usando arrays si se usa NumPy.
    Para pocos fotones, Qiskit y NumPy no se diferencian mucho pero Qiskit
    deja ver la fisica detras de los procesos. Para muchos fotones, NumPy
    es mas rapido ya que utiliza un truco matematico para simular la
    medida de Bob sin necesidad de lanzar un circuito cuantico por foton.

    Eve (intercept-resend, ver eve.py) solo esta modelada en el backend
    numpy: intercepta el canal entre la preparacion de Alice y la medida
    de Bob, con eve_rate como fraccion de fotones interceptados.
    """
    if n_photons <= 0:
        # Si no se envian fotones, no hay nada que procesar: SiftedKeys
        # vacio.
        return SiftedKeys(
            alice=np.empty(0, dtype=np.uint8),
            bob=np.empty(0, dtype=np.uint8),
            indices=np.empty(0, dtype=np.int64),
            n_sent=0,
        )

    # 1. Seleccion global de bits y bases al azar para Alice y Bob. Se
    # hace de una sola vez para todos los fotones.
    alice_bits = rng.integers(0, 2, size=n_photons, dtype=np.uint8)
    alice_bases = rng.integers(0, 2, size=n_photons, dtype=np.uint8)
    bob_bases = rng.integers(0, 2, size=n_photons, dtype=np.uint8)

    # 2. Transmision
    if backend == "numpy":
        # El canal: si Eve intercepta, Bob recibe el estado que ELLA
        # reenvia (su bit, en su base), no el original de Alice. El
        # sifting de mas abajo sigue comparando las bases ORIGINALES
        # de Alice y Bob: Eve nunca participa en el sifting publico.
        if eve_rate > 0.0:
            channel_bits, channel_bases, _ = intercept_resend(
                alice_bits, alice_bases, eve_rate, rng
            )
        else:
            channel_bits, channel_bases = alice_bits, alice_bases
        # Simula la medida de Bob con NumPy, aplicando el ruido si
        # procede.
        bob_bits = _bob_measures(channel_bits, channel_bases, bob_bases, rng, noise)

    elif backend == "qiskit":
        if eve_rate > 0.0:
            # Eve solo se modela como ataque vectorizado en el backend
            # numpy (ver eve.py, tarea 1.4). No hay circuito de Eve a
            # nivel de puertas: lanzamos un error explicito en vez de
            # devolver un QBER incorrecto en silencio.
            raise NotImplementedError(
                "Eve no esta implementada en el backend qiskit; usa "
                "backend=numpy con eve_rate > 0."
            )
        # MEJORA D2 (cierra I3): el simulador se creaba sin seed_simulator, asi
        # que las medidas de Bob por circuito NO eran reproducibles entre
        # ejecuciones (a diferencia del QRNG, que si propaga su semilla). La
        # semilla se SORTEA del rng que ya recibe la funcion en vez de anadir
        # un parametro nuevo: asi la ruta qiskit queda atada al mismo
        # Generator que gobierna el resto y no se introduce una segunda
        # fuente de aleatoriedad (convencion de aleatoriedad explicita).
        semilla_sim = int(rng.integers(0, 2**31 - 1))
        sim = AerSimulator(seed_simulator=semilla_sim)
        bob_bits_list = []

        # Procesamos los fotones en porciones (lotes) de tamaño k
        for i in range(0, n_photons, k):
            # Tamaño real del bloque (el ultimo lote puede ser menor a k)
            current_k = min(k, n_photons - i)

            # Extraemos los datos de este lote
            b_alice = alice_bits[i : i + current_k]
            base_alice = alice_bases[i : i + current_k]
            base_bob = bob_bases[i : i + current_k]

            # Construimos un unico circuito para este lote de fotones
            qc = _block_circuit(current_k, b_alice, base_alice, base_bob)

            # Ejecutamos 1 shot (mide los 'current_k' qubits a la vez)
            result = sim.run(qc, shots=1, memory=True).result()

            # Leemos la cadena binaria de la memoria (igual que en QRNG,
            # pero ahora es un bloque de k qubits)
            raw_memory = result.get_memory()[0]

            # Qiskit ordena los qubits al reves en el string de memoria
            # (Qbit_n ... Qbit_0), por lo que invertimos [::-1] para
            # emparejarlo con nuestros arrays.
            # astype fuerza uint8: la resta con un int de Python
            # promociona el resultado a un entero con signo.
            block_bits = (
                np.frombuffer(raw_memory[::-1].encode(), dtype=np.uint8) - ord("0")
            ).astype(np.uint8)

            # Aplicamos el ruido al bloque completo
            if noise > 0.0:
                flips = rng.random(block_bits.size) < noise
                block_bits = np.bitwise_xor(block_bits, flips.astype(np.uint8))

            bob_bits_list.append(block_bits)

        # Unimos todos los lotes en un unico array de NumPy
        bob_bits = np.concatenate(bob_bits_list)
    else:
        # Por si el usuario pasa un backend que no es "numpy" ni "qiskit".
        raise ValueError(f"Backend no reconocido: {backend}")

    # 3. Cribado publico: SiftedKeys con los bits que coinciden en bases
    # ORIGINALES de Alice y Bob (Eve no interviene en el sifting), sus
    # indices y el numero total de fotones enviados.
    return sift(alice_bits, alice_bases, bob_bits, bob_bases)
