#!/usr/bin/env bash
# Канон: два слоя. Запуск из каталога audit/.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
LEX="${LEX_NATURAE:-lex_naturae.py}"        # путь к lex_naturae.py (репо lex-naturae)
HLFSDIR="${HUMAN_LFS_DIR:-.}"               # каталог с validate_graph.py и BUILD_GRAPH.json
python3 -I "$LEX" "$HERE/claims.json"
python3 -I "$HLFSDIR/validate_graph.py" "$HERE/BUILD_GRAPH.json"
