#!/usr/bin/env python3
"""
Monitor de Confiança — Sistema de Alertas

Monitora a taxa de confiança no cruzamento RedTrack↔ClickUp.
Se cair abaixo de 85%, dispara um alerta.

Uso:
  python3 impera_confidence_monitor.py              # Checa últimos 7 dias
  python3 impera_confidence_monitor.py --period 14  # Últimos 14 dias
  python3 impera_confidence_monitor.py --auto       # Post alert ao ClickUp
"""

import sys
import os
import json
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/Scripts"))

from impera_cache import cached_rt_adgroups
from impera_ad_registry import get_or_build_registry, lookup_ad
from fetch_redtrack_com_copywriter_ultimate import extract_ad_number

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
CLICKUP_CHAT_VIEW = "8cm1w4b-9993"
CONFIDENCE_THRESHOLD = 0.85
STATUS_FILE = os.path.expanduser("~/Scripts/data/confidence_status.json")


def check_confidence(date_from: str, date_to: str) -> dict:
    """Checa taxa de confiança para um período."""
    registry = get_or_build_registry(max_age_hours=4)
    adgroup_data = cached_rt_adgroups(date_from, date_to)
    adgroups = adgroup_data.get("adgroups", [])

    stats = {
        "total": len(adgroups),
        "found": 0,
        "not_found": 0,
        "confidence_1_0": 0,
        "confidence_0_9": 0,
        "confidence_0_85": 0,
        "confidence_0_0": 0,
        "confidence_high": 0,
    }

    for row in adgroups:
        rt_adgroup = row.get("rt_adgroup", "")
        ad_num = extract_ad_number(rt_adgroup)

        if not ad_num:
            stats["not_found"] += 1
            continue

        result = lookup_ad(ad_num, registry, context_campaign=row.get("campaign", ""))
        confidence = result["confidence"]

        stats["found"] += 1

        if confidence == 1.0:
            stats["confidence_1_0"] += 1
        elif confidence == 0.9:
            stats["confidence_0_9"] += 1
        elif confidence == 0.85:
            stats["confidence_0_85"] += 1
        else:
            stats["confidence_0_0"] += 1

        if confidence >= CONFIDENCE_THRESHOLD:
            stats["confidence_high"] += 1

    # Calcular taxa
    stats["match_rate"] = 100 * stats["found"] / max(stats["total"], 1)
    stats["high_confidence_rate"] = 100 * stats["confidence_high"] / max(stats["found"], 1)

    return stats


def post_alert(message: str) -> bool:
    """Posta alerta no ClickUp Chat View."""
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


def load_status() -> dict:
    """Carrega status anterior."""
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"last_check": None, "last_confidence": None, "alert_sent": False}


def save_status(status: dict) -> None:
    """Salva status atual."""
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Monitor de Confiança")
    parser.add_argument("--period", type=int, default=7, help="Últimos N dias")
    parser.add_argument("--date-from", help="Data início (YYYY-MM-DD)")
    parser.add_argument("--date-to", help="Data fim (YYYY-MM-DD)")
    parser.add_argument("--auto", action="store_true", help="Post alert ao ClickUp se necessário")

    args = parser.parse_args()

    if args.date_from and args.date_to:
        date_from = args.date_from
        date_to = args.date_to
    else:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        date_to = today.strftime("%Y-%m-%d")
        date_from = (today - timedelta(days=args.period - 1)).strftime("%Y-%m-%d")

    print(f"🔍 Verificando confiança ({date_from} a {date_to})...\n")

    stats = check_confidence(date_from, date_to)

    # Mostrar resultados
    print("📊 CONFIANÇA DOS DADOS:\n")
    print(f"   Taxa de Matching: {stats['match_rate']:.1f}%")
    print(f"   Taxa de Confiança Alta (≥85%): {stats['high_confidence_rate']:.1f}%")
    print(f"   Registros encontrados: {stats['found']}/{stats['total']}")
    print(f"   Confiança 100%: {stats['confidence_1_0']}")
    print(f"   Confiança 90%: {stats['confidence_0_9']}")
    print(f"   Confiança 0%: {stats['confidence_0_0']}\n")

    # Checar se precisa de alerta
    status = load_status()
    should_alert = stats["high_confidence_rate"] < 85 and not status.get("alert_sent", False)
    should_clear = stats["high_confidence_rate"] >= 85 and status.get("alert_sent", False)

    if should_alert:
        print("⚠️  ALERTA: Confiança caiu abaixo de 85%!")
        alert_msg = f"""⚠️ **ALERTA: Taxa de Confiança Baixa**

Período: {date_from} a {date_to}
Taxa de Confiança: **{stats['high_confidence_rate']:.1f}%** (limiar: 85%)

Detalhes:
- Registros analisados: {stats['total']}
- Encontrados: {stats['found']} ({stats['match_rate']:.1f}%)
- Confiança 100%: {stats['confidence_1_0']} ({100*stats['confidence_1_0']/max(stats['found'], 1):.1f}%)
- Confiança 90%: {stats['confidence_0_9']} ({100*stats['confidence_0_9']/max(stats['found'], 1):.1f}%)
- Confiança 0%: {stats['confidence_0_0']} ({100*stats['confidence_0_0']/max(stats['found'], 1):.1f}%)

⚡ Ação recomendada: Verificar registry ou dados do RedTrack"""

        if args.auto:
            if post_alert(alert_msg):
                print("✅ Alerta postado no ClickUp")
                status["alert_sent"] = True
            else:
                print("❌ Falha ao postar alerta")
        else:
            print(alert_msg)
            print("\nUse --auto para postar alerta ao ClickUp")

    elif should_clear:
        print("✅ Confiança recuperada!")
        print("   Sistema retornou ao normal (≥85%)")
        status["alert_sent"] = False

    else:
        if stats["high_confidence_rate"] >= 85:
            print(f"✅ Confiança OK ({stats['high_confidence_rate']:.1f}%)")
        else:
            print(f"❌ Confiança baixa ({stats['high_confidence_rate']:.1f}%)")

    status["last_check"] = datetime.now().isoformat()
    status["last_confidence"] = stats["high_confidence_rate"]
    save_status(status)


if __name__ == "__main__":
    main()
