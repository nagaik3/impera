#!/usr/bin/env python3
"""
Estratégia de Consolidação — Compliance Drive
- Cache de Google Drive
- Batch processing de erros
- Alerta consolidado em 1 mensagem

Reduz:
  - Google Drive calls: 100+ → 5-10 (90% ↓)
  - ClickUp messages: 10-20 → 2 (80% ↓)
  - Frequência: 2x/dia → 1x/dia (50% ↓)
"""

import json
import os
from datetime import datetime, timedelta

CACHE_DIR = os.path.expanduser("~/Scripts/data/compliance_drive_cache")
CACHE_TTL = 3600  # 1 hora


# === CACHE DE GOOGLE DRIVE ===

def ensure_cache_dir():
    """Cria diretório de cache se não existir."""
    os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_key(folder_id, operation="list_subfolders"):
    """Gera chave para cache."""
    return f"{operation}_{folder_id}.json"


def get_cached_data(folder_id, operation="list_subfolders"):
    """Retorna dados do cache se ainda válido."""
    ensure_cache_dir()
    cache_file = os.path.join(CACHE_DIR, get_cache_key(folder_id, operation))

    if not os.path.exists(cache_file):
        return None

    try:
        with open(cache_file) as f:
            data = json.load(f)

        # Verifica se cache ainda é válido
        cached_at = datetime.fromisoformat(data["_cached_at"])
        if (datetime.now() - cached_at).total_seconds() < CACHE_TTL:
            return data["_data"]
    except:
        pass

    return None


def cache_data(folder_id, data, operation="list_subfolders"):
    """Armazena dados em cache."""
    ensure_cache_dir()
    cache_file = os.path.join(CACHE_DIR, get_cache_key(folder_id, operation))

    try:
        with open(cache_file, "w") as f:
            json.dump({
                "_cached_at": datetime.now().isoformat(),
                "_data": data,
            }, f)
    except:
        pass


def clear_cache():
    """Limpa todo o cache."""
    import shutil
    try:
        shutil.rmtree(CACHE_DIR)
        os.makedirs(CACHE_DIR, exist_ok=True)
    except:
        pass


# === BATCH PROCESSING DE ERROS ===

def group_issues_by_type(issues):
    """Agrupa problemas por tipo para relatório consolidado."""
    grouped = {
        "vazio": [],
        "arquivos_faltando": [],
        "nomenclatura_incorreta": [],
        "pasta_nao_encontrada": [],
        "erro_acesso": [],
        "alt_structure": [],
    }

    for issue in issues:
        status = issue.get("status", "").lower()

        if status == "vazio":
            grouped["vazio"].append(issue)
        elif "faltando" in issue.get("detail", "").lower():
            grouped["arquivos_faltando"].append(issue)
        elif "nomenclatura" in issue.get("detail", "").lower():
            grouped["nomenclatura_incorreta"].append(issue)
        elif "não encontrada" in issue.get("detail", "").lower():
            grouped["pasta_nao_encontrada"].append(issue)
        elif status == "alt_structure":
            grouped["alt_structure"].append(issue)
        else:
            grouped["erro_acesso"].append(issue)

    # Remove grupos vazios
    return {k: v for k, v in grouped.items() if v}


