#!/usr/bin/env python3
"""
Hook de sessão Claude → Obsidian
Cria/atualiza Daily Note com o que foi feito na sessão.

Uso (chamado pelo Claude ao final de cada sessão):
  python3 obsidian_session.py "resumo do que foi feito"
  python3 obsidian_session.py --update "item adicional"
"""

import os
import sys
from datetime import datetime
from pathlib import Path

VAULT = Path.home() / "Obsidian" / "IMPERA"
DAILY_DIR = VAULT / "Daily Notes"
SESSION_DIR = VAULT / "Sessões"


def get_daily_path():
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now()
    return DAILY_DIR / f"{today.strftime('%Y-%m-%d')}.md"


def get_session_path():
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now()
    return SESSION_DIR / f"Sessão {today.strftime('%Y-%m-%d')}.md"


def create_or_update_daily(summary):
    """Adiciona entrada de sessão na Daily Note."""
    path = get_daily_path()
    now = datetime.now()
    timestamp = now.strftime("%H:%M")

    session_entry = f"\n### Sessão {timestamp}\n{summary}\n"

    if path.exists():
        content = path.read_text()
        # Adiciona antes de "## Notas do dia" se existir
        if "## Notas do dia" in content:
            content = content.replace("## Notas do dia", f"{session_entry}\n## Notas do dia")
        else:
            content += session_entry
        path.write_text(content)
    else:
        note = f"""---
tipo: daily
data: {now.strftime('%Y-%m-%d')}
dia_semana: {now.strftime('%A')}
tags: [daily]
---

# {now.strftime('%d/%m/%Y')} — {now.strftime('%A')}

## Sessões com Claude

{session_entry}

## Notas do dia
_Adicione aqui observações, decisões ou contexto._
"""
        path.write_text(note)

    return path


def create_session_note(summary):
    """Cria nota de sessão detalhada."""
    path = get_session_path()
    now = datetime.now()

    # Se já existe, append
    if path.exists():
        content = path.read_text()
        content += f"\n---\n\n### Continuação ({now.strftime('%H:%M')})\n\n{summary}\n"
        path.write_text(content)
    else:
        note = f"""---
tipo: sessão
data: {now.strftime('%Y-%m-%d')}
tags: [sessão]
---

# Sessão {now.strftime('%d/%m/%Y')}

{summary}
"""
        path.write_text(note)

    return path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 obsidian_session.py 'resumo da sessão'")
        sys.exit(1)

    summary = sys.argv[1]

    daily = create_or_update_daily(summary)
    session = create_session_note(summary)

    print(f"Daily Note: {daily}")
    print(f"Sessão: {session}")
