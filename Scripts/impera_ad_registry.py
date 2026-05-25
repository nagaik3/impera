#!/usr/bin/env python3
"""
Registry Central de ADs — Mapa consolidado de todos os creatives do ClickUp

Este módulo:
1. Varre TODAS as tarefas (COPY + TRAFEGO, abertas + fechadas)
2. Extrai e indexa TODOS os AD numbers
3. Explode ranges: [AD100-AD110] → 100, 101, ..., 110 (cada um com copywriter)
4. Trata RIP prefixes: CE##→ELIAS, CY##→YAN, CC##→CASSIO
5. Persiste em ~/Scripts/data/ad_registry.json para reutilização

Uso:
    from impera_ad_registry import get_or_build_registry, lookup_ad

    registry = get_or_build_registry()
    result = lookup_ad(101, registry, context_campaign="[FB] - BR - MM")
    print(result)  # {copywriter: "ELIAS", confidence: 1.0, method: "direct"}
"""

import sys
import os
import json
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/Scripts"))

from impera_cache import cached_cu_tasks
from impera_utils import get_cf_value, normalize_person_name, detect_nicho, extract_ad_range
from fetch_redtrack_com_copywriter_ultimate import extract_ad_number

# Constants
COPY_LIST = "901324556390"
TRAFEGO_LIST = "901324476398"
REGISTRY_PATH = os.path.expanduser("~/Scripts/data/ad_registry.json")

# RIP Prefix mappings (from cruzamento_por_criativo)
RIP_PREFIXES = {
    "CE": "ELIAS",
    "CY": "YAN",
    "CC": "CASSIO",
}


def extract_ad_numbers(task_name: str) -> List[int]:
    """
    Extrai TODOS os AD numbers de uma tarefa, incluindo ranges explodidos.

    Exemplos:
      "[MM][BR][OF01][FB][AD101][V1]" → [101]
      "[MM][BR][OF01][FB][AD101V1][V1-V12]" → [101]
      "[MM][BR][OF01][FB][AD100-AD110][V1]" → [100, 101, ..., 110]
      "[MM][BR][OF01][FB][CE119][V1]" → [119] (com RIP mapeamento)
      "[EM][OF02][FB] AD644 V128" → [644]
    """
    ads = set()

    # Strategy 1a: Direct [AD###] pattern (exact)
    pattern_direct = r'\[AD(\d+)\]'
    matches = re.findall(pattern_direct, task_name)
    ads.update(int(m) for m in matches)

    # Strategy 1b: Direct with variant [AD###V#] pattern (e.g., [AD101V1])
    pattern_direct_variant = r'\[AD(\d+)V\d+\]'
    matches = re.findall(pattern_direct_variant, task_name)
    ads.update(int(m) for m in matches)

    # Strategy 2: Range [AD###-AD###]
    pattern_range = r'\[AD(\d+)-AD(\d+)\]'
    ranges = re.findall(pattern_range, task_name)
    for low, high in ranges:
        ads.update(range(int(low), int(high) + 1))

    # Strategy 3: Bare AD### (without brackets)
    pattern_bare = r'\bAD(\d+)\b'
    matches = re.findall(pattern_bare, task_name)
    # Filter out false positives (only if not already in brackets)
    for m in matches:
        if f"[AD{m}]" not in task_name and f"[AD{m}V" not in task_name and f"AD{m}-" not in task_name:
            ads.add(int(m))

    # Strategy 4: RIP Prefixes (CE###, CY###, CC###)
    for prefix, _ in RIP_PREFIXES.items():
        pattern_rip = rf'\[{prefix}(\d+)\]'
        matches = re.findall(pattern_rip, task_name)
        ads.update(int(m) for m in matches)

        # Also bare prefix (without brackets)
        pattern_rip_bare = rf'\b{prefix}(\d+)\b'
        matches = re.findall(pattern_rip_bare, task_name)
        for m in matches:
            if f"[{prefix}{m}]" not in task_name:
                ads.add(int(m))

    return sorted(list(ads))


def get_rip_copywriter(task_name: str) -> Optional[str]:
    """
    Se a tarefa tem um RIP prefix, retorna o copywriter fixo (ELIAS/YAN/CASSIO).
    Senão, retorna None.
    """
    for prefix, cw in RIP_PREFIXES.items():
        if re.search(rf'\[{prefix}\d+\]|\b{prefix}\d+\b', task_name):
            return cw
    return None


