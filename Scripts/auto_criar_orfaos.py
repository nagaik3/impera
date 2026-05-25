#!/usr/bin/env python3
"""
Auto-criar tarefas para ads orfãos (sem ClickUp match) — IMPERA
Script que identifica ads no RedTrack sem correspondência em ClickUp e cria tarefas automaticamente.

Uso:
  python3 auto_criar_orfaos.py --preview     # mostra sem criar
  python3 auto_criar_orfaos.py --execute     # cria as tarefas
  python3 auto_criar_orfaos.py --top 40      # top 40 ao invés de 38
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.expanduser("~/Scripts"))
from impera_cache import cached_rt_ads, cached_cu_tasks

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

CLICKUP_API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
CLICKUP_LIST_TRAFEGO = "901324476398"

# Mapas de extractores
NICHO_MAP = {
    'EMAGRECIMENTO': 'EM', 'DIABETES': 'DB', 'NEUROPATIA': 'NE',
    'MEMORIA': 'MM', 'PROSTATA': 'PT', 'DORES': 'DA',
    'ZUMBIDO': 'ZB', 'ADULTO': 'ED', 'REJUVENESCIMENTO': 'RJ',
}

FONTE_MAP = {
    'FB': 'FB', 'FACEBOOK': 'FB',
    'GG': 'GG', 'GOOGLE': 'GG',
    'YT': 'YT', 'YOUTUBE': 'YT',
    'TK': 'TK', 'TIKTOK': 'TK',
    'TB': 'TB', 'TABOOLA': 'TB',
    'KW': 'KW', 'KEYWORDS': 'KW',
}

REGIOES = {'BR', 'EUA', '[BR]', '[EUA]'}

# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def normalize_ref_for_matching(ref: str) -> set:
    """
    Retorna variações de um referência para matching flex.
    Ex: CE119 → {CE119, ADCE119}
         C123 → {C123, ADC123}
         AD14 → {AD14, AG14}  (AG = alias de AD para alguns contextos)
    """
    upper = ref.upper()
    variants = {upper}

    # CE <-> ADCE
    if upper.startswith("CE"):
        variants.add(f"ADCE{upper[2:]}")
    elif upper.startswith("ADCE"):
        variants.add(f"CE{upper[4:]}")

    # C <-> ADC (mas não confundir com ranges)
    if re.match(r"^C\d+", upper) and not upper.startswith("CE"):
        variants.add(f"ADC{upper[1:]}")
    elif upper.startswith("ADC") and not upper.startswith("ADCE"):
        variants.add(f"C{upper[3:]}")

    # AG <-> AD (para criativos específicos)
    if upper.startswith("AG"):
        variants.add(f"AD{upper[2:]}")
    elif upper.startswith("AD"):
        # Apenas para AD14, AD18 que sabemos ter aliases AG
        num = upper[2:]
        if num in {"14", "18"}:
            variants.add(f"AG{num}")

    return variants


def is_valid_nomenclature(name: str) -> bool:
    """
    Valida se ad segue padrão de nomenclatura ClickUp.
    Padrões válidos:
    - [NICHO][...] ... AD## [V#]
    - AD## [V#]
    - ## [V#]
    - C## [V#]
    """
    if not name:
        return False

    # Rejeita nomes com caracteres inválidos
    if any(c in name for c in ['{', '}', '—', '–']):
        return False

    # Rejeita se tem "Cópia" ou "Copy" no final (variação manual, não automática)
    if re.search(r'Cópi[ao]|Copy', name, re.IGNORECASE):
        return False

    # Deve ter AD##, AG##, CE##, C##, números, ou variações (ADCE, ADC, CY, etc)
    has_ad_pattern = bool(re.search(r'AD\s*\d+|AG\s*\d+|ADCE?\s*\d+|CY\s*\d+|^\d+\s|C[EYC]?\s*\d+', name, re.IGNORECASE))
    if not has_ad_pattern:
        return False

    return True

def normalize_ad_name(name: str) -> tuple[str, dict]:
    """
    Normaliza nome de ad e extrai metadados.
    Retorna: (nome_normalizado, {nicho, oferta, fonte, regiao, ad_num, versao})
    """
    if not name or not is_valid_nomenclature(name):
        return "", {}

    original = name.strip()
    meta = {
        "nicho": None,
        "oferta": None,
        "fonte": None,
        "regiao": "BR",  # default
    }

    # Extract from [BRACKETS]
    brackets = re.findall(r'\[([^\]]+)\]', original)
    for bracket in brackets:
        upper = bracket.upper()
        # Nicho
        if upper in NICHO_MAP.values():
            meta["nicho"] = upper
        elif any(k in upper for k in NICHO_MAP.keys()):
            for key, val in NICHO_MAP.items():
                if key in upper:
                    meta["nicho"] = val
                    break
        # Fonte
        elif upper in FONTE_MAP:
            meta["fonte"] = FONTE_MAP[upper]
        # Oferta
        elif upper.startswith("OF"):
            meta["oferta"] = upper
        # Região
        elif upper in REGIOES:
            meta["regiao"] = upper.replace('[', '').replace(']', '')

    # Remove brackets e clean
    cleaned = re.sub(r'\[([^\]]+)\]', '', original)
    cleaned = re.sub(r'\s*-+\s*(Cópi[ao]|Copy).*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Extract AD##, AD## V#, etc (inclui variações como ADCE, ADC, CE, etc)
    ad_match = re.search(r'AD\s*(\d+)(?:\s*V(\d+))?', cleaned, re.IGNORECASE)
    if ad_match:
        ad_num = int(ad_match.group(1))
        version = ad_match.group(2)
        cleaned = f"AD{ad_num}" + (f" V{version}" if version else "")
    else:
        # Fallback: tenta CE, ADC, ADCE prefixes
        ce_match = re.search(r'(?:ADCE|ADC|CE|C)\s*(\d+)(?:\s*V(\d+))?', cleaned, re.IGNORECASE)
        if ce_match:
            num = ce_match.group(1)
            version = ce_match.group(2)
            cleaned = f"CE{num}" + (f" V{version}" if version else "")

    # Infer nicho from name (fallback)
    if not meta["nicho"]:
        for key in NICHO_MAP.keys():
            if key in cleaned.upper():
                meta["nicho"] = NICHO_MAP[key]
                break

    # Infer fonte from name (fallback)
    if not meta["fonte"]:
        for key in FONTE_MAP.keys():
            if key in cleaned.upper():
                meta["fonte"] = FONTE_MAP[key]
                break

    return cleaned, meta

def api_post(endpoint, data):
    """POST request to ClickUp API."""
    url = f"https://api.clickup.com/api/v2{endpoint}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", CLICKUP_API_TOKEN)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"  ❌ HTTP {e.code}: {error_body[:200]}")
        return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

def create_task(name: str, description: str = "") -> bool:
    """Create task in ClickUp GESTÃO TRÁFEGO."""
    payload = {
        "name": name,
        "description": description,
        "status": "aguardando teste",
    }

    result = api_post(f"/list/{CLICKUP_LIST_TRAFEGO}/task", payload)
    return result is not None

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    if not CLICKUP_API_TOKEN:
        print("❌ CLICKUP_API_TOKEN não configurado")
        sys.exit(1)

    # Parse args
    preview_mode = "--preview" in sys.argv
    execute_mode = "--execute" in sys.argv
    limit = 38  # default

    for arg in sys.argv:
        if arg.startswith("--top"):
            try:
                limit = int(arg.split()[1]) if " " in arg else int(sys.argv[sys.argv.index(arg) + 1])
            except:
                pass

    print("=" * 80)
    print(f"📋 AUTO-CRIAR TAREFAS PARA ORFÃOS (top {limit})")
    print("=" * 80)

    # Get data
    today = datetime.now().date()
    days_since_monday = today.weekday()
    this_monday = today - timedelta(days=days_since_monday)
    prev_monday = this_monday - timedelta(days=7)
    prev_sunday = prev_monday + timedelta(days=6)
    date_from = prev_monday.strftime('%Y-%m-%d')
    date_to = prev_sunday.strftime('%Y-%m-%d')

    print(f"\n[1/3] Buscando dados RedTrack ({date_from} a {date_to})...")
    rt_data = cached_rt_ads(date_from, date_to)
    rt_ads = rt_data.get("ads", [])
    print(f"  ✓ {len(rt_ads)} ads encontrados")

    print(f"\n[2/3] Buscando tarefas ClickUp...")
    cu_tasks = cached_cu_tasks(CLICKUP_LIST_TRAFEGO, include_closed=True)
    cu_names = set()
    for task in cu_tasks:
        name = task.get("name", "").strip().upper()
        if name:
            cu_names.add(name)
    print(f"  ✓ {len(cu_tasks)} tarefas encontradas")

    print(f"\n[3/3] Identificando orfãos...")
    orphans = []
    for ad in rt_ads:
        rt_ad = ad.get("rt_ad", "").strip()
        if not rt_ad:
            continue

        # Check se existe em ClickUp (exact + variações)
        candidates = [rt_ad.upper(), f"AD{rt_ad}".upper()]

        # Adiciona variações de matching flex (CE <-> ADCE, C <-> ADC, etc)
        base_ref = candidates[0]  # primeira candidato
        for variant in normalize_ref_for_matching(base_ref):
            candidates.append(variant)

        found = False
        for candidate in candidates:
            if any(candidate in cu_name for cu_name in cu_names):
                found = True
                break

        if found:
            continue  # encontrado em ClickUp, skip

        # Extract performance
        revenue = float(ad.get("revenuetype2", 0) or 0) + float(ad.get("revenuetype3", 0) or 0)
        if revenue == 0:
            continue  # skip sem faturamento

        orphans.append({
            "rt_ad": rt_ad,
            "revenue": revenue,
            "cost": float(ad.get("cost", 0) or 0),
            "sales": int(ad.get("convtype4", 0) or 0),
        })

    orphans.sort(key=lambda x: x["revenue"], reverse=True)
    orphans = orphans[:limit]

    print(f"  ✓ {len(orphans)} orfãos identificados (top {limit})")

    # Prepare tasks to create (with validation)
    print(f"\n📝 Validando {len(orphans)} orfãos...")
    print("=" * 80)

    tasks_to_create = []
    filtered_out = []

    for orphan in orphans:
        normalized_name, meta = normalize_ad_name(orphan["rt_ad"])

        # Check if valid
        if not normalized_name:
            filtered_out.append({
                "rt_ad": orphan["rt_ad"],
                "reason": "Nome fora do padrão ClickUp",
                "revenue": orphan["revenue"],
            })
            continue

        # Build task name
        parts = []
        if meta["nicho"]:
            parts.append(f"[{meta['nicho']}]")
        if meta["oferta"]:
            parts.append(f"[{meta['oferta']}]")
        if meta["fonte"]:
            parts.append(f"[{meta['fonte']}]")
        parts.append(normalized_name)

        task_name = "".join(parts)

        # Build description
        description = f"Criada automaticamente como orfã resgatada\nRedTrack: {orphan['rt_ad']}\nRevenue: R$ {orphan['revenue']:,.2f}"

        tasks_to_create.append({
            "name": task_name,
            "description": description,
            "revenue": orphan["revenue"],
            "rt_ad": orphan["rt_ad"],
        })

    # Show valid tasks
    print(f"✅ Válidas: {len(tasks_to_create)}")
    print(f"⚠️  Filtradas: {len(filtered_out)}")
    print("=" * 80)

    if len(tasks_to_create) == 0:
        print("\n❌ Nenhuma tarefa válida para criar")
        return

    print(f"\n📝 Tarefas a criar ({len(tasks_to_create)}):")
    print("=" * 80)
    for i, task_info in enumerate(tasks_to_create, 1):
        print(f"{i:2}. {task_info['name']:50} | R$ {task_info['revenue']:10,.2f}")

    if len(filtered_out) > 0:
        print(f"\n⚠️  FILTRADAS ({len(filtered_out)}) - fora do padrão ClickUp:")
        print("=" * 80)
        for f in filtered_out:
            print(f"  ❌ {f['rt_ad']:35} | R$ {f['revenue']:10,.2f} | Motivo: {f['reason']}")

    print("=" * 80)

    if preview_mode:
        print("\n✅ PREVIEW MODE - nenhuma tarefa foi criada")
        print("Use --execute para criar as tarefas")
        return

    if not execute_mode:
        print("\nUse --execute para criar, ou --preview para ver apenas")
        return

    # Create tasks
    print(f"\n🔧 Criando tarefas no ClickUp...")
    created = 0
    failed = 0

    for i, task_info in enumerate(tasks_to_create, 1):
        print(f"\n[{i}/{len(tasks_to_create)}] {task_info['name'][:60]}...")
        if create_task(task_info["name"], task_info["description"]):
            print(f"  ✅ Criada")
            created += 1
        else:
            print(f"  ❌ Falha")
            failed += 1

        time.sleep(0.5)  # Rate limit

    print("\n" + "=" * 80)
    print(f"✅ CONCLUÍDO")
    print(f"  Criadas: {created}/{len(tasks_to_create)}")
    if failed > 0:
        print(f"  Falhadas: {failed}")
    print(f"  Total faturamento resgatado: R$ {sum(t['revenue'] for t in tasks_to_create):,.2f}")
    print("=" * 80)

if __name__ == "__main__":
    main()
