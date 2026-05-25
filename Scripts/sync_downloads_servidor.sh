#!/bin/bash
# Sync Downloads → Servidor AL
# Copia arquivos novos do ~/Downloads para /Volumes/Servidor AL/DOWNLOADS MAC/
# Mantém os arquivos no Downloads do Mac

ORIGEM="$HOME/Downloads"
DESTINO="/Volumes/Servidor AL/DOWNLOADS MAC"
LOG="$HOME/Scripts/data/sync_downloads.log"

# Verifica se o Servidor AL está montado
if [ ! -d "$DESTINO" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') | Servidor AL não está montado. Pulando." >> "$LOG"
    exit 0
fi

# Copia cada arquivo/pasta que ainda não existe no destino
cd "$ORIGEM" || exit 0
for item in *; do
    # Ignora arquivos temporários de download
    case "$item" in
        *.crdownload|*.part|*.download|*.tmp|.DS_Store) continue ;;
    esac

    # Se não existe no destino, copia
    if [ ! -e "$DESTINO/$item" ]; then
        cp -R "$ORIGEM/$item" "$DESTINO/$item" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "$(date '+%Y-%m-%d %H:%M:%S') | Copiado: $item" >> "$LOG"
        else
            echo "$(date '+%Y-%m-%d %H:%M:%S') | Erro ao copiar: $item" >> "$LOG"
        fi
    fi
done

echo "$(date '+%Y-%m-%d %H:%M:%S') | Sync concluído." >> "$LOG"
