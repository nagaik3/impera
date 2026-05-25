#!/usr/bin/env python3
"""
Relatório Mensal Copywriters → ClickUp Chat View
Híbrida: produção + aprovação + faturamento por copywriter.

Cruza: ClickUp COPY + GESTÃO DE TRÁFEGO + RedTrack API
Posta consolidado em ClickUp Chat View (formato texto)

Uso:
  python3 relatorio_mensal_copywriters_clickup.py              # mês anterior
  python3 relatorio_mensal_copywriters_clickup.py --mes=5     # maio/2026
  python3 relatorio_mensal_copywriters_clickup.py --ano=2025 --mes=12

Crontab:
  0 9 1 * * cd ~/Scripts && python3 relatorio_mensal_copywriters_clickup.py >> ~/Scripts/logs/relatorio_mensal_cw.log 2>&1

GPDR — Iago Almeida | Assistido por Claude — Anthropic
"""

import json
import os
import sys
import urllib.request
import urllib.parse
from collections import defaultdict
from datetime import datetime, timedelta
import calendar
import re

sys.path.insert(0, os.path.expanduser("~/Scripts"))
try:
    from impera_utils import normalize_person_name, classify_task
    from cruzamento_clickup_redtrack import parse_campaign_name, fetch_redtrack_campaigns
except:
    def normalize_person_name(name):
        return name
    def classify_task(name):
        return "?", 1, "?", "BR", False

# === CONFIG ===
API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
REDTRACK_KEY = os.environ.get("REDTRACK_API_KEY", "")
LIST_COPY = "901324556390"
LIST_TRAFEGO = "901324476398"
CLICKUP_CHAT_VIEW = "8cm1w4b-9973"
LOG_DIR = os.path.expanduser("~/Scripts/logs")

COPYWRITERS = ["ANA", "CAROL", "CASSIO", "CRISPIM", "ELIAS", "YAN"]
SUCESSO_STATUSES = {"pré-escala", "validado", "escala", "vturb"}
ESCALA_STATUSES = {"escala"}