def resolve_task_conflict(candidates: List[Dict]) -> Dict:
    """
    Resolve conflicts quando há múltiplas tarefas diretas para o mesmo AD.

    Estratégia:
    1. Se há uma maioria clara, use a maioria
    2. Senão, use a tarefa mais recente
    3. Entre tarefas antigas, use a de maior confiança

    Args:
        candidates: Lista de task_info dicts (todos diretos, não ranges)

    Returns:
        Dict com a tarefa escolhida
    """
    # Contar quantas vezes cada copywriter aparece
    cw_counts = defaultdict(int)
    cw_tasks = defaultdict(list)

    for candidate in candidates:
        cw = candidate["copywriter"] or "Desconhecido"
        cw_counts[cw] += 1
        cw_tasks[cw].append(candidate)

    # Se há uma maioria clara (>50%), usar
    total = len(candidates)
    if total > 0:
        # Ordenar por contagem
        sorted_cws = sorted(cw_counts.items(), key=lambda x: x[1], reverse=True)
        top_cw, top_count = sorted_cws[0]

        if top_count > total * 0.5:
            # Maioria clara - usar a mais recente da maioria
            majority_tasks = cw_tasks[top_cw]
            majority_tasks.sort(key=lambda x: x["date_created"], reverse=True)
            return majority_tasks[0]

    # Sem maioria clara - usar a mais recente
    candidates.sort(key=lambda x: x["date_created"], reverse=True)
    return candidates[0]


def build_registry(include_closed: bool = True) -> Dict:
    """
    Constrói o registry consolidado a partir de TODAS as tarefas do ClickUp.

    Estratégia de conflito resolver:
    1. Tarefas específicas (sem ranges) SEMPRE vencem ranges
    2. Entre múltiplas tarefas específicas, contar quantas cada copywriter tem (maioria vence)
    3. Usar tarefa mais recente como tiebreaker
    4. Ranges: prefer tarefas com copywriter preenchido

    Returns: {
        "generated_at": iso_str,
        "ads": {
            "101": {
                "copywriter": "ELIAS",
                "nicho": "MM",
                "task_id": "86ah...",
                "task_name": "[MM][BR][OF01][FB][AD101][V1]",
                "source": "direct" | "range_expansion" | "rip_prefix",
                "confidence": 1.0 | 0.9 | 0.85
            },
            ...
        },
        "stats": {
            "total_tasks_scanned": 850,
            "total_ads_indexed": 620,
            "direct": 420,
            "range_expanded": 160,
            "rip_prefix": 40,
            "with_copywriter": 590,
            "missing_copywriter": 30
        }
    }
    """
    print("🔨 Construindo registry de ADs (com conflict resolution)...")

    # Fase 1: Coletar TODAS as tarefas para cada AD
    ads_tasks = defaultdict(list)  # {ad_num: [task_info, ...]}

    stats = {
        "total_tasks_scanned": 0,
        "total_ads_indexed": 0,
        "direct": 0,
        "range_expanded": 0,
        "rip_prefix": 0,
        "with_copywriter": 0,
        "missing_copywriter": 0,
    }

    # Fetch both lists
    print("  Carregando COPY list...")
    copy_tasks = cached_cu_tasks(COPY_LIST, include_closed=include_closed)

    print("  Carregando TRAFEGO list...")
    trafego_tasks = cached_cu_tasks(TRAFEGO_LIST, include_closed=include_closed)

    all_tasks = copy_tasks + trafego_tasks
    stats["total_tasks_scanned"] = len(all_tasks)
    print(f"  Total tarefas: {len(all_tasks)}")

    # Process each task to collect AD candidates
    for task in all_tasks:
        task_name = task.get("name", "")
        task_id = task.get("id", "")

        # Skip tasks that don't start with brackets (not in standard format)
        if not task_name.startswith("["):
            continue

        # Extract all AD numbers from this task
        ad_numbers = extract_ad_numbers(task_name)

        if not ad_numbers:
            continue

        # Get copywriter from custom field
        cf_copywriter = get_cf_value(task, "copywritter")
        cf_copywriter = normalize_person_name(cf_copywriter) if cf_copywriter else None

        # Check for RIP prefix (takes precedence)
        rip_copywriter = get_rip_copywriter(task_name)

        # Determine actual copywriter
        copywriter = rip_copywriter or cf_copywriter

        # Get nicho
        nicho = detect_nicho(task_name)

        # Get date_created for recency tiebreaker
        date_created = task.get("date_created", 0)

        # Determine source
        is_range = len(ad_numbers) > 1
        is_rip = rip_copywriter is not None

        if is_rip:
            source = "rip_prefix"
            confidence = 0.85
            stats["rip_prefix"] += 1
        elif is_range:
            source = "range_expansion"
            confidence = 0.9
            stats["range_expanded"] += 1
        else:
            source = "direct"
            confidence = 1.0 if copywriter else 0.7
            stats["direct"] += 1

        if copywriter:
            stats["with_copywriter"] += 1
        else:
            stats["missing_copywriter"] += 1

        # Store ALL candidates for each AD (for conflict resolution)
        task_info = {
            "copywriter": copywriter,
            "nicho": nicho,
            "task_id": task_id,
            "task_name": task_name,
            "source": source,
            "confidence": confidence,
            "is_range": is_range,
            "date_created": date_created,
        }

        for ad_num in ad_numbers:
            ads_tasks[ad_num].append(task_info)
            stats["total_ads_indexed"] += 1

    # Fase 2: Resolver conflitos - escolher a melhor tarefa para cada AD
    print("  Resolvendo conflitos...")
    ads_map = {}

    for ad_num in ads_tasks:
        candidates = ads_tasks[ad_num]

        # Estratégia 1: Preferir tarefas diretas (não ranges)
        direct_candidates = [c for c in candidates if not c["is_range"]]

        if direct_candidates:
            # Há tarefas diretas - usar conflicto resolution entre elas
            chosen = resolve_task_conflict(direct_candidates)
        else:
            # Só tem ranges - usar o de maior confiança, depois mais recente
            best = max(candidates, key=lambda x: (x["confidence"], x["date_created"]))
            chosen = best

        ads_map[str(ad_num)] = {
            "copywriter": chosen["copywriter"],
            "nicho": chosen["nicho"],
            "task_id": chosen["task_id"],
            "task_name": chosen["task_name"],
            "source": chosen["source"],
            "confidence": chosen["confidence"],
        }

    # Build final registry
    registry = {
        "generated_at": datetime.now().isoformat(),
        "ads": ads_map,
        "stats": stats,
    }

    print(f"\n✅ Registry construído!")
    print(f"  Total ADs indexados: {stats['total_ads_indexed']}")
    print(f"    Direct: {stats['direct']} ({100*stats['direct']/max(stats['total_ads_indexed'],1):.1f}%)")
    print(f"    Range expanded: {stats['range_expanded']} ({100*stats['range_expanded']/max(stats['total_ads_indexed'],1):.1f}%)")
    print(f"    RIP prefix: {stats['rip_prefix']} ({100*stats['rip_prefix']/max(stats['total_ads_indexed'],1):.1f}%)")
    print(f"  Com copywriter: {stats['with_copywriter']} ({100*stats['with_copywriter']/max(stats['total_ads_indexed'],1):.1f}%)")

    return registry


