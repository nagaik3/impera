#!/usr/bin/env python3
"""
Cruzamento ClickUp + RedTrack — IMPERA
Cruza dados de produção (ClickUp) com performance (RedTrack).

Uso:
  python3 cruzamento_clickup_redtrack.py oferta       # Performance por nicho/oferta
  python3 cruzamento_clickup_redtrack.py gestor       # Performance por gestor de trafego
  python3 cruzamento_clickup_redtrack.py copywriter   # Ranking por copywriter
  python3 cruzamento_clickup_redtrack.py criativo     # Performance por criativo individual
  python3 cruzamento_clickup_redtrack.py completo     # Todos os cruzamentos
"""

import os
import sys
import json
import re
import time
import urllib.request
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/Scripts"))
from impera_utils import get_cf_value, detect_nicho, normalize_person_name
from impera_cache import cached_rt_ads

CLICKUP_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
REDTRACK_KEY = os.environ.get("REDTRACK_API_KEY", "")

COPY_LIST = "901324556390"       # COPY | EDIÇÃO (produção)
TRAFEGO_LIST = "901324476398"   # GESTÃO DE TRÁFEGO (tasks ativas com copywriter atribuído)

HEADERS_CU = {"Authorization": CLICKUP_TOKEN, "Content-Type": "application/json"}


# ============================================================
# REDTRACK: PARSING DE CAMPANHAS
# ============================================================

# Mapeamento nicho por palavra-chave na campanha
NICHO_KEYWORDS = {
    "EMAGRECIMENTO": "EM",
    "DIABETES": "DB",
    "NEUROPATIA": "NE",
    "ADULTO": "ED",
    "MEMORIA": "MM",
    "PROSTATA": "PT",
    "ZUMBIDO": "ZB",
    "ARTICULAR": "DA",
    "DORES": "DA",
    "VISAO": "VS",
}

# Oferta padrao por nicho (quando nao ha nome explicito)
OFERTA_PADRAO = {
    "EM": "GELATINA FIT",
    "DB": "GLICO RESET",
    "ED": "EREMED",
    "NE": "NEUROCARE",
    "MM": "MEMOFORTE",
    "DA": "ARTICURE",
    "PT": "PROSTASAFE",
    "ZB": "NEUROSILENCE",
}

# Oferta padrao EUA (quando campanha indica mercado EUA)
OFERTA_EUA = {
    "EM": "SLIMPIC",
    "MM": "BRAIN HONEY",
}

# Nomes de oferta que podem aparecer explicitamente nas campanhas
OFERTA_EXPLICITA = {
    "GELATINAFIT": "GELATINA FIT",
    "GELATINA FIT": "GELATINA FIT",
    "GELATINA": "GELATINA FIT",
    "INSULVITA": "INSULVITA",
    "GLICORESET": "GLICO RESET",
    "GLICOSET": "GLICO RESET",
    "GLICO RESET": "GLICO RESET",
    "EREMED": "EREMED",
    "EREPOWER": "EREPOWER",
    "NEUROCARE": "NEUROCARE",
    "NEUROSILENCE": "NEUROSILENCE",
    "NEUROPLUS": "NEUROPLUS",
    "MEMOFORTE": "MEMOFORTE",
    "BRAIN HONEY": "BRAIN HONEY",
    "BRAINHONEY": "BRAIN HONEY",
    "ARTICURE": "ARTICURE",
    "PROSTASAFE": "PROSTASAFE",
    "SLIMPIC": "SLIMPIC",
}

# Fontes por sigla na campanha
FONTE_MAP = {
    "FB": "FB", "FACEBOOK": "FB",
    "GG": "GG", "GOOGLE": "GG",
    "YT": "YT", "YOUTUBE": "YT",
    "TT": "TT", "TIKTOK": "TT",
    "KW": "KW", "KWAI": "KW",
    "MG": "MG", "MGID": "MG",
    "TB": "TB", "TABOOLA": "TB",
    "OB": "OB", "OUTBRAIN": "OB",
}

# Gestores
GESTOR_MAP = {
    "LUCAS": "LUCAS",
    "LUDSON": "LUDSON",
    "DOUG": "DOUGLAS",
    "DOUGLAS": "DOUGLAS",
    "FRAZA": "GABRIEL FRAZA",
    "GABRIEL": "GABRIEL FRAZA",
    "GUSTAVO": "GUSTAVO LISNER",
    "LISNER": "GUSTAVO LISNER",
}


