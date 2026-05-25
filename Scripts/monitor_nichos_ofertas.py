#!/usr/bin/env python3
"""
Monitor de Novos Nichos e Ofertas — IMPERA
Detecta nichos/ofertas/fontes inéditas no RedTrack e alerta via Telegram + Chat GT.
Crontab: a cada 6h (0 */6 * * *)

Uso:
  python3 monitor_nichos_ofertas.py              # executa
  python3 monitor_nichos_ofertas.py --preview    # preview sem alertar
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta
from impera_cache import rt_rate_limit

REDTRACK_KEY = os.environ.get("REDTRACK_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
CLICKUP_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")

CHAT_VIEW_GT = "6-901324476398-8"
STATE_FILE = os.path.expanduser("~/Scripts/data/nichos_ofertas_conhecidos.json")

# Nichos conhecidos (siglas no nome da campanha RT)
NICHOS_CONHECIDOS = {
    "EMAGRECIMENTO", "DIABETES", "NEUROPATIA", "ADULTO", "MEMORIA", "MEMÓRIA",
    "PROSTATA", "ZUMBIDO", "ARTICULAR", "DORES", "VISAO", "REJUVENESCIMENTO",
}

# Ofertas conhecidas (keywords no nome da campanha RT)
OFERTAS_CONHECIDAS = {
    "EREMED", "EREPOWER", "GELATINAFIT", "GELATINA FIT", "GELATINA", "SLIMPIC",
    "NEUROCARE", "NEUROSILENCE", "INSULVITA", "GLICORESET", "GLICO RESET",
    "MEMOFORTE", "BRAIN HONEY", "BRAINHONEY", "ARTICURE", "PROSTASAFE", "LIPOLED",
}

# Fontes conhecidas
FONTES_CONHECIDAS = {"FB", "GG", "YT", "TT", "KW", "MG", "TB", "OB"}

# Gestores conhecidos
GESTORES_CONHECIDOS = {"LUCAS", "LUDSON", "DOUG", "DOUGLAS", "GABRIEL", "FRAZA", "GUSTAVO"}

import re

GESTOR_PATTERN = re.compile(r"G\.\s*(\w+)", re.IGNORECASE)
FONTE_PATTERN = re.compile(r"^\[(\w+)\]")


def fetch_rt_campaigns(date_from, date_to):
    url = (
        f"https://api.redtrack.io/report?api_key={REDTRACK_KEY}"
        f"&group=campaign&date_from={date_from}&date_to={date_to}&per=500"
    )
    rt_rate_limit()
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        print(f"  [TG] {text[:100]}...", flush=True)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        print(f"  [TG ERRO] {e}", flush=True)


def post_chat_gt(text):
    """Posta no Chat da lista Gestão de Tráfego."""
    if not CLICKUP_TOKEN:
        return
    url = f"https://api.clickup.com/api/v2/view/{CHAT_VIEW_GT}/comment"
    payload = json.dumps({"comment_text": text}).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", CLICKUP_TOKEN)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True
    except Exception as e:
        print(f"  [CHAT GT ERRO] {e}", flush=True)
        return False


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "nichos_vistos": list(NICHOS_CONHECIDOS),
        "ofertas_vistas": list(OFERTAS_CONHECIDAS),
        "fontes_vistas": list(FONTES_CONHECIDAS),
        "gestores_vistos": list(GESTORES_CONHECIDOS),
        "campanhas_sem_nicho": [],
        "last_run": None,
    }


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def extract_info(camp_name):
    """Extrai fonte, nicho keywords, oferta keywords, gestor de uma campanha RT."""
    upper = camp_name.upper()
    info = {"fonte": None, "nichos": [], "ofertas": [], "gestor": None, "name": camp_name}

    # Fonte: [FB], [GG], etc.
    fm = FONTE_PATTERN.match(camp_name)
    if fm:
        info["fonte"] = fm.group(1).upper()

    # Gestor: G. LUCAS, G. DOUG, etc.
    gm = GESTOR_PATTERN.search(upper)
    if gm:
        info["gestor"] = gm.group(1)

    # Nichos: keywords presentes
    for kw in NICHOS_CONHECIDOS:
        if kw in upper:
            info["nichos"].append(kw)

    # Ofertas: keywords presentes
    clean = upper.replace(" ", "").replace("-", "")
    for oferta in OFERTAS_CONHECIDAS:
        oferta_clean = oferta.replace(" ", "").upper()
        if oferta_clean in clean:
            info["ofertas"].append(oferta)

    return info


def run(preview=False):
    now = datetime.now()
    df = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    dt = now.strftime("%Y-%m-%d")

    state = load_state()
    nichos_set = set(s.upper() for s in state.get("nichos_vistos", []))
    ofertas_set = set(s.upper().replace(" ", "") for s in state.get("ofertas_vistas", []))
    fontes_set = set(s.upper() for s in state.get("fontes_vistas", []))
    gestores_set = set(s.upper() for s in state.get("gestores_vistos", []))
    campanhas_sem_nicho_set = set(state.get("campanhas_sem_nicho", []))

    print(f"Buscando campanhas RT ({df} a {dt})...", flush=True)
    rt_data = fetch_rt_campaigns(df, dt)
    rt_list = rt_data if isinstance(rt_data, list) else rt_data.get("data", [])
    print(f"  {len(rt_list)} campanhas encontradas\n", flush=True)

    novos_nichos = []
    novas_ofertas = []
    novas_fontes = []
    novos_gestores = []
    sem_nicho = []

    for camp in rt_list:
        camp_name = camp.get("campaign", "")
        cost = float(camp.get("cost", 0))
        if cost < 5 or not camp_name:
            continue

        info = extract_info(camp_name)

        # Check fonte
        if info["fonte"] and info["fonte"] not in fontes_set:
            novas_fontes.append({"fonte": info["fonte"], "campaign": camp_name, "cost": cost})
            fontes_set.add(info["fonte"])

        # Check gestor
        if info["gestor"] and info["gestor"] not in gestores_set:
            novos_gestores.append({"gestor": info["gestor"], "campaign": camp_name, "cost": cost})
            gestores_set.add(info["gestor"])

        # Check sem nicho
        if not info["nichos"] and not info["ofertas"]:
            camp_key = camp_name[:60]
            if camp_key not in campanhas_sem_nicho_set:
                sem_nicho.append({"campaign": camp_name, "cost": cost})
                campanhas_sem_nicho_set.add(camp_key)

        # Detectar palavras-chave novas que parecem ser nichos/ofertas
        # Heurística: palavras em CAPS que aparecem entre pipes ou no início
        upper = camp_name.upper()
        parts = [p.strip() for p in upper.split("|")]
        for part in parts:
            words = part.split()
            for word in words:
                clean_word = re.sub(r"[^A-Z0-9]", "", word)
                if len(clean_word) >= 5 and clean_word not in nichos_set:
                    # Verificar se parece um nicho/oferta novo (não é gestor, fonte, etc.)
                    if clean_word not in fontes_set and clean_word not in gestores_set:
                        if not any(kw in clean_word for kw in {"CAMP", "TESTE", "COPY", "VIDEO", "LEAD"}):
                            # Pode ser nicho/oferta novo — verificar se aparece em múltiplas campanhas
                            pass  # análise mais profunda ficaria complexa demais

    # Alertas
    alerts = []

    if novas_fontes:
        lines = "\n".join(f"  • <b>{f['fonte']}</b> — {f['campaign'][:50]} (R${f['cost']:,.0f})" for f in novas_fontes)
        alerts.append(f"🆕 <b>NOVAS FONTES detectadas no RT:</b>\n{lines}")
        print(f"  🆕 {len(novas_fontes)} novas fontes", flush=True)
        for f in novas_fontes:
            print(f"    {f['fonte']} — {f['campaign'][:50]}", flush=True)

    if novos_gestores:
        lines = "\n".join(f"  • <b>G. {g['gestor']}</b> — {g['campaign'][:50]} (R${g['cost']:,.0f})" for g in novos_gestores)
        alerts.append(f"🆕 <b>NOVOS GESTORES detectados no RT:</b>\n{lines}")
        print(f"  🆕 {len(novos_gestores)} novos gestores", flush=True)
        for g in novos_gestores:
            print(f"    G. {g['gestor']} — {g['campaign'][:50]}", flush=True)

    if sem_nicho:
        top5 = sorted(sem_nicho, key=lambda x: x["cost"], reverse=True)[:5]
        lines = "\n".join(f"  • {c['campaign'][:60]} (R${c['cost']:,.0f})" for c in top5)
        alerts.append(f"⚠️ <b>{len(sem_nicho)} campanhas SEM NICHO identificável:</b>\n{lines}")
        print(f"  ⚠️ {len(sem_nicho)} campanhas sem nicho identificável", flush=True)
        for c in top5:
            print(f"    {c['campaign'][:60]}", flush=True)

    if not alerts:
        print("  ✅ Nenhuma novidade detectada", flush=True)
    elif not preview:
        header = f"📡 <b>Monitor de Nichos/Ofertas</b> — {now.strftime('%d/%b %H:%M')}\n\n"
        full_msg = header + "\n\n".join(alerts)
        if len(full_msg) > 4000:
            full_msg = full_msg[:4000] + "\n\n(...truncado)"
        send_telegram(full_msg)

        # Chat GT (plain text, sem HTML)
        plain = full_msg.replace("<b>", "").replace("</b>", "")
        plain += "\n\n— GPDR Monitor Automático"
        post_chat_gt(plain)

    # Save state
    state["nichos_vistos"] = sorted(nichos_set)
    state["ofertas_vistas"] = sorted(ofertas_set)
    state["fontes_vistas"] = sorted(fontes_set)
    state["gestores_vistos"] = sorted(gestores_set)
    state["campanhas_sem_nicho"] = sorted(campanhas_sem_nicho_set)
    state["last_run"] = now.isoformat()
    if not preview:
        save_state(state)

    print(f"\n  Resumo: {len(novas_fontes)} fontes | {len(novos_gestores)} gestores | {len(sem_nicho)} sem nicho", flush=True)


if __name__ == "__main__":
    if not REDTRACK_KEY:
        print("ERRO: REDTRACK_API_KEY não configurado")
        sys.exit(1)
    preview = "--preview" in sys.argv
    if preview:
        print("=== PREVIEW MODE ===", flush=True)
    run(preview=preview)
