#!/usr/bin/env python3
"""
Dashboard de Cobertura CU↔RT — IMPERA
Mostra % de cobertura entre ClickUp (GESTÃO DE TRÁFEGO) e RedTrack.
Breakdown por nicho, gestor e fonte.

Uso:
  python3 dashboard_cobertura_rt_cu.py                    # últimos 7 dias
  python3 dashboard_cobertura_rt_cu.py --days 30          # últimos 30 dias
  python3 dashboard_cobertura_rt_cu.py --telegram         # envia pro Telegram
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta

sys.path.insert(0, os.path.expanduser("~/Scripts"))
from impera_cache import cached_cu_tasks, cached_rt_ads

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
REDTRACK_KEY = os.environ.get("REDTRACK_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

LIST_TRAFEGO = "901324476398"
CHAT_VIEW_GT = "6-901324476398-8"

NICHO_KEYWORDS = {
    "EMAGRECIMENTO": "EM", "DIABETES": "DB", "NEUROPATIA": "NE",
    "ADULTO": "ED", "MEMORIA": "MM", "MEMÓRIA": "MM",
    "PROSTATA": "PT", "ZUMBIDO": "ZB", "ARTICULAR": "DA", "DORES": "DA",
    "VISAO": "VS", "REJUVENESCIMENTO": "RJ",
}

GESTOR_MAP = {
    "LUCAS": "LUCAS", "LUDSON": "LUDSON", "DOUG": "DOUGLAS",
    "DOUGLAS": "DOUGLAS", "FRAZA": "GABRIEL", "GABRIEL": "GABRIEL",
    "GUSTAVO": "GUSTAVO",
}

FONTE_MAP = {
    "FB": "FB", "FACEBOOK": "FB", "GG": "GG", "GOOGLE": "GG",
    "YT": "YT", "YOUTUBE": "YT", "TT": "TT", "TIKTOK": "TT",
    "KW": "KW", "KWAI": "KW", "MG": "MG", "MGID": "MG",
    "TB": "TB", "TABOOLA": "TB", "OB": "OB", "OUTBRAIN": "OB",
}


def api_get_cu(endpoint):
    url = f"https://api.clickup.com/api/v2{endpoint}"
    req = urllib.request.Request(url, headers={"Authorization": API_TOKEN})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def fetch_rt(group, date_from, date_to, campaign_id=None):
    url = (
        f"https://api.redtrack.io/report?api_key={REDTRACK_KEY}"
        f"&group={group}&date_from={date_from}&date_to={date_to}&per=500"
    )
    if campaign_id:
        url += f"&campaign_id={campaign_id}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


def fetch_all_cu(list_id):
    all_t = []
    page = 0
    while True:
        data = api_get_cu(f"/list/{list_id}/task?include_closed=false&subtasks=true&page={page}")
        tasks = data.get("tasks", [])
        if not tasks:
            break
        all_t.extend(tasks)
        page += 1
    return all_t


def parse_campaign(name):
    upper = name.upper()
    nicho = None
    for kw, code in NICHO_KEYWORDS.items():
        if kw in upper:
            nicho = code
            break

    fonte = None
    m = re.match(r"\[(\w+)\]", name)
    if m:
        f = m.group(1).upper()
        fonte = FONTE_MAP.get(f, None)

    gestor = None
    gm = re.search(r"G\.\s*(\w+)", upper)
    if gm:
        gestor = GESTOR_MAP.get(gm.group(1), gm.group(1))
    if not gestor:
        for part in name.split("|"):
            for gk, gn in GESTOR_MAP.items():
                if gk in part.upper():
                    gestor = gn
                    break

    return {"nicho": nicho, "fonte": fonte, "gestor": gestor}


def build_cu_index(tasks):
    """Build a set of normalized creative references from CU tasks."""
    refs = set()
    for t in tasks:
        name = t["name"].upper()
        # AD ranges
        for m in re.finditer(r"AD(\d+)\s*-\s*(?:AD)?(\d+)", name):
            for n in range(int(m.group(1)), int(m.group(2)) + 1):
                refs.add(f"AD{n}")
        # AD singles
        if not re.search(r"AD\d+\s*-", name):
            for m in re.findall(r"AD(\d+)", name):
                refs.add(f"AD{m}")
        # CE/CY/CC
        for m in re.finditer(r"(C[EYC])(\d+)\s*V(\d+)\s*-\s*V?(\d+)", name):
            for v in range(int(m.group(3)), int(m.group(4)) + 1):
                refs.add(f"{m.group(1)}{m.group(2)}V{v}")
        for m in re.finditer(r"(C[EYC])(\d+)\s*-\s*(?:C[EYC])?(\d+)(?!\s*V)", name):
            for n in range(int(m.group(2)), int(m.group(3)) + 1):
                refs.add(f"{m.group(1)}{n}")
        for m in re.findall(r"(C[EYC])(\d+)(?:\s*V(\d+))?", name):
            refs.add(f"{m[0]}{m[1]}")
            if m[2]:
                refs.add(f"{m[0]}{m[1]}V{m[2]}")
        # IMG
        for m in re.findall(r"IMG(\d+)", name):
            refs.add(f"IMG{m}")
    return refs


def normalize_rt_ad(ad_name):
    """Normalize a RT ad name to match CU refs."""
    ref = re.sub(r"\s+", "", ad_name.upper().strip())
    if re.match(r"^\d", ref):
        ref = "AD" + ref
    ref = re.sub(r"^ADAD", "AD", ref)
    return ref


def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception:
        pass


def post_chat_gt(text):
    """Posta no Chat da lista Gestão de Tráfego."""
    url = f"https://api.clickup.com/api/v2/view/{CHAT_VIEW_GT}/comment"
    payload = json.dumps({"comment_text": text}).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", API_TOKEN)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True
    except Exception:
        return False


def run(days=7, send_tg=False):
    now = datetime.now()
    df = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    dt = now.strftime("%Y-%m-%d")

    print(f"Dashboard de Cobertura CU↔RT ({df} a {dt})\n", flush=True)
    print("Buscando dados...", flush=True)

    # CU data
    cu_tasks = cached_cu_tasks(LIST_TRAFEGO, include_closed=False, ttl=1800)
    cu_refs = build_cu_index(cu_tasks)

    # RT data — 1 call (multi-group) instead of N+1
    rt_data = cached_rt_ads(df, dt, ttl=1800)
    rt_list = rt_data["campaigns"]

    print(f"  CU: {len(cu_tasks)} tarefas ({len(cu_refs)} refs) | RT: {len(rt_list)} campanhas\n", flush=True)

    # Per-campaign: fetch ads and check coverage
    stats = {
        "total_ads": 0, "covered": 0, "orphan": 0,
        "by_nicho": {}, "by_gestor": {}, "by_fonte": {},
        "top_orphans": [],
    }

    # Group ads by campaign
    ads_by_camp = {}
    for ad in rt_data["ads"]:
        cid = ad.get("campaign_id", "")
        if cid not in ads_by_camp:
            ads_by_camp[cid] = {"name": ad.get("campaign", ""), "ads": []}
        ads_by_camp[cid]["ads"].append(ad)

    for camp_id, camp_data in ads_by_camp.items():
        camp_name = camp_data["name"]
        camp_cost = sum(float(a.get("cost", 0)) for a in camp_data["ads"])
        if camp_cost < 10 or not camp_name:
            continue

        parsed = parse_campaign(camp_name)
        nicho = parsed["nicho"] or "?"
        gestor = parsed["gestor"] or "?"
        fonte = parsed["fonte"] or "?"

        # Init buckets
        for key, bucket in [("by_nicho", nicho), ("by_gestor", gestor), ("by_fonte", fonte)]:
            if bucket not in stats[key]:
                stats[key][bucket] = {"total": 0, "covered": 0, "cost": 0, "revenue": 0}

        ad_list = camp_data["ads"]

        for ad in ad_list:
            ad_name = (ad.get("rt_ad", "") or "").strip()
            ad_cost = float(ad.get("cost", 0))
            ad_rev = float(ad.get("revenuetype2", 0)) + float(ad.get("revenuetype3", 0))
            if ad_cost < 2:
                continue

            stats["total_ads"] += 1
            for key, bucket in [("by_nicho", nicho), ("by_gestor", gestor), ("by_fonte", fonte)]:
                stats[key][bucket]["total"] += 1
                stats[key][bucket]["cost"] += ad_cost
                stats[key][bucket]["revenue"] += ad_rev

            # Check coverage
            normalized = normalize_rt_ad(ad_name)
            # Try multiple variants
            found = False
            variants = {normalized}
            base = re.match(r"((?:AD|C[EYC]|IMG|C)\d+)", normalized)
            if base:
                variants.add(base.group(1))
            ver = re.match(r"((?:AD|C[EYC]|IMG|C)\d+V\d+)", normalized)
            if ver:
                variants.add(ver.group(1))

            for v in variants:
                if v in cu_refs:
                    found = True
                    break

            if found:
                stats["covered"] += 1
                for key, bucket in [("by_nicho", nicho), ("by_gestor", gestor), ("by_fonte", fonte)]:
                    stats[key][bucket]["covered"] += 1
            else:
                stats["orphan"] += 1
                stats["top_orphans"].append({
                    "ad": ad_name, "campaign": camp_name[:50],
                    "cost": ad_cost, "revenue": ad_rev, "gestor": gestor,
                })

    # Sort orphans by cost
    stats["top_orphans"].sort(key=lambda x: x["cost"], reverse=True)

    # Print report
    total = stats["total_ads"]
    covered = stats["covered"]
    pct = (covered / total * 100) if total else 0

    print(f"{'='*60}", flush=True)
    print(f"  COBERTURA GLOBAL: {covered}/{total} ({pct:.1f}%)", flush=True)
    print(f"  Órfãos: {stats['orphan']}", flush=True)
    print(f"{'='*60}\n", flush=True)

    # By nicho
    print("  POR NICHO:", flush=True)
    print(f"  {'Nicho':<8} {'Cobertos':>10} {'Total':>8} {'%':>7} {'Investido':>12}", flush=True)
    print(f"  {'-'*50}", flush=True)
    for nicho in sorted(stats["by_nicho"].keys()):
        d = stats["by_nicho"][nicho]
        p = (d["covered"] / d["total"] * 100) if d["total"] else 0
        print(f"  {nicho:<8} {d['covered']:>10} {d['total']:>8} {p:>6.1f}% R${d['cost']:>10,.0f}", flush=True)

    # By gestor
    print(f"\n  POR GESTOR:", flush=True)
    print(f"  {'Gestor':<12} {'Cobertos':>10} {'Total':>8} {'%':>7} {'Investido':>12}", flush=True)
    print(f"  {'-'*54}", flush=True)
    for gestor in sorted(stats["by_gestor"].keys()):
        d = stats["by_gestor"][gestor]
        p = (d["covered"] / d["total"] * 100) if d["total"] else 0
        print(f"  {gestor:<12} {d['covered']:>10} {d['total']:>8} {p:>6.1f}% R${d['cost']:>10,.0f}", flush=True)

    # By fonte
    print(f"\n  POR FONTE:", flush=True)
    print(f"  {'Fonte':<8} {'Cobertos':>10} {'Total':>8} {'%':>7} {'Investido':>12}", flush=True)
    print(f"  {'-'*50}", flush=True)
    for fonte in sorted(stats["by_fonte"].keys()):
        d = stats["by_fonte"][fonte]
        p = (d["covered"] / d["total"] * 100) if d["total"] else 0
        print(f"  {fonte:<8} {d['covered']:>10} {d['total']:>8} {p:>6.1f}% R${d['cost']:>10,.0f}", flush=True)

    # Top orphans
    if stats["top_orphans"][:10]:
        print(f"\n  TOP 10 ÓRFÃOS (por investimento):", flush=True)
        print(f"  {'AD':<20} {'Gestor':<10} {'Investido':>10} {'Receita':>10}", flush=True)
        print(f"  {'-'*54}", flush=True)
        for o in stats["top_orphans"][:10]:
            print(f"  {o['ad'][:20]:<20} {o['gestor']:<10} R${o['cost']:>8,.0f} R${o['revenue']:>8,.0f}", flush=True)

    # Telegram + Chat GT
    if send_tg:
        tg_lines = [
            f"<b>Dashboard Cobertura CU↔RT</b> ({df} a {dt})\n",
            f"<b>Global:</b> {covered}/{total} ({pct:.1f}%)\n",
            "<b>Por Gestor:</b>",
        ]
        for gestor in sorted(stats["by_gestor"].keys()):
            d = stats["by_gestor"][gestor]
            p = (d["covered"] / d["total"] * 100) if d["total"] else 0
            emoji = "🟢" if p >= 90 else "🟡" if p >= 70 else "🔴"
            tg_lines.append(f"  {emoji} {gestor}: {d['covered']}/{d['total']} ({p:.0f}%)")

        if stats["top_orphans"][:5]:
            tg_lines.append("\n<b>Top 5 Órfãos:</b>")
            for o in stats["top_orphans"][:5]:
                tg_lines.append(f"  • {o['ad'][:20]} ({o['gestor']}) R${o['cost']:,.0f}")

        send_telegram("\n".join(tg_lines))

        # Chat GT (plain text)
        gt_lines = [
            f"📊 Dashboard Cobertura CU↔RT — {df} a {dt}",
            "",
            f"Global: {covered}/{total} criativos cobertos ({pct:.1f}%)",
            "",
            "Por Gestor:",
        ]
        for gestor in sorted(stats["by_gestor"].keys()):
            d = stats["by_gestor"][gestor]
            p = (d["covered"] / d["total"] * 100) if d["total"] else 0
            emoji = "🟢" if p >= 90 else "🟡" if p >= 70 else "🔴"
            gt_lines.append(f"  {emoji} {gestor}: {d['covered']}/{d['total']} ({p:.0f}%)")

        if stats["top_orphans"][:5]:
            gt_lines.append("")
            gt_lines.append("Top 5 Órfãos (sem tarefa no CU):")
            for o in stats["top_orphans"][:5]:
                gt_lines.append(f"  • {o['ad'][:20]} ({o['gestor']}) R${o['cost']:,.0f}")

        gt_lines.append("")
        gt_lines.append("— GPDR Cruzamento RT↔CU")
        post_chat_gt("\n".join(gt_lines))
        print("\n  Telegram + Chat GT enviados!", flush=True)

    return stats


if __name__ == "__main__":
    if not API_TOKEN or not REDTRACK_KEY:
        print("ERRO: CLICKUP_API_TOKEN ou REDTRACK_API_KEY não configurados")
        sys.exit(1)

    days = 7
    send_tg = "--telegram" in sys.argv or "--chat" in sys.argv
    for i, arg in enumerate(sys.argv):
        if arg == "--days" and i + 1 < len(sys.argv):
            days = int(sys.argv[i + 1])

    run(days=days, send_tg=send_tg)