def parse_campaign_name(name):
    """Extrai nicho, oferta, fonte, mercado e gestor do nome da campanha RedTrack."""
    upper = name.upper()

    # Fonte: geralmente entre colchetes no inicio [FB], [YT], etc.
    fonte = None
    fonte_match = re.match(r"\[(\w+)\]", name)
    if fonte_match:
        f = fonte_match.group(1).upper()
        fonte = FONTE_MAP.get(f, f)

    # Nicho
    nicho = None
    for keyword, code in NICHO_KEYWORDS.items():
        if keyword in upper:
            nicho = code
            break

    # Mercado EUA?
    is_eua = "EUA" in upper or ("USA" in upper)

    # Oferta: primeiro tenta detectar nome explicito na campanha
    oferta = None
    # Campanhas YT geralmente tem formato: "NomeProduto - Nicho"
    # Ex: "GelatinaFit - Emagrecimento", "NeuroCare - Neuropatia"
    for oferta_key, oferta_name in OFERTA_EXPLICITA.items():
        # Busca case-insensitive, com ou sem espaço
        if oferta_key.upper() in upper.replace(" ", "").replace("-", ""):
            oferta = oferta_name
            break

    # Se nao achou oferta explicita, usa padrao do nicho
    if not oferta and nicho:
        if is_eua and nicho in OFERTA_EUA:
            oferta = OFERTA_EUA[nicho]
        else:
            oferta = OFERTA_PADRAO.get(nicho)

    # Gestor: padrão G. NOME (FB) ou texto plano no final (YT/TB)
    gestor = None
    gestor_match = re.search(r"G\.\s*(\w+)", upper)
    if gestor_match:
        g = gestor_match.group(1)
        gestor = GESTOR_MAP.get(g, g)
    # Fallback: nome completo no final da campanha — Gabriel Fraza aparece sem "G."
    if not gestor:
        for g_key, g_name in GESTOR_MAP.items():
            if g_key in upper:
                gestor = g_name
                break
    # Inferência por fonte: YT/TB sem gestor identificado → Gabriel Fraza
    if not gestor and fonte in ("YT", "TB"):
        gestor = "GABRIEL FRAZA"

    mercado = "EUA" if is_eua else "BR"

    return {
        "nicho": nicho,
        "oferta": oferta,
        "fonte": fonte,
        "mercado": mercado,
        "gestor": gestor,
    }


# ============================================================
# REDTRACK: FETCH DATA
# ============================================================

def fetch_redtrack_campaigns(date_from, date_to):
    """Busca campanhas do RedTrack no periodo."""
    url = (
        f"https://api.redtrack.io/report?api_key={REDTRACK_KEY}"
        f"&group=campaign&date_from={date_from}&date_to={date_to}&per=200"
    )
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def fetch_redtrack_adgroups(campaign_id, date_from, date_to):
    """Busca adgroups de uma campanha especifica."""
    url = (
        f"https://api.redtrack.io/report?api_key={REDTRACK_KEY}"
        f"&group=rt_adgroup&campaign_id={campaign_id}"
        f"&date_from={date_from}&date_to={date_to}&per=500"
    )
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


# ============================================================
# CLICKUP: FETCH TASKS
# ============================================================

def fetch_clickup_tasks(list_id, include_closed=True):
    """Busca todas as tarefas de uma lista."""
    tasks = []
    page = 0
    while True:
        url = f"https://api.clickup.com/api/v2/list/{list_id}/task"
        params = f"?page={page}&limit=100&subtasks=true&include_closed={'true' if include_closed else 'false'}"
        req = urllib.request.Request(url + params)
        req.add_header("Authorization", CLICKUP_TOKEN)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        batch = data.get("tasks", [])
        tasks.extend(batch)
        if not batch or data.get("last_page", True):
            break
        page += 1
    return tasks


def get_cf_dropdown(task, search_term):
    """Extrai valor de dropdown de campo customizado (busca por substring case-insensitive)."""
    for cf in task.get("custom_fields", []):
        cf_name = cf.get("name", "").lower()
        # Remove emojis pra comparacao
        cf_clean = re.sub(r'[^\w\s]', '', cf_name).strip().lower()
        if search_term.lower() in cf_clean:
            opts = cf.get("type_config", {}).get("options", [])
            val = cf.get("value")
            if val is not None:
                for o in opts:
                    if o.get("orderindex") == val:
                        return normalize_person_name(o["name"])
    return None


