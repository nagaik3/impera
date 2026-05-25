"""
Funções utilitárias compartilhadas — IMPERA
Importar em qualquer script: from impera_utils import *
"""

import re

# Nichos válidos
NICHOS_VALIDOS = {"DA", "DB", "ED", "EM", "ME", "MM", "NE", "PT", "ZB"}
MODIFICADORES = {"BR", "EUA", "RP"}

NICHO_NAMES = {
    'DA': 'Dores Articulares', 'DB': 'Diabetes', 'ED': 'Adulto / ED',
    'EM': 'Emagrecimento', 'ME': 'Memória EUA', 'MM': 'Memória BR',
    'NE': 'Neuropatia', 'PT': 'Próstata', 'ZB': 'Zumbido',
}


def detect_nicho(name):
    """Detecta o nicho da tarefa. Ignora [RP], [BR], [EUA]."""
    for m in re.findall(r"\[([A-Z]{2,3})\]", name):
        if m in NICHOS_VALIDOS:
            return m
    return "??"


def detect_mercado(name):
    """Detecta BR ou EUA."""
    upper = name.upper()
    if "[EUA]" in upper:
        return "EUA"
    return "BR"


def is_ripado(name):
    """Detecta se é conteúdo ripado [RP]."""
    upper = name.upper()
    return "[RP]" in upper or "RIPAGEM" in upper


def extract_ad_range(text):
    """Extrai range de AD. Suporta: [AD196-AD200], [AD11-15], [AD01 ao AD50], [CY01-CY08]."""
    # Full: [AD196- AD200] or [AD01 ao AD50]
    for p in [r"AD\s*(\d+)\s*(?:ao|-)\s*AD\s*(\d+)", r"AD(\d+)\s*-\s*AD(\d+)"]:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return int(m.group(1)), int(m.group(2))
    # Short: [AD11-15]
    m = re.search(r"\[AD(\d+)\s*-\s*(\d+)\]", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    # CY (ripados): [CY01-CY08] or [CY01-08]
    m = re.search(r"CY(\d+)\s*-\s*(?:CY)?(\d+)", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def extract_ld_mld_range(text):
    """Extrai range de Lead ou Microlead. Suporta separadores: -, A, a, ao."""
    # MLD: MLD01-05, MLD 01-05, MLD04 A 13
    m = re.search(r"MLD\s*(\d+)\s*[-aA]\s*(?:MLD)?\s*(\d+)", text)
    if m:
        return "Microlead", int(m.group(1)), int(m.group(2))
    # LD: LD01-05, LD01 A LD03, LD01 a 03
    m = re.search(r"(?<!\w)LD\s*(\d+)\s*[-aA]\s*(?:LD)?\s*(\d+)", text, re.IGNORECASE)
    if m:
        return "Lead", int(m.group(1)), int(m.group(2))
    return None, None, None


def extract_version_range(text):
    """Extrai range de versão."""
    m = re.search(r"\[V(\d+)\s*-\s*V?(\d+)\]", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"\[V(\d+)\]", text)
    if m:
        return int(m.group(1)), int(m.group(1))
    return None, None


def classify_task(name):
    """
    Classifica uma tarefa e retorna: cat, qtd, nicho, mercado, is_rp
    cat: img_novo, img_otim, vid_novo, vid_otim, lead, microlead
    """
    nicho = detect_nicho(name)
    mercado = detect_mercado(name)
    rp = is_ripado(name)

    # MLD/LD
    ld_type, ld_low, ld_high = extract_ld_mld_range(name)
    if ld_type:
        cat = "lead" if ld_type == "Lead" else "microlead"
        qtd = ld_high - ld_low + 1
        return cat, qtd, nicho, mercado, rp

    # AD range
    ad_low, ad_high = extract_ad_range(name)
    ac = (ad_high - ad_low + 1) if ad_low is not None else 0

    # Version range
    v_low, v_high = extract_version_range(name)
    vc = (v_high - v_low + 1) if v_low is not None and v_high is not None else 1

    # Classification
    img = "IMG" in name.upper()
    v1 = v_low == 1 if v_low is not None else False

    if img and v1:
        cat = "img_novo"
    elif img:
        cat = "img_otim"
    elif v1:
        cat = "vid_novo"
    else:
        cat = "vid_otim"

    # Count
    if ac > 0:
        qtd = ac * vc  # AD × Versões
    elif v_low is not None:
        qtd = vc
    else:
        qtd = 1

    return cat, qtd, nicho, mercado, rp


def normalize_person_name(name):
    """Normaliza nomes de pessoas do ClickUp (copywriters, editores).
    REAPER = CASSIO em todos os contextos."""
    if not name:
        return None
    upper = name.strip().upper()
    if upper == "REAPER":
        return "CASSIO"
    return upper


def get_cf_value(task, field_name):
    """Extrai valor de campo customizado do ClickUp."""
    for cf in task.get("custom_fields", []):
        if field_name.lower() in cf.get("name", "").lower():
            opts = cf.get("type_config", {}).get("options", [])
            val = cf.get("value")
            if val is not None:
                for o in opts:
                    if o.get("orderindex") == val:
                        return normalize_person_name(o["name"])
    return None


CAT_LABELS = {
    'img_novo': 'Img Novo', 'img_otim': 'Img Otim',
    'vid_novo': 'Víd Novo', 'vid_otim': 'Víd Otim',
    'lead': 'Lead', 'microlead': 'MLD',
}

CATS = ['img_novo', 'img_otim', 'vid_novo', 'vid_otim', 'lead', 'microlead']
