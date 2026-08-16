"""API publica del paquete chaos (Fase 3: cifrado de imagenes con caos
determinista). Solo lo que se exporta aqui es "publico"; el resto son
detalles de implementacion.
"""

from __future__ import annotations

from .baseline import cifrar_aes_gcm, cifrar_flujo_trivial
from .cipher import cifrar_imagen, descifrar_imagen
from .diffusion import deshacer_adelante, difundir_adelante
from .keystream import histograma_chi2, keystream, keystream_logistico, keystream_lorenz
from .lyapunov import detectar_ciclo, espectro_lyapunov_lorenz, lyapunov_logistico
from .maps import orbita_logistica, orbita_lorenz
from .metrics import (
    calcular_npcr,
    calcular_uaci,
    chi2_histograma,
    correlacion_adyacente,
    entropia_esperada,
    entropia_shannon,
    medir_imagen,
    npcr_esperado,
    uaci_esperado,
)
from .permutation import invertir_permutacion, permutacion_desde_orbita
from .testimg import imagen_de_prueba
from .types import (
    ClaveCaotica,
    DiagnosticoCaos,
    ImagenCifrada,
    MetricasImagen,
    Sistema,
)

__all__ = [
    "ClaveCaotica",
    "DiagnosticoCaos",
    "ImagenCifrada",
    "MetricasImagen",
    "Sistema",
    "orbita_logistica",
    "orbita_lorenz",
    "lyapunov_logistico",
    "espectro_lyapunov_lorenz",
    "detectar_ciclo",
    "keystream",
    "keystream_logistico",
    "keystream_lorenz",
    "histograma_chi2",
    "permutacion_desde_orbita",
    "invertir_permutacion",
    "difundir_adelante",
    "deshacer_adelante",
    "cifrar_imagen",
    "descifrar_imagen",
    "entropia_esperada",
    "entropia_shannon",
    "correlacion_adyacente",
    "npcr_esperado",
    "uaci_esperado",
    "calcular_npcr",
    "calcular_uaci",
    "chi2_histograma",
    "medir_imagen",
    "cifrar_aes_gcm",
    "cifrar_flujo_trivial",
    "imagen_de_prueba",
]
