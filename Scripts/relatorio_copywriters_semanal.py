#!/usr/bin/env python3
"""
Relatório Semanal de Performance por Copywriter — IMPERA PRODUTOS NATURAIS
Gera PDF com atribuição de criativos a copywriters via prefixo + ClickUp.
Crontab: toda segunda-feira às 09:30.

GPDR — Iago Almeida, assistido por Claude
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.expanduser("~/Scripts"))
from impera_cache import cached_rt_ads, cached_cu_tasks

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════
REDTRACK_API_KEY = os.environ.get("REDTRACK_API_KEY", "")
CLICKUP_API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

OUTPUT_DIR = os.path.expanduser("~/Documents")
CLICKUP_LIST_COPY = "901324556390"      # COPY | EDIÇÃO
CLICKUP_LIST_TRAFEGO = "901324476398"   # GESTÃO DE TRÁFEGO (fonte primária)
CLICKUP_LIST_ID = CLICKUP_LIST_COPY     # legado — usado em clickup_search_task individual
COPYWRITER_FIELD_ID = "eeb64866-df57-4dbf-8338-5d4fb58837aa"

# Dropdown mapping: orderindex -> name
COPYWRITER_DROPDOWN = {
    0: "ANA",
    1: "CAROL",
    2: "CRISPIM",
    3: "ELIAS",
    4: "CASSIO",   # Reaper
    5: "YAN",
}

NICHO_MAP = {
    'EMAGRECIMENTO': 'EM', 'DIABETES': 'DB', 'NEUROPATIA': 'NE',
    'MEMORIA': 'MM', 'PROSTATA': 'PT', 'DORES': 'DA',
    'ZUMBIDO': 'ZB', 'ADULTO': 'ED', 'REJUVENESCIMENTO': 'RJ',
    'GELATINAFIT': 'EM', 'GELATINA': 'EM', 'EREMED': 'ED',
}

NICHO_NAMES = {
    'EM': 'Emagrecimento', 'DB': 'Diabetes', 'NE': 'Neuropatia',
    'MM': 'Memoria BR', 'ME': 'Memoria EUA', 'PT': 'Prostata',
    'DA': 'Dores Articulares', 'ED': 'Disfuncao', 'ZB': 'Zumbido',
    'RJ': 'Rejuvenescimento',
}

# ═══════════════════════════════════════════════════════════════
# DATE RANGE
# ═══════════════════════════════════════════════════════════════

def get_previous_week():
    """Return (monday, sunday) of the previous week as YYYY-MM-DD strings."""
    today = datetime.now().date()
    # Last Monday = this Monday - 7 days
    days_since_monday = today.weekday()  # 0=Mon
    this_monday = today - timedelta(days=days_since_monday)
    prev_monday = this_monday - timedelta(days=7)
    prev_sunday = prev_monday + timedelta(days=6)
    return prev_monday.strftime('%Y-%m-%d'), prev_sunday.strftime('%Y-%m-%d')


# ═══════════════════════════════════════════════════════════════
# REDTRACK API
# ═══════════════════════════════════════════════════════════════

def fetch_all_ads(date_from, date_to):
    """Busca ads via cached_rt_ads (group=campaign,rt_ad). Cache compartilhado, rate-limited."""
    rt_data = cached_rt_ads(date_from, date_to)
    return rt_data.get("ads", [])


# ═══════════════════════════════════════════════════════════════
# AD NAME CLEANING
# ═══════════════════════════════════════════════════════════════

def clean_ad_name(name):
    """Strip suffixes like ' - Copia', ' - Copy', ' L', trailing numbers after copies.
    IMPORTANT: Normalize to UPPERCASE for deduplication (644 V9 == 644 v9)"""
    if not name:
        return ""
    cleaned = name.strip()
    # Remove " - Copia", " - Cópia", " - Copy", " -- Copia" (and trailing numbers)
    cleaned = re.sub(r'\s*-{1,2}\s*C[oó]pi[ao](?:\s*\d+)?$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*-{1,2}\s*Copy(?:\s*\d+)?$', '', cleaned, flags=re.IGNORECASE)
    # Remove trailing " L" (lead version)
    cleaned = re.sub(r'\s+L$', '', cleaned)
    # CRITICAL FIX: Normalize case to uppercase (644 v9 → 644 V9)
    cleaned = cleaned.upper()
    return cleaned.strip()


# ═══════════════════════════════════════════════════════════════
# CREATIVE ID EXTRACTION
# ═══════════════════════════════════════════════════════════════

# Patterns for creative identifiers, ordered by specificity
CREATIVE_PATTERNS = [
    # IMG ## or IMG##
    (r'IMG\s*(\d+)', 'IMG'),
    # ADC## (= C## in RT)
    (r'ADC\s*(\d+)', 'ADC'),
    # AD C## -> ADC## (RT bug)
    (r'AD\s+C\s*(\d+)', 'ADC'),
    # CE## (Elias)
    (r'CE\s*(\d+)', 'CE'),
    # CY## (Yan)
    (r'CY\s*(\d+)', 'CY'),
    # CC## (Cassio)
    (r'CC\s*(\d+)', 'CC'),
    # C## (must NOT match CE/CY/CC) — Douglas
    (r'(?<![A-Z])C(\d+)', 'C'),
    # AD## (generic)
    (r'AD\s*(\d+)', 'AD'),
]

def extract_creative_id(ad_name):
    """
    Extract creative identifier and version from ad name.
    Returns (prefix, number, version_str, full_id)
    e.g. ("CE", "15", "V12", "CE15 V12") or ("AD", "63", None, "AD63")
    CRITICAL: Normalizes ADC→C (both are DOUGLAS)
    """
    if not ad_name:
        return None, None, None, None

    upper = ad_name.upper().strip()

    # Try each pattern
    for pattern, prefix in CREATIVE_PATTERNS:
        m = re.search(pattern, upper)
        if m:
            num = m.group(1)
            # Look for version after the match
            after = upper[m.end():]
            version = None
            vm = re.search(r'V\s*(\d+)', after)
            if vm:
                version = f"V{vm.group(1)}"

            # Also check for version embedded: AD63V40 or CE15V12
            embedded = re.search(pattern + r'\s*V(\d+)', upper)
            if embedded and not version:
                version = f"V{embedded.group(2) if embedded.lastindex >= 2 else embedded.group(1)}"

            # CRITICAL FIX #6: Normalize ADC→C (both DOUGLAS prefix)
            # ADC123 and C123 are the same creative, just different naming conventions
            normalized_prefix = 'C' if prefix == 'ADC' else prefix

            full_id = f"{normalized_prefix}{num}"
            if version:
                # Standardize format without spaces for ClickUp matching
                # [AD644V9] in ClickUp vs "AD644 V9" in RedTrack
                full_id = f"{normalized_prefix}{num}{version}"
            return normalized_prefix, num, version, full_id

    return None, None, None, None


def extract_base_creative(prefix, num):
    """Get the base creative (without version) for grouping."""
    if prefix and num:
        return f"{prefix}{num}"
    return None


# ═══════════════════════════════════════════════════════════════
# NICHO EXTRACTION
# ═══════════════════════════════════════════════════════════════

def extract_nicho_from_campaign(campaign_name):
    """Extract nicho code from campaign name."""
    if not campaign_name:
        return '??'
    upper = campaign_name.upper()

    # Special cases
    if 'MEMORIA EUA' in upper or 'MEMÓRIA EUA' in upper:
        return 'ME'
    if 'GELATINAFIT' in upper or 'GELATINA' in upper:
        return 'EM'
    if 'EREMED' in upper:
        return 'ED'
    if 'EMAGRECIMENTOLUDSON' in upper:
        return 'EM'

    # Standard keyword search
    for keyword, sigla in NICHO_MAP.items():
        if keyword in upper:
            return sigla

    # Pattern: [XX] brackets
    for tag in re.findall(r'\[([A-Z]{2,3})\]', campaign_name):
        if tag in NICHO_NAMES:
            return tag

    # Abbreviated patterns: " EM ", " DB ", " NE " etc.
    for code in NICHO_NAMES:
        if re.search(rf'(?:^|\s|[-_/])({code})(?:\s|[-_/]|$)', upper):
            return code

    return '??'


# ═══════════════════════════════════════════════════════════════
# CLICKUP ATTRIBUTION
# ═══════════════════════════════════════════════════════════════

_clickup_cache = {}  # creative_key -> copywriter name


def clickup_search_task(creative_key):
    """Search ClickUp list for a task matching the creative key. Returns copywriter name or None."""
    if creative_key in _clickup_cache:
        return _clickup_cache[creative_key]

    if not CLICKUP_API_TOKEN:
        _clickup_cache[creative_key] = None
        return None

    # Search by task name in the COPY list
    try:
        search_term = creative_key.replace(" ", "%20")
        url = (
            f"https://api.clickup.com/api/v2/list/{CLICKUP_LIST_ID}/task"
            f"?include_closed=true&subtasks=true&page=0"
        )
        req = urllib.request.Request(url)
        req.add_header("Authorization", CLICKUP_API_TOKEN)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        tasks = data.get("tasks", [])

        # Find task matching creative key
        for task in tasks:
            task_name = task.get("name", "").upper()
            # Check if the creative key appears in the task name
            if creative_key.upper() in task_name:
                # Extract copywriter from custom field
                for cf in task.get("custom_fields", []):
                    if cf.get("id") == COPYWRITER_FIELD_ID:
                        val = cf.get("value")
                        if val is not None:
                            cw = COPYWRITER_DROPDOWN.get(val, None)
                            if cw:
                                _clickup_cache[creative_key] = cw
                                return cw
                        break

        _clickup_cache[creative_key] = None
        return None

    except Exception as e:
        print(f"    ClickUp search error for '{creative_key}': {e}")
        _clickup_cache[creative_key] = None
        return None


def clickup_search_by_ad_number(ad_num, version=None):
    """Search ClickUp for AD## or AD##V## pattern."""
    # Try "AD{num}" or "AD{num} V{ver}" or "AD{num}V{ver}"
    keys_to_try = [f"AD{ad_num}"]
    if version:
        keys_to_try.insert(0, f"AD{ad_num} {version}")
        keys_to_try.insert(0, f"AD{ad_num}{version}")

    for key in keys_to_try:
        result = clickup_search_task(key)
        if result:
            return result
    return None


