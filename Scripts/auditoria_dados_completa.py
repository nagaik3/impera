#!/usr/bin/env python3
"""
Auditoria Completa de Dados — IMPERA
Valida integridade de dados em Copy, Edição, Tráfego e RedTrack.

Uso:
  python3 auditoria_dados_completa.py

GPDR — Iago Almeida | Assistido por Claude — Anthropic
"""

import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.expanduser("~/Scripts"))
try:
    from cruzamento_clickup_redtrack import parse_campaign_name, fetch_redtrack_campaigns
except:
    pass

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
REDTRACK_KEY = os.environ.get("REDTRACK_API_KEY", "")

LIST_COPY = "901324556390"
LIST_TRAFEGO = "901324476398"

COPYWRITERS_ESPERADOS = {"YAN", "CASSIO", "CRISPIM", "ANA", "ELIAS", "CAROL"}
EDITORES_ESPERADOS = {"IGOR OLIVEIRA", "IGOR PAIVA", "WELL", "NICOLAS", "MURYLLO"}


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def api_get(endpoint):
    url = f"https://api.clickup.com/api/v2{endpoint}"
    req = urllib.request.Request(url, headers={"Authorization": API_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log(f"❌ Erro API: {e}")
        return {"tasks": []}


def fetch_all_tasks(list_id):
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


def get_cf_value(task, cf_id):
    """Extrai valor de custom field."""
    for cf in task.get("custom_fields", []):
        if cf.get("id") == cf_id:
            val = cf.get("value")
            if val is not None:
                opts = cf.get("type_config", {}).get("options", [])
                for o in opts:
                    if o.get("orderindex") == val:
                        return o.get("name", "")
    return None


def audit_copy():
    """Auditoria do setor de Copy."""
    log("\n" + "="*70)
    log("🔍 AUDITORIA COPY (ClickUp List)")
    log("="*70)

    tasks = fetch_all_tasks(LIST_COPY)
    log(f"Total de tarefas: {len(tasks)}")

    issues = defaultdict(list)
    stats = {
        "total": len(tasks),
        "com_copywriter": 0,
        "sem_copywriter": 0,
        "com_start_date": 0,
        "sem_start_date": 0,
        "nomenclatura_invalida": 0,
        "copywriters_unicos": set(),
    }

    for task in tasks:
        tid = task.get("id", "")
        name = task.get("name", "")

        # Validação 1: Copywriter
        cw = get_cf_value(task, "eeb64866-df57-4dbf-8338-5d4fb58837aa")
        if cw:
            stats["com_copywriter"] += 1
            stats["copywriters_unicos"].add(cw)
            if cw not in COPYWRITERS_ESPERADOS and cw != "REAPER":
                issues["copywriter_desconhecido"].append({
                    "task": tid,
                    "name": name[:50],
                    "cw": cw
                })
        else:
            stats["sem_copywriter"] += 1
            issues["sem_copywriter"].append({"task": tid, "name": name[:50]})

        # Validação 2: Start Date
        sd = task.get("start_date")
        if sd:
            stats["com_start_date"] += 1
        else:
            stats["sem_start_date"] += 1
            issues["sem_start_date"].append({"task": tid, "name": name[:50]})

        # Validação 3: Nomenclatura
        if not name.startswith("["):
            issues["nomenclatura_invalida"].append({"task": tid, "name": name[:50]})

    # Relatório
    log(f"\n✅ COM COPYWRITER: {stats['com_copywriter']}/{stats['total']} ({stats['com_copywriter']/stats['total']*100:.1f}%)")
    if stats["sem_copywriter"] > 0:
        log(f"❌ SEM COPYWRITER: {stats['sem_copywriter']} tarefas")
        for item in issues["sem_copywriter"][:5]:
            log(f"   - {item['task']}: {item['name']}")
        if len(issues["sem_copywriter"]) > 5:
            log(f"   ... e mais {len(issues['sem_copywriter'])-5}")

    log(f"\n✅ COM START_DATE: {stats['com_start_date']}/{stats['total']} ({stats['com_start_date']/stats['total']*100:.1f}%)")
    if stats["sem_start_date"] > 0:
        log(f"❌ SEM START_DATE: {stats['sem_start_date']} tarefas")

    log(f"\n✅ NOMENCLATURA VÁLIDA: {stats['total'] - len(issues['nomenclatura_invalida'])}/{stats['total']}")
    if issues["nomenclatura_invalida"]:
        log(f"❌ NOMENCLATURA INVÁLIDA: {len(issues['nomenclatura_invalida'])} tarefas")
        for item in issues["nomenclatura_invalida"][:3]:
            log(f"   - {item['task']}: {item['name']}")

    log(f"\n📊 COPYWRITERS ÚNICOS: {len(stats['copywriters_unicos'])}")
    for cw in sorted(stats["copywriters_unicos"]):
        expected = "✓" if cw in COPYWRITERS_ESPERADOS or cw == "REAPER" else "✗"
        log(f"   {expected} {cw}")

    return {
        "total": stats["total"],
        "issues": len(issues),
        "sem_copywriter": len(issues.get("sem_copywriter", [])),
        "sem_start_date": len(issues.get("sem_start_date", [])),
        "nomenclatura_invalida": len(issues.get("nomenclatura_invalida", [])),
    }


def audit_edicao():
    """Auditoria do setor de Edição (GESTÃO DE TRÁFEGO)."""
    log("\n" + "="*70)
    log("🎬 AUDITORIA EDIÇÃO (GESTÃO DE TRÁFEGO)")
    log("="*70)

    tasks = fetch_all_tasks(LIST_TRAFEGO)
    log(f"Total de tarefas: {len(tasks)}")

    CF_EDITOR = "6002b1b9-e8c5-49ad-9e3d-3d8c314a1c91"

    issues = defaultdict(list)
    stats = {
        "total": len(tasks),
        "com_editor": 0,
        "sem_editor": 0,
        "editores_unicos": set(),
        "com_parent_task": 0,
        "sem_parent_task": 0,
        "statuses_unicos": set(),
    }

    for task in tasks:
        tid = task.get("id", "")
        name = task.get("name", "")
        status = task.get("status", {}).get("status", "?")

        # Validação 1: Editor
        editor = get_cf_value(task, CF_EDITOR)
        if editor:
            stats["com_editor"] += 1
            stats["editores_unicos"].add(editor)
        else:
            stats["sem_editor"] += 1
            issues["sem_editor"].append({"task": tid, "name": name[:50]})

        # Validação 2: Parent Task (link para COPY)
        parent_found = False
        for cf in task.get("custom_fields", []):
            cf_name = cf.get("name", "").lower()
            if "parent" in cf_name or "pai" in cf_name:
                if cf.get("value"):
                    parent_found = True
                    stats["com_parent_task"] += 1
                    break

        if not parent_found:
            stats["sem_parent_task"] += 1
            issues["sem_parent_task"].append({"task": tid, "name": name[:50]})

        # Validação 3: Status
        stats["statuses_unicos"].add(status)

    # Relatório
    log(f"\n✅ COM EDITOR: {stats['com_editor']}/{stats['total']} ({stats['com_editor']/stats['total']*100:.1f}%)")
    if stats["sem_editor"] > 0:
        log(f"❌ SEM EDITOR: {stats['sem_editor']} tarefas")

    log(f"\n✅ COM PARENT_TASK (link Copy): {stats['com_parent_task']}/{stats['total']} ({stats['com_parent_task']/stats['total']*100:.1f}%)")
    if stats["sem_parent_task"] > 0:
        log(f"⚠️  SEM PARENT_TASK: {stats['sem_parent_task']} (podem ser órfãs)")

    log(f"\n📊 EDITORES ÚNICOS: {len(stats['editores_unicos'])}")
    for ed in sorted(stats["editores_unicos"]):
        expected = "✓" if ed in EDITORES_ESPERADOS else "✗"
        log(f"   {expected} {ed}")

    log(f"\n📋 STATUSES: {len(stats['statuses_unicos'])}")
    for st in sorted(stats["statuses_unicos"])[:10]:
        log(f"   • {st}")

    return {
        "total": stats["total"],
        "issues": len(issues),
        "sem_editor": len(issues.get("sem_editor", [])),
        "sem_parent_task": len(issues.get("sem_parent_task", [])),
    }


def audit_redtrack():
    """Auditoria do cruzamento RedTrack."""
    log("\n" + "="*70)
    log("📈 AUDITORIA REDTRACK (Cruzamento de Dados)")
    log("="*70)

    # Buscar última semana
    today = datetime.now()
    date_to = today.strftime("%Y-%m-%d")
    date_from = (today - timedelta(days=7)).strftime("%Y-%m-%d")

    log(f"Período: {date_from} a {date_to}")

    try:
        campaigns = fetch_redtrack_campaigns(date_from, date_to)
        if not campaigns:
            log("⚠️  Nenhuma campanha retornada")
            return {"total": 0, "issues": 0}

        log(f"Total de campanhas: {len(campaigns)}")

        issues = defaultdict(int)
        stats = {
            "total": len(campaigns),
            "parseadas_com_sucesso": 0,
            "sem_nicho": 0,
            "sem_oferta": 0,
            "sem_gestor": 0,
            "nichos_unicos": set(),
            "gestores_unicos": set(),
        }

        for camp in campaigns:
            parsed = parse_campaign_name(camp.get("campaign", ""))

            nicho = parsed.get("nicho")
            oferta = parsed.get("oferta")
            gestor = parsed.get("gestor")

            if nicho:
                stats["parseadas_com_sucesso"] += 1
                stats["nichos_unicos"].add(nicho)
            else:
                stats["sem_nicho"] += 1
                issues["sem_nicho"] += 1

            if not oferta:
                stats["sem_oferta"] += 1
                issues["sem_oferta"] += 1

            if not gestor:
                stats["sem_gestor"] += 1
                issues["sem_gestor"] += 1

            # Validar dados numéricos
            cost = float(camp.get("cost", 0))
            rev = float(camp.get("revenuetype2", 0)) + float(camp.get("revenuetype3", 0))

            if cost < 0 or rev < 0:
                issues["dados_negativos"] += 1

        # Relatório
        log(f"\n✅ CAMPANHAS PARSEADAS: {stats['parseadas_com_sucesso']}/{stats['total']} ({stats['parseadas_com_sucesso']/stats['total']*100:.1f}%)")

        if stats["sem_nicho"] > 0:
            log(f"❌ SEM NICHO: {stats['sem_nicho']} campanhas (não pode parsear)")

        if stats["sem_oferta"] > 0:
            log(f"⚠️  SEM OFERTA: {stats['sem_oferta']} campanhas")

        if stats["sem_gestor"] > 0:
            log(f"⚠️  SEM GESTOR: {stats['sem_gestor']} campanhas")

        log(f"\n📊 NICHOS ENCONTRADOS: {len(stats['nichos_unicos'])}")
        for nicho in sorted(stats["nichos_unicos"]):
            log(f"   • {nicho}")

        log(f"\n👥 GESTORES ENCONTRADOS: {len(stats['gestores_unicos'])}")
        for gestor in sorted(stats["gestores_unicos"])[:10]:
            log(f"   • {gestor}")
        if len(stats["gestores_unicos"]) > 10:
            log(f"   ... e mais {len(stats['gestores_unicos'])-10}")

        return {
            "total": stats["total"],
            "parseadas": stats["parseadas_com_sucesso"],
            "issues": len(issues),
            "sem_nicho": stats["sem_nicho"],
            "sem_oferta": stats["sem_oferta"],
            "sem_gestor": stats["sem_gestor"],
        }

    except Exception as e:
        log(f"❌ Erro ao buscar RedTrack: {e}")
        return {"total": 0, "issues": 0, "error": str(e)}


def audit_cruzamento():
    """Auditoria do cruzamento Copy ↔ Tráfego."""
    log("\n" + "="*70)
    log("🔗 AUDITORIA CRUZAMENTO (Copy ↔ Tráfego)")
    log("="*70)

    copy_tasks = fetch_all_tasks(LIST_COPY)
    trafego_tasks = fetch_all_tasks(LIST_TRAFEGO)

    log(f"Copy tasks: {len(copy_tasks)}")
    log(f"Tráfego tasks: {len(trafego_tasks)}")

    # Criar índices
    copy_by_id = {t["id"]: t for t in copy_tasks}
    trafego_matched = 0
    trafego_orphans = 0

    for traf in trafego_tasks:
        parent_found = False
        for cf in traf.get("custom_fields", []):
            val = cf.get("value")
            # Handle both string and list values
            if isinstance(val, list):
                val = val[0] if val else None
            if val and isinstance(val, str) and val in copy_by_id:
                trafego_matched += 1
                parent_found = True
                break

        if not parent_found:
            trafego_orphans += 1

    matching_rate = (trafego_matched / len(trafego_tasks) * 100) if trafego_tasks else 0

    log(f"\n✅ CRUZAMENTO SUCESSO: {trafego_matched}/{len(trafego_tasks)} ({matching_rate:.1f}%)")
    if trafego_orphans > 0:
        log(f"⚠️  TAREFAS ÓRFÃS: {trafego_orphans} (sem parent_task_id válido)")

    return {
        "copy_total": len(copy_tasks),
        "trafego_total": len(trafego_tasks),
        "matched": trafego_matched,
        "orphans": trafego_orphans,
        "matching_rate": matching_rate,
    }


def main():
    log(f"\n🔍 AUDITORIA COMPLETA DE DADOS — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {}
    results["copy"] = audit_copy()
    results["edicao"] = audit_edicao()
    results["redtrack"] = audit_redtrack()
    results["cruzamento"] = audit_cruzamento()

    # Sumário final
    log("\n" + "="*70)
    log("📋 SUMÁRIO EXECUTIVO")
    log("="*70)

    copy_score = (results["copy"]["total"] - results["copy"]["issues"]) / results["copy"]["total"] * 100
    edicao_score = (results["edicao"]["total"] - results["edicao"]["issues"]) / results["edicao"]["total"] * 100 if results["edicao"]["total"] > 0 else 0
    redtrack_score = (results["redtrack"]["parseadas"] / results["redtrack"]["total"] * 100) if results["redtrack"]["total"] > 0 else 0
    cruzamento_score = results["cruzamento"]["matching_rate"]

    log(f"\n📊 QUALIDADE DOS DADOS:")
    log(f"  Copy:       {copy_score:.0f}% {'✅' if copy_score > 90 else '⚠️' if copy_score > 70 else '❌'}")
    log(f"  Edição:     {edicao_score:.0f}% {'✅' if edicao_score > 90 else '⚠️' if edicao_score > 70 else '❌'}")
    log(f"  RedTrack:   {redtrack_score:.0f}% {'✅' if redtrack_score > 90 else '⚠️' if redtrack_score > 70 else '❌'}")
    log(f"  Cruzamento: {cruzamento_score:.0f}% {'✅' if cruzamento_score > 80 else '⚠️' if cruzamento_score > 60 else '❌'}")

    overall = (copy_score + edicao_score + redtrack_score + cruzamento_score) / 4
    log(f"\n🎯 SCORE GERAL: {overall:.0f}% {'✅ SEGURO' if overall > 85 else '⚠️ ATENÇÃO' if overall > 70 else '❌ CRÍTICO'}")

    log(f"\n{'='*70}\n")


if __name__ == "__main__":
    if not API_TOKEN:
        log("ERRO: CLICKUP_API_TOKEN não definido.")
        sys.exit(1)

    try:
        main()
    except Exception as e:
        log(f"ERRO FATAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