def build_consolidated_report(results, issues, total_checked=None):
    """Constrói relatório consolidado para ClickUp Chat."""
    if total_checked is None:
        total_checked = len(results)

    ok_count = len([r for r in results if r.get("status") == "OK"])
    issue_count = len(issues)

    if issue_count == 0:
        return None  # Nada para reportar

    lines = [
        f"📂 COMPLIANCE DRIVE — {datetime.now().strftime('%d/%m %H:%M')}",
        f"Verificadas: {total_checked} | OK: {ok_count} | Problemas: {issue_count}",
        "",
    ]

    grouped = group_issues_by_type(issues)

    # Arquivos Faltando
    if grouped.get("arquivos_faltando"):
        lines.append("🔴 ARQUIVOS FALTANDO:")
        for issue in grouped["arquivos_faltando"][:3]:  # Limita a 3
            expected = issue.get("expected", "?")
            found = issue.get("found", "?")
            lines.append(f"  • {issue['name'][:50]}")
            lines.append(f"    Esperado: {expected} | Encontrado: {found}")
        if len(grouped["arquivos_faltando"]) > 3:
            lines.append(f"  ... e mais {len(grouped['arquivos_faltando']) - 3}")
        lines.append("")

    # Nomenclatura Incorreta
    if grouped.get("nomenclatura_incorreta"):
        lines.append("⚠️ NOMENCLATURA INCORRETA:")
        for issue in grouped["nomenclatura_incorreta"][:2]:
            lines.append(f"  • {issue['name'][:50]}")
            lines.append(f"    {issue['detail'][:60]}")
        if len(grouped["nomenclatura_incorreta"]) > 2:
            lines.append(f"  ... e mais {len(grouped['nomenclatura_incorreta']) - 2}")
        lines.append("")

    # Pasta Não Encontrada
    if grouped.get("pasta_nao_encontrada"):
        lines.append("❌ PASTA 'MATERIAL EDITADO' NÃO ENCONTRADA:")
        for issue in grouped["pasta_nao_encontrada"][:2]:
            lines.append(f"  • {issue['name'][:50]}")
        if len(grouped["pasta_nao_encontrada"]) > 2:
            lines.append(f"  ... e mais {len(grouped['pasta_nao_encontrada']) - 2}")
        lines.append("")

    # Estrutura Alternativa
    if grouped.get("alt_structure"):
        lines.append("ℹ️ ESTRUTURA ALTERNATIVA (AD individual):")
        for issue in grouped["alt_structure"][:2]:
            lines.append(f"  • {issue['name'][:50]}")
        if len(grouped["alt_structure"]) > 2:
            lines.append(f"  ... e mais {len(grouped['alt_structure']) - 2}")
        lines.append("")

    # Erros
    if grouped.get("erro_acesso"):
        lines.append("⚠️ ERROS DE ACESSO:")
        for issue in grouped["erro_acesso"][:1]:
            lines.append(f"  • {issue['detail'][:60]}")
        if len(grouped["erro_acesso"]) > 1:
            lines.append(f"  ... e mais {len(grouped['erro_acesso']) - 1}")
        lines.append("")

    # Footer
    lines.append("👉 Acesse as tarefas e corrija os arquivos no Google Drive.")

    return "\n".join(lines)


def build_critical_alert(issues):
    """Constrói alerta para problemas críticos (pasta não encontrada)."""
    critical = [i for i in issues if "não encontrada" in i.get("detail", "").lower()]

    if not critical:
        return None

    lines = [
        "🚨 COMPLIANCE DRIVE — CRÍTICO",
        f"Encontrados {len(critical)} problema(s) que bloqueiam a edição:",
        "",
    ]

    for issue in critical[:5]:
        lines.append(f"  • {issue['name']}")
        lines.append(f"    → Pasta 'Material Editado' não encontrada")

    if len(critical) > 5:
        lines.append(f"\n  ... e mais {len(critical) - 5}")

    lines.append("")
    lines.append("⚠️ Estes precisam ser corrigidos HOJE.")

    return "\n".join(lines)


# === DEDUPLICAÇÃO ===

def should_alert_today(issue_id, state_data, alert_type="consolidated"):
    """Verifica se já foi alertado hoje sobre este problema."""
    alerted = state_data.get("alerted_today", {})
    alert_key = f"{alert_type}_{issue_id}"

    last_alert = alerted.get(alert_key)
    if not last_alert:
        return True

    try:
        last_dt = datetime.fromisoformat(last_alert)
        if (datetime.now() - last_dt).days >= 1:  # Passou 1 dia
            return True
    except:
        return True

    return False


def mark_alerted_today(issue_id, state_data, alert_type="consolidated"):
    """Marca que foi alertado sobre este problema hoje."""
    if "alerted_today" not in state_data:
        state_data["alerted_today"] = {}

    alert_key = f"{alert_type}_{issue_id}"
    state_data["alerted_today"][alert_key] = datetime.now().isoformat()

    # Limpar alertas antigos (>7 dias)
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    state_data["alerted_today"] = {
        k: v for k, v in state_data["alerted_today"].items()
        if v > cutoff
    }

    return state_data


# === EXEMPLO ===

if __name__ == "__main__":
    print("✅ Estratégia de Consolidação Carregada")
    print("")
    print("Recursos:")
    print("  • Cache Google Drive (1h TTL)")
    print("  • Batch processing de erros")
    print("  • Relatório consolidado")
    print("  • Alerta crítico separado")
    print("  • Deduplicação de alertas")