def parse_clickup_task(task):
    """Extrai dados relevantes de uma tarefa ClickUp."""
    name = task["name"]
    nicho = detect_nicho(name)
    copywriter = get_cf_dropdown(task, "copywritter") or get_cf_dropdown(task, "copy") or "N/A"
    editor = get_cf_dropdown(task, "editor") or "N/A"

    # Detecta oferta pelo codigo no nome
    oferta_code = None
    oferta_match = re.search(r"\[(OF\d+|C\d+)\]", name, re.IGNORECASE)
    if oferta_match:
        oferta_code = oferta_match.group(1).upper()

    # Detecta fonte
    fonte = None
    fonte_match = re.search(r"\[(FB|GG|YT|TT|KW|MG|TB|OB)\]", name, re.IGNORECASE)
    if fonte_match:
        fonte = fonte_match.group(1).upper()

    # Detecta mercado
    mercado = "BR"
    if "[EUA]" in name.upper():
        mercado = "EUA"

    # Detecta AD range
    ad_match = re.search(r"AD\s*(\d+)\s*[-aA]\s*(?:AD)?\s*(\d+)", name, re.IGNORECASE)
    ad_single = re.search(r"\[AD(\d+)\]", name)
    # Geração 2: [AD644V9] — número e versão fundidos no mesmo bracket
    ad_gen2 = re.search(r"\[AD(\d+)V(\d+)\]", name, re.IGNORECASE)
    ads = []
    if ad_match:
        for i in range(int(ad_match.group(1)), int(ad_match.group(2)) + 1):
            ads.append(f"AD{i}")
    elif ad_gen2:
        # Indexa como AD644 (gen 1) E AD644V9 (gen 2) para cobrir ambos os lookups
        n, v = int(ad_gen2.group(1)), int(ad_gen2.group(2))
        ads.append(f"AD{n}")
        ads.append(f"AD{n}V{v}")
    elif ad_single:
        ads.append(f"AD{int(ad_single.group(1))}")

    # Detecta prefixos de ripagem: CE##, CY##, CC##, C## (range ou individual)
    # CE = Elias, CY = Yan, CC = Cassio, C = Douglas (gestor)
    # Também captura variantes com AD prefix: [ADCE##] → CE##, [ADCY##] → CY##, [ADCC##] → CC##
    rip_ids = []
    for prefix in ["CE", "CY", "CC"]:
        # Tenta primeiro a forma com AD prefix espúrio: [ADCE119], [ADCY##]
        adp_single = re.search(rf"\[AD{prefix}(\d+)\]", name, re.IGNORECASE)
        # Range padrão e individual
        rip_range = re.search(rf"\[{prefix}(\d+)\s*-\s*{prefix}?(\d+)\]", name, re.IGNORECASE)
        rip_single = re.search(rf"\[{prefix}(\d+)\]", name, re.IGNORECASE)
        if adp_single:
            rip_ids.append(f"{prefix}{int(adp_single.group(1))}")
        elif rip_range:
            for i in range(int(rip_range.group(1)), int(rip_range.group(2)) + 1):
                rip_ids.append(f"{prefix}{i}")
        elif rip_single:
            rip_ids.append(f"{prefix}{int(rip_single.group(1))}")

    # C## generico (Douglas) — cuidado pra nao pegar C01 que e oferta
    # So pega C## que NAO esta precedido de OF ou dentro de [OFC##]
    c_range = re.search(r"\[C(\d+)\s*-\s*C?(\d+)\]", name)
    c_single = re.search(r"\[C(\d+)\](?!\s*\[)", name)
    # Exclui se parece codigo de oferta (C01, C02 entre ofertas conhecidas)
    oferta_codes = {"C01", "C02", "C03"}
    if c_range:
        for i in range(int(c_range.group(1)), int(c_range.group(2)) + 1):
            cid = f"C{i}"
            if cid not in oferta_codes:
                rip_ids.append(cid)
    elif c_single:
        cid = f"C{int(c_single.group(1))}"
        if cid not in oferta_codes and int(c_single.group(1)) > 3:
            rip_ids.append(cid)

    # Combina todos os identificadores de criativos
    all_creative_ids = ads + rip_ids

    return {
        "id": task["id"],
        "name": name,
        "nicho": nicho,
        "oferta_code": oferta_code,
        "fonte": fonte,
        "mercado": mercado,
        "copywriter": copywriter.upper(),
        "editor": editor.upper(),
        "ads": ads,
        "rip_ids": rip_ids,
        "all_ids": all_creative_ids,
        "status": task.get("status", {}).get("status", ""),
    }