def save_registry(registry: Dict) -> None:
    """Salva registry em ~/Scripts/data/ad_registry.json"""
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)
    print(f"💾 Registry salvo: {REGISTRY_PATH}")


def load_registry() -> Optional[Dict]:
    """Carrega registry de ~/Scripts/data/ad_registry.json"""
    if not os.path.exists(REGISTRY_PATH):
        return None
    try:
        with open(REGISTRY_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Erro ao carregar registry: {e}")
        return None


def get_or_build_registry(max_age_hours: int = 4) -> Dict:
    """
    Carrega registry do disco se existente e < max_age_hours.
    Caso contrário, reconstrói e salva.
    """
    registry = load_registry()

    if registry:
        generated_at = datetime.fromisoformat(registry.get("generated_at", ""))
        age = datetime.now() - generated_at

        if age < timedelta(hours=max_age_hours):
            print(f"📦 Registry carregado do cache (age: {age.total_seconds():.0f}s)")
            return registry

    print(f"🔄 Registry desatualizado ou não existe. Reconstruindo...")
    registry = build_registry(include_closed=True)
    save_registry(registry)

    return registry


def lookup_ad(ad_num: int, registry: Dict, context_campaign: Optional[str] = None) -> Dict:
    """
    Busca um AD no registry e retorna informações do copywriter.

    Args:
        ad_num: Número do AD (ex: 101)
        registry: Dict do registry
        context_campaign: Nome da campanha (não usado por enquanto, placeholder para estratégia 3)

    Returns: {
        "copywriter": "ELIAS" | "Desconhecido",
        "confidence": float,
        "method": "direct" | "range" | "rip" | "not_found"
    }
    """
    ad_str = str(ad_num)

    if ad_str in registry.get("ads", {}):
        ad_info = registry["ads"][ad_str]
        return {
            "copywriter": ad_info.get("copywriter") or "Desconhecido",
            "confidence": ad_info.get("confidence", 0.0),
            "method": ad_info.get("source", "unknown"),
        }

    return {
        "copywriter": "Desconhecido",
        "confidence": 0.0,
        "method": "not_found",
    }


def main():
    """CLI: mostra stats do registry"""
    import argparse

    parser = argparse.ArgumentParser(description="AD Registry Manager")
    parser.add_argument("--rebuild", action="store_true", help="Força rebuild do registry")
    parser.add_argument("--stats", action="store_true", help="Mostra stats do registry")
    args = parser.parse_args()

    if args.rebuild:
        registry = build_registry(include_closed=True)
        save_registry(registry)
    else:
        registry = get_or_build_registry(max_age_hours=4)

    if args.stats or True:  # Always show stats
        stats = registry.get("stats", {})
        print("\n" + "="*60)
        print("📊 AD REGISTRY STATISTICS")
        print("="*60)
        print(f"Generated: {registry.get('generated_at', 'unknown')}")
        print(f"\nTasks scanned: {stats.get('total_tasks_scanned', 0)}")
        print(f"ADs indexed: {stats.get('total_ads_indexed', 0)}")
        print(f"  - Direct: {stats.get('direct', 0)}")
        print(f"  - Range expanded: {stats.get('range_expanded', 0)}")
        print(f"  - RIP prefix: {stats.get('rip_prefix', 0)}")
        print(f"\nCopywriter data:")
        print(f"  - With copywriter: {stats.get('with_copywriter', 0)}")
        print(f"  - Missing copywriter: {stats.get('missing_copywriter', 0)}")
        print("="*60 + "\n")


if __name__ == "__main__":
    main()
