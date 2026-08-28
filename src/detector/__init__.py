"""API publica del paquete detector (Fase 4: ruido de detectores, extraccion
de entropia). Solo lo que se exporta aqui es "publico"; el resto son
detalles de implementacion.
"""

from __future__ import annotations

from .carga import cargar_muestra, senal_de_prueba
from .entropia import (
    digitalizar,
    estimar_entropia,
    h_min_colision,
    h_min_markov,
    h_min_mas_comun,
)
from .espectro import densidad_espectral
from .extraccion import extraer
from .filtrado import filtrar
from .identificacion import (
    ajustar_alfa,
    detectar_picos,
    factor_fano,
    identificar_tipo_dominante,
)
from .types import (
    AnalisisEspectral,
    EstimacionEntropia,
    ResultadoExtraccion,
    TipoRuido,
)

__all__ = [
    "AnalisisEspectral",
    "EstimacionEntropia",
    "ResultadoExtraccion",
    "TipoRuido",
    "cargar_muestra",
    "senal_de_prueba",
    "densidad_espectral",
    "ajustar_alfa",
    "detectar_picos",
    "factor_fano",
    "identificar_tipo_dominante",
    "filtrar",
    "digitalizar",
    "h_min_mas_comun",
    "h_min_colision",
    "h_min_markov",
    "estimar_entropia",
    "extraer",
]
