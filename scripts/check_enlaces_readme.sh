#!/usr/bin/env bash
# Tarea 4.14: comprueba que los enlaces relativos del README.md resuelven a
# ficheros que existen de verdad. Solo enlaces relativos (rutas de fichero
# dentro del repo): los http(s) externos no se comprueban aqui a proposito,
# para no depender de la disponibilidad de sitios de terceros ni de rate
# limits -eso haria la CI flakeante por razones ajenas al repositorio.
set -euo pipefail

grep -oE '\]\([^)]+\)' README.md | sed 's/^](//;s/)$//' > /tmp/enlaces_readme.txt

FALLO=0
while read -r ruta; do
  ruta_fichero="${ruta%%#*}"
  case "$ruta_fichero" in
    http://*|https://*|"") continue ;;
  esac
  if [ ! -e "$ruta_fichero" ]; then
    echo "ENLACE ROTO en README.md: $ruta -> $ruta_fichero no existe"
    FALLO=1
  fi
done < /tmp/enlaces_readme.txt

if [ "$FALLO" -eq 1 ]; then
  exit 1
fi

echo "Enlaces del README: OK"
