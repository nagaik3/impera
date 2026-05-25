#!/bin/bash
# Alarme com notificação macOS + som
# Uso: alarme.sh "Título" "Mensagem"

TITULO="${1:-Alarme}"
MENSAGEM="${2:-Hora de agir!}"

# Notificação nativa macOS
osascript -e "display notification \"$MENSAGEM\" with title \"$TITULO\" sound name \"Glass\""

# Falar em voz alta (opcional mas útil com bebê - volume baixo)
say -v Luciana "$TITULO. $MENSAGEM" -r 180 &
