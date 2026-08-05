"""src/qkd/qrng.py — tarea 1.2 (Gonzalo). Generacion cuantica de bits."""

from __future__ import annotations

from typing import Literal

import numpy as np
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

from .types import Bases, Bits


class QRNG:  # Importar con "from .qrng import QRNG"
    """Generador de bits aleatorios por medida de |+> en la base Z.
    Cada bit procede de una medida proyectiva sobre un estado en superposicion
    uniforme: P(0) = P(1) = 1/2 por la regla de Born.
    """

    def __init__(
        self,
        qubits_per_circuit: int = 16,
        seed: int | None = None,
        # Selector de backend para la velocidad de procesamiento.
        backend: Literal["qiskit", "numpy"] = "numpy",
    ) -> None:
        """Por defecto, se lanza un circuito de 16 qubits por cada llamada a
        random_bits. Se puede cambiar con qubits_per_circuit. El generador
        de numeros aleatorios de la simulacion se puede volver determinista
        cambiando el seed.
        """
        # Numero de qubits por circuito: se lanza un circuito de k qubits
        # por cada llamada a random_bits. Variable interna de la clase.
        self._k = qubits_per_circuit
        self._backend_type = backend

        # Inicializamos los motores correspondientes
        if self._backend_type == "qiskit":
            # Backend de simulacion de Qiskit con un generador de numeros
            # aleatorios determinista si se proporciona un seed.
            self._backend = AerSimulator(seed_simulator=seed)
            # Circuito de k qubits que prepara el estado |+> y lo mide en
            # la base Z, construido por _build.
            self._circuit = self._build(self._k)
        else:
            # Generador clasico aislado y reproducible con la semilla
            self._rng = np.random.default_rng(seed)

    @staticmethod
    def _build(k: int) -> QuantumCircuit:
        """Crea un circuito de k qubits: azar cuantico (Hadamard) a todos
        y un medidor al final.
        """
        # k qubits y k bits clasicos para almacenar los resultados.
        qc = QuantumCircuit(k, k)
        # |0...0> -> |+...+>: puerta Hadamard a cada qubit, superposicion
        # uniforme.
        qc.h(range(k))
        # Mide cada qubit en la base Z y almacena el resultado en el bit
        # clasico correspondiente.
        qc.measure(range(k), range(k))
        return qc

    def random_bits(self, n: int) -> Bits:
        """Devuelve n bits. Lanza ceil(n/k) shots de un circuito de k
        qubits. Ver docs/theory/qkd.md.
        """
        if n == 0:
            # Para no encender el simulador de Qiskit sin necesidad.
            return np.empty(0, dtype=np.uint8)

        # CAMINO RAPIDO: NumPy para las graficas de Carlos
        if self._backend_type == "numpy":
            return self._rng.integers(0, 2, size=n, dtype=np.uint8)

        # CAMINO CUANTICO: Qiskit para tests de fisica y demostraciones
        # Techo de la division (ceil) sin necesidad de importar math.
        shots = -(-n // self._k)
        result = self._backend.run(
            self._circuit,
            shots=shots,
            memory=True,  # Necesario para la secuencia exacta de disparos
        ).result()
        # get_memory() -> ['0110...', '1001...'] con k caracteres por shot
        # Une todos los resultados de los disparos en una sola cadena.
        raw = "".join(result.get_memory())
        # Convierte la cadena en un array de 0/1 restando el ASCII de "0".
        # astype fuerza uint8: la resta con un int de Python promociona
        # el resultado a un entero con signo (contrato roto en types.py).
        bits = (np.frombuffer(raw.encode(), dtype=np.uint8) - ord("0")).astype(np.uint8)
        # Los primeros n bits (los pedidos; sobran los del "ceil"), copiados.
        return bits[:n].copy()

    def random_bases(self, n: int) -> Bases:
        """Bases: 0 = Z (rectilinea), 1 = X (diagonal). Misma distribucion,
        significado distinto.
        """
        # MEJORA A5: el retorno se anotaba como Bits. Bits y Bases son el mismo
        # tipo fisico (alias de uint8), pero types.py los mantiene separados
        # justo para que las firmas se lean solas; esta es la unica funcion
        # cuyo motivo de existir es semantico, asi que devuelve Bases.
        # Reutiliza random_bits: misma distribucion, solo cambia la
        # interpretacion de los bits generados.
        return self.random_bits(n)
