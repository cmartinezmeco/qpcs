"""src/qkd/qrng.py — tarea 1.2 (Gonzalo). Generacion cuantica de bits."""

from __future__ import annotations

import numpy as np  # noqa: F401 - se usara al implementar random_bits (parte 1.2)

from .types import Bits

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

class QRNG: # Para importar esta clase, utilizar "from .qrng import QRNG"
    """Generador de bits aleatorios por medida de |+> en la base Z.
    Cada bit procede de una medida proyectiva sobre un estado en superposición
    uniforme: P(0) = P(1) = 1/2 por la regla de Born.
    """

    def __init__(self, qubits_per_circuit: int = 16, seed: int | None = None) -> None:
        """Por defecto, se lanza un circuito de 16 qubits por cada llamada a random_bits. Se puede cambiar con qubits_per_circuit.
        El generador de números aleatorios de la simulación se puede volver determinista cambiando el seed.
        """

        self._k = qubits_per_circuit # Número de qubits por circuito. Se lanza un circuito de k qubits por cada llamada a random_bits. Se almacena en self._k, que es una variable interna de la clase.

        self._backend = AerSimulator(seed_simulator=seed) # Inicializa el backend de simulación de Qiskit con un generador de números aleatorios determinista si se proporciona un seed.

        self._circuit = self._build(self._k) # Construye un circuito de k qubits que prepara el estado |+> y lo mide en la base Z llamando a la función _build.

    @staticmethod # Indica que el método no depende de la instancia de la clase, sino que es un método estático que se puede llamar sin crear una instancia de QRNG.
    def _build(k: int) -> QuantumCircuit: # crea un chip cuántico virtual de 16 cables, les aplica el azar cuántico (Hadamard) a todos y les conecta un medidor al final.
        qc = QuantumCircuit(k, k) # El primer argumento es el número de qubits, el segundo es el número de bits clásicos para almacenar los resultados de la medida.
        qc.h(range(k))  # |0...0> -> |+...+>, aplica la puerta Hadamard a cada qubit para crear superposición uniforme.
        qc.measure(range(k), range(k)) # Mide cada qubit en la base Z y almacena el resultado en el bit clásico correspondiente.
        return qc
    
    def random_bits(self, n: int) -> Bits:
        """Devuelve n bits. Lanza ceil(n/k) shots de un circuito de k qubits. Ver docs/theory/qkd.md."""
        if n == 0:
            return np.empty(0, dtype=np.uint8) # Para que no pierda el tiempo encendiendo el simulador de Qiskit.
            
        shots = -(-n // self._k)  # Techo de la división (ceil) sin necesidad de importar math.
        result = self._backend.run(
            self._circuit, 
            shots=shots, 
            memory=True  # Necesario para obtener la secuencia exacta de disparos
        ).result()
        
        # get_memory() -> ['0110...', '1001...'] con k caracteres por shot
        raw = "".join(result.get_memory()) # Une todos los resultados de los disparos en una sola cadena de bits.
        bits = np.frombuffer(raw.encode(), dtype=np.uint8) - ord("0") # Convierte la cadena de bits en un array de enteros (0 y 1) restando el valor ASCII de '0'.
        return bits[:n].copy() # Devuelve solo los primeros n bits (los que realmente se pidieron y se modificaron al hacer el "ceil") y hace una copia.

    def random_bases(self, n: int) -> Bits:
        """Bases: 0 = Z (rectilínea), 1 = X (diagonal). Misma distribución, significado distinto."""
        return self.random_bits(n) # Reutiliza la función random_bits para generar bases aleatorias, ya que la distribución es la misma, solo cambia la interpretación de los bits generados.