def clickup_batch_search(creative_keys):
    """
    Batch search ClickUp para múltiplos creative keys.
    Usa cached_cu_tasks() — cache compartilhado, evita chamadas duplicadas.
    Busca em GESTÃO TRÁFEGO (primária) e COPY|EDIÇÃO (secundária).
    """
    if not CLICKUP_API_TOKEN:
        return {}

    print("  Buscando tarefas ClickUp (GESTÃO TRÁFEGO + COPY|EDIÇÃO)...")
    trafego_tasks = cached_cu_tasks(CLICKUP_LIST_TRAFEGO, include_closed=True)
    copy_tasks = cached_cu_tasks(CLICKUP_LIST_COPY, include_closed=True)

    # GESTÃO TRÁFEGO tem prioridade (deduplicar por nome)
    seen = set()
    all_tasks = []
    for t in trafego_tasks + copy_tasks:
        name_key = t.get("name", "").strip().upper()
        if name_key not in seen:
            seen.add(name_key)
            all_tasks.append(t)

    print(f"  {len(all_tasks)} tarefas únicas (GT={len(trafego_tasks)}, COPY={len(copy_tasks)})")

    # Build index: task_name_upper -> copywriter
    task_index = {}
    for task in all_tasks:
        task_name = task.get("name", "").upper()
        for cf in task.get("custom_fields", []):
            if cf.get("id") == COPYWRITER_FIELD_ID:
                val = cf.get("value")
                if val is not None:
                    cw = COPYWRITER_DROPDOWN.get(val, None)
                    if cw:
                        task_index[task_name] = cw
                break

    # Match creative keys against tasks
    results = {}
    for key in creative_keys:
        key_upper = key.upper()
        # Try exact substring match
        for task_name, cw in task_index.items():
            if key_upper in task_name:
                results[key] = cw
                _clickup_cache[key] = cw
                break

    return results


