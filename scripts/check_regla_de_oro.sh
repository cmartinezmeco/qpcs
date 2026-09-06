#!/usr/bin/env bash
# Tarea 4.14: la regla de oro (D1, tarea 4.11) como paso de CI, no manual.
#
# Compara los test_* citados en los cuatro documentos de teoria (mas
# limitaciones.md y decisiones.md, que tambien citan tests) contra los
# def test_ reales de tests/. Se ejecuta directo en el runner: son ficheros
# de texto ya presentes tras el checkout, no hace falta el contenedor.
#
# Los falsos positivos conocidos son enlaces markdown a rutas de fichero
# (tests/pqc/test_hybrid.py cita "test_hybrid" al partir por "_" y ".") y el
# propio fragmento de texto de detector.md que describe esta regla citando
# "def test_" en prosa. Se filtran explicitamente para que el paso no se
# ponga rojo con ellos ni deje de detectar una cita rota de verdad.
set -euo pipefail

FALSOS_POSITIVOS="^test_$|^test_cipher$|^test_extraccion$|^test_hybrid$|^test_scaffold$"

grep -oh "test_[a-z0-9_]*" docs/theory/*.md docs/limitaciones.md docs/decisiones.md 2>/dev/null \
  | sort -u > /tmp/citados.txt
grep -rhoE "def (test_[a-z0-9_]*)" tests/ | sed 's/def //' | sort -u > /tmp/reales.txt

ROTAS=$(comm -23 /tmp/citados.txt /tmp/reales.txt | grep -vE "$FALSOS_POSITIVOS" || true)

if [ -n "$ROTAS" ]; then
  echo "Citas de test rotas en docs/theory/*.md (o limitaciones.md/decisiones.md):"
  echo "$ROTAS"
  exit 1
fi

echo "Regla de oro: OK"