# ============================================================
# CRUZAMENTO
# ============================================================

def build_redtrack_data(date_from, date_to):
    """Busca e processa todos os dados do RedTrack."""
    print("  Buscando campanhas RedTrack...")
    campaigns_raw = fetch_redtrack_campaigns(date_from, date_to)

    campaigns = []
    for r in campaigns_raw:
        name = r.get("campaign", "")
        cost = float(r.get("cost", 0))
        rev = float(r.get("revenuetype2", 0)) + float(r.get("revenuetype3", 0))
        vendas = int(r.get("convtype4", 0))
        parsed = parse_campaign_name(name)

        campaigns.append({
            "name": name,
            "campaign_id": r.get("campaign_id", ""),
            "cost": cost,
            "revenue": rev,
            "roas": rev / cost if cost > 0 else 0,
            "vendas": vendas,
            **parsed,
        })

    print(f"  {len(campaigns)} campanhas encontradas.")
    return campaigns


def build_clickup_data():
    """Busca e processa tarefas de ambas as listas ClickUp.
    GESTÃO TRÁFEGO é a fonte primária (1429 tasks, campo copywriter preenchido).
    COPY|EDIÇÃO é fonte secundária para tasks que ainda não foram enviadas ao tráfego.
    Deduplicação por nome de tarefa — GESTÃO TRÁFEGO tem prioridade.
    """
    print("  Buscando tarefas ClickUp (GESTÃO TRÁFEGO + COPY|EDIÇÃO)...")
    trafego_raw = fetch_clickup_tasks(TRAFEGO_LIST)
    copy_raw = fetch_clickup_tasks(COPY_LIST)
    print(f"  Listas brutas: GT={len(trafego_raw)}, COPY={len(copy_raw)}")

    seen_names = set()
    tasks = []

    for t in trafego_raw + copy_raw:
        if not re.match(r"\s*\[", t["name"]):
            continue
        name_key = t["name"].strip().upper()
        if name_key in seen_names:
            continue
        seen_names.add(name_key)
        parsed = parse_clickup_task(t)
        tasks.append(parsed)

    print(f"  {len(tasks)} tarefas únicas após deduplicação.")
    return tasks


def cruzamento_por_oferta(campaigns):
    """Cruzamento nivel 1: Performance por nicho/oferta."""
    ofertas = defaultdict(lambda: {"cost": 0, "revenue": 0, "vendas": 0, "campanhas": 0})

    for c in campaigns:
        if not c["nicho"] or not c["oferta"]:
            continue
        key = f"{c['nicho']} | {c['oferta']}"
        if c["mercado"] == "EUA":
            key += " (EUA)"
        ofertas[key]["cost"] += c["cost"]
        ofertas[key]["revenue"] += c["revenue"]
        ofertas[key]["vendas"] += c["vendas"]
        ofertas[key]["campanhas"] += 1

    print("\n" + "=" * 70)
    print("CRUZAMENTO 1: PERFORMANCE POR OFERTA")
    print(f"Periodo: ultimos 7 dias")
    print("=" * 70)

    sorted_ofertas = sorted(ofertas.items(), key=lambda x: x[1]["revenue"], reverse=True)

    for key, data in sorted_ofertas:
        if data["cost"] < 10:
            continue
        roas = data["revenue"] / data["cost"] if data["cost"] > 0 else 0
        status = "OK" if roas >= 2.0 else ("!!" if roas >= 1.0 else "XX")
        cpa = data["cost"] / data["vendas"] if data["vendas"] > 0 else 0

        print(f"\n  [{status}] {key}")
        print(f"      Custo: R${data['cost']:,.0f} | Receita: R${data['revenue']:,.0f} | ROAS: {roas:.2f}")
        print(f"      Vendas CC: {data['vendas']} | CPA: R${cpa:,.0f} | Campanhas: {data['campanhas']}")

    return sorted_ofertas