# ═══════════════════════════════════════════════════════════════
# COPYWRITER ATTRIBUTION
# ═══════════════════════════════════════════════════════════════

def attribute_copywriter(prefix, num, version, full_id):
    """
    Attribute a creative to a copywriter.
    Rules:
    1. Prefix-based (no version): CE=ELIAS, CY=YAN, CC=CASSIO, C/ADC=DOUGLAS
    2. ClickUp-based: AD## and versioned creatives
    """
    if not prefix:
        return "DESCONHECIDO"

    # Prefix-based attribution for base creatives (no version)
    if prefix == 'CE' and not version:
        return "ELIAS"
    if prefix == 'CY' and not version:
        return "YAN"
    if prefix == 'CC' and not version:
        return "CASSIO"
    if prefix in ('C', 'ADC') and not version:
        return "DOUGLAS"
    if prefix == 'IMG':
        # IMG creatives: check ClickUp
        pass

    # For versioned creatives and AD##, try ClickUp
    # (will be resolved in batch later)
    return None  # Needs ClickUp lookup


# ═══════════════════════════════════════════════════════════════
# MAIN DATA PROCESSING
# ═══════════════════════════════════════════════════════════════

def process_ads(raw_items, campaign_items=None):
    """
    Process raw RedTrack ad data (group=campaign,rt_ad):
    1. Clean names, merge duplicates
    2. Extract creative IDs
    3. Calculate metrics
    Returns list of creative dicts.
    """
    # Step 1: Clean and merge
    # raw_items já vêm de cached_rt_ads() com campos rt_ad e campaign por row
    merged = defaultdict(lambda: {
        'cost': 0, 'front_rev': 0, 'sales': 0, 'original_names': [],
        'campaigns': set(),
    })
    for item in raw_items:
        raw_name = item.get('rt_ad', '') or ''
        if not raw_name or raw_name.strip() == '' or raw_name.strip() == '{ad}':
            continue
        cost = float(item.get('cost', 0) or 0)
        rev2 = float(item.get('revenuetype2', 0) or 0)
        rev3 = float(item.get('revenuetype3', 0) or 0)
        sales = int(float(item.get('convtype4', 0) or 0))  # convtype4 = Vendas CC
        front_rev = rev2 + rev3

        cleaned = clean_ad_name(raw_name)
        if not cleaned:
            continue

        merged[cleaned]['cost'] += cost
        merged[cleaned]['front_rev'] += front_rev
        merged[cleaned]['sales'] += sales
        merged[cleaned]['original_names'].append(raw_name)

        # campaign já está no row (multi-group campaign,rt_ad)
        campaign = item.get('campaign', '') or ''
        if campaign:
            merged[cleaned]['campaigns'].add(campaign)

    # Step 2: Extract creative IDs and build creative list
    creatives = []
    for name, data in merged.items():
        if data['cost'] <= 0 and data['front_rev'] <= 0:
            continue

        prefix, num, version, full_id = extract_creative_id(name)

        # Determine nicho
        # Priority: campaign name extraction, then ad name
        nicho = '??'
        # Try from campaign names first
        for camp in data['campaigns']:
            nicho = extract_nicho_from_campaign(camp)
            if nicho != '??':
                break
        # Last resort: try from the ad name itself
        if nicho == '??':
            nicho = extract_nicho_from_campaign(name)

        roas = data['front_rev'] / data['cost'] if data['cost'] > 0 else 0

        creatives.append({
            'name': name,
            'prefix': prefix,
            'num': num,
            'version': version,
            'full_id': full_id,
            'base_creative': extract_base_creative(prefix, num),
            'cost': data['cost'],
            'front_rev': data['front_rev'],
            'sales': data['sales'],
            'roas': roas,
            'nicho': nicho,
        })

    return creatives


