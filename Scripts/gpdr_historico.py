#!/usr/bin/env python3
"""
GPDR Histórico — Persistência de KPIs Semanais
Armazena dados estruturados para comparação semana-a-semana e mês-a-mês.

Uso:
  from gpdr_historico import save_week_kpis, load_prev_week, load_month_kpis

  # Salvar KPIs da semana
  save_week_kpis("2026-W21", {
    "copy": {...},
    "edicao": {...},
    "trafego": {...}
  })

  # Carregar semana anterior para delta
  prev = load_prev_week("2026-W21")

  # Carregar todas as semanas de um mês para agregação
  month = load_month_kpis("2026-05")
"""

import json
import os
from datetime import datetime, timedelta

HISTORICO_FILE = os.path.expanduser("~/Scripts/data/gpdr_kpis_historico.json")


def ensure_dir():
    """Cria diretório se não existir."""
    os.makedirs(os.path.dirname(HISTORICO_FILE), exist_ok=True)


def load_historico():
    """Carrega histórico completo."""
    ensure_dir()
    if os.path.exists(HISTORICO_FILE):
        try:
            with open(HISTORICO_FILE) as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_historico(data):
    """Salva histórico."""
    ensure_dir()
    with open(HISTORICO_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_week_key(date=None):
    """Gera chave ISO da semana: 2026-W21."""
    if not date:
        date = datetime.now()
    elif isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d")
    return date.strftime("%Y-W%V")


def get_month_key(date=None):
    """Gera chave do mês: 2026-05."""
    if not date:
        date = datetime.now()
    elif isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d")
    return date.strftime("%Y-%m")


def save_week_kpis(week_key, data):
    """Salva KPIs de uma semana."""
    hist = load_historico()
    if "semanas" not in hist:
        hist["semanas"] = {}

    hist["semanas"][week_key] = {
        "timestamp": datetime.now().isoformat(),
        "data": data
    }
    save_historico(hist)
    print(f"✓ KPIs salvos para {week_key}")


def load_prev_week(week_key):
    """Carrega dados da semana anterior."""
    hist = load_historico()
    semanas = hist.get("semanas", {})

    if week_key not in semanas:
        return None

    # Extrair número da semana
    year, week_num = week_key.split("-W")
    prev_week_num = int(week_num) - 1

    if prev_week_num < 1:
        # Semana anterior do ano anterior
        year = str(int(year) - 1)
        prev_week_num = 52

    prev_key = f"{year}-W{prev_week_num:02d}"

    if prev_key in semanas:
        return semanas[prev_key].get("data")

    return None


def load_week_kpis(week_key):
    """Carrega KPIs de uma semana específica."""
    hist = load_historico()
    semanas = hist.get("semanas", {})

    if week_key in semanas:
        return semanas[week_key].get("data")

    return None


def load_month_kpis(month_key):
    """Carrega e agrega todas as semanas de um mês."""
    hist = load_historico()
    semanas = hist.get("semanas", {})

    # Filtrar semanas que pertencem ao mês
    month_semanas = {}
    for week_key, week_data in semanas.items():
        if week_key.startswith(month_key):
            month_semanas[week_key] = week_data.get("data")

    return month_semanas


def delta_kpi(current, previous, key_path):
    """Calcula delta percentual entre dois valores."""
    try:
        # Navega pela estrutura nested (ex: "copy.volume" → current["copy"]["volume"])
        parts = key_path.split(".")
        curr_val = current
        prev_val = previous

        for part in parts:
            curr_val = curr_val[part] if isinstance(curr_val, dict) else None
            prev_val = prev_val[part] if isinstance(prev_val, dict) else None

        if curr_val is None or prev_val is None or prev_val == 0:
            return None

        return ((curr_val - prev_val) / prev_val) * 100
    except:
        return None


def format_kpi_table(current, previous=None):
    """Formata tabela de comparação de KPIs para relatório."""
    lines = []

    if not previous:
        lines.append("| KPI | Valor |")
        lines.append("|-----|-------|")
        if "copy" in current:
            lines.append(f"| Copy Volume | {current['copy'].get('volume_total', 0)} |")
            lines.append(f"| Copy Assertividade | {current['copy'].get('assertividade', 0):.1f}% |")
        return "\n".join(lines)

    # Com comparação semana anterior
    lines.append("| KPI | Atual | Anterior | Delta |")
    lines.append("|-----|-------|----------|-------|")

    if "copy" in current and "copy" in previous:
        curr_vol = current["copy"].get("volume_total", 0)
        prev_vol = previous["copy"].get("volume_total", 0)
        delta = ((curr_vol - prev_vol) / prev_vol * 100) if prev_vol > 0 else 0
        delta_str = f"+{delta:.0f}%" if delta >= 0 else f"{delta:.0f}%"
        lines.append(f"| Copy Volume | {curr_vol} | {prev_vol} | {delta_str} |")

    return "\n".join(lines)


def test():
    """Testa funcionalidade de persistência."""
    print("Testing gpdr_historico.py...")

    # Salvar dados de teste
    test_data = {
        "copy": {
            "volume_total": 45,
            "assertividade": 82.5,
            "faturamento": 15000
        },
        "edicao": {
            "volume_total": 45,
            "assertividade_sem_revisao": 88.0
        },
        "trafego": {
            "faturamento": 32000,
            "roas": 1.85,
            "volume_testes": 12
        }
    }

    week_key = get_week_key()
    save_week_kpis(week_key, test_data)

    # Carregar dados
    loaded = load_week_kpis(week_key)
    assert loaded == test_data, "Dados não combinam!"
    print(f"✓ Dados salvos e carregados com sucesso para {week_key}")

    # Testar comparação
    table = format_kpi_table(loaded)
    print("\nFormatação de tabela:")
    print(table)

    print("\n✓ Todos os testes passaram!")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test()
    else:
        print(__doc__)