def cruzamento_por_copywriter(campaigns, tasks):
    """Cruzamento nivel 2: Performance por copywriter."""
    # Agrupa campanhas por nicho+fonte
    camp_by_nicho_fonte = defaultdict(lambda: {"cost": 0, "revenue": 0, "vendas": 0})
    for c in campaigns:
        if not c["nicho"] or not c["fonte"]:
            continue
        key = (c["nicho"], c["fonte"])
        camp_by_nicho_fonte[key]["cost"] += c["cost"]
        camp_by_nicho_fonte[key]["revenue"] += c["revenue"]
        camp_by_nicho_fonte[key]["vendas"] += c["vendas"]

    # Agrupa tarefas por copywriter, contando quantas por nicho+fonte
    copy_tasks = defaultdict(lambda: defaultdict(int))
    copy_total = defaultdict(int)
    for t in tasks:
        if t["copywriter"] == "N/A" or not t["nicho"] or not t["fonte"]:
            continue
        key = (t["nicho"], t["fonte"])
        copy_tasks[t["copywriter"]][key] += len(t["ads"]) if t["ads"] else 1
        copy_total[t["copywriter"]] += len(t["ads"]) if t["ads"] else 1

    # Calcula performance ponderada por copywriter
    # Logica: se copywriter X produziu 30% dos criativos de [EM][FB], atribui 30% da performance
    copy_perf = defaultdict(lambda: {"cost_attr": 0, "rev_attr": 0, "vendas_attr": 0, "criativos": 0})

    for copywriter, nicho_fonte_counts in copy_tasks.items():
        for (nicho, fonte), count in nicho_fonte_counts.items():
            # Total de criativos nesse nicho+fonte
            total_criativos_nf = sum(
                copy_tasks[cw].get((nicho, fonte), 0) for cw in copy_tasks
            )
            if total_criativos_nf == 0:
                continue

            share = count / total_criativos_nf
            perf = camp_by_nicho_fonte.get((nicho, fonte))
            if not perf:
                continue

            copy_perf[copywriter]["cost_attr"] += perf["cost"] * share
            copy_perf[copywriter]["rev_attr"] += perf["revenue"] * share
            copy_perf[copywriter]["vendas_attr"] += perf["vendas"] * share
            copy_perf[copywriter]["criativos"] += count

    print("\n" + "=" * 70)
    print("CRUZAMENTO 2: RANKING POR COPYWRITER")
    print("(Performance atribuida proporcionalmente ao volume de criativos)")
    print("=" * 70)

    sorted_copy = sorted(copy_perf.items(), key=lambda x: x[1]["rev_attr"], reverse=True)

    for copywriter, data in sorted_copy:
        if data["cost_attr"] < 10:
            continue
        roas = data["rev_attr"] / data["cost_attr"] if data["cost_attr"] > 0 else 0
        print(f"\n  {copywriter} ({data['criativos']} criativos)")
        print(f"      Receita atribuida: R${data['rev_attr']:,.0f} | Custo atribuido: R${data['cost_attr']:,.0f}")
        print(f"      ROAS atribuido: {roas:.2f} | Vendas atribuidas: {data['vendas_attr']:.0f}")

    return sorted_copy