def consolidate_by_base_creative(creatives):
    """
    CRITICAL FIX: Consolidate variants by base creative (AD10 + AD10 V2 + AD10 V30 → single AD10 entry).
    This prevents duplicate counting and provides accurate top 10 ads ranking.
    """
    consolidated = {}  # base_creative or name -> consolidated data

    for c in creatives:
        # Use base_creative if available (AD10 from "AD10 V2"), else use name
        key = c.get('base_creative') or c['name']

        if key not in consolidated:
            consolidated[key] = {
                'name': c.get('base_creative') or c['name'],
                'prefix': c['prefix'],
                'num': c['num'],
                'base_creative': c.get('base_creative'),
                'cost': 0,
                'front_rev': 0,
                'sales': 0,
                'nicho': c['nicho'],
                'variants': [],
                'copywriter': None,  # Will resolve later
            }

        # Aggregate metrics
        consolidated[key]['cost'] += c['cost']
        consolidated[key]['front_rev'] += c['front_rev']
        consolidated[key]['sales'] += c['sales']
        consolidated[key]['variants'].append(c['name'])

        # Use first copywriter found (all variants should have same copywriter)
        if consolidated[key]['copywriter'] is None:
            consolidated[key]['copywriter'] = c.get('copywriter')

    # Calculate ROAS and convert back to list
    result = []
    for key, data in consolidated.items():
        cost = data['cost']
        rev = data['front_rev']
        data['roas'] = rev / cost if cost > 0 else 0
        result.append(data)

    return result


def attribute_all_copywriters(creatives):
    """Attribute copywriters to all creatives."""
    # Phase 1: Prefix-based attribution
    needs_clickup = []
    for c in creatives:
        version = c.get('version')  # May be None in consolidated creatives
        full_id = c.get('full_id')  # May be None in consolidated creatives
        cw = attribute_copywriter(c['prefix'], c['num'], version, full_id)
        c['copywriter'] = cw
        if cw is None:
            needs_clickup.append(c)

    print(f"  Atribuicao por prefixo: {len(creatives) - len(needs_clickup)} criativos")
    print(f"  Pendentes (ClickUp): {len(needs_clickup)} criativos")

    # Phase 2: Batch ClickUp lookup
    if needs_clickup and CLICKUP_API_TOKEN:
        # Collect unique keys to search.
        # Para criativos de geração 2 (ex: full_id="AD644 V9"), adiciona também
        # a forma sem espaço ("AD644V9") porque o ClickUp usa [AD644V9] fundido.
        keys = set()
        for c in needs_clickup:
            full_id = c.get('full_id')
            base_creative = c.get('base_creative')
            if full_id:
                keys.add(full_id)
                # Normaliza "AD644 V9" → "AD644V9" para match no bracket (já feito em extract_creative_id)
                normalized = re.sub(r'(AD\d+)\s+(V\d+)', r'\1\2', full_id, flags=re.IGNORECASE)
                if normalized != full_id:
                    keys.add(normalized)
            if base_creative:
                keys.add(base_creative)
            else:
                # For consolidated creatives without base_creative, try AD{num}
                if c.get('prefix') == 'AD' and c.get('num'):
                    keys.add(f"AD{c['num']}")

        cu_results = clickup_batch_search(list(keys))
        print(f"  ClickUp encontrou: {len(cu_results)} matches")

        for c in needs_clickup:
            if c['copywriter'] is not None:
                continue
            # Try full_id first, then base_creative, then AD{num}
            full_id = c.get('full_id')
            base_creative = c.get('base_creative')
            cw = cu_results.get(full_id) if full_id else None
            if not cw and base_creative:
                cw = cu_results.get(base_creative)
            if not cw and c.get('prefix') == 'AD' and c.get('num'):
                cw = cu_results.get(f"AD{c['num']}")
            c['copywriter'] = cw or "DESCONHECIDO"
    else:
        for c in needs_clickup:
            if c['copywriter'] is None:
                # Fallback: prefix-based for versioned creatives
                if c['prefix'] == 'CE':
                    c['copywriter'] = "ELIAS"
                elif c['prefix'] == 'CY':
                    c['copywriter'] = "YAN"
                elif c['prefix'] == 'CC':
                    c['copywriter'] = "CASSIO"
                elif c['prefix'] in ('C', 'ADC'):
                    c['copywriter'] = "DOUGLAS"
                else:
                    c['copywriter'] = "DESCONHECIDO"

    # Summary
    cw_counts = defaultdict(int)
    for c in creatives:
        cw_counts[c['copywriter']] += 1
    for cw, count in sorted(cw_counts.items(), key=lambda x: -x[1]):
        print(f"    {cw}: {count} criativos")

    return creatives


# ═══════════════════════════════════════════════════════════════
# METRICS AGGREGATION
# ═══════════════════════════════════════════════════════════════