def log(msg):
    """Log com timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def api_get(endpoint):
    """ClickUp API GET."""
    url = f"https://api.clickup.com/api/v2{endpoint}"
    req = urllib.request.Request(url, headers={"Authorization": API_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log(f"❌ Erro API: {e}")
        return {"tasks": []}


def post_clickup(message):
    """Posta mensagem no ClickUp Chat View."""
    if not message or not CLICKUP_CHAT_VIEW:
        return False

    try:
        cmd = [
            "curl", "-s", "-X", "POST",
            f"https://api.clickup.com/api/v2/view/{CLICKUP_CHAT_VIEW}/comment",
            "-H", f"Authorization: {API_TOKEN}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({"comment_text": message})
        ]
        import subprocess
        result = subprocess.run(cmd, timeout=10, capture_output=True, text=True)
        if result.returncode == 0:
            log("✓ Relatório postado em ClickUp")
            return True
        else:
            log(f"✗ Erro ao postar: {result.stderr}")
            return False
    except Exception as e:
        log(f"✗ Erro: {e}")
        return False


def fetch_all_tasks(list_id):
    """Busca todas as tarefas com paginação."""
    tasks = []
    page = 0
    while True:
        params = f"subtasks=true&include_closed=true&page={page}"
        data = api_get(f"/list/{list_id}/task?{params}")
        batch = data.get("tasks", [])
        tasks.extend(batch)
        if data.get("last_page", True) or not batch:
            break
        page += 1
    return tasks


def get_cf_copywriter(task):
    """Extrai copywriter responsável da tarefa."""
    for cf in task.get("custom_fields", []):
        if "copywritter" in cf.get("name", "").lower():
            opts = cf.get("type_config", {}).get("options", [])
            val = cf.get("value")
            if val is not None:
                for o in opts:
                    if o.get("orderindex") == val:
                        return normalize_person_name(o["name"]) or "NÃO ATRIBUÍDO"
    return "NÃO ATRIBUÍDO"


def get_cf_parent_task_id(task):
    """Extrai parent_task_id da tarefa."""
    for cf in task.get("custom_fields", []):
        cf_name = cf.get("name", "").lower()
        if "parent" in cf_name or "pai" in cf_name or "relacionado" in cf_name:
            val = cf.get("value")
            if val and val.strip():
                return val.strip()
    return None


def normalize_creative_name(name):
    """Normaliza nome do criativo para matching."""
    name = re.sub(r"\[V\d+(?:-V?\d+)?\]", "", name)
    name = name.replace("[IMG]", "")
    name = " ".join(name.split())
    return name.strip()


def fetch_copy_tasks_by_month(year, month):
    """Busca tarefas COPY criadas no mês."""
    log(f"  📝 Buscando criativos criados em {month:02d}/{year}...")
    all_tasks = fetch_all_tasks(LIST_COPY)

    month_start = datetime(year, month, 1, 0, 0, 0).timestamp() * 1000
    last_day = calendar.monthrange(year, month)[1]
    month_end = datetime(year, month, last_day, 23, 59, 59).timestamp() * 1000

    filtered = []
    for task in all_tasks:
        sd = task.get("start_date")
        if sd and month_start <= int(sd) <= month_end:
            filtered.append(task)

    log(f"  ✅ {len(filtered)} criativos criados")
    return filtered


def fetch_trafego_tasks():
    """Busca todas as tarefas da GESTÃO DE TRÁFEGO."""
    log(f"  🚀 Buscando testes...")
    tasks = fetch_all_tasks(LIST_TRAFEGO)
    log(f"  ✅ {len(tasks)} tarefas de teste carregadas")
    return tasks


def match_copy_to_trafego(copy_tasks, trafego_tasks):
    """Match entre COPY e TRAFEGO."""
    matched = {}

    copy_by_id = {t["id"]: t for t in copy_tasks}
    trafego_by_name = {}
    for t in trafego_tasks:
        name_norm = normalize_creative_name(t["name"])
        if name_norm not in trafego_by_name:
            trafego_by_name[name_norm] = []
        trafego_by_name[name_norm].append(t)

    # Via parent_task_id
    for traf_task in trafego_tasks:
        parent_id = get_cf_parent_task_id(traf_task)
        if parent_id and parent_id in copy_by_id:
            copy_id = parent_id
            if copy_id not in matched:
                matched[copy_id] = []
            matched[copy_id].append(traf_task)

    # Via nome (fallback)
    for copy_task in copy_tasks:
        if copy_task["id"] in matched:
            continue
        name_norm = normalize_creative_name(copy_task["name"])
        if name_norm in trafego_by_name:
            matched[copy_task["id"]] = trafego_by_name[name_norm]

    return matched


def fetch_redtrack_data(date_from, date_to):
    """Fetch RedTrack campaigns."""
    try:
        campaigns = fetch_redtrack_campaigns(date_from, date_to)
        return campaigns or []
    except Exception as e:
        log(f"⚠️ RedTrack indisponível: {e}")
        return []


def enrich_with_redtrack(copy_tasks, campaigns):
    """Enriquece tarefas com dados de faturamento do RedTrack."""
    # Map: (base_id, version, nicho) → {cost, revenue, vendas}
    rt_map = defaultdict(lambda: {"cost": 0, "revenue": 0, "vendas": 0})

    for camp in campaigns:
        parsed = parse_campaign_name(camp.get("campaign", ""))
        nicho = parsed.get("nicho", "?")

        # Extrai base_id do ad_name da campanha
        ad_name = camp.get("ad", "")
        if not ad_name:
            continue

        # Match pattern: AD123, AD123V1, C71V12, etc
        m = re.search(r"((?:AD|CE|CY|CC|C)\d+)(?:V(\d+))?", ad_name.upper())
        if not m:
            continue

        base_id = m.group(1)
        version = m.group(2) if m.group(2) else "1"
        key = (base_id, version, nicho)

        cost = float(camp.get("cost", 0))
        rev = float(camp.get("revenuetype2", 0)) + float(camp.get("revenuetype3", 0))
        vendas = int(camp.get("convtype1", 0))

        rt_map[key]["cost"] += cost
        rt_map[key]["revenue"] += rev
        rt_map[key]["vendas"] += vendas

    # Enrich copy tasks
    for task in copy_tasks:
        task_name = task.get("name", "").upper()

        # Parse base, version, nicho
        m_base = re.search(r"((?:AD|CE|CY|CC|C)\d+)(?:V(\d+))?", task_name)
        m_nicho = re.search(r"\[([A-Z]{2,3})\]", task_name)

        if m_base and m_nicho:
            base = m_base.group(1)
            ver = m_base.group(2) or "1"
            nicho = m_nicho.group(1)
            key = (base, ver, nicho)

            data = rt_map.get(key, {})
            task["rt_cost"] = data.get("cost", 0)
            task["rt_revenue"] = data.get("revenue", 0)
            task["rt_vendas"] = data.get("vendas", 0)
            task["rt_roas"] = task["rt_revenue"] / task["rt_cost"] if task["rt_cost"] > 0 else 0
        else:
            task["rt_cost"] = 0
            task["rt_revenue"] = 0
            task["rt_vendas"] = 0
            task["rt_roas"] = 0


def build_report(copy_tasks, matched_trafego, year, month):
    """Constrói relatório consolidado."""
    report = defaultdict(lambda: {
        "criados": 0,
        "em_teste": 0,
        "aprovados": 0,
        "em_escala": 0,
        "cost": 0,
        "revenue": 0,
        "vendas": 0,
        "criativos": [],
    })

    for copy_task in copy_tasks:
        cw = get_cf_copywriter(copy_task)
        cat, qtd, nicho, mercado, is_rp = classify_task(copy_task["name"])

        report[cw]["criados"] += qtd
        report[cw]["cost"] += copy_task.get("rt_cost", 0)
        report[cw]["revenue"] += copy_task.get("rt_revenue", 0)
        report[cw]["vendas"] += copy_task.get("rt_vendas", 0)

        # Se tem trafego task
        if copy_task["id"] in matched_trafego:
            report[cw]["em_teste"] += 1
            trafego_tasks = matched_trafego[copy_task["id"]]
            for traf in trafego_tasks:
                status = traf.get("status", {}).get("status", "desconhecido").lower()
                if status in SUCESSO_STATUSES:
                    report[cw]["aprovados"] += 1
                if status in ESCALA_STATUSES:
                    report[cw]["em_escala"] += 1

        # Guarda criativo para top 10
        roas = copy_task.get("rt_roas", 0)
        report[cw]["criativos"].append({
            "name": copy_task.get("name", ""),
            "revenue": copy_task.get("rt_revenue", 0),
            "roas": roas,
            "vendas": copy_task.get("rt_vendas", 0),
        })

    # Top 10 por CW
    for cw in report:
        report[cw]["criativos"] = sorted(
            report[cw]["criativos"],
            key=lambda x: x["revenue"],
            reverse=True
        )[:10]

    return report


def format_currency(value):
    """Formata valor monetário."""
    if value == 0:
        return "R$0"
    if value >= 1000:
        return f"R${value:,.0f}".replace(",", ".")
    return f"R${value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def build_message(report, year, month, prev_report=None):
    """Constrói mensagem para ClickUp."""
    month_name = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }[month]

    lines = [
        f"📊 RELATÓRIO MENSAL COPYWRITERS — {month_name}/{year}",
        f"",
    ]

    # Resumo executivo
    total_criados = sum(r["criados"] for r in report.values())
    total_teste = sum(r["em_teste"] for r in report.values())
    total_aprov = sum(r["aprovados"] for r in report.values())
    total_escala = sum(r["em_escala"] for r in report.values())
    total_revenue = sum(r["revenue"] for r in report.values())

    lines.append("💼 RESUMO EXECUTIVO")
    lines.append(f"  Criativos criados: {total_criados}")
    lines.append(f"  Em teste: {total_teste} | Aprovados: {total_aprov} | Em escala: {total_escala}")
    lines.append(f"  Faturamento: {format_currency(total_revenue)}")
    if total_teste > 0:
        taxa_aprov = (total_aprov / total_teste) * 100
        lines.append(f"  Taxa de aprovação: {taxa_aprov:.0f}%")
    lines.append("")

    # Ranking por faturamento
    lines.append("✍️ RANKING COPYWRITERS")
    sorted_cw = sorted(
        report.items(),
        key=lambda x: x[1]["revenue"],
        reverse=True
    )

    for i, (cw, data) in enumerate(sorted_cw[:5], 1):
        if data["criados"] == 0:
            continue
        roas = data["revenue"] / data["cost"] if data["cost"] > 0 else 0
        aprov_pct = (data["aprovados"] / data["em_teste"] * 100) if data["em_teste"] > 0 else 0
        lines.append(f"  {i}. {cw}: {data['criados']} criados | {format_currency(data['revenue'])} | ROAS {roas:.2f}")
        lines.append(f"     Aprovação: {aprov_pct:.0f}% | Escala: {data['em_escala']}")

    lines.append("")

    # Top 10 criativos por CW
    lines.append("🏆 TOP CRIATIVOS")
    top_criativos = []
    for cw, data in sorted_cw:
        for criativo in data["criativos"][:3]:
            top_criativos.append((cw, criativo))

    top_criativos = sorted(
        top_criativos,
        key=lambda x: x[1]["revenue"],
        reverse=True
    )[:5]

    for cw, criativo in top_criativos:
        name = criativo["name"][:50]
        roas = criativo["roas"]
        lines.append(f"  • {cw}: {name}")
        lines.append(f"    {format_currency(criativo['revenue'])} | ROAS {roas:.2f} | Vendas: {criativo['vendas']}")

    lines.append("")

    # Alertas
    lines.append("⚠️ ALERTAS")
    has_alerts = False
    for cw, data in sorted_cw:
        if data["em_teste"] > 0:
            aprov_pct = (data["aprovados"] / data["em_teste"]) * 100
            if aprov_pct < 50:
                lines.append(f"  🔴 {cw}: aprovação baixa ({aprov_pct:.0f}%)")
                has_alerts = True

        if data["criados"] == 0:
            lines.append(f"  ⚫ {cw}: sem criativos no mês")
            has_alerts = True

    if not has_alerts:
        lines.append("  ✅ Nenhum alerta crítico")

    return "\n".join(lines)


def main():
    """Executa relatório mensal."""
    now = datetime.now()
    year = now.year
    month = now.month - 1
    if month < 1:
        month = 12
        year -= 1

    for arg in sys.argv[1:]:
        if arg.startswith("--ano="):
            year = int(arg.split("=")[1])
        elif arg.startswith("--mes="):
            month = int(arg.split("=")[1])

    log(f"Iniciando relatório mensal {month:02d}/{year}...")

    # Fetch data
    copy_tasks = fetch_copy_tasks_by_month(year, month)
    trafego_tasks = fetch_trafego_tasks()

    if not copy_tasks:
        log("Nenhum criativo encontrado")
        return False

    # Match
    matched = match_copy_to_trafego(copy_tasks, trafego_tasks)

    # RedTrack
    date_from = f"{year}-{month:02d}-01"
    last_day = calendar.monthrange(year, month)[1]
    date_to = f"{year}-{month:02d}-{last_day:02d}"
    campaigns = fetch_redtrack_data(date_from, date_to)
    enrich_with_redtrack(copy_tasks, campaigns)

    # Build report
    report = build_report(copy_tasks, matched, year, month)

    # Build message
    message = build_message(report, year, month)

    # Post
    success = post_clickup(message)

    if success:
        log("✓ Relatório postado com sucesso")
        return True
    else:
        log("✗ Erro ao postar relatório")
        return False


if __name__ == "__main__":
    os.makedirs(LOG_DIR, exist_ok=True)

    if not API_TOKEN:
        log("ERRO: CLICKUP_API_TOKEN não definido.")
        sys.exit(1)

    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        log(f"ERRO FATAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