def cruzamento_por_criativo(campaigns, tasks, date_from, date_to):
    """Cruzamento nivel 3: Performance por criativo individual via rt_ad."""
    print("\n" + "=" * 70)
    print("CRUZAMENTO 3: PERFORMANCE POR CRIATIVO")
    print("(rt_ad via API — group=campaign,rt_ad)")
    print("=" * 70)

    # Mapa campaign_id -> parsed campaign (nicho, oferta, fonte, gestor)
    camp_map = {c["campaign_id"]: c for c in campaigns if c.get("campaign_id")}

    print(f"\n  Buscando rt_ad (cached_rt_ads)...")
    rt_data = cached_rt_ads(date_from, date_to)
    ads_raw = rt_data.get("ads", [])
    print(f"  {len(ads_raw)} ads encontrados no RT.")

    all_adgroups = []
    for ad in ads_raw:
        ad_name = ad.get("rt_ad", "")
        cost = float(ad.get("cost", 0))
        rev = float(ad.get("revenuetype2", 0)) + float(ad.get("revenuetype3", 0))
        vendas = int(ad.get("convtype4", 0))

        if cost < 1:
            continue

        cid = ad.get("campaign_id", "")
        camp = camp_map.get(cid, {})

        all_adgroups.append({
            "adgroup": ad_name,
            "campaign": ad.get("campaign", camp.get("name", "")),
            "nicho": camp.get("nicho"),
            "oferta": camp.get("oferta"),
            "fonte": camp.get("fonte"),
            "cost": cost,
            "revenue": rev,
            "roas": rev / cost if cost > 0 else 0,
            "vendas": vendas,
        })

    print(f"  {len(all_adgroups)} ads com custo > 0.\n")

    # Mapeamento de prefixo de ripagem para copywriter
    RIP_PREFIX_COPY = {
        "CE": "ELIAS", "CY": "YAN", "CC": "CASSIO",
    }

    # Tenta match com ClickUp tasks
    matched = []
    unmatched = []

    for ag in all_adgroups:
        ag_name = ag["adgroup"]
        ag_upper = ag_name.upper().strip()
        best_match = None
        match_type = None

        # Remove sufixos comuns do adgroup: " — Cópia", " - Cópia 2", " - Copy", etc.
        ag_clean = re.sub(r"\s*[—-]\s*(C[oó]pia|Copy)(\s*\d*)?$", "", ag_name, flags=re.IGNORECASE).strip()
        # Normaliza variantes de nomenclatura RT:
        # ADC## → C##  (RT bug: C## às vezes aparece como ADC##)
        ag_clean = re.sub(r"\bADC\s*(\d+)", r"C\1", ag_clean, flags=re.IGNORECASE)
        # ADCE## → CE##, ADCY## → CY##, ADCC## → CC## (prefixo AD espúrio antes de ripagem)
        ag_clean = re.sub(r"\bAD(CE|CY|CC)\s*(\d+)", r"\1\2", ag_clean, flags=re.IGNORECASE)
        # AG## → AD## (variação de nomenclatura)
        ag_clean = re.sub(r"\bAG\s*(\d+)", r"AD\1", ag_clean, flags=re.IGNORECASE)
        # "AD C##" → "C##" (AD + espaço + C##, prefixo AD espúrio)
        ag_clean = re.sub(r"\bAD\s+C(\d+)", r"C\1", ag_clean, flags=re.IGNORECASE)
        ag_clean_upper = ag_clean.upper()

        # Strip prefix de tags [EM][OF02][FB] para matchs baseados em re.match (ancored ao início)
        # "[EM][OF02][FB] C123" → "C123"; "[NE][OF03][FB] AD09V2 V10" → "AD09V2 V10"
        ag_no_tags = re.sub(r'^(\[[^\]]*\]\s*)+[-–]?\s*', '', ag_clean).strip()
        ag_no_tags_upper = ag_no_tags.upper()

        # 1a. Tenta match por AD##V## — geração 2 (ex: rt_ad "AD644 V9" → task [AD644V9])
        ad_gen2_match = re.search(r"AD\s*(\d+)\s+V\s*(\d+)", ag_clean_upper)
        if ad_gen2_match:
            gen2_id = f"AD{int(ad_gen2_match.group(1))}V{int(ad_gen2_match.group(2))}"
            for t in tasks:
                if t["nicho"] == ag["nicho"]:
                    if gen2_id in t["all_ids"]:
                        best_match = t
                        match_type = "AD_GEN2"
                        break

        # 1b. Tenta match por AD## — geração 1
        if not best_match:
            ad_match = re.search(r"AD\s*(\d+)", ag_clean_upper)
            if ad_match:
                ad_num = f"AD{int(ad_match.group(1))}"
                for t in tasks:
                    if t["nicho"] == ag["nicho"]:
                        if ad_num in t["all_ids"]:
                            best_match = t
                            match_type = "AD"
                            break

        # 2. Tenta match por prefixo de ripagem CE##, CY##, CC##
        # Usa ag_no_tags_upper para ignorar prefixo [EM][OF02][FB]
        if not best_match:
            for prefix in ["CE", "CY", "CC"]:
                rip_match = re.match(rf"^{prefix}\s*(\d+)", ag_no_tags_upper) or \
                            re.match(rf"^{prefix}\s*(\d+)", ag_clean_upper)
                if rip_match:
                    rip_id = f"{prefix}{int(rip_match.group(1))}"
                    for t in tasks:
                        if t["nicho"] == ag["nicho"]:
                            if rip_id in t["all_ids"]:
                                best_match = t
                                match_type = f"RIP({prefix})"
                                break
                    if not best_match:
                        match_type = f"RIP_INFERRED({prefix})"
                    break

        # 3. C## sem versão = Douglas (definitivo, sem consultar ClickUp)
        #    C## V## = variação → buscar copywriter no ClickUp
        # Usa ag_no_tags_upper para capturar "[EM][OF02][FB] C123" → "C123"
        if not best_match:
            for candidate in [ag_no_tags_upper, ag_clean_upper]:
                c_match = re.match(r"^C\s*(\d+)", candidate)
                if c_match:
                    c_num = int(c_match.group(1))
                    c_id = f"C{c_num}"
                    has_version = bool(re.search(r"V\s*\d+", candidate[c_match.end():]))
                    if has_version:
                        for t in tasks:
                            if t["nicho"] == ag["nicho"]:
                                if c_id in t["all_ids"]:
                                    best_match = t
                                    match_type = "C_VARIACAO"
                                    break
                    else:
                        match_type = "DOUGLAS_GESTOR"
                        best_match = {"copywriter": "DOUGLAS (GESTOR)", "editor": "N/A",
                                      "name": c_id, "nicho": ag.get("nicho"), "all_ids": [c_id]}
                    break

        # 4. Número puro = AD## (ex: "232", "740" → AD232, AD740)
        if not best_match:
            num_only = re.match(r"^(\d+)$", ag_no_tags_upper.strip())
            if num_only:
                ad_num = f"AD{int(num_only.group(1))}"
                for t in tasks:
                    if t["nicho"] == ag["nicho"]:
                        if ad_num in t["all_ids"]:
                            best_match = t
                            match_type = "NUM_BARE"
                            break

        # 5. Número com versão solto (ex: "76 V10", "644 v9", "232 V3")
        if not best_match:
            num_match = re.match(r"^(\d+)\s", ag_no_tags_upper) or \
                        re.match(r"^(\d+)\s", ag_clean_upper)
            if num_match:
                num = num_match.group(1)
                for t in tasks:
                    if t["nicho"] == ag["nicho"]:
                        if f"AD{num}" in t["all_ids"] or f"C{num}" in t["all_ids"]:
                            best_match = t
                            match_type = "NUM"
                            break

        if best_match:
            matched.append({**ag, "task": best_match, "match_type": match_type})
        else:
            # Tenta inferir copywriter pelo prefixo mesmo sem match de task
            inferred_copy = None
            for check in [ag_no_tags_upper, ag_clean_upper]:
                for prefix, copy_name in RIP_PREFIX_COPY.items():
                    if re.match(rf"^{prefix}\s*\d+", check):
                        inferred_copy = copy_name
                        break
                if inferred_copy:
                    break
            if not inferred_copy:
                for check in [ag_no_tags_upper, ag_clean_upper]:
                    c_bare = re.match(r"^C\s*(\d+)", check)
                    if c_bare:
                        after_c = check[c_bare.end():]
                        has_v = bool(re.search(r"V\s*\d+", after_c))
                        inferred_copy = "DOUGLAS (GESTOR)" if not has_v else "VARIAÇÃO C## (sem tarefa CU)"
                        break

            unmatched.append({**ag, "inferred_copy": inferred_copy})

    # Mostra resultados
    print(f"  Criativos com match ClickUp: {len(matched)}")
    print(f"  Criativos sem match: {len(unmatched)}")

    # Separar criativos de Douglas (gestor) dos de copywriters
    douglas_ads = [m for m in matched if m.get("match_type") == "DOUGLAS_GESTOR"]
    copy_ads = [m for m in matched if m.get("match_type") != "DOUGLAS_GESTOR"]

    if copy_ads:
        print(f"\n  --- CRIATIVOS IDENTIFICADOS (copywriters) ---")
        copy_ads.sort(key=lambda x: x["revenue"], reverse=True)
        for m in copy_ads[:20]:
            roas = m["roas"]
            status = "OK" if roas >= 2.0 else ("!!" if roas >= 1.0 else "XX")
            print(f"\n  [{status}] {m['adgroup'][:50]}")
            print(f"      Custo: R${m['cost']:,.0f} | Receita: R${m['revenue']:,.0f} | ROAS: {roas:.2f}")
            print(f"      Copy: {m['task']['copywriter']} | Editor: {m['task']['editor']}")
            print(f"      Tarefa: {m['task']['name'][:60]}")

    if douglas_ads:
        print(f"\n  --- CRIATIVOS DOUGLAS (gestor — oculto no relatório de copy) ---")
        douglas_ads.sort(key=lambda x: x["revenue"], reverse=True)
        for m in douglas_ads[:10]:
            roas = m["roas"]
            print(f"  [GT] {m['adgroup'][:50]}")
            print(f"      Custo: R${m['cost']:,.0f} | Receita: R${m['revenue']:,.0f} | ROAS: {roas:.2f}")

    if unmatched:
        print(f"\n  --- TOP CRIATIVOS SEM MATCH (por receita) ---")
        unmatched.sort(key=lambda x: x["revenue"], reverse=True)
        for u in unmatched[:10]:
            roas = u["roas"]
            inferred = u.get("inferred_copy")
            copy_line = f" | Copy inferido: {inferred}" if inferred else ""
            print(f"\n  [??] {u['adgroup'][:50]}")
            print(f"      Custo: R${u['cost']:,.0f} | Receita: R${u['revenue']:,.0f} | ROAS: {roas:.2f}{copy_line}")
            print(f"      Campanha: {u['campaign'][:50]}")

    return matched, unmatched