def aggregate_by_copywriter(creatives):
    """Aggregate metrics per copywriter."""
    cw_data = defaultdict(lambda: {
        'cost': 0, 'front_rev': 0, 'sales': 0,
        'creatives': [],
        'nichos': defaultdict(lambda: {'cost': 0, 'front_rev': 0, 'sales': 0, 'count': 0}),
    })

    for c in creatives:
        cw = c['copywriter']
        cw_data[cw]['cost'] += c['cost']
        cw_data[cw]['front_rev'] += c['front_rev']
        cw_data[cw]['sales'] += c['sales']
        cw_data[cw]['creatives'].append(c)

        nicho = c['nicho']
        cw_data[cw]['nichos'][nicho]['cost'] += c['cost']
        cw_data[cw]['nichos'][nicho]['front_rev'] += c['front_rev']
        cw_data[cw]['nichos'][nicho]['sales'] += c['sales']
        cw_data[cw]['nichos'][nicho]['count'] += 1

    # Calculate derived metrics
    results = {}
    for cw, data in cw_data.items():
        cost = data['cost']
        rev = data['front_rev']
        sales = data['sales']
        roas = rev / cost if cost > 0 else 0
        unique = len(data['creatives'])

        # Assertividade
        assert_10 = sum(1 for c in data['creatives'] if c['roas'] >= 1.0 and c['cost'] > 5) / max(1, sum(1 for c in data['creatives'] if c['cost'] > 5)) * 100
        assert_18 = sum(1 for c in data['creatives'] if c['roas'] >= 1.8 and c['cost'] > 5) / max(1, sum(1 for c in data['creatives'] if c['cost'] > 5)) * 100

        # Top 3 by revenue
        top3 = sorted(data['creatives'], key=lambda x: -x['front_rev'])[:3]

        # Nicho breakdown
        nichos_sorted = sorted(data['nichos'].items(), key=lambda x: -x[1]['front_rev'])

        results[cw] = {
            'cost': cost, 'front_rev': rev, 'sales': sales, 'roas': roas,
            'unique_creatives': unique,
            'assert_10': assert_10, 'assert_18': assert_18,
            'top3': top3, 'nichos': nichos_sorted,
            'creatives': data['creatives'],
        }

    return results


# ═══════════════════════════════════════════════════════════════
# PDF GENERATION (reportlab)
# ═══════════════════════════════════════════════════════════════

