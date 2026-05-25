#!/usr/bin/env python3
"""
Estratégia Inteligente de Notificações — Rastreador Esteira
- Evita spam no ClickUp
- Prioriza críticos (imediato)
- Consolida informações (2x/dia)
- Mantém auditoria (tudo logado)

Níveis:
  🚨 CRÍTICO: Notifica < 1 min (copywriter vazio, bloqueios)
  ⚠️ IMPORTANTE: Consolida 2x/dia (atrasos, em risco)
  📊 INFORMATIVO: Semanal (trends, padrões)
"""

from datetime import datetime, timedelta
import json
import os

# Estados que bloqueiam a esteira
BLOCKING_STATUSES = {
    "parado para revisão",
    "aguardando aprovação",
    "em espera",
    "bloqueado"
}

# SLA em dias por fase
FASES_SLA = {
    "backlog copy": 2,
    "escrevendo - copy": 2,
    "pré-produção": 1,
    "produção": 3,
    "alteração": 1,
    "avaliação - pós edição": 1,
    "avaliação - pós alteração": 1,
    "freelancer": 5,
}

NOTIFICATION_LOG = os.path.expanduser("~/Scripts/data/notificacao_log.jsonl")


# === NÍVEL 1: CRÍTICO (Notifica Imediato) ===

def is_critical_issue(old_status, new_status, task_data=None, missing_copywriter=False):
    """
    Determina se uma mudança de status é CRÍTICA.

    Retorna: (is_critical: bool, reason: str)
    """
    old_status = old_status.lower() if old_status else ""
    new_status = new_status.lower() if new_status else ""

    # Crítico 1: Copywriter vazio ao sair de backlog
    if old_status == "backlog copy" and missing_copywriter:
        return True, "copywriter_vazio"

    # Crítico 2: Entrando em status bloqueado
    if new_status in BLOCKING_STATUSES:
        return True, "bloqueado"

    # Crítico 3: Saindo de status bloqueado (melhoria)
    if old_status in BLOCKING_STATUSES and new_status not in BLOCKING_STATUSES:
        return True, "desbloqueado"

    # Não é crítico
    return False, None


def task_exceeds_sla_critical(status, entered_at, days_threshold=3):
    """
    Retorna True se tarefa excedeu SLA por MAIS DE 3 DIAS (crítico).
    """
    try:
        sla_days = FASES_SLA.get(status.lower(), 1)
        critical_threshold = sla_days + days_threshold  # SLA + 3 dias de buffer

        entered_dt = datetime.fromisoformat(entered_at)
        now = datetime.now()
        days_elapsed = (now - entered_dt).days

        if days_elapsed >= critical_threshold:
            return True, days_elapsed
        return False, days_elapsed
    except:
        return False, 0


