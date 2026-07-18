"""src/qkd/bb84.py — tarea 1.3 (Gonzalo). Nucleo BB84 sin Eve."""

from __future__ import annotations

from typing import Literal

import numpy as np

from .types import Bases, Bits, SiftedKeys

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator


def _bob_measures(
    alice_bits: Bits, 
    alice_bases: Bases, 
    bob_bases: Bases,
    rng: np.random.Generator, 
    noise: float = 0.0
) -> Bits:
    """Resultado de Bob (Backend NumPy)."""
    same = alice_bases == bob_bases # Posiciones donde las bases coinciden
    coin = rng.integers(0, 2, size=alice_bits.size, dtype=np.uint8) # Bits aleatorios para las posiciones donde las bases no coinciden
    bits = np.where(same, alice_bits, coin).astype(np.uint8) # Si las bases coinciden, Bob obtiene el bit de Alice; si no, obtiene un bit aleatorio.
    
    if noise > 0.0: # Aplica ruido a los bits de Bob. Cada bit tiene una probabilidad 'noise' de ser volteado (0 -> 1 o 1 -> 0).
        flips = rng.random(bits.size) < noise
        bits = np.bitwise_xor(bits, flips.astype(np.uint8))
        
    return bits

def _block_circuit(k: int, alice_bits: Bits, alice_bases: Bases, bob_bases: Bases) -> QuantumCircuit:
    """Construye un único circuito para un lote (bloque) de k fotones a la vez.
    
    Aplica las operaciones qubit a qubit dentro del mismo registro.
    """
    qc = QuantumCircuit(k, k)
    
    for i in range(k):
        # Alice prepara el qubit i
        if alice_bits[i] == 1:
            qc.x(i) # Puerta NOT cuántica (cambia |0> a |1> y viceversa si el bit de Alice es 1)
        if alice_bases[i] == 1: # Base X
            qc.h(i) # Puerta de Hadamard (cambia la base de Z a X y viceversa si la base de Alice es 1)
            
    qc.barrier() # Le prohíben al simulador fusionar o reordenar las compuertas de Alice con las de Bob.
    # --- Canal (Futura tarea de Eve) ---
    qc.barrier()
    
    for i in range(k):
        # Bob mide el qubit i
        if bob_bases[i] == 1: # Si Bob decide que quiere medir el fotón en la Base X (bit = 1), tiene que deshacer matemáticamente esa base aplicando una puerta Hadamard justo antes de medir.
            qc.h(i)
        qc.measure(i, i) # Destruye el qubit i (la superposición) y almacena el resultado en el bit clásico i.
        
    return qc

def sift(
    alice_bits: Bits, 
    alice_bases: Bases,
    bob_bits: Bits, 
    bob_bases: Bases
) -> SiftedKeys:
    """Descarta las posiciones con bases distintas."""
    keep = np.flatnonzero(alice_bases == bob_bases)
    # Forzamos .copy() explícito para asegurar que Cascade no mute los arrays originales
    return SiftedKeys(
        alice=alice_bits[keep].copy(), 
        bob=bob_bits[keep].copy(),
        indices=keep.copy(), 
        n_sent=alice_bits.size
    )

def run_bb84(
    n_photons: int,
    rng: np.random.Generator,
    eve_rate: float = 0.0,
    noise: float = 0.0,
    backend: Literal["qiskit", "numpy"] = "numpy",
    k: int = 16  # Tamaño del lote, por defecto 16 como en QRNG
) -> SiftedKeys:
    """Ejecuta el protocolo BB84 procesando en lotes de k qubits si usa Qiskit y usando arrays si se usa NumPy.
    Para pocos fotones, Quiskit y NumPy no se diferencian mucho pero Qiskit deja ver la física detrás de los procesos. 
    Para muchos fotones, NumPy es más rápido ya que utiliza un truco matemático para simular la medida de Bob 
    sin necesidad de lanzar un circuito cuántico por cada fotón.
    """
    if n_photons <= 0: # Si no se envían fotones, no hay nada que procesar y se devuelve un SiftedKeys vacío.
        return SiftedKeys(
            alice=np.empty(0, dtype=np.uint8), 
            bob=np.empty(0, dtype=np.uint8), 
            indices=np.empty(0, dtype=np.int64), 
            n_sent=0
        )

    # 1. Selección global de bits y bases de forma aleatoria (entre 0 y 1) para Alice y Bob. Se hace de una sola vez para todos los fotones.
    alice_bits = rng.integers(0, 2, size=n_photons, dtype=np.uint8)
    alice_bases = rng.integers(0, 2, size=n_photons, dtype=np.uint8)
    bob_bases = rng.integers(0, 2, size=n_photons, dtype=np.uint8)

    # 2. Transmisión
    if backend == "numpy":
        bob_bits = _bob_measures(alice_bits, alice_bases, bob_bases, rng, noise) # Llama a la función que simula la medida de Bob usando NumPy, aplicando el ruido si es necesario.
        
    elif backend == "qiskit":
        sim = AerSimulator()
        bob_bits_list = []
        
        # Procesamos los fotones en porciones (lotes) de tamaño k
        for i in range(0, n_photons, k):
            # Determinamos el tamaño real del bloque (el último lote puede ser menor a k)
            current_k = min(k, n_photons - i)
            
            # Extraemos los datos de este lote
            b_alice = alice_bits[i : i + current_k]
            base_alice = alice_bases[i : i + current_k]
            base_bob = bob_bases[i : i + current_k]
            
            # Construimos un ÚNICO circuito para este lote de fotones
            qc = _block_circuit(current_k, b_alice, base_alice, base_bob)
            
            # Ejecutamos 1 shot (que mide los 'current_k' qubits a la vez)
            result = sim.run(qc, shots=1, memory=True).result()
            
            # Leemos la cadena binaria de la memoria (igual que en QRNG, pero ahora es un bloque de k qubits)
            raw_memory = result.get_memory()[0]
            
            # Qiskit ordena los qubits al revés en el string de memoria (Qbit_n ... Qbit_0), 
            # por lo que invertimos el string [::-1] para emparejarlo con nuestros arrays.
            block_bits = np.frombuffer(raw_memory[::-1].encode(), dtype=np.uint8) - ord("0") # Restamos el valor ASCII de '0' para obtener un array de 0s y 1s (igual que en QRNG).
            
            # Aplicamos el ruido al bloque completo
            if noise > 0.0:
                flips = rng.random(block_bits.size) < noise
                block_bits = np.bitwise_xor(block_bits, flips.astype(np.uint8))
                
            bob_bits_list.append(block_bits)
            
        # Unimos todos los lotes en un único array de NumPy
        bob_bits = np.concatenate(bob_bits_list)
    else:
        raise ValueError(f"Backend no reconocido: {backend}") # Por si el usuario pasa un backend que no es "numpy" ni "qiskit".

    # 3. Cribado público
    return sift(alice_bits, alice_bases, bob_bits, bob_bases) # Devuelve un objeto SiftedKeys que contiene los bits de Alice y Bob que coinciden en las bases, los índices de esos bits y el número total de fotones enviados.