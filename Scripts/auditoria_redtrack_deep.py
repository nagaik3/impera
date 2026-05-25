#!/usr/bin/env python3
"""
Auditoria Profunda: RedTrack ↔ ClickUp Matching System

Este script executa uma auditoria completa da taxa de confiança no cruzamento
de dados RedTrack com ClickUp usando o AD Registry.

Uso:
  python3 auditoria_redtrack_deep.py              # Auditoria últimos 7 dias
  python3 auditoria_redtrack_deep.py --period 14  # Últimos 14 dias
  python3 auditoria_redtrack_deep.py --date-from 2026-05-01 --date-to 2026-05-31

Output:
  - Taxa de matching global e por estratégia
  - Faturamento atribuído por copywriter
  - Análise de órfãos
  - Validação de confiança
"""

import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/Scripts"))

from impera_cache import cached_rt_adgroups
from impera_ad_registry import get_or_build_registry, lookup_ad
from fetch_redtrack_com_copywriter_ultimate import extract_ad_number
from cruzamento_clickup_redtrack import parse_campaign_name


def run_deep_audit(date_from: str, date_to: str):
    """Executa auditoria profunda."""
    print("=" * 70)
    print("🔍 AUDITORIA PROFUNDA: RedTrack ↔ ClickUp Matching System")
    print("=" * 70)
    print(f"\n📅 Período: {date_from} a {date_to}\n")

    # Construir/carregar registry
    print("📦 Carregando AD Registry...")
    registry = get_or_build_registry(max_age_hours=4)
    registry_stats = registry.get("stats", {})

    print(f"\n📊 REGISTRY DE ADs:")
    print(f"   Total tarefas varridas: {registry_stats.get('total_tasks_scanned', 0):,}")
    print(f"   ADs indexados: {registry_stats.get('total_ads_indexed', 0):,}")
    print(f"     - Direct: {registry_stats.get('direct', 0):,} ({100*registry_stats.get('direct', 0)/max(registry_stats.get('total_ads_indexed', 1), 1):.1f}%)")
    print(f"     - Range expanded: {registry_stats.get('range_expanded', 0):,} ({100*registry_stats.get('range_expanded', 0)/max(registry_stats.get('total_ads_indexed', 1), 1):.1f}%)")
    print(f"     - RIP prefix: {registry_stats.get('rip_prefix', 0):,} ({100*registry_stats.get('rip_prefix', 0)/max(registry_stats.get('total_ads_indexed', 1), 1):.1f}%)")
    print(f"   Com copywriter: {registry_stats.get('with_copywriter', 0):,} ({100*registry_stats.get('with_copywriter', 0)/max(registry_stats.get('total_ads_indexed', 1), 1):.1f}%)")

    # Buscar dados RedTrack
    print(f"\n📡 Carregando RedTrack data...")
    adgroup_data = cached_rt_adgroups(date_from, date_to)
    adgroups = adgroup_data.get("adgroups", [])
    print(f"   Total de adgroups: {len(adgroups):,}")

    # Processar matching
    print(f"\n🔄 Processando matching (3 estratégias em cascata)...\n")

    stats = {
        "total": len(adgroups),
        "direct": 0,
        "range": 0,
        "rip": 0,
        "found": 0,
        "not_found": 0,
        "confidence_1_0": 0,
        "confidence_0_9": 0,
        "confidence_0_85": 0,
        "confidence_0_0": 0,
    }

    fat_por_cw = defaultdict(lambda: {
        "faturamento": 0.0,
        "custo": 0.0,
        "vendas": 0,
        "ads": set(),
        "count": 0,
        "avg_confidence": 0.0,
        "confidence_sum": 0.0,
    })

    orphans = []

    for row in adgroups:
        rt_adgroup = row.get("rt_adgroup", "")
        campaign = row.get("campaign", "")

        ad_num = extract_ad_number(rt_adgroup)

        if not ad_num:
            orphans.append({
                "reason": "no_ad_extraction",
                "rt_adgroup": rt_adgroup,
                "campaign": campaign,
            })
            stats["not_found"] += 1
            continue

        # Lookup no registry
        result = lookup_ad(ad_num, registry, context_campaign=campaign)
        copywriter = result["copywriter"]
        confidence = result["confidence"]
        method = result["method"]

        # Atualizar stats
        stats["found"] += 1
        if method == "direct":
            stats["direct"] += 1
        elif method == "range":
            stats["range"] += 1
        elif method == "rip":
            stats["rip"] += 1

        if confidence == 1.0:
            stats["confidence_1_0"] += 1
        elif confidence == 0.9:
            stats["confidence_0_9"] += 1
        elif confidence == 0.85:
            stats["confidence_0_85"] += 1
        else:
            stats["confidence_0_0"] += 1

        # Agregar faturamento
        try:
            faturamento = float(row.get("revenuetype2", 0)) + float(row.get("revenuetype3", 0))
            custo = float(row.get("cost", 0))
            vendas = int(row.get("convtype1", 0))

            fat_por_cw[copywriter]["faturamento"] += faturamento
            fat_por_cw[copywriter]["custo"] += custo
            fat_por_cw[copywriter]["vendas"] += vendas
            fat_por_cw[copywriter]["ads"].add(ad_num)
            fat_por_cw[copywriter]["count"] += 1
            fat_por_cw[copywriter]["confidence_sum"] += confidence
        except:
            pass

        if copywriter == "Desconhecido":
            orphans.append({
                "reason": "not_found_in_registry",
                "ad_num": ad_num,
                "rt_adgroup": rt_adgroup,
                "campaign": campaign,
            })

    # Calcular médias de confiança
    for cw in fat_por_cw:
        count = fat_por_cw[cw]["count"]
        if count > 0:
            fat_por_cw[cw]["avg_confidence"] = fat_por_cw[cw]["confidence_sum"] / count

    # Relatório
    print("📡 CRUZAMENTO REDTRACK:\n")
    match_rate = 100 * stats["found"] / max(stats["total"], 1)
    print(f"   ✅ Encontrados: {stats['found']:,} ({match_rate:.1f}%)")
    print(f"      - Direct: {stats['direct']:,} ({100*stats['direct']/max(stats['found'], 1):.1f}%)")
    print(f"      - Range: {stats['range']:,} ({100*stats['range']/max(stats['found'], 1):.1f}%)")
    print(f"      - RIP: {stats['rip']:,} ({100*stats['rip']/max(stats['found'], 1):.1f}%)")
    print(f"   ❌ Órfãos: {stats['not_found']:,} ({100*stats['not_found']/max(stats['total'], 1):.1f}%)")

    print(f"\n🎯 CONFIANÇA DOS DADOS:\n")
    print(f"   Confiança 100%: {stats['confidence_1_0']:,} ({100*stats['confidence_1_0']/max(stats['found'], 1):.1f}%)")
    print(f"   Confiança 90%:  {stats['confidence_0_9']:,} ({100*stats['confidence_0_9']/max(stats['found'], 1):.1f}%)")
    print(f"   Confiança 85%:  {stats['confidence_0_85']:,} ({100*stats['confidence_0_85']/max(stats['found'], 1):.1f}%)")
    print(f"   Confiança 0%:   {stats['confidence_0_0']:,} ({100*stats['confidence_0_0']/max(stats['found'], 1):.1f}%)")

    high_confidence = (stats['confidence_1_0'] + stats['confidence_0_9'] + stats['confidence_0_85']) / max(stats['found'], 1) * 100
    print(f"\n   ✅ TAXA DE CONFIANÇA ALTA (≥85%): {high_confidence:.1f}%\n")

    # Faturamento por copywriter
    print("💰 FATURAMENTO POR COPYWRITER:\n")
    print("| Copywriter | Faturamento | % | Custo | Confiança | ADs Únicos |")
    print("|------------|-------------|---|-------|-----------|-----------|")

    total_fat = sum(d["faturamento"] for d in fat_por_cw.values())
    for cw in sorted(fat_por_cw.keys(), key=lambda x: fat_por_cw[x]["faturamento"], reverse=True):
        data = fat_por_cw[cw]
        fat = data["faturamento"]
        custo = data["custo"]
        pct = 100 * fat / max(total_fat, 1)
        conf = data["avg_confidence"]
        ads_count = len(data["ads"])

        print(f"| **{cw}** | R${fat:,.0f} | {pct:.1f}% | R${custo:,.0f} | {conf:.0%} | {ads_count} |")

    print(f"\n**TOTAL RASTREÁVEL**: R${total_fat:,.0f}")

    # Análise de órfãos
    if orphans:
        print(f"\n🚨 ANÁLISE DE ÓRFÃOS ({len(orphans):,} registros):\n")

        orphan_reasons = defaultdict(int)
        for o in orphans:
            orphan_reasons[o["reason"]] += 1

        for reason, count in sorted(orphan_reasons.items(), key=lambda x: x[1], reverse=True):
            pct = 100 * count / len(orphans)
            print(f"   - {reason}: {count:,} ({pct:.1f}%)")

    # Conclusão
    print(f"\n{'='*70}")
    print(f"✅ AUDITORIA CONCLUÍDA\n")
    print(f"Taxa de matching: {match_rate:.1f}%")
    print(f"Taxa de confiança alta (≥85%): {high_confidence:.1f}%")
    print(f"Faturamento rastreável: R${total_fat:,.0f}")
    print(f"{'='*70}\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Auditoria Profunda RedTrack")
    parser.add_argument("--date-from", help="Data início (YYYY-MM-DD)")
    parser.add_argument("--date-to", help="Data fim (YYYY-MM-DD)")
    parser.add_argument("--period", type=int, default=7, help="Últimos N dias")

    args = parser.parse_args()

    if args.date_from and args.date_to:
        date_from = args.date_from
        date_to = args.date_to
    else:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        date_to = today.strftime("%Y-%m-%d")
        date_from = (today - timedelta(days=args.period - 1)).strftime("%Y-%m-%d")

    run_deep_audit(date_from, date_to)


if __name__ == "__main__":
    main()