def log_notification(notification_type, task_id, message, posted=True):
    """Log de todas as notificações para auditoria."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "type": notification_type,  # critical, consolidated, weekly
        "task_id": task_id,
        "message": message[:100],
        "posted": posted,
    }
    try:
        with open(NOTIFICATION_LOG, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except:
        pass


# === NÍVEL 2: IMPORTANTE (Consolida 2x/dia) ===

def build_consolidated_alert(tracking, critical_issues=None):
    """
    Consolida dados de análise em UMA ÚNICA mensagem para 11h/16h.

    Args:
        tracking: dict com dados de tarefas
        critical_issues: list de problemas críticos não resolvidos

    Returns: mensagem formatada ou None se nada relevante
    """
    if critical_issues is None:
        critical_issues = []

    now = datetime.now()
    lines = []

    # Header
    lines.append(f"📊 RASTREADOR ESTEIRA — {now.strftime('%d/%m %H:%M')}")
    lines.append("")

    # Críticos não resolvidos (se houver)
    if critical_issues:
        lines.append("🚨 CRÍTICOS (ação necessária):")
        for issue in critical_issues[:5]:  # Limita a 5
            lines.append(f"  • {issue['task_name'][:50]}")
            lines.append(f"    → {issue['reason']}")
        lines.append("")

    # Análise por setor
    setor_summary = analyze_by_sector(tracking)

    atrasadas_total = 0
    em_risco_total = 0

    for setor, data in setor_summary.items():
        atrasadas = len(data.get("atrasadas", []))
        em_risco = len(data.get("em_risco", []))

        if atrasadas > 0 or em_risco > 0:
            atrasadas_total += atrasadas
            em_risco_total += em_risco

            lines.append(f"📂 {setor}")
            if atrasadas > 0:
                lines.append(f"  🔴 {atrasadas} atrasada(s)")
            if em_risco > 0:
                lines.append(f"  🟡 {em_risco} em risco")

    # Resumo final
    lines.append("")
    lines.append(f"📈 RESUMO: {atrasadas_total} atrasadas | {em_risco_total} em risco")

    # Se não tem nada crítico, retorna None
    if not critical_issues and atrasadas_total == 0 and em_risco_total == 0:
        return None

    return "\n".join(lines)


def analyze_by_sector(tracking):
    """Agrupa tarefas por setor com status."""
    setores = {
        "Escrevendo - Copy": {"atrasadas": [], "em_risco": []},
        "Pré-Produção": {"atrasadas": [], "em_risco": []},
        "Produção": {"atrasadas": [], "em_risco": []},
        "Alteração": {"atrasadas": [], "em_risco": []},
        "Avaliação": {"atrasadas": [], "em_risco": []},
        "Freelancer": {"atrasadas": [], "em_risco": []},
    }

    now = datetime.now()

    for tid, task_data in tracking.items():
        status = task_data.get("current_status", "").lower()
        entered_at = task_data.get("status_entered_at", "")
        name = task_data.get("name", "")

        if not status or not entered_at:
            continue

        # Determinar setor
        setor = None
        if "escrevendo" in status:
            setor = "Escrevendo - Copy"
        elif "pré-produção" in status:
            setor = "Pré-Produção"
        elif "produção" in status and "alteração" not in status:
            setor = "Produção"
        elif "alteração" in status:
            setor = "Alteração"
        elif "avaliação" in status:
            setor = "Avaliação"
        elif "freelancer" in status:
            setor = "Freelancer"

        if not setor or setor not in setores:
            continue

        # Calcular dias na fase
        try:
            entered_dt = datetime.fromisoformat(entered_at)
            days_elapsed = (now - entered_dt).days
        except:
            continue

        sla_days = FASES_SLA.get(status, 1)

        # Classificar
        if days_elapsed >= sla_days:
            setores[setor]["atrasadas"].append({
                "name": name,
                "days": days_elapsed,
                "sla": sla_days,
            })
        elif days_elapsed >= int(sla_days * 0.7):  # 70% do SLA
            setores[setor]["em_risco"].append({
                "name": name,
                "days": days_elapsed,
                "sla": sla_days,
            })

    return setores


# === NÍVEL 3: INFORMATIVO (Semanal) ===

def should_send_weekly_report(last_weekly_sent=None):
    """Retorna True se é hora de enviar relatório semanal (segunda 11h)."""
    now = datetime.now()

    # Segunda-feira (weekday=0) às 11h
    if now.weekday() == 0 and 11 <= now.hour < 12:
        if last_weekly_sent:
            try:
                last_dt = datetime.fromisoformat(last_weekly_sent)
                if (now - last_dt).days >= 6:  # Pelo menos 6 dias
                    return True
            except:
                pass
        else:
            return True

    return False


def build_weekly_report(tracking, last_7_days_log=None):
    """Constrói relatório semanal de trends e padrões."""
    lines = [
        "📊 RELATÓRIO SEMANAL — RASTREADOR ESTEIRA",
        f"Semana de {(datetime.now() - timedelta(days=7)).strftime('%d/%m')} a {datetime.now().strftime('%d/%m')}",
        "",
    ]

    # Métricas da semana
    setor_summary = analyze_by_sector(tracking)

    total_atrasadas = sum(len(s["atrasadas"]) for s in setor_summary.values())
    total_em_risco = sum(len(s["em_risco"]) for s in setor_summary.values())

    lines.append(f"📈 MÉTRICAS:")
    lines.append(f"  Atrasadas: {total_atrasadas}")
    lines.append(f"  Em risco: {total_em_risco}")
    lines.append("")

    # Top gargalos
    lines.append(f"🔴 TOP GARGALOS:")
    worst_setores = sorted(
        [(s, len(d["atrasadas"])) for s, d in setor_summary.items()],
        key=lambda x: x[1],
        reverse=True
    )
    for setor, count in worst_setores[:3]:
        if count > 0:
            lines.append(f"  {setor}: {count} tarefas")

    return "\n".join(lines)


# === LÓGICA DE DECISÃO ===

def should_notify_immediately(notification_type, task_id, last_notification_time=None):
    """
    Determina se deve notificar AGORA ou aguardar consolidação.

    Evita notificar a mesma coisa múltiplas vezes em janela curta.
    """
    if notification_type not in ["critical"]:
        return False

    # Se não há registro de última notificação, notifica
    if not last_notification_time:
        return True

    # Só notifica de novo se passou 30 minutos
    try:
        last_dt = datetime.fromisoformat(last_notification_time)
        if (datetime.now() - last_dt).total_seconds() >= 1800:  # 30 min
            return True
    except:
        return True

    return False


def should_consolidate_now():
    """Retorna True se é horário de enviar consolidado (11h ou 16h)."""
    now = datetime.now()
    return (now.hour == 11 or now.hour == 16) and now.minute < 10


# === EXEMPLO DE USO ===

if __name__ == "__main__":
    print("✅ Estratégia de Notificações Carregada")
    print("")
    print("Níveis implementados:")
    print("  🚨 CRÍTICO: < 1 min (copywriter vazio, bloqueios)")
    print("  ⚠️  IMPORTANTE: 2x/dia (11h, 16h)")
    print("  📊 INFORMATIVO: Semanal (segunda 11h)")
