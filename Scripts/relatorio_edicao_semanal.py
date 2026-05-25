#!/usr/bin/env python3
"""
EDIÇÃO — Relatório Semanal
Setor: Edição de Vídeo (Head: Muryllo)
Modelo: Consultivo (dados AUTO + campos MANUAIS para validação)

Cron: Domingo 23:00

Uso:
  python3 relatorio_edicao_semanal.py          # Gera e posta no Chat View
  python3 relatorio_edicao_semanal.py --preview # Apenas preview, sem postar

GPDR — Iago Almeida | Assistido por Claude — Anthropic
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/Scripts"))

from impera_cache import cached_cu_tasks
from impera_utils import classify_task, normalize_person_name, get_cf_value
from cruzamento_clickup_redtrack import COPY_LIST

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
CLICKUP_CHAT_VIEW = "8cm1w4b-9993"


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def post_clickup(message):
    if not message or not CLICKUP_CHAT_VIEW or not API_TOKEN:
        return False
    try:
        cmd = [
            "curl", "-s", "-X", "POST",
            f"https://api.clickup.com/api/v2/view/{CLICKUP_CHAT_VIEW}/comment",
            "-H", f"Authorization: {API_TOKEN}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({"comment_text": message})
        ]
        result = subprocess.run(cmd, timeout=10, capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False


def get_monday_to_sunday():
    """Retorna período segunda-domingo."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    days_since_monday = today.weekday()
    monday = today - timedelta(days=days_since_monday)
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")


def parse_timestamp(ts):
    """Parse timestamp em múltiplos formatos."""
    if ts is None:
        return None
    try:
        if isinstance(ts, (int, float)) or (isinstance(ts, str) and ts.isdigit()):
            ts_num = int(ts)
            if ts_num > 1000000000:
                return datetime.fromtimestamp(ts_num / 1000)
            else:
                return datetime.fromtimestamp(ts_num)
        else:
            return datetime.fromisoformat(str(ts)[:10])
    except:
        return None


def build_edicao_data(date_from, date_to):
    """Agrega dados Edição por editor."""
    tasks = cached_cu_tasks(COPY_LIST, include_closed=True)

    by_editor = defaultdict(lambda: {
        "total": 0, "novos": 0, "otimizacoes": 0, "leads": 0, "mlds": 0, "vsls": 0,
        "no_prazo": 0, "atrasadas": 0, "sem_alteracao": 0
    })

    date_from_obj = datetime.fromisoformat(date_from)
    date_to_obj = datetime.fromisoformat(date_to)

    for task in tasks:
        try:
            created = task.get("date_created")
            if created:
                task_date = parse_timestamp(created)
                if not task_date or not (date_from_obj <= task_date <= date_to_obj):
                    continue

            status = task.get("status", {}).get("status", "").lower()
            if "enviado" not in status or "trafego" not in status:
                continue

            editor = normalize_person_name(get_cf_value(task, "editor") or "Desconhecido")
            name = task.get("name", "")
            cat, qtd, is_lead, is_mld, is_vsl = classify_task(name)

            by_editor[editor]["total"] += qtd

            if "V1" in name and "[" in name:
                by_editor[editor]["novos"] += qtd
            else:
                by_editor[editor]["otimizacoes"] += qtd

            if is_lead:
                by_editor[editor]["leads"] += qtd
            if is_mld:
                by_editor[editor]["mlds"] += qtd
            if is_vsl:
                by_editor[editor]["vsls"] += qtd

            # Due date logic
            due_date = task.get("due_date")
            if due_date:
                try:
                    due = parse_timestamp(due_date)
                    if due and due <= date_to_obj:
                        by_editor[editor]["no_prazo"] += qtd
                    elif due:
                        by_editor[editor]["atrasadas"] += qtd
                except:
                    by_editor[editor]["no_prazo"] += qtd

            # Teve alteração?
            teve_alteracao = get_cf_value(task, "teve alteracao")
            if not teve_alteracao or teve_alteracao in [False, "0", "não", "n"]:
                by_editor[editor]["sem_alteracao"] += qtd

        except:
            pass

    return dict(by_editor)


def build_sla_edicao(date_from, date_to):
    """Calcula SLA individual por editor (em dias)."""
    tasks = cached_cu_tasks(COPY_LIST, include_closed=True)

    by_editor = defaultdict(lambda: {"total_days": 0, "count": 0})

    date_from_obj = datetime.fromisoformat(date_from)
    date_to_obj = datetime.fromisoformat(date_to)

    for task in tasks:
        try:
            editor = normalize_person_name(get_cf_value(task, "editor") or "Desconhecido")

            start_ts = task.get("date_created")
            end_ts = task.get("date_closed")

            start = parse_timestamp(start_ts)
            if not start or not (date_from_obj <= start <= date_to_obj):
                continue

            end = parse_timestamp(end_ts) if end_ts else datetime.now()

            delta = (end - start).days
            if delta >= 0:
                by_editor[editor]["total_days"] += delta
                by_editor[editor]["count"] += 1
        except:
            pass

    return {editor: data["total_days"] / max(data["count"], 1) for editor, data in by_editor.items()}


