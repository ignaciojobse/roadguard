#!/usr/bin/env bash
# Demo en vivo de RoadGuard (19-nov). Desde la raiz del repo:
#
#   bash scripts/demo_en_vivo.sh              # chequeo + MVI_39271 completa
#   bash scripts/demo_en_vivo.sh chequeo      # solo el chequeo previo
#   bash scripts/demo_en_vivo.sh MVI_40742    # otra secuencia (sin calibrar)
#
# No necesita red: usa los pesos de datos/modelos/ y YOLO_OFFLINE=1. Usa
# PYTHONPATH=src en vez del paquete instalado, porque en esta maquina el
# Escritorio se sincroniza con iCloud y los .pth ocultos del venv dejan de
# cargarse. Ctrl+C corta la corrida y deja igual las salidas parciales.
set -euo pipefail

cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
PESOS="datos/modelos/yolov8n.pt"
SECUENCIA="${1:-MVI_39271}"
export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"
export YOLO_OFFLINE=1

falta=0
ok()    { printf '  \033[32mOK\033[0m   %s\n' "$1"; }
error() { printf '  \033[31mFALTA\033[0m %s\n' "$1"; falta=1; }

echo "Chequeo previo"
[ -x "$PY" ] && ok "Python: $($PY --version 2>&1)" || error "Python en $PY (crear el venv e instalar requirements.txt)"
$PY -c "import roadguard, ultralytics, cv2" 2>/dev/null && ok "roadguard, ultralytics y OpenCV importan" \
  || error "dependencias: $PY -m pip install -r requirements.txt"
[ -f "$PESOS" ] && ok "pesos $PESOS" || error "pesos: curl -L -o $PESOS https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt"
for s in MVI_39271 MVI_40714 MVI_40742; do
  [ -f "datos/videos/$s.mp4" ] && ok "video $s" \
    || error "video $s: python scripts/bajar_ua_detrac.py $s && python scripts/jpg_a_mp4.py $s"
  [ -f "configs/$s.yaml" ] || error "configs/$s.yaml"
done
DISPOSITIVO=$($PY -c "import torch; print('cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu')" 2>/dev/null || echo cpu)
ok "dispositivo de inferencia: $DISPOSITIVO"
if [ "$falta" -ne 0 ]; then
  echo "Hay requisitos pendientes; la demo no se corre." >&2
  exit 1
fi
[ "$SECUENCIA" = "chequeo" ] && exit 0

echo
echo "Pruebas"
$PY -m pytest -q
echo
SALIDA="salidas/demo/$SECUENCIA"
echo "python -m roadguard procesar --video datos/videos/$SECUENCIA.mp4 --config configs/$SECUENCIA.yaml --salida $SALIDA"
set +e
$PY -m roadguard procesar --video "datos/videos/$SECUENCIA.mp4" --config "configs/$SECUENCIA.yaml" \
  --salida "$SALIDA" --pesos "$PESOS" --dispositivo "$DISPOSITIVO"
codigo=$?
set -e
[ "$codigo" -ne 0 ] && [ "$codigo" -ne 130 ] && exit "$codigo"
echo
echo "Eventos (primeras filas de $SALIDA/eventos.csv):"
# Los campos vacios se rellenan con "-" porque column -t los colapsa.
head -10 "$SALIDA/eventos.csv" | cut -d, -f1-6 | sed -e 's/,,/,-,/g' -e 's/,,/,-,/g' -e 's/,$/,-/' | column -t -s,
if [ -z "${NO_ABRIR:-}" ] && command -v open >/dev/null; then open "$SALIDA/anotado.mp4"; fi
