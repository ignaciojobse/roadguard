#!/usr/bin/env bash
# Demo interactiva de RoadGuard en el navegador.
#
#   bash scripts/demo_web.sh            # prepara lo que falte y abre la demo
#   bash scripts/demo_web.sh --rehacer  # vuelve a correr el pipeline de las 3 secuencias
#
# Sirve la raiz del repo en http://127.0.0.1:8000 (sin red: los cuadros y los
# datos son locales) y abre demo_web/. Ctrl+C la cierra.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"
PUERTO="${PUERTO:-8000}"
SECUENCIAS=(MVI_39271 MVI_40243 MVI_40712 MVI_40714 MVI_40742)

for s in "${SECUENCIAS[@]}"; do
  if [ ! -f "datos/ua-detrac/$s/img00001.jpg" ]; then
    echo "Aviso: faltan los cuadros de $s (la camara se vera en negro): python scripts/bajar_ua_detrac.py $s" >&2
  fi
done

faltan=()
for s in "${SECUENCIAS[@]}"; do
  [ -f "demo_web/datos/$s.json" ] || faltan+=("$s")
done
if [ "${1:-}" = "--rehacer" ]; then
  PYTHONPATH=src "$PY" scripts/exportar_demo.py "${SECUENCIAS[@]}" --rehacer
elif [ ${#faltan[@]} -gt 0 ]; then
  PYTHONPATH=src "$PY" scripts/exportar_demo.py "${faltan[@]}"
fi

# Si el puerto esta ocupado (por ejemplo, una demo anterior que sigue
# abierta), se usa el siguiente libre.
PUERTO="$("$PY" - "$PUERTO" <<'PYEOF'
import socket, sys
p = int(sys.argv[1])
for intento in range(p, p + 20):
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", intento))
        except OSError:
            continue
        print(intento)
        break
PYEOF
)"
URL="http://127.0.0.1:$PUERTO/demo_web/?seq=MVI_39271&paso=1"
echo "Demo en $URL  (Ctrl+C para cerrar)"
echo "Teclas: espacio reproduce · 1-6 cambia de paso · flechas avanzan · f pantalla completa"
( sleep 1; command -v open >/dev/null && open "$URL" || true ) &
# Servidor silencioso: no imprime una linea por cada cuadro, solo los errores.
exec "$PY" - "$PUERTO" <<'PYEOF'
import http.server, sys
class Silencioso(http.server.SimpleHTTPRequestHandler):
    def log_message(self, formato, *args):
        if len(args) > 1 and str(args[1])[:1] in "45":
            sys.stderr.write("Error %s: %s\n" % (args[1], args[0]))
puerto = int(sys.argv[1])
with http.server.ThreadingHTTPServer(("127.0.0.1", puerto), Silencioso) as servidor:
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nDemo cerrada.")
PYEOF
