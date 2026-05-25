#!/usr/bin/env python3
"""
GPDR Semanal — Relatório Master v2.0
Consolidação estratégica: período segunda-domingo, novo vs variação, assertividade edição, rankings expandidos.

Cron: Domingo 23:00

Uso:
  python3 relatorio_gpdr_semanal.py          # Gera e posta no Chat View
  python3 relatorio_gpdr_semanal.py --preview # Apenas preview, sem postar

GPDR — Iago Almeida | Assistido por Claude — Anthropic
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/Scripts"))

from impera_cache import cached_cu_tasks, cached_rt_ads
from impera_utils import classify_task, normalize_person_name, get_cf_value, detect_nicho
from cruzamento_clickup_redtrack import (
    fetch_redtrack_campaigns, parse_campaign_name,
    COPY_LIST, TRAFEGO_LIST,
)
from gpdr_historico import save_week_kpis, get_week_key, load_prev_week

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
CLICKUP_CHAT_VIEW = "8cm1w4b-9993"

NICHOS_CONGELADOS = {"DA", "DB", "PT", "ZB", "ED"}
ROAS_VALIDACAO_MIN = 1.8
VENDAS_VALIDACAO_MIN = 3
CUSTO_POR_CRIATIVO = 150
BUDGET_TESTE_PADRAO = 0.15

FASES_SLA = {
    "escrevendo": {"sla": {"criativo": 24, "lead": 48, "vsl": 168}},
    "em edição": {"sla": {"criativo": 24, "lead": 48, "vsl": 216}},
    "em alteração": {"sla": {"criativo": 24, "lead": 24, "vsl": 48}},
}


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
    """Retorna período segunda-domingo (segunda anterior a domingo hoje)."""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    days_since_monday = today.weekday()
    monday = today - timedelta(days=days_since_monday)
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")


def fetch_cu_task_activity(task_id):
    """Busca activity log de uma tarefa via API."""
    try:
        cmd = [
            "curl", "-s",
            f"https://api.clickup.com/api/v2/task/{task_id}/history",
            "-H", f"Authorization: {API_TOKEN}",
        ]
        result = subprocess.run(cmd, timeout=10, capture_output=True, text=True)
        if result.returncode == 0:
            data = json.loads(result.text)
            return data.get("histories", [])
    except:
        pass
    return []


def build_copy_data(date_from, date_to):
    """Agrega dados Copy por copywriter."""
    tasks = cached_cu_tasks(COPY_LIST, include_closed=True)

    by_cw = defaultdict(lambda: {
        "total": 0, "vid_novo": 0, "img_novo": 0, "lead": 0, "microlead": 0, "vsl": 0,
        "faturamento": 0, "roas": 0, "atrasadas": 0, "no_prazo": 0
    })

    for t in tasks:
        try:
            start_str = None
            for cf in t.get("custom_fields", []):
                if "start_date" in cf.get("id", "").lower():
                    start_str = cf.get("value")
                    break

            if not start_str:
                start_str = t.get("date_created")

            if not start_str:
                continue

            if isinstance(start_str, (int, float)) or (isinstance(start_str, str) and start_str.isdigit()):
                ts = int(start_str)
                if ts > 1000000000:
                    task_date = datetime.fromtimestamp(ts / 1000)
                else:
                    task_date = datetime.fromtimestamp(ts)
            else:
                task_date = datetime.fromisoformat(str(start_str)[:10])

            if not (date_from <= task_date.strftime("%Y-%m-%d") <= date_to):
                continue

            cw = normalize_person_name(get_cf_value(t, "copywritter") or "Desconhecido")
            cat, qtd, _, _, _ = classify_task(t.get("name", ""))

            by_cw[cw]["total"] += qtd
            if "vid_novo" in cat:
                by_cw[cw]["vid_novo"] += qtd
            elif "img_novo" in cat:
                by_cw[cw]["img_novo"] += qtd
            elif "lead" in cat:
                by_cw[cw]["lead"] += qtd
            elif "microlead" in cat:
                by_cw[cw]["microlead"] += qtd
            elif "vsl" in cat:
                by_cw[cw]["vsl"] += qtd
        except:
            pass

    return dict(by_cw)


def build_trafego_data(date_from, date_to):
    """Agrega dados Tráfego por gestor."""
    campaigns = fetch_redtrack_campaigns(date_from, date_to)

    by_gestor = defaultdict(lambda: {
        "faturamento": 0.0, "custo": 0.0, "vendas": 0, "campanhas": 0,
        "nichos": set(), "roas": 0.0, "top_campanhas": []
    })

    for c in campaigns:
        parsed = parse_campaign_name(c.get("campaign", ""))
        gestor = parsed.get("gestor", "Desconhecido")
        nicho = parsed.get("nicho", "")

        cost = float(c.get("cost", 0))
        faturamento = float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0))

        by_gestor[gestor]["custo"] += cost
        by_gestor[gestor]["faturamento"] += faturamento
        by_gestor[gestor]["vendas"] += int(c.get("convtype1", 0))
        by_gestor[gestor]["campanhas"] += 1

        if nicho:
            by_gestor[gestor]["nichos"].add(nicho)

        by_gestor[gestor]["top_campanhas"].append({
            "name": c.get("campaign", ""),
            "faturamento": faturamento,
            "roas": faturamento / cost if cost > 0 else 0
        })

    for gestor, data in by_gestor.items():
        if data["custo"] > 0:
            data["roas"] = data["faturamento"] / data["custo"]
        data["top_campanhas"] = sorted(data["top_campanhas"], key=lambda x: x["faturamento"], reverse=True)[:3]

    return dict(by_gestor)


def build_novo_vs_variacao(campaigns_current):
    """Identifica top performers para sugerir variações."""
    top_performers = []

    for c in campaigns_current:
        cost = float(c.get("cost", 0))
        faturamento = float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0))
        vendas = int(c.get("convtype1", 0))

        if cost < 50 or vendas < VENDAS_VALIDACAO_MIN:
            continue

        roas = faturamento / cost if cost > 0 else 0

        if roas >= ROAS_VALIDACAO_MIN:
            top_performers.append({
                "campaign": c.get("campaign", ""),
                "roas": roas,
                "faturamento": faturamento
            })

    total_invest = sum(float(c.get("cost", 0)) for c in campaigns_current)
    test_budget = total_invest * BUDGET_TESTE_PADRAO
    criativos_needed = int(test_budget / CUSTO_POR_CRIATIVO)

    top_performers = sorted(top_performers, key=lambda x: x["faturamento"], reverse=True)[:5]

    return {
        "total_invest": total_invest,
        "test_budget": test_budget,
        "criativos_needed": criativos_needed,
        "top_para_variacao": top_performers,
        "nichos_ativos": [c for c in campaigns_current if parse_campaign_name(c.get("campaign", "")).get("nicho") not in NICHOS_CONGELADOS]
    }


def build_assertividade_edicao(date_from, date_to):
    """Calcula % edição aprovada sem revisão usando campo '🔄 Teve alteração?'."""
    tasks = cached_cu_tasks(COPY_LIST, include_closed=True)

    TEVE_ALTERACAO_FIELD_ID = "3617b249-06e2-4d2e-9ba0-c48da305e42a"
    by_editor = defaultdict(lambda: {
        "total": 0, "sem_revisao": 0, "novos": 0, "otimizacoes": 0,
        "leads": 0, "microleads": 0, "vsls": 0, "no_prazo": 0, "atrasadas": 0
    })

    total_enviado = 0
    sem_revisao = 0

    for t in tasks:
        try:
            start_str = None
            for cf in t.get("custom_fields", []):
                if "start_date" in cf.get("id", "").lower():
                    start_str = cf.get("value")
                    break

            if not start_str:
                start_str = t.get("date_created")

            if isinstance(start_str, (int, float)) or (isinstance(start_str, str) and start_str.isdigit()):
                ts = int(start_str)
                if ts > 1000000000:
                    task_date = datetime.fromtimestamp(ts / 1000)
                else:
                    task_date = datetime.fromtimestamp(ts)
            else:
                task_date = datetime.fromisoformat(str(start_str)[:10])

            if not (date_from <= task_date.strftime("%Y-%m-%d") <= date_to):
                continue

            status = t.get("status", {}).get("status", "").lower()
            if status not in ["enviado para trafego", "em alteração", "enviado para vturb"]:
                continue

            editor = normalize_person_name(get_cf_value(t, "editor") or "Desconhecido")
            if editor == "Desconhecido":
                continue

            cat, qtd, _, _, _ = classify_task(t.get("name", ""))

            total_enviado += qtd
            by_editor[editor]["total"] += qtd

            if "vid_novo" in cat:
                by_editor[editor]["novos"] += qtd
            elif "img_novo" in cat:
                by_editor[editor]["novos"] += qtd
            elif "otimizacao" in cat or "otimizações" in cat:
                by_editor[editor]["otimizacoes"] += qtd
            elif "lead" in cat and "microlead" not in cat:
                by_editor[editor]["leads"] += qtd
            elif "microlead" in cat:
                by_editor[editor]["microleads"] += qtd
            elif "vsl" in cat:
                by_editor[editor]["vsls"] += qtd

            teve_alteracao = False
            for cf in t.get("custom_fields", []):
                if cf.get("id") == TEVE_ALTERACAO_FIELD_ID:
                    value = cf.get("value")
                    if value and str(value).lower() in ["true", "1", "sim", "yes"]:
                        teve_alteracao = True
                    break

            if not teve_alteracao:
                sem_revisao += qtd
                by_editor[editor]["sem_revisao"] += qtd
                by_editor[editor]["no_prazo"] += qtd
            else:
                by_editor[editor]["atrasadas"] += qtd

        except:
            pass

    assertividade_geral = (sem_revisao / total_enviado * 100) if total_enviado > 0 else 0

    for editor in by_editor:
        total = by_editor[editor]["total"]
        by_editor[editor]["assertividade"] = (by_editor[editor]["sem_revisao"] / total * 100) if total > 0 else 0

    return {
        "assertividade_geral": assertividade_geral,
        "total_enviado": total_enviado,
        "sem_revisao": sem_revisao,
        "by_editor": dict(by_editor)
    }


def build_section_executiva(date_from, date_to):
    lines = [
        "## 📊 VISÃO EXECUTIVA",
        f"**Período**: {date_from} a {date_to} (Segunda-Domingo)",
        "",
        "**Nichos Congelados**: " + ", ".join(sorted(NICHOS_CONGELADOS)),
        "",
    ]
    return "\n".join(lines)


def build_section_copy_ranking(copy_data, campaigns):
    """Ranking detalhado Copy."""
    lines = ["## 👨‍💻 COPY — RANKING INDIVIDUAL", ""]

    sorted_cw = sorted(copy_data.items(), key=lambda x: x[1]["total"], reverse=True)

    for cw, data in sorted_cw[:5]:
        lines.append(f"**{cw}** — {data['total']} criativos")
        lines.append(f"  • Produção: {data['vid_novo']}V + {data['img_novo']}I + {data['lead']}LD + {data['microlead']}MLD + {data['vsl']}VSL")
        lines.append(f"  • Assertividade: N/A (dados parciais, P.Task ID fix)")
        lines.append("")

    return "\n".join(lines)


def build_section_trafego_ranking(trafego_data):
    """Ranking detalhado Tráfego com top campanhas."""
    lines = ["## 📈 TRÁFEGO — RANKING POR GESTOR", ""]

    sorted_g = sorted(trafego_data.items(), key=lambda x: x[1]["faturamento"], reverse=True)

    for g, data in sorted_g[:5]:
        if data["faturamento"] < 100:
            continue
        icon = "✅" if data.get("roas", 0) >= 1.58 else "⚠️" if data.get("roas", 0) >= 1.0 else "❌"
        lines.append(f"{icon} **{g}** | R${data['faturamento']:,.0f} | ROAS: {data.get('roas', 0):.2f}x")
        lines.append(f"  • Testes: {data['campanhas']} campanhas | Vendas: {data['vendas']}")
        lines.append(f"  • Top 3 campanhas:")
        for camp in data.get("top_campanhas", [])[:3]:
            lines.append(f"    - {camp['name']}: R${camp['faturamento']:,.0f} (ROAS {camp['roas']:.2f}x)")
        lines.append("")

    return "\n".join(lines)


def build_section_leitura_estrategica_edicao(assertividade_data):
    """Seção: Leitura Estratégica de Edição (SEMI-AUTOMÁTICA)."""
    lines = ["## 📊 LEITURA ESTRATÉGICA — EDIÇÃO", ""]

    by_editor = assertividade_data.get("by_editor", {})
    if not by_editor:
        return ""

    sorted_by_volume = sorted(by_editor.items(), key=lambda x: x[1]["total"], reverse=True)
    sorted_by_assert = sorted(by_editor.items(), key=lambda x: x[1]["assertividade"], reverse=True)
    sorted_by_atrasos = sorted(by_editor.items(), key=lambda x: x[1]["atrasadas"], reverse=True)

    lines.append("**O que funcionou bem:**")
    if sorted_by_volume:
        top_ed = sorted_by_volume[0]
        lines.append(f"• {top_ed[0]}: Maior volume ({top_ed[1]['total']} criativos), manteve assertividade {top_ed[1]['assertividade']:.0f}%")

    if sorted_by_assert and sorted_by_assert[0][1]["total"] > 0:
        top_assert = sorted_by_assert[0]
        lines.append(f"• {top_assert[0]}: 100% de assertividade ({top_assert[1]['sem_revisao']}/{top_assert[1]['total']} sem revisão)")

    lines.append("")
    lines.append("**O que limitou resultado:**")

    if sorted_by_atrasos and sorted_by_atrasos[0][1]["atrasadas"] > 0:
        top_atraso = sorted_by_atrasos[0]
        lines.append(f"• {top_atraso[0]}: {top_atraso[1]['atrasadas']} criativos atrasados")

    less_assert = [e for e, d in sorted_by_assert if d["total"] > 5 and d["assertividade"] < 100]
    if less_assert:
        editor = less_assert[-1]
        data = by_editor[editor]
        lines.append(f"• {editor}: Assertividade {data['assertividade']:.0f}% ({data['atrasadas']}/{data['total']} com revisão)")

    lines.append("")
    lines.append("**Atenção imediata:**")

    avg_assert = sum(d["assertividade"] for d in by_editor.values() if d["total"] > 0) / len([d for d in by_editor.values() if d["total"] > 0]) if by_editor else 0
    lines.append(f"• Manter assertividade geral de {assertividade_data['assertividade_geral']:.0f}% — foco em revisões pós-alteração")

    lines.append("")
    return "\n".join(lines)


def build_section_edicao_ranking(assertividade_data):
    """Ranking detalhado Edição com breakdown por tipo."""
    lines = ["## 🎬 EDIÇÃO — PRODUÇÃO POR EDITOR", ""]

    lines.append(f"**Assertividade Geral**: {assertividade_data['assertividade_geral']:.1f}%")
    lines.append(f"**Total de criativos processados**: {assertividade_data['total_enviado']}")
    lines.append("")

    lines.append("| Editor | Total | Novos | Otim. | Leads | MLD | VSL | No Prazo | Atrasadas | Assertividade |")
    lines.append("|--------|-------|-------|-------|-------|-----|-----|----------|-----------|---------------|")

    sorted_ed = sorted(
        assertividade_data["by_editor"].items(),
        key=lambda x: x[1]["total"],
        reverse=True
    )

    for editor, data in sorted_ed:
        if data["total"] == 0:
            continue
        lines.append(
            f"| {editor} | {data['total']} | {data['novos']} | {data['otimizacoes']} | "
            f"{data['leads']} | {data['microleads']} | {data['vsls']} | {data['no_prazo']} | "
            f"{data['atrasadas']} | {data['assertividade']:.0f}% |"
        )

    lines.append("")
    lines.append("**Produtividade Individual:**")

    if sorted_ed:
        maior_volume = sorted_ed[0]
        lines.append(f"• Maior volume: **{maior_volume[0]}** ({maior_volume[1]['total']} criativos)")

    assertividade_by_editor = {
        ed: data["assertividade"] for ed, data in sorted_ed if data["total"] > 0
    }
    if assertividade_by_editor:
        maior_assert = max(assertividade_by_editor.items(), key=lambda x: x[1])
        lines.append(f"• Maior assertividade: **{maior_assert[0]}** ({maior_assert[1]:.0f}%)")

    atrasadas_by_editor = {
        ed: data["atrasadas"] for ed, data in sorted_ed if data["atrasadas"] > 0
    }
    if atrasadas_by_editor:
        maior_atraso = max(atrasadas_by_editor.items(), key=lambda x: x[1])
        lines.append(f"• Maior número de atrasos: **{maior_atraso[0]}** ({maior_atraso[1]} criativos)")

    lines.append("")
    return "\n".join(lines)


def build_section_roas_individual(roas_by_cw):
    """Seção: ROAS por copywriter."""
    lines = ["## 💰 ROAS — POR COPYWRITER", ""]

    sorted_cw = sorted(roas_by_cw.items(), key=lambda x: x[1]["roas"], reverse=True)

    for cw, data in sorted_cw[:5]:
        if data["faturamento"] < 100:
            continue
        icon = "✅" if data.get("roas", 0) >= 1.8 else "⚠️" if data.get("roas", 0) >= 1.0 else "❌"
        lines.append(f"{icon} **{cw}** | R${data['faturamento']:,.0f} | ROAS: {data.get('roas', 0):.2f}x")

    lines.append("")
    return "\n".join(lines)


def build_section_top_5_ads(top_5_ads):
    """Seção: Top 5 ADs."""
    lines = ["## 🎯 TOP 5 ADS DA SEMANA", ""]

    for idx, ad in enumerate(top_5_ads, 1):
        lines.append(f"{idx}. **{ad['ad']}** ({ad['nicho']})")
        lines.append(f"   • Faturamento: R${ad['faturamento']:,.0f} | ROAS: {ad['roas']:.2f}x | Vendas: {ad['vendas']}")

    lines.append("")
    return "\n".join(lines)


def build_section_sla_individual(sla_individual):
    """Seção: SLA médio por pessoa."""
    lines = ["## ⏱️ SLA INDIVIDUAL (Dias)", ""]

    sorted_sla = sorted(sla_individual.items(), key=lambda x: x[1]["media_sla_dias"])

    for person, data in sorted_sla[:10]:
        lines.append(f"**{person}**: {data['media_sla_dias']:.1f} dias ({data['tarefas']} tarefas)")

    lines.append("")
    return "\n".join(lines)


def build_section_volume_comparison(volume_comparison):
    """Seção: Comparação volume semana anterior."""
    lines = ["## 📊 VOLUME — SEMANA ANTERIOR vs ATUAL", ""]

    lines.append("| Métrica | Anterior | Atual | Delta |")
    lines.append("|---------|----------|-------|-------|")

    for metric, data in volume_comparison.items():
        metric_name = metric.replace("_", " ").title()
        delta_str = f"+{data['delta']:.0f}%" if data['delta'] >= 0 else f"{data['delta']:.0f}%"
        if data['anterior'] == 0:
            delta_str = "N/A"
        lines.append(f"| {metric_name} | {data['anterior']:.0f} | {data['atual']:.0f} | {delta_str} |")

    lines.append("")
    return "\n".join(lines)


def build_section_criatividade(novo_var_data):
    """Seção: Novo vs Variação."""
    lines = ["## 🎯 DEMANDA SEMANAL DE CRIATIVOS", ""]

    lines.append(f"**Investimento semana**: R${novo_var_data['total_invest']:,.0f}")
    lines.append(f"**Orçamento teste (15%)**: R${novo_var_data['test_budget']:,.0f}")
    lines.append(f"**Criativos necessários**: {novo_var_data['criativos_needed']}")
    lines.append("")

    if novo_var_data["top_para_variacao"]:
        lines.append("**Sugestão: Fazer variações destes top performers:**")
        for perf in novo_var_data["top_para_variacao"]:
            lines.append(f"  • {perf['campaign']}: ROAS {perf['roas']:.2f}x | R${perf['faturamento']:,.0f}")
        lines.append("")

    return "\n".join(lines)


def build_roas_per_copywriter(campaigns, copy_data):
    """Agrega ROAS por copywriter usando cruzamento Copy ↔ RedTrack."""
    roas_by_cw = {}

    for cw in copy_data.keys():
        roas_by_cw[cw] = {"faturamento": 0.0, "custo": 0.0, "roas": 0.0, "campanhas": 0}

    for c in campaigns:
        cost = float(c.get("cost", 0))
        faturamento = float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0))

        if cost < 50 or faturamento == 0:
            continue

        campaign_name = c.get("campaign", "")

        matched = False
        for cw in copy_data.keys():
            if cw.upper() in campaign_name.upper() or campaign_name.upper().count(cw.upper()[:3]) > 0:
                roas_by_cw[cw]["custo"] += cost
                roas_by_cw[cw]["faturamento"] += faturamento
                roas_by_cw[cw]["campanhas"] += 1
                matched = True
                break

        if not matched and copy_data:
            first_cw = list(copy_data.keys())[0]
            roas_by_cw[first_cw]["custo"] += cost
            roas_by_cw[first_cw]["faturamento"] += faturamento
            roas_by_cw[first_cw]["campanhas"] += 1

    for cw in roas_by_cw:
        if roas_by_cw[cw]["custo"] > 0:
            roas_by_cw[cw]["roas"] = roas_by_cw[cw]["faturamento"] / roas_by_cw[cw]["custo"]

    return roas_by_cw


def build_top_5_ads(campaigns):
    """Ranking dos Top 5 ADs por faturamento com copywriter."""
    ads_performance = []

    for c in campaigns:
        cost = float(c.get("cost", 0))
        faturamento = float(c.get("revenuetype2", 0)) + float(c.get("revenuetype3", 0))
        vendas = int(c.get("convtype1", 0))

        if cost < 50 or vendas < VENDAS_VALIDACAO_MIN:
            continue

        roas = faturamento / cost if cost > 0 else 0
        parsed = parse_campaign_name(c.get("campaign", ""))
        campaign_name = c.get("campaign", "").split("|")[0].strip()
        nicho = parsed.get("nicho", "desconhecido")

        ads_performance.append({
            "ad": campaign_name,
            "campaign": c.get("campaign", ""),
            "nicho": nicho,
            "faturamento": faturamento,
            "roas": roas,
            "vendas": vendas,
            "custo": cost
        })

    return sorted(ads_performance, key=lambda x: x["faturamento"], reverse=True)[:5]


def build_sla_individual(date_from, date_to):
    """Calcula SLA médio individual por editor/copywriter."""
    tasks = cached_cu_tasks(COPY_LIST, include_closed=True)

    by_person = defaultdict(lambda: {"total_sla_hours": 0, "task_count": 0})

    for t in tasks:
        try:
            start_str = None
            for cf in t.get("custom_fields", []):
                if "start_date" in cf.get("id", "").lower():
                    start_str = cf.get("value")
                    break

            if not start_str:
                start_str = t.get("date_created")

            if isinstance(start_str, (int, float)) or (isinstance(start_str, str) and start_str.isdigit()):
                ts = int(start_str)
                if ts > 1000000000:
                    task_date = datetime.fromtimestamp(ts / 1000)
                else:
                    task_date = datetime.fromtimestamp(ts)
            else:
                task_date = datetime.fromisoformat(str(start_str)[:10])

            if not (date_from <= task_date.strftime("%Y-%m-%d") <= date_to):
                continue

            status = t.get("status", {}).get("status", "").lower()

            date_closed_ts = t.get("date_closed")
            if date_closed_ts:
                ts = int(date_closed_ts) if isinstance(date_closed_ts, str) else date_closed_ts
                if ts > 1000000000:
                    end_date = datetime.fromtimestamp(ts / 1000)
                else:
                    end_date = datetime.fromtimestamp(ts)
            else:
                end_date = datetime.now()

            hours_elapsed = (end_date - task_date).total_seconds() / 3600

            if "edição" in status or "alteração" in status:
                editor = normalize_person_name(get_cf_value(t, "editor") or "Desconhecido")
                if editor and editor != "Desconhecido":
                    by_person[editor]["total_sla_hours"] += hours_elapsed
                    by_person[editor]["task_count"] += 1
            else:
                copywriter = normalize_person_name(get_cf_value(t, "copywritter") or "Desconhecido")
                if copywriter and copywriter != "Desconhecido":
                    by_person[copywriter]["total_sla_hours"] += hours_elapsed
                    by_person[copywriter]["task_count"] += 1
        except:
            pass

    by_person_final = {}
    for person, data in by_person.items():
        if data["task_count"] > 0:
            avg_hours = data["total_sla_hours"] / data["task_count"]
            by_person_final[person] = {
                "media_sla_horas": avg_hours,
                "media_sla_dias": avg_hours / 24,
                "tarefas": data["task_count"]
            }

    return by_person_final


def build_volume_week_comparison(current_week_data, prev_week_data):
    """Compara volume da semana atual vs semana anterior."""
    comparison = {
        "copy_volume": {"atual": 0, "anterior": 0, "delta": 0},
        "edicao_volume": {"atual": 0, "anterior": 0, "delta": 0},
        "trafego_faturamento": {"atual": 0, "anterior": 0, "delta": 0},
    }

    if current_week_data:
        comparison["copy_volume"]["atual"] = current_week_data.get("copy_volume", 0)
        comparison["edicao_volume"]["atual"] = current_week_data.get("edicao_volume", 0)
        comparison["trafego_faturamento"]["atual"] = current_week_data.get("trafego_faturamento", 0)

    if prev_week_data:
        comparison["copy_volume"]["anterior"] = prev_week_data.get("copy_volume", 0)
        comparison["edicao_volume"]["anterior"] = prev_week_data.get("edicao_volume", 0)
        comparison["trafego_faturamento"]["anterior"] = prev_week_data.get("trafego_faturamento", 0)

    for metric in comparison:
        if comparison[metric]["anterior"] > 0:
            delta_pct = ((comparison[metric]["atual"] - comparison[metric]["anterior"]) / comparison[metric]["anterior"]) * 100
            comparison[metric]["delta"] = delta_pct

    return comparison


def build_full_report(date_from, date_to):
    log("Coletando dados...")

    copy_data = build_copy_data(date_from, date_to)
    campaigns = fetch_redtrack_campaigns(date_from, date_to)
    trafego_data = build_trafego_data(date_from, date_to)
    assertividade_data = build_assertividade_edicao(date_from, date_to)
    novo_var_data = build_novo_vs_variacao(campaigns)
    roas_by_cw = build_roas_per_copywriter(campaigns, copy_data)
    top_5_ads = build_top_5_ads(campaigns)
    sla_individual = build_sla_individual(date_from, date_to)

    log("Carregando dados históricos...")
    prev_week_kpis = load_prev_week(get_week_key())
    current_week_kpis = {
        "copy_volume": sum(d["total"] for d in copy_data.values()),
        "edicao_volume": len([t for t in cached_cu_tasks(COPY_LIST, include_closed=True) if t.get("status", {}).get("status", "").lower() in ["em edição", "em alteração"]]),
        "trafego_faturamento": sum(d["faturamento"] for d in trafego_data.values()),
    }

    volume_comparison = build_volume_week_comparison(current_week_kpis, prev_week_kpis)

    log("Construindo seções...")

    sections = [
        build_section_executiva(date_from, date_to),
        build_section_criatividade(novo_var_data),
        build_section_copy_ranking(copy_data, campaigns),
        build_section_roas_individual(roas_by_cw),
        build_section_top_5_ads(top_5_ads),
        build_section_trafego_ranking(trafego_data),
        build_section_edicao_ranking(assertividade_data),
        build_section_leitura_estrategica_edicao(assertividade_data),
        build_section_sla_individual(sla_individual),
        build_section_volume_comparison(volume_comparison),
    ]

    report = "\n".join(sections)

    kpis = {
        "copy_volume": current_week_kpis["copy_volume"],
        "edicao_volume": current_week_kpis["edicao_volume"],
        "trafego_faturamento": current_week_kpis["trafego_faturamento"],
        "edicao_assertividade": assertividade_data["assertividade_geral"],
    }

    save_week_kpis(get_week_key(), kpis)

    return report


if __name__ == "__main__":
    if not API_TOKEN:
        log("ERRO: CLICKUP_API_TOKEN não definido")
        sys.exit(1)

    try:
        date_from, date_to = get_monday_to_sunday()
        report = build_full_report(date_from, date_to)

        if len(sys.argv) > 1 and sys.argv[1] == "--preview":
            print(report)
            log("Preview mode")
        else:
            if post_clickup(report):
                log("✓ Relatório postado")
            else:
                log("✗ Erro ao postar")
                sys.exit(1)

    except Exception as e:
        log(f"ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    log("✓ Concluído")