def build_report(date_from, date_to):
    """Gera relatório completo de Edição."""
    log(f"Gerando relatório Edição para {date_from} a {date_to}")

    edicao_data = build_edicao_data(date_from, date_to)
    sla = build_sla_edicao(date_from, date_to)

    report = []
    report.append("🎬 EDIÇÃO — RELATÓRIO SEMANAL\n")
    report.append(f"**Período**: {date_from} a {date_to}")
    report.append(f"**Responsável**: Muryllo")
    report.append(f"**Status**: Consultivo (validar dados com head)\n")

    # KPIs Críticos
    report.append("## 1️⃣ KPIs Críticos\n")
    report.append("| Métrica | Valor |")
    report.append("|---------|-------|")

    total_enviados = sum(d["total"] for d in edicao_data.values())
    total_no_prazo = sum(d["no_prazo"] for d in edicao_data.values())
    total_atrasadas = sum(d["atrasadas"] for d in edicao_data.values())
    total_sem_alteracao = sum(d["sem_alteracao"] for d in edicao_data.values())
    assertividade = (total_sem_alteracao / max(total_enviados, 1) * 100) if total_enviados > 0 else 0

    report.append(f"| **Criativos Enviados a Tráfego** | {total_enviados} |")
    report.append(f"| **No Prazo** | {total_no_prazo} |")
    report.append(f"| **Atrasadas** | {total_atrasadas} |")
    report.append(f"| **Assertividade** | {assertividade:.1f}% (sem alterações) |\n")

    # Produção por Editor
    report.append("## 2️⃣ Produção por Editor\n")
    report.append("| Editor | Total | Novos | Otim. | Leads | MLDs | VSLs | No Prazo | Atrasadas | Assertividade |")
    report.append("|--------|-------|-------|-------|-------|------|------|----------|-----------|----------------|")

    for editor in sorted(edicao_data.keys(), key=lambda x: edicao_data[x]["total"], reverse=True):
        data = edicao_data[editor]
        ed_assertividade = (data["sem_alteracao"] / max(data["total"], 1) * 100) if data["total"] > 0 else 0
        report.append(
            f"| {editor} | {data['total']} | {data['novos']} | {data['otimizacoes']} | {data['leads']} | {data['mlds']} | {data['vsls']} | {data['no_prazo']} | {data['atrasadas']} | {ed_assertividade:.1f}% |"
        )

    report.append("")

    # Produtividade Individual
    report.append("## 3️⃣ Produtividade Individual\n")
    report.append("| Métrica | Editor | Valor |")
    report.append("|---------|--------|-------|")

    if edicao_data:
        maior_volume = max(edicao_data.items(), key=lambda x: x[1]["total"])
        maior_assertividade = max(edicao_data.items(), key=lambda x: (x[1]["sem_alteracao"] / max(x[1]["total"], 1)))
        maior_atraso = max(edicao_data.items(), key=lambda x: x[1]["atrasadas"])

        report.append(f"| Maior Volume | {maior_volume[0]} | {maior_volume[1]['total']} criativos |")
        report.append(f"| Maior Assertividade | {maior_assertividade[0]} | {(maior_assertividade[1]['sem_alteracao'] / max(maior_assertividade[1]['total'], 1) * 100):.1f}% |")
        if maior_atraso[1]["atrasadas"] > 0:
            report.append(f"| Maior Atraso | {maior_atraso[0]} | {maior_atraso[1]['atrasadas']} atrasadas |")

    report.append("")

    # SLA Individual
    report.append("## 4️⃣ SLA Individual (Dias)\n")
    report.append("| Editor | Dias Médios |")
    report.append("|--------|-------------|")

    for editor in sorted(sla.keys(), key=lambda x: sla[x]):
        report.append(f"| {editor} | {sla[editor]:.1f} dias |")

    report.append("")

    # Campos Manuais
    report.append("## 5️⃣ Leitura Estratégica (Preencher com Muryllo)\n")
    report.append("**O que funcionou bem?**\n")
    report.append("_[Muryllo, quais foram os pontos fortes da semana?]_\n")
    report.append("**O que limitou resultado?**\n")
    report.append("_[Muryllo, quais foram os gargalos/desafios?]_\n")
    report.append("**Atenção imediata?**\n")
    report.append("_[Muryllo, algo que precise de ação urgente?]_\n")

    # Glossário
    report.append("---\n")
    report.append("## 📋 GLOSSÁRIO — Definições de Métricas\n")
    report.append("**Criativos Enviados a Tráfego**: Status 'enviado trafego' ou 'enviado vturb'")
    report.append("\n**Novos**: Criativos com [V1] na nomenclatura")
    report.append("\n**Otimizações**: Criativos sem [V1] (variações)")
    report.append("\n**No Prazo**: Tarefas com due_date ≤ data final do período")
    report.append("\n**Atrasadas**: Tarefas com due_date > data final do período")
    report.append("\n**Assertividade**: % de criativos sem o campo 'Teve alteração?' marcado (sem revisões)")
    report.append("\n**SLA**: Tempo médio em dias desde criação até conclusão da tarefa")

    return "\n".join(report)


def main():
    date_from, date_to = get_monday_to_sunday()
    report = build_report(date_from, date_to)

    if "--preview" in sys.argv:
        print(report)
        log("Preview mode — relatório não foi postado")
    else:
        if post_clickup(report):
            log("✅ Relatório Edição postado com sucesso")
        else:
            log("❌ Erro ao postar relatório Edição")
            print(report)


if __name__ == "__main__":
    main()