def generate_pdf(cw_stats, creatives, date_from, date_to, output_path):
    """Generate PDF report using reportlab with IMPERA layout."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm, mm
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, PageBreak
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    # Colors
    GOLD = HexColor("#C8A84E")
    DARK = HexColor("#1A1A1A")
    GRAY_BG = HexColor("#F5F5F0")
    LIGHT_GOLD = HexColor("#FDF6E3")
    GREEN_BG = HexColor("#E8F8F5")
    RED_BG = HexColor("#FDEDEC")
    BLUE_BG = HexColor("#EBF5FB")
    ORANGE_BG = HexColor("#FEF5E7")

    # Styles
    title_style = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=16, textColor=DARK, alignment=TA_CENTER, spaceAfter=2*mm)
    subtitle_style = ParagraphStyle("subtitle", fontName="Helvetica", fontSize=9, textColor=HexColor("#666666"), alignment=TA_CENTER, spaceAfter=4*mm)
    section_style = ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=11, textColor=DARK, spaceBefore=5*mm, spaceAfter=2*mm)
    subsection_style = ParagraphStyle("subsection", fontName="Helvetica-Bold", fontSize=9, textColor=HexColor("#444444"), spaceBefore=3*mm, spaceAfter=1.5*mm)
    note_style = ParagraphStyle("note", fontName="Helvetica-Oblique", fontSize=7.5, textColor=HexColor("#555555"), spaceAfter=2*mm, leading=9)
    sign_style = ParagraphStyle("sign", fontName="Helvetica", fontSize=7, textColor=HexColor("#888888"), alignment=TA_CENTER, spaceBefore=3*mm)

    def make_table(headers, rows, col_widths=None, total_row=True):
        data = [headers] + rows
        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), DARK),
            ('TEXTCOLOR', (0, 0), (-1, 0), GOLD),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7.5),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7.5),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.4, HexColor("#CCCCCC")),
            ('LINEBELOW', (0, 0), (-1, 0), 1, GOLD),
        ]
        for i in range(1, len(data)):
            if i % 2 == 0:
                style_cmds.append(('BACKGROUND', (0, i), (-1, i), GRAY_BG))
        if total_row and rows and rows[-1][0] in ('TOTAL', 'Total'):
            last = len(data) - 1
            style_cmds.append(('FONTNAME', (0, last), (-1, last), 'Helvetica-Bold'))
            style_cmds.append(('BACKGROUND', (0, last), (-1, last), LIGHT_GOLD))
            style_cmds.append(('LINEABOVE', (0, last), (-1, last), 1, GOLD))
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle(style_cmds))
        return t

    def make_profile_table(headers, rows, col_widths=None, accent_color=BLUE_BG):
        data = [headers] + rows
        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), DARK),
            ('TEXTCOLOR', (0, 0), (-1, 0), GOLD),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 1.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.3, HexColor("#CCCCCC")),
            ('LINEBELOW', (0, 0), (-1, 0), 0.8, GOLD),
        ]
        for i in range(1, len(data)):
            if i % 2 == 0:
                style_cmds.append(('BACKGROUND', (0, i), (-1, i), accent_color))
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle(style_cmds))
        return t

    def fmt_money(v):
        """Format money without R$ duplication."""
        return f"R$ {v:,.0f}"

    def fmt_roas(v):
        return f"{v:.2f}"

    # Accent colors per copywriter
    CW_COLORS = {
        'YAN': BLUE_BG, 'CRISPIM': ORANGE_BG, 'DOUGLAS': GREEN_BG,
        'CASSIO': BLUE_BG, 'ELIAS': ORANGE_BG, 'ANA': GRAY_BG,
        'CAROL': GREEN_BG, 'DESCONHECIDO': RED_BG,
    }

    # Build document
    df_str = datetime.strptime(date_from, '%Y-%m-%d').strftime('%d/%m')
    dt_str = datetime.strptime(date_to, '%Y-%m-%d').strftime('%d/%m')
    df_file = datetime.strptime(date_from, '%Y-%m-%d').strftime('%d')
    dt_file = datetime.strptime(date_to, '%Y-%m-%d').strftime('%d')
    month_name = datetime.strptime(date_to, '%Y-%m-%d').strftime('%b %Y').title()

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=1*cm, rightMargin=1*cm,
        topMargin=1*cm, bottomMargin=1.2*cm,
        title=f"Performance Copywriters - {df_str} a {dt_str}"
    )
    w = A4[0] - 2*cm
    elements = []

    # ── HEADER ──
    elements.append(Paragraph("PERFORMANCE INDIVIDUAL", title_style))
    elements.append(Paragraph(
        f"Copywriters — Semana {df_str} a {dt_str} — IMPERA Produtos Naturais",
        subtitle_style
    ))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=GOLD, spaceAfter=4*mm))

    # ── TOTALS ──
    total_cost = sum(s['cost'] for s in cw_stats.values())
    total_rev = sum(s['front_rev'] for s in cw_stats.values())
    total_sales = sum(s['sales'] for s in cw_stats.values())
    total_roas = total_rev / total_cost if total_cost > 0 else 0
    total_unique = sum(s['unique_creatives'] for s in cw_stats.values())

    # Coverage (vs all creatives including DESCONHECIDO)
    known_cost = sum(s['cost'] for cw, s in cw_stats.items() if cw != 'DESCONHECIDO')
    coverage = known_cost / total_cost * 100 if total_cost > 0 else 0

    elements.append(Paragraph("1. Resumo Geral", section_style))
    kpi_h = ['Fat. Front Total', 'Custo Total', 'ROAS Geral', 'Vendas', 'Criativos Unicos', 'Cobertura']
    kpi_r = [[fmt_money(total_rev), fmt_money(total_cost), fmt_roas(total_roas),
              str(total_sales), str(total_unique), f"{coverage:.1f}%"]]
    cw_kpi = [w*0.18, w*0.16, w*0.12, w*0.12, w*0.17, w*0.13]
    elements.append(make_table(kpi_h, kpi_r, cw_kpi, total_row=False))

    # ── RANKING ──
    elements.append(Paragraph("2. Ranking por Faturamento", section_style))
    ranked = sorted(
        [(cw, s) for cw, s in cw_stats.items() if cw != 'DESCONHECIDO'],
        key=lambda x: -x[1]['front_rev']
    )

    rank_h = ['#', 'Copywriter', 'Fat. Front', 'Custo', 'ROAS', 'Vendas', 'Criativos', 'Assert. >=1.0', 'Assert. >=1.8']
    rank_r = []
    for i, (cw, s) in enumerate(ranked, 1):
        rank_r.append([
            str(i), cw,
            fmt_money(s['front_rev']), fmt_money(s['cost']),
            fmt_roas(s['roas']), str(s['sales']),
            str(s['unique_creatives']),
            f"{s['assert_10']:.1f}%", f"{s['assert_18']:.1f}%",
        ])
    rank_r.append([
        'TOTAL', '',
        fmt_money(total_rev), fmt_money(total_cost),
        fmt_roas(total_roas), str(total_sales),
        str(total_unique), '', '',
    ])
    cw_rank = [w*0.04, w*0.12, w*0.14, w*0.13, w*0.08, w*0.09, w*0.10, w*0.13, w*0.13]
    elements.append(make_table(rank_h, rank_r, cw_rank))

    # Participation table
    elements.append(Spacer(1, 2*mm))
    part_h = ['Copywriter', '% Faturamento', 'ROAS', 'Assert. >=1.0', 'Criativos']
    part_r = []
    for cw, s in ranked:
        pct = s['front_rev'] / total_rev * 100 if total_rev > 0 else 0
        part_r.append([cw, f"{pct:.1f}%", fmt_roas(s['roas']), f"{s['assert_10']:.1f}%", str(s['unique_creatives'])])
    cw_part = [w*0.18, w*0.18, w*0.14, w*0.18, w*0.14]
    elements.append(make_table(part_h, part_r, cw_part, total_row=False))

    elements.append(PageBreak())

    # ── INDIVIDUAL PROFILES ──
    elements.append(Paragraph("3. Perfis Individuais", ParagraphStyle(
        "sec_top", fontName="Helvetica-Bold", fontSize=12, textColor=DARK, spaceAfter=2*mm
    )))
    elements.append(HRFlowable(width="100%", thickness=1, color=GOLD, spaceAfter=2*mm))

    for rank_idx, (cw, s) in enumerate(ranked, 1):
        if rank_idx > 1:
            elements.append(Spacer(1, 2*mm))
            elements.append(HRFlowable(width="60%", thickness=0.4, color=HexColor("#DDDDDD"), spaceAfter=1*mm))

        pct_total = s['front_rev'] / total_rev * 100 if total_rev > 0 else 0
        accent = CW_COLORS.get(cw, GRAY_BG)

        # Header
        elements.append(Paragraph(
            f"#{rank_idx} {cw} — {fmt_money(s['front_rev'])} ({pct_total:.1f}% do faturamento total)",
            section_style
        ))

        # KPI row
        kpi_h2 = ['Fat. Front', 'Custo', 'ROAS', 'Vendas', 'Criativos', 'Assert. >=1.0', 'Assert. >=1.8']
        kpi_r2 = [[
            fmt_money(s['front_rev']), fmt_money(s['cost']),
            fmt_roas(s['roas']), str(s['sales']),
            str(s['unique_creatives']),
            f"{s['assert_10']:.1f}%", f"{s['assert_18']:.1f}%",
        ]]
        cw_kpi2 = [w*0.15, w*0.14, w*0.09, w*0.10, w*0.12, w*0.14, w*0.14]
        elements.append(make_profile_table(kpi_h2, kpi_r2, cw_kpi2, accent))

        # Nicho breakdown
        elements.append(Spacer(1, 1.5*mm))
        n_h = ['Nicho', 'Custo', 'Fat. Front', 'ROAS', 'Vendas']
        n_rows = []
        for nicho_code, nicho_data in s['nichos']:
            nicho_name = NICHO_NAMES.get(nicho_code, nicho_code)
            n_roas = nicho_data['front_rev'] / nicho_data['cost'] if nicho_data['cost'] > 0 else 0
            n_rows.append([
                nicho_name,
                fmt_money(nicho_data['cost']),
                fmt_money(nicho_data['front_rev']),
                fmt_roas(n_roas),
                str(nicho_data['sales']),
            ])
        if n_rows:
            cw_n = [w*0.25, w*0.18, w*0.20, w*0.12, w*0.13]
            elements.append(make_profile_table(n_h, n_rows, cw_n, accent))

        # Top 3 creatives
        elements.append(Spacer(1, 1.5*mm))
        t_h = ['#', 'Criativo', 'Nicho', 'Fat. Front', 'ROAS', 'Vendas']
        t_rows = []
        for ti, tc in enumerate(s['top3'], 1):
            nicho_name = NICHO_NAMES.get(tc['nicho'], tc['nicho'])
            t_rows.append([
                str(ti),
                tc['name'][:30],
                nicho_name,
                fmt_money(tc['front_rev']),
                fmt_roas(tc['roas']),
                str(tc['sales']),
            ])
        if t_rows:
            cw_t = [w*0.05, w*0.30, w*0.15, w*0.18, w*0.10, w*0.12]
            elements.append(make_profile_table(t_h, t_rows, cw_t, accent))

        # Page break every 2 profiles (after 2nd, 4th, etc.)
        if rank_idx % 2 == 0 and rank_idx < len(ranked):
            elements.append(PageBreak())

    # ── NOTAS METODOLOGICAS ──
    elements.append(Spacer(1, 4*mm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#CCCCCC"), spaceAfter=2*mm))
    elements.append(Paragraph("Notas Metodologicas", subsection_style))

    notas = [
        "Front Revenue = revenuetype2 + revenuetype3 (RedTrack). ROAS = Front Revenue / Cost.",
        "Assertividade >=1.0 = % de criativos com ROAS breakeven ou superior. >=1.8 = % validados. Apenas criativos com custo > R$5.",
        "Atribuicao: C## = Douglas (ripagem). CE## = Elias. CY## = Yan. CC## = Cassio. "
        "Versoes (V2, V3...) e AD## = copywriter no campo ClickUp da tarefa correspondente.",
        "Copias em ads manager (Copia, Copy, L) foram unificadas no criativo pai.",
        f"Cobertura: {coverage:.1f}% do custo total ({fmt_money(known_cost)} de {fmt_money(total_cost)}) foi atribuido com sucesso.",
    ]
    for i, n in enumerate(notas, 1):
        elements.append(Paragraph(f"{i}. {n}", note_style))

    # ── ASSINATURA ──
    elements.append(Spacer(1, 5*mm))
    elements.append(HRFlowable(width="40%", thickness=0.5, color=HexColor("#CCCCCC"), spaceAfter=2*mm))
    elements.append(Paragraph("Desenvolvido por", sign_style))
    elements.append(Paragraph(
        "<b>GPDR — Iago Almeida</b>",
        ParagraphStyle("sn", fontName="Helvetica-Bold", fontSize=8, textColor=DARK, alignment=TA_CENTER)
    ))
    elements.append(Paragraph("Gestao de Performance e Dados em Resultados", sign_style))
    elements.append(Paragraph("IMPERA Produtos Naturais", sign_style))
    elements.append(Spacer(1, 2*mm))
    elements.append(Paragraph("Assistido por Claude — Anthropic", sign_style))
    elements.append(Paragraph(f"v2.0 — {datetime.now().strftime('%d/%m/%Y')}", sign_style))

    doc.build(elements)
    print(f"  PDF gerado: {output_path}")


# ═══════════════════════════════════════════════════════════════
# TELEGRAM NOTIFICATION
# ═══════════════════════════════════════════════════════════════

def send_telegram(msg):
    """Send notification via Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("  Telegram nao configurado, pulando notificacao.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    body = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True
    except Exception as e:
        print(f"  [ERRO] Telegram: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("RELATORIO SEMANAL - PERFORMANCE COPYWRITERS")
    print(f"Executado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 60)

    if not REDTRACK_API_KEY:
        print("ERRO: REDTRACK_API_KEY nao configurado")
        sys.exit(1)

    # 1. Date range
    date_from, date_to = get_previous_week()
    print(f"\nPeriodo: {date_from} a {date_to}")

    # 2. Fetch RedTrack data (group=campaign,rt_ad — cache compartilhado)
    print("\n[1/4] Buscando dados RedTrack (rt_ad via cached_rt_ads)...")
    try:
        raw_ads = fetch_all_ads(date_from, date_to)
        print(f"  {len(raw_ads)} registros de ads encontrados")
    except Exception as e:
        print(f"ERRO RedTrack: {e}")
        sys.exit(1)

    if not raw_ads:
        print("Nenhum dado encontrado no RedTrack para o periodo.")
        sys.exit(0)

    # 3. Process and clean (campaign já vem no row via multi-group)
    print("\n[2/4] Processando e limpando nomes de ads...")
    creatives = process_ads(raw_ads)
    print(f"  {len(creatives)} criativos unicos apos merge")

    # 3.5 CRITICAL FIX: Consolidate by base creative (AD10 + variants → single entry)
    print("\n[2.5/4] Consolidando variantes por criativo-base...")
    creatives_before = len(creatives)
    creatives = consolidate_by_base_creative(creatives)
    print(f"  Consolidado: {creatives_before} → {len(creatives)} criativos unicos")

    # 4. Attribute copywriters
    print("\n[3/4] Atribuindo copywriters...")
    creatives = attribute_all_copywriters(creatives)

    # 5. Aggregate
    cw_stats = aggregate_by_copywriter(creatives)

    # 6. Generate PDF
    print("\n[4/4] Gerando PDF...")
    df_label = datetime.strptime(date_from, '%Y-%m-%d').strftime('%d')
    dt_label = datetime.strptime(date_to, '%Y-%m-%d').strftime('%d')
    month_label = datetime.strptime(date_to, '%Y-%m-%d').strftime('%b').lower()

    output_name = f"Performance Copywriters - {df_label} a {dt_label} {month_label}.pdf"
    output_path = os.path.join(OUTPUT_DIR, output_name)
    latest_path = os.path.join(OUTPUT_DIR, "Performance Copywriters - Latest.pdf")

    try:
        generate_pdf(cw_stats, creatives, date_from, date_to, output_path)

        # Also save as "Latest"
        import shutil
        shutil.copy2(output_path, latest_path)
        print(f"  Copia salva: {latest_path}")
    except Exception as e:
        print(f"ERRO ao gerar PDF: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # 7. Summary
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)

    total_cost = sum(s['cost'] for s in cw_stats.values())
    total_rev = sum(s['front_rev'] for s in cw_stats.values())
    total_roas = total_rev / total_cost if total_cost > 0 else 0

    ranked = sorted(
        [(cw, s) for cw, s in cw_stats.items() if cw != 'DESCONHECIDO'],
        key=lambda x: -x[1]['front_rev']
    )
    for i, (cw, s) in enumerate(ranked, 1):
        pct = s['front_rev'] / total_rev * 100 if total_rev > 0 else 0
        print(f"  #{i} {cw}: R$ {s['front_rev']:,.0f} ({pct:.1f}%) | ROAS {s['roas']:.2f} | {s['unique_creatives']} criativos")

    print(f"\n  TOTAL: R$ {total_rev:,.0f} | ROAS {total_roas:.2f}")
    print(f"  PDF: {output_path}")

    # 8. Telegram notification
    df_str = datetime.strptime(date_from, '%Y-%m-%d').strftime('%d/%m')
    dt_str = datetime.strptime(date_to, '%Y-%m-%d').strftime('%d/%m')

    msg_lines = [
        f"<b>Performance Copywriters - {df_str} a {dt_str}</b>\n",
    ]
    for i, (cw, s) in enumerate(ranked, 1):
        pct = s['front_rev'] / total_rev * 100 if total_rev > 0 else 0
        msg_lines.append(
            f"#{i} <b>{cw}</b>: R$ {s['front_rev']:,.0f} ({pct:.0f}%) | ROAS {s['roas']:.2f} | {s['unique_creatives']} criativos"
        )
    msg_lines.append(f"\nTotal: R$ {total_rev:,.0f} | ROAS {total_roas:.2f}")
    msg_lines.append(f"PDF salvo em ~/Documents/")

    send_telegram("\n".join(msg_lines))

    print("\nConcluido!")


if __name__ == "__main__":
    main()