def cruzamento_por_gestor(campaigns):
    """Cruzamento nivel 4: Performance por gestor de trafego."""
    gestores = defaultdict(lambda: {"cost": 0, "revenue": 0, "vendas": 0, "campanhas": 0, "nichos": set(), "ofertas": set()})

    for c in campaigns:
        gestor = c.get("gestor") or "N/A"
        gestores[gestor]["cost"] += c["cost"]
        gestores[gestor]["revenue"] += c["revenue"]
        gestores[gestor]["vendas"] += c["vendas"]
        gestores[gestor]["campanhas"] += 1
        if c.get("nicho"):
            gestores[gestor]["nichos"].add(c["nicho"])
        if c.get("oferta"):
            gestores[gestor]["ofertas"].add(c["oferta"])

    print("\n" + "=" * 70)
    print("CRUZAMENTO 4: PERFORMANCE POR GESTOR DE TRAFEGO")
    print("=" * 70)

    # Ordena por faturamento (receita)
    sorted_gestores = sorted(gestores.items(), key=lambda x: x[1]["revenue"], reverse=True)

    for gestor, data in sorted_gestores:
        if data["cost"] < 10:
            continue
        roas = data["revenue"] / data["cost"] if data["cost"] > 0 else 0
        cpa = data["cost"] / data["vendas"] if data["vendas"] > 0 else 0
        status = "OK" if roas >= 2.0 else ("!!" if roas >= 1.0 else "XX")
        nichos = ", ".join(sorted(data["nichos"]))
        ofertas = ", ".join(sorted(data["ofertas"]))

        print(f"\n  [{status}] {gestor} ({data['campanhas']} campanhas)")
        print(f"      Receita: R${data['revenue']:,.0f} | Custo: R${data['cost']:,.0f} | ROAS: {roas:.2f}")
        print(f"      Vendas CC: {data['vendas']} | CPA: R${cpa:,.0f}")
        print(f"      Nichos: {nichos}")
        print(f"      Ofertas: {ofertas}")

    return sorted_gestores


# ============================================================
# MAIN
# ============================================================

def run(mode="completo"):
    today = datetime.now()
    date_to = today.strftime("%Y-%m-%d")
    date_from = (today - timedelta(days=7)).strftime("%Y-%m-%d")

    print(f"Cruzamento ClickUp + RedTrack - {date_from} a {date_to}")
    print("-" * 70)

    campaigns = build_redtrack_data(date_from, date_to)

    if mode in ("oferta", "completo"):
        cruzamento_por_oferta(campaigns)

    if mode in ("gestor", "completo"):
        cruzamento_por_gestor(campaigns)

    if mode in ("copywriter", "completo"):
        tasks = build_clickup_data()
        cruzamento_por_copywriter(campaigns, tasks)

    if mode in ("criativo", "completo"):
        if "tasks" not in dir():
            tasks = build_clickup_data()
        cruzamento_por_criativo(campaigns, tasks, date_from, date_to)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "completo"
    if mode not in ("oferta", "gestor", "copywriter", "criativo", "completo"):
        print(__doc__)
        sys.exit(1)
    run(mode)
