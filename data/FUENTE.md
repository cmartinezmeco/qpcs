# Procedencia de data/muestra_pedestal.npz

## Qué es, y qué NO es

Este fichero contiene 495.562 muestras de la variable `nPFCands` (número de
candidatos reconstruidos por el algoritmo de Particle Flow) del dataset
público de CMS listado abajo. **No es una lectura directa de un ADC**, ni un
run de pedestal en sentido estricto: es un proxy razonado, no una medida
de bajo nivel.

## Por qué esta variable y no otra

Se intentó primero acceder a colecciones de más bajo nivel (EBDigiCollection
del calorímetro ECAL, DetId de siStripDigis, BeamSpotOnline, LumiScalers) en
el dataset RECO original (/ZeroBias/Commissioning10-May19ReReco-v1/RECO,
record 14002). Las cinco fallaron: uproot no puede deserializar las clases
C++ propietarias de CMSSW en las que están serializadas esas colecciones
(NotImplementedError: memberwise serialization, y errores de tamaño de
estructura), incluso cuando el fichero ROOT incluye el streamer completo de
la clase. Es una limitación conocida de uproot frente a formatos anteriores
a NanoAOD, no un problema de esta exploración concreta.

Se cambió a un *dataset* derivado en formato NanoAOD (PFNano), que por diseño
usa tipos de C++ estándar en vez de clases propias, y es explícitamente
legible con «bare ROOT or other ROOT-compatible software» según su propia
documentación. Dentro de él, `nPFCands` es la variable más cercana al
espíritu del módulo: en un evento ZeroBias —sin selección de física, sin
colisión garantizada— la mayoría de los candidatos reconstruidos en el
detector son fluctuaciones de baja actividad (ruido del calorímetro y del
trazador que sobrevive al umbral del algoritmo de reconstrucción), así que
su fluctuación evento a evento lleva la firma estadística del ruido
subyacente: un paso más lejos del ADC crudo que un *pedestal run* ideal.

## Dataset de origen

- Nombre: ZeroBias dataset in NanoAOD format enhanced with Particle Flow
  candidates from RunG of 2016
- Registro: https://opendata.cern.ch/record/31316
- Dataset padre: /ZeroBias/Run2016G-UL2016_MiniAODv2-v1/MINIAOD
- Licencia: Creative Commons Zero v1.0 Universal (CC0)
- Fichero concreto usado: nano_data2016_44.root (uno de los 67 ficheros del
  índice del *dataset*)
- URI: root://eospublic.cern.ch//eos/opendata/cms/derived-data/PFNano/
  29-Feb-24/ZeroBias/Run2016G-UL2016_MiniAODv2_PFNanoAODv1/240212_182529/
  0000/nano_data2016_44.root
- Tamaño del fichero original: ~124 MB (495.562 eventos)

## Cómo se generó este subconjunto

```python
import uproot
import numpy as np

url = ("root://eospublic.cern.ch//eos/opendata/cms/derived-data/PFNano/"
       "29-Feb-24/ZeroBias/Run2016G-UL2016_MiniAODv2_PFNanoAODv1/"
       "240212_182529/0000/nano_data2016_44.root")
with uproot.open(url) as f:
    senal = f["Events"]["nPFCands"].array(library="np").astype(np.int32)

np.savez_compressed("data/muestra_pedestal.npz", senal=senal, fs=np.float64(1000.0))
```

## Sobre la frecuencia de muestreo (`fs`)

`fs = 1000.0` Hz es una **convención**, no una medida física. Los eventos de
ZeroBias no llegan a intervalos perfectamente regulares del reloj del
acelerador, y no se ha investigado la tasa de eventos real del run 2016G.
Se fija un valor nominal solo para que el eje de frecuencias del análisis
de Welch tenga una escala consistente. Cualquier frecuencia que se
identifique en ese análisis debe interpretarse en unidades de «por cada mil
eventos», no en Hz reales.

## Se intentaron primero, y no funcionaron (por orden)

1. EBDigiCollection / EEDigiCollection (ECAL digis) — vacías en la muestra
   explorada.
2. DetIdedmEDCollection (siStripDigis) — NotImplementedError, vector de
   objetos DetId.
3. BeamSpotOnlines — error de tamaño de estructura (relleno de la clase).
4. LumiScalerss — NotImplementedError pese a tener el *streamer* completo
   (incluye el campo lumiNoise_, vector<float>, que habría sido ideal).

## Verificación de calidad hecha antes de fijar el fichero

- Se probó primero concatenar 5 ficheros elegidos al azar (semilla 42) del
  índice de 67: las medias por fichero iban de 871 a 1436, un 65 % de rango,
  con escalones claros entre ficheros. Se descartó por introducir
  estructura de baja frecuencia ARTIFICIAL, que habría contaminado el
  ajuste del exponente alfa.
- El fichero final es un único bloque CONTIGUO, sin ese riesgo.
- Solo 4 de 495.562 muestras (0.0008%) tienen nPFCands = 0; no requiere
  filtrado.
