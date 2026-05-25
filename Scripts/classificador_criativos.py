#!/usr/bin/env python3
"""
Classificador de Criativos — IMPERA
Regras oficiais do Super Cérebro de Tráfego V5.

Níveis:
  Em Teste      → <3 vendas OU CPA > meta
  Pré-validado  → 3-9 vendas, CPA max R$180
  Validado      → 10+ vendas, CPA dentro da meta
  Top / Escala  → 30+ vendas no período de teste

Funcionalidades:
  1. Classificação automática (vendas + CPA) — atualiza status no CU
  2. Alerta de promoção via Telegram
  3. Monitor "quase lá" (criativos a 1-2 vendas de promoção)
  4. Tags de jornada acumulativas (potential-*, pré-validado, validado, top)

Tags de Jornada:
  - Em "aguardando teste": potential-top, potential-validado, potential-pré-validado
    (herdado do criativo pai, indica potencial)
  - Em status ativos: pré-validado, validado, top
    (conquistado pela própria performance, acumulativo)
  - Tags NUNCA são removidas — criam rastro da jornada completa

Modos:
  python3 classificador_criativos.py --preview       # mostra sem alterar
  python3 classificador_criativos.py --execute        # move status + tags + alerta
  python3 classificador_criativos.py --quase-la       # mostra criativos perto de promoção
  python3 classificador_criativos.py --report         # relatório completo Telegram
  python3 classificador_criativos.py --tags-retroativo # aplica tags em toda a lista

Crontab: diário às 11h (após briefing diário)
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.expanduser("~/Scripts"))
from impera_cache import cached_cu_tasks, cached_rt_ads

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

LIST_TRAFEGO = "901324476398"

STATE_FILE = os.path.expanduser("~/Scripts/data/classificador_state.json")

# ============================================================
# REGRAS OFICIAIS — Super Cérebro de Tráfego V5
# ============================================================

CPA_META = 180  # R$ — CPA máximo para pré-validado e validado
ROAS_MIN = 1.8  # ROAS Front mínimo para validar (revenuetype2 + revenuetype3 / cost)

# Configurável por nicho (override do default)
CPA_META_NICHO = {
    "EM": 180, "DB": 180, "NE": 180, "ED": 180,
    "MM": 180, "PT": 180, "DA": 180, "ZB": 180,
}

# ============================================================
# REGRAS NEGATIVAS — Trilha de performance negativa
# ============================================================

# Em Risco: gastou budget de corte mas ROAS < 1.0 (sinal de alerta, recuperável)
EM_RISCO_CUSTO_MIN = 200   # R$ — equivalente ao corte de venda do playbook
EM_RISCO_ROAS_MAX = 1.0    # ROAS Front abaixo disso = em risco
EM_RISCO_VENDAS_MAX = 2    # Com poucas vendas — não validou

# Negativo: gastou budget significativo e confirmou que não funciona
NEGATIVO_CUSTO_MIN = 500   # R$ — ~2.7× CPA meta, chance justa dada
NEGATIVO_ROAS_MAX = 1.0    # ROAS Front abaixo disso = negativo confirmado

RULES = {
    "em teste":      {"min_vendas": 0,  "max_vendas": 2,  "cpa_max": None,    "min_roas": None},
    "pré-validado":  {"min_vendas": 3,  "max_vendas": 9,  "cpa_max": CPA_META, "min_roas": ROAS_MIN},
    "validado":      {"min_vendas": 10, "max_vendas": 29, "cpa_max": CPA_META, "min_roas": ROAS_MIN},
    "top / escala":  {"min_vendas": 30, "max_vendas": None, "cpa_max": None,   "min_roas": ROAS_MIN},
}

# Mapeamento para status do ClickUp
NIVEL_TO_CU_STATUS = {
    "em teste":     "em teste",
    "pré-validado": "pré-escala",
    "validado":     "validado",
    "top / escala": "escala",
}

# Status negativos — movimentação automática (sem confirmação do gestor)
NIVEL_NEGATIVO_TO_STATUS = {
    "em risco": "em risco",
    "negativo": "negativo",
}

# Status com movimentação automática — DESATIVADO (02/Mai/2026)
# Agora todos os movimentos passam por confirmação do gestor via comentário
AUTO_MOVE_STATUSES = set()  # vazio = tudo pede confirmação

# Tags de jornada (substituem os selos visuais antigos)
NIVEL_TO_TAG = {
    "pré-validado": "pré-validado",
    "validado":     "validado",
    "top / escala": "top",
}

# Tags potential (para tarefas em aguardando teste)
NIVEL_TO_POTENTIAL_TAG = {
    "pré-validado": "potential-pré-validado",
    "validado":     "potential-validado",
    "top / escala": "potential-top",
}

# Selos visuais LEGADOS (para remoção em tarefas antigas)
SELOS_LEGADOS = ["[PRE-V]", "[VALIDADO]", "[TOP]", "[PRÉ-V]"]

# Gestores
GESTORES_CU = {
    87343090: "Lucas Pereira Cavalcanti",
    82074473: "Ludson Chaves",
    82118000: "Douglas de Oliveira",
    105940694: "Gabriel Fraza",
    82168803: "Gustavo Lisner",
}

GESTOR_KEYWORDS = {
    "LUCAS": "LUCAS", "LUDSON": "LUDSON", "DOUG": "DOUGLAS",
    "DOUGLAS": "DOUGLAS", "GABRIEL": "GABRIEL", "FRAZA": "GABRIEL",
    "GUSTAVO": "GUSTAVO",
}

NICHO_KEYWORDS = {
    "EMAGRECIMENTO": "EM", "DIABETES": "DB", "NEUROPATIA": "NE",
    "ADULTO": "ED", "MEMORIA": "MM", "MEMÓRIA": "MM",
    "PROSTATA": "PT", "ZUMBIDO": "ZB", "ARTICULAR": "DA", "DORES": "DA",
}


# ============================================================
# API HELPERS
# ============================================================

def api_put(endpoint, data):
    url = f"https://api.clickup.com/api/v2{endpoint}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="PUT")
    req.add_header("Authorization", API_TOKEN)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def api_post(endpoint, data):
    url = f"https://api.clickup.com/api/v2{endpoint}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", API_TOKEN)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


CHAT_VIEW_GT = "6-901324476398-8"


def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = json.dumps({"chat_id": TELEGRAM_CHAT, "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception:
        pass


def post_chat_gt(text):
    """Posta no Chat da lista Gestão de Tráfego."""
    url = f"https://api.clickup.com/api/v2/view/{CHAT_VIEW_GT}/comment"
    payload = json.dumps({"comment_text": text}).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", API_TOKEN)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True
    except Exception:
        return False


# ============================================================
# PARSING
# ============================================================

def extract_refs(name):
    """Extrai referências de criativos de um nome de tarefa CU."""
    upper = name.upper()
    refs = set()
    for m in re.finditer(r"AD(\d+)\s*-\s*(?:AD)?(\d+)", upper):
        for n in range(int(m.group(1)), int(m.group(2)) + 1):
            refs.add(f"AD{n}")
    if not re.search(r"AD\d+\s*-", upper):
        for m in re.findall(r"AD(\d+)", upper):
            refs.add(f"AD{m}")
    for m in re.findall(r"(C[EYC])(\d+)", upper):
        refs.add(f"{m[0]}{m[1]}")
    for m in re.findall(r"(?<![A-Z])C(\d+)", re.sub(r"\s+", "", upper)):
        refs.add(f"C{m}")
    for m in re.findall(r"IMG(\d+)", upper):
        refs.add(f"IMG{m}")
    return refs


def normalize_rt_ref(ad_name):
    """Normaliza nome de ad RT para matching com refs CU."""
    clean = ad_name.upper().strip()
    adc = re.match(r"AD\s+(C[A-Z]*\s*\d.*)", clean)
    if adc:
        clean = adc.group(1)
    norm = re.sub(r"\s+", "", clean)
    if re.match(r"^\d", norm):
        norm = "AD" + norm
    norm = re.sub(r"^ADAD", "AD", norm)
    base = re.match(r"((?:AD|C[EYC]|IMG|C)\d+)", norm)
    return base.group(1) if base else norm


def detect_nicho_from_name(name):
    upper = name.upper()
    for m in re.findall(r"\[([A-Z]{2,3})\]", name):
        if m in {"EM", "DB", "NE", "ED", "MM", "PT", "DA", "ZB"}:
            return m
    return "?"


def detect_nicho_campaign(name):
    upper = name.upper()
    for kw, code in NICHO_KEYWORDS.items():
        if kw in upper:
            return code
    return "?"


def detect_gestor(task):
    for a in task.get("assignees", []):
        aid = a.get("id")
        if aid in GESTORES_CU:
            return aid
    return None


def get_current_tags(task):
    """Retorna set de tags atuais da tarefa."""
    return {tag["name"] for tag in task.get("tags", [])}


def remove_selos_legados(name):
    """Remove selos visuais legados do nome."""
    for selo in SELOS_LEGADOS:
        name = name.replace(f" {selo}", "").replace(selo, "")
    return name.strip()


def add_tag(task_id, tag_name):
    """Adiciona tag a uma tarefa no ClickUp."""
    try:
        encoded_tag = urllib.parse.quote(tag_name)
        url = f"https://api.clickup.com/api/v2/task/{task_id}/tag/{encoded_tag}"
        req = urllib.request.Request(url, data=b"", method="POST")
        req.add_header("Authorization", API_TOKEN)
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, timeout=30)
        return True
    except Exception as e:
        print(f"  [ERRO] Tag '{tag_name}' em {task_id}: {e}")
        return False


# ============================================================
# CLASSIFICAÇÃO
# ============================================================

def classify(vendas, cpa, roas, custo, nicho="?"):
    """Classifica um criativo baseado nas regras oficiais (Super Cérebro V5).
    Inclui trilha negativa: em risco → negativo.
    """
    meta = CPA_META_NICHO.get(nicho, CPA_META)

    # Trilha positiva (prioridade)
    if vendas >= 30 and roas >= ROAS_MIN:
        return "top / escala"
    if vendas >= 10 and cpa <= meta and roas >= ROAS_MIN:
        return "validado"
    if vendas >= 3 and cpa <= meta and roas >= ROAS_MIN:
        return "pré-validado"

    # Trilha negativa (performance ruim com budget suficiente)
    if custo >= NEGATIVO_CUSTO_MIN and (vendas == 0 or roas < NEGATIVO_ROAS_MAX):
        return "negativo"
    if custo >= EM_RISCO_CUSTO_MIN and roas < EM_RISCO_ROAS_MAX and vendas <= EM_RISCO_VENDAS_MAX:
        return "em risco"

    return "em teste"


def distance_to_next(vendas, cpa, roas, custo, nicho="?"):
    """Retorna (próximo_nível, vendas_faltando) ou None se já é Top."""
    meta = CPA_META_NICHO.get(nicho, CPA_META)
    nivel = classify(vendas, cpa, roas, custo, nicho)

    if nivel == "top / escala":
        return None
    if roas < ROAS_MIN:
        return None  # ROAS baixo, mais vendas não ajudam
    if nivel == "validado":
        return "top / escala", 30 - vendas
    if nivel == "pré-validado":
        return "validado", 10 - vendas
    # em teste
    if (cpa <= meta or vendas == 0) and (roas >= ROAS_MIN or vendas == 0):
        return "pré-validado", 3 - vendas
    return None  # CPA alto ou ROAS baixo


# ============================================================
# STATE
# ============================================================

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ============================================================
# CORE
# ============================================================

def build_rt_index(date_from, date_to):
    """Constrói índice RT: base_ref → {vendas, custo, receita}."""
    rt_data = cached_rt_ads(date_from, date_to, ttl=1800)
    index = defaultdict(lambda: {"vendas": 0, "custo": 0, "receita": 0})

    for ad in rt_data["ads"]:
        ad_name = (ad.get("rt_ad", "") or "").strip()
        ad_cost = float(ad.get("cost", 0))
        if ad_cost < 1 or not ad_name:
            continue
        if ad_name in ("{AD}", "(sem nome)", "-", "?"):
            continue

        base_ref = normalize_rt_ref(ad_name)
        ad_rev = float(ad.get("revenuetype2", 0)) + float(ad.get("revenuetype3", 0))
        ad_vendas = int(ad.get("convtype1", 0))

        index[base_ref]["vendas"] += ad_vendas
        index[base_ref]["custo"] += ad_cost
        index[base_ref]["receita"] += ad_rev

    return index


def consolidate_tasks_by_base_creative(tasks):
    """
    CRÍTICO: Consolida variações de um mesmo criativo (AD10 + AD10 V2 + AD10 V30).
    Previne contagem duplicada e melhora precisão da classificação.

    Problema resolvido:
    - Antes: AD10, AD10 V2, AD10 V30 eram tarefas separadas no ClickUp
    - Cada uma puxava dados RT duplicados (todos apontavam para AD10 no RedTrack)
    - Causava contagem duplicada e false negatives (ex: AD10 V2 sozinha <10 vendas, mas consolidada >30)

    Solução:
    - Agrupa tarefas por base_creative (todas variações de AD10 ficam juntas)
    - Combina todas as refs (refs consolidadas)
    - Retorna tarefa representante com metrics agregadas

    Impacto:
    - ✅ Validação mais precisa (AD10 V2 nunca foi "negativo" isoladamente, só em consolidação)
    - ✅ Rankings corretos (top 10 mostra criativos, não variações)
    - ✅ Histórico preservado (_variants tracks todas as variações)
    """
    consolidated = {}  # base_ref -> tarefa representante

    for t in tasks:
        # Extrai referências desta tarefa
        refs = extract_refs(t.get("name", ""))
        if not refs:
            continue

        # Usa primeira referência como chave de consolidação
        base_ref = min(refs)  # AD10 < AD10V2 < AD10V30

        if base_ref not in consolidated:
            # Primeira tarefa desta variante: usa como representante
            consolidated[base_ref] = {
                "task": t,
                "refs": refs,
                "variant_names": [t.get("name", "")],
            }
        else:
            # Tarefa adicional para mesma variante
            consolidated[base_ref]["refs"].update(refs)
            consolidated[base_ref]["variant_names"].append(t.get("name", ""))

    # Retorna apenas as tarefas representantes (com todas as refs agregadas)
    result = []
    for base_ref, data in consolidated.items():
        t = data["task"].copy()
        # Adiciona todas as refs combinadas para agregação RT
        t["_consolidated_refs"] = data["refs"]
        t["_variants"] = data["variant_names"]
        result.append(t)

    return result


def analyze_tasks(tasks, rt_index):
    """Analisa cada tarefa e retorna lista de classificações."""
    results = []
    active_statuses = {"em teste", "pré-escala", "validado", "escala", "aguardando teste", "em risco"}

    # CONSOLIDAÇÃO: agrupar variações do mesmo criativo
    tasks = consolidate_tasks_by_base_creative(tasks)

    for t in tasks:
        if t.get("parent"):
            continue
        status = t["status"]["status"].lower()
        if status not in active_statuses:
            continue

        name = t["name"]
        tid = t["id"]
        # Use consolidated refs if available (from consolidation), else extract
        refs = t.get("_consolidated_refs") or extract_refs(name)
        if not refs:
            continue

        # Agregar dados RT para esta tarefa (consolidada ou não)
        total_vendas = 0
        total_custo = 0
        total_receita = 0
        for ref in refs:
            if ref in rt_index:
                total_vendas += rt_index[ref]["vendas"]
                total_custo += rt_index[ref]["custo"]
                total_receita += rt_index[ref]["receita"]

        if total_custo == 0:
            continue

        cpa = total_custo / total_vendas if total_vendas > 0 else float("inf")
        roas = total_receita / total_custo if total_custo > 0 else 0
        nicho = detect_nicho_from_name(name)
        nivel = classify(total_vendas, cpa, roas, total_custo, nicho)
        current_tags = get_current_tags(t)
        gestor_id = detect_gestor(t)

        # Status CU que deveria ter
        if nivel in NIVEL_TO_CU_STATUS:
            target_status = NIVEL_TO_CU_STATUS[nivel]
        elif nivel in NIVEL_NEGATIVO_TO_STATUS:
            target_status = NIVEL_NEGATIVO_TO_STATUS[nivel]
        else:
            target_status = status

        # Determinar tags necessárias (trilha positiva)
        tags_to_add = []
        if nivel in NIVEL_TO_TAG:
            tag = NIVEL_TO_TAG[nivel]
            if tag not in current_tags:
                tags_to_add.append(tag)
        # Acumular tags intermediárias (jornada completa)
        if nivel == "top / escala":
            for intermediate in ["pré-validado", "validado"]:
                if intermediate not in current_tags:
                    tags_to_add.append(intermediate)
        elif nivel == "validado":
            if "pré-validado" not in current_tags:
                tags_to_add.append("pré-validado")

        # Tags negativas
        if nivel == "em risco" and "em-risco" not in current_tags:
            tags_to_add.append("em-risco")
        elif nivel == "negativo" and "negativo" not in current_tags:
            tags_to_add.append("negativo")

        # Checar se tem selos legados no nome para limpar
        has_legacy_selo = any(s in name for s in SELOS_LEGADOS)

        # Auto-move: validado, em risco, negativo não precisam de confirmação
        is_auto_move = target_status in AUTO_MOVE_STATUSES

        # Info sobre consolidação (se houver)
        variants = t.get("_variants", [])
        num_variants = len(variants) if variants else 1

        results.append({
            "task_id": tid,
            "name": name,
            "nicho": nicho,
            "status_atual": status,
            "nivel": nivel,
            "target_status": target_status,
            "vendas": total_vendas,
            "custo": total_custo,
            "receita": total_receita,
            "cpa": cpa,
            "roas": roas,
            "current_tags": current_tags,
            "tags_to_add": tags_to_add,
            "has_legacy_selo": has_legacy_selo,
            "needs_status_change": status != target_status and status != "aguardando teste",
            "is_auto_move": is_auto_move,
            "gestor_id": gestor_id,
            "_num_variants": num_variants,  # Info sobre consolidação (1 = não consolidado)
            "_variants": variants,  # Nomes das variantes consolidadas
        })

    return results


# ============================================================
# AÇÕES
# ============================================================

def apply_tags(task_id, tags_to_add):
    """Adiciona tags de jornada à tarefa no ClickUp."""
    count = 0
    for tag in tags_to_add:
        if add_tag(task_id, tag):
            count += 1
        time.sleep(0.2)
    return count


def clean_legacy_selos(task_id, name):
    """Remove selos legados do nome da tarefa."""
    clean = remove_selos_legados(name)
    if clean != name:
        try:
            api_put(f"/task/{task_id}", {"name": clean})
            return clean
        except Exception as e:
            print(f"  [ERRO] Limpar selo {task_id}: {e}")
    return name


def move_status(task_id, target_status):
    """Move status da tarefa no ClickUp."""
    try:
        api_put(f"/task/{task_id}", {"status": target_status})
        return True
    except Exception as e:
        print(f"  [ERRO] Status {task_id}: {e}")
        return False


def post_confirmation_request(task_id, name, nivel, target_status, vendas, cpa, roas, gestor_id=None, custo=0):
    """Posta comentário pedindo confirmação do gestor para mudar status."""
    emoji = {
        "pré-validado": "🟡", "validado": "🟢", "top / escala": "🏆",
        "em risco": "⚠️", "negativo": "🔴",
    }.get(nivel, "📊")
    gestor_name = GESTORES_CU.get(gestor_id, "Gestor") if gestor_id else "Gestor"

    cpa_str = f"R${cpa:.2f}" if vendas > 0 else "N/A"

    if nivel in ("em risco", "negativo"):
        comment = (
            f"{emoji} ALERTA DE PERFORMANCE — @{gestor_name}\n\n"
            f"Este criativo foi classificado como: {nivel.upper()}\n"
            f"Custo: R${custo:.2f} | Vendas: {vendas} | CPA: {cpa_str} | ROAS Front: {roas:.2f}\n\n"
            f"Status sugerido: {target_status}\n"
            f"Regra: custo >= R${EM_RISCO_CUSTO_MIN if nivel == 'em risco' else NEGATIVO_CUSTO_MIN} com ROAS < {EM_RISCO_ROAS_MAX}\n\n"
            f"📋 Responda para confirmar:\n"
            f"• \"Confirmar\" — mover para {target_status}\n"
            f"• \"Manter\" — manter em teste (dar mais tempo)\n"
            f"• \"Pausar\" — mover para pausado"
        )
    else:
        comment = (
            f"{emoji} CLASSIFICAÇÃO — @{gestor_name}\n\n"
            f"Este criativo atingiu nível: {nivel.upper()}\n"
            f"Vendas: {vendas} | CPA: {cpa_str} | ROAS Front: {roas:.2f}\n\n"
            f"Status sugerido: {target_status}\n"
            f"Regra: Super Cérebro de Tráfego V5\n\n"
            f"📋 Responda para confirmar:\n"
            f"• \"Confirmar\" — mover para {target_status}\n"
            f"• \"Manter\" — manter status atual\n"
            f"• \"Pausar\" — mover para pausado"
        )
    payload = {"comment_text": comment, "notify_all": False}
    if gestor_id:
        payload["assignee"] = gestor_id
    try:
        api_post(f"/task/{task_id}/comment", payload)
        return True
    except Exception:
        return False


def check_confirmation(task_id, requested_at_ms):
    """Verifica se o gestor respondeu ao pedido de confirmação."""
    try:
        url = f"https://api.clickup.com/api/v2/task/{task_id}/comment"
        req = urllib.request.Request(url, headers={"Authorization": API_TOKEN})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        for c in data.get("comments", []):
            commenter = c.get("user", {}).get("id", 0)
            if commenter == 176404277:  # Bot (Iago automation)
                continue
            comment_ts = int(c.get("date", 0))
            if comment_ts > requested_at_ms:
                text = (c.get("comment_text", "") or "").upper()
                if "CONFIRMAR" in text or "APROVADO" in text or "OK" in text or "SIM" in text:
                    return "confirmed"
                if "MANTER" in text:
                    return "keep"
                if "PAUSAR" in text:
                    return "pause"
    except Exception:
        pass
    return None


# ============================================================
# MODOS DE EXECUÇÃO
# ============================================================

def run_preview(results):
    """Mostra classificação sem alterar nada."""
    print(f"\n{'='*80}")
    print(f"CLASSIFICAÇÃO DE CRIATIVOS — Preview")
    print(f"{'='*80}\n")

    # Resumo por nível
    nivels = defaultdict(list)
    for r in results:
        nivels[r["nivel"]].append(r)

    NIVEL_EMOJI = {
        "em teste": "🔵", "pré-validado": "🟡", "validado": "🟢",
        "top / escala": "🏆", "em risco": "⚠️", "negativo": "🔴",
    }
    for nivel in ["top / escala", "validado", "pré-validado", "em teste", "em risco", "negativo"]:
        items = nivels.get(nivel, [])
        if not items:
            continue
        emoji = NIVEL_EMOJI.get(nivel, "📊")
        print(f"\n{emoji} {nivel.upper()} ({len(items)} criativos)")
        print(f"  {'Tarefa':<50} {'Vendas':>6} {'CPA':>10} {'ROAS':>6} {'Ação'}")
        print(f"  {'-'*90}")
        for r in sorted(items, key=lambda x: x["vendas"], reverse=True):
            short = r["name"][:48]
            cpa_str = f"R${r['cpa']:.0f}" if r["vendas"] > 0 else "N/A"
            actions = []
            if r["needs_status_change"]:
                auto = " (auto)" if r.get("is_auto_move") else ""
                actions.append(f"status→{r['target_status']}{auto}")
            if r["tags_to_add"]:
                actions.append(f"tags→{','.join(r['tags_to_add'])}")
            if r["has_legacy_selo"]:
                actions.append("limpar selo")
            action = " | ".join(actions) if actions else "-"
            print(f"  {short:<50} {r['vendas']:>6} {cpa_str:>10} {r['roas']:>6.2f} {action}")

    # Contagem de ações
    status_changes = sum(1 for r in results if r["needs_status_change"])
    auto_moves = sum(1 for r in results if r["needs_status_change"] and r.get("is_auto_move"))
    confirm_moves = status_changes - auto_moves
    tag_changes = sum(1 for r in results if r["tags_to_add"])
    selo_cleanups = sum(1 for r in results if r["has_legacy_selo"])
    print(f"\n📊 Resumo: {len(results)} criativos analisados")
    print(f"   {status_changes} mudanças de status ({auto_moves} automáticas, {confirm_moves} aguardam confirmação)")
    print(f"   {tag_changes} tarefas precisam de tags")
    print(f"   {selo_cleanups} selos legados a limpar")


def run_execute(results):
    """Aplica tags de jornada + pede confirmação ao gestor antes de mover status.
    Fluxo:
      1. Limpa selos legados do nome (se existirem)
      2. Aplica tags de jornada acumulativas
      3. Para mudança de status: posta comentário pedindo confirmação
      4. Em execuções seguintes: checa se gestor respondeu e aplica
    """
    state = load_state()
    now_ms = int(datetime.now().timestamp() * 1000)
    tag_count = 0
    selo_cleaned = 0
    requested_count = 0
    confirmed_count = 0
    tg_promotions = []
    tg_confirmed = []

    for r in results:
        tid = r["task_id"]
        name = r["name"]
        prev = state.get(tid, {})

        # 1. Limpar selos legados do nome
        if r["has_legacy_selo"]:
            name = clean_legacy_selos(tid, name)
            selo_cleaned += 1
            time.sleep(0.3)

        # 2. Tags de jornada — aplica imediatamente (acumulativo)
        if r["tags_to_add"]:
            added = apply_tags(tid, r["tags_to_add"])
            tag_count += added
            tag_str = ", ".join(r["tags_to_add"])
            print(f"  🏷️ +{tag_str} → {name[:50]}", flush=True)

        # 3. Mudança de status
        if r["needs_status_change"]:
            # Auto-move: validado, em risco, negativo (sem confirmação)
            if r["is_auto_move"]:
                if move_status(tid, r["target_status"]):
                    emoji = {"validado": "🟢", "em risco": "⚠️", "negativo": "🔴"}.get(r["target_status"], "📊")
                    print(f"  {emoji} {name[:50]} → {r['target_status']} (automático)", flush=True)
                    tg_confirmed.append(r)
                    confirmed_count += 1
                    state[tid] = {
                        "nivel": r["nivel"], "vendas": r["vendas"],
                        "cpa": round(r["cpa"], 2) if r["vendas"] > 0 else None,
                        "updated": datetime.now().isoformat(),
                    }
                    time.sleep(0.3)
                continue

            # Escala: fluxo de confirmação com gestor
            pending_ts = prev.get("pending_confirmation_ts")

            if pending_ts:
                # Já pediu confirmação antes — checar resposta
                response = check_confirmation(tid, pending_ts)
                if response == "confirmed":
                    move_status(tid, r["target_status"])
                    confirmed_count += 1
                    tg_confirmed.append(r)
                    print(f"  ✅ {name[:50]} → {r['target_status']} (gestor confirmou)", flush=True)
                    state[tid] = {
                        "nivel": r["nivel"], "vendas": r["vendas"],
                        "cpa": round(r["cpa"], 2) if r["vendas"] > 0 else None,
                        "updated": datetime.now().isoformat(),
                    }
                    time.sleep(0.3)
                    continue
                elif response == "keep":
                    print(f"  ⏸️ {name[:50]} — gestor optou por manter", flush=True)
                    state[tid] = {
                        "nivel": r["nivel"], "vendas": r["vendas"],
                        "cpa": round(r["cpa"], 2) if r["vendas"] > 0 else None,
                        "updated": datetime.now().isoformat(),
                        "gestor_override": "manter",
                    }
                    continue
                elif response == "pause":
                    move_status(tid, "pausado")
                    print(f"  ⏸️ {name[:50]} → pausado (gestor pediu)", flush=True)
                    state[tid] = {
                        "nivel": r["nivel"], "vendas": r["vendas"],
                        "cpa": round(r["cpa"], 2) if r["vendas"] > 0 else None,
                        "updated": datetime.now().isoformat(),
                    }
                    time.sleep(0.3)
                    continue
                else:
                    # Sem resposta ainda — skip (aguardando)
                    print(f"  ⏳ {name[:50]} — aguardando confirmação do gestor", flush=True)
                    continue
            else:
                # Gestor fez override anteriormente — não pedir de novo
                if prev.get("gestor_override") and prev.get("nivel") == r["nivel"]:
                    continue

                # Primeira vez — pedir confirmação
                if post_confirmation_request(
                    tid, name, r["nivel"], r["target_status"],
                    r["vendas"], r["cpa"], r["roas"], r["gestor_id"],
                    custo=r["custo"]
                ):
                    requested_count += 1
                    tg_promotions.append(r)
                    print(f"  📋 {name[:50]} → pediu confirmação para {r['target_status']}", flush=True)
                    state[tid] = {
                        "nivel": r["nivel"], "vendas": r["vendas"],
                        "cpa": round(r["cpa"], 2) if r["vendas"] > 0 else None,
                        "updated": datetime.now().isoformat(),
                        "pending_confirmation_ts": now_ms,
                        "pending_target": r["target_status"],
                    }
                    time.sleep(0.5)
        else:
            # Sem mudança de status — atualizar state
            state[tid] = {
                "nivel": r["nivel"], "vendas": r["vendas"],
                "cpa": round(r["cpa"], 2) if r["vendas"] > 0 else None,
                "updated": datetime.now().isoformat(),
            }

    save_state(state)

    # Telegram + Chat GT: pedidos de confirmação
    if tg_promotions:
        msg = "📋 <b>CLASSIFICAÇÃO — AGUARDANDO CONFIRMAÇÃO</b>\n\n"
        gt_lines = [f"📋 Classificação de Criativos — {datetime.now().strftime('%d/%m %Hh')}", "",
                    "Aguardando confirmação dos gestores:", ""]
        for p in tg_promotions:
            emoji = {"pré-validado": "🟡", "validado": "🟢", "top / escala": "🏆"}.get(p["nivel"], "📊")
            cpa_str = f"R${p['cpa']:.0f}" if p["vendas"] > 0 else "N/A"
            short = p["name"][:40]
            msg += f"{emoji} {short}\n"
            msg += f"   {p['vendas']}v | CPA {cpa_str} | ROAS {p['roas']:.2f} → {p['target_status']}\n\n"
            gt_lines.append(f"{emoji} {short} → {p['target_status']}")
            gt_lines.append(f"   {p['vendas']}v | CPA {cpa_str} | ROAS {p['roas']:.2f}")
            gt_lines.append("")
        msg += f"Total: {len(tg_promotions)} pedidos enviados aos gestores"
        send_telegram(msg)
        gt_lines.append(f"Total: {len(tg_promotions)} pedidos enviados aos gestores")
        gt_lines.append("")
        gt_lines.append("— GPDR Classificador Automático")
        post_chat_gt("\n".join(gt_lines))

    # Telegram + Chat GT: confirmações aplicadas
    if tg_confirmed:
        msg = "✅ <b>STATUS CONFIRMADOS PELOS GESTORES</b>\n\n"
        gt_lines = [f"✅ Status confirmados pelos gestores — {datetime.now().strftime('%d/%m')}", ""]
        for c in tg_confirmed:
            short = c["name"][:40]
            msg += f"• {short} → {c['target_status']}\n"
            gt_lines.append(f"• {short} → {c['target_status']}")
        send_telegram(msg)
        gt_lines.append("")
        gt_lines.append("— GPDR Classificador Automático")
        post_chat_gt("\n".join(gt_lines))

    print(f"\n✅ {tag_count} tags | {selo_cleaned} selos limpos | {requested_count} confirmações | {confirmed_count} confirmados")


def run_quase_la(results):
    """Mostra criativos perto de promoção."""
    print(f"\n{'='*60}")
    print(f"CRIATIVOS 'QUASE LÁ'")
    print(f"{'='*60}\n")

    near = []
    for r in results:
        if r["vendas"] < 1:
            continue  # Sem vendas não é "quase lá"
        dist = distance_to_next(r["vendas"], r["cpa"], r["roas"], r["custo"], r["nicho"])
        if dist and dist[1] <= 3:  # Faltam até 3 vendas
            near.append({**r, "next_nivel": dist[0], "faltam": dist[1]})

    if not near:
        print("Nenhum criativo perto de promoção no momento.")
        return

    near.sort(key=lambda x: x["faltam"])

    msg_lines = ["🎯 <b>CRIATIVOS QUASE LÁ</b>\n"]

    for n in near:
        emoji = "🔥" if n["faltam"] <= 1 else "⚡"
        cpa_str = f"R${n['cpa']:.0f}" if n["vendas"] > 0 else "N/A"
        short = n["name"][:40]
        print(f"  {emoji} {short}")
        print(f"     {n['vendas']} vendas (faltam {n['faltam']}) → {n['next_nivel'].upper()}")
        print(f"     CPA: {cpa_str} | ROAS: {n['roas']:.2f}\n")

        msg_lines.append(
            f"{emoji} <b>{short}</b>\n"
            f"   {n['vendas']} vendas — falta{'m' if n['faltam'] > 1 else ''} "
            f"<b>{n['faltam']}</b> para {n['next_nivel'].upper()}\n"
            f"   CPA {cpa_str} | ROAS {n['roas']:.2f}\n"
        )

    print(f"Total: {len(near)} criativos perto de promoção")

    # Enviar pro Telegram + Chat GT
    msg_lines.append(f"\nTotal: {len(near)} criativos monitorados")
    send_telegram("\n".join(msg_lines))

    # Chat GT (plain text)
    gt_lines = [f"🎯 Criativos Quase Lá — {datetime.now().strftime('%d/%m %Hh')}", ""]
    for n in near:
        emoji = "🔥" if n["faltam"] <= 1 else "⚡"
        cpa_str = f"R${n['cpa']:.0f}" if n["vendas"] > 0 else "N/A"
        short = n["name"][:40]
        gt_lines.append(f"{emoji} {short}")
        gt_lines.append(f"   {n['vendas']} vendas — falta{'m' if n['faltam'] > 1 else ''} {n['faltam']} para {n['next_nivel'].upper()}")
        gt_lines.append(f"   CPA {cpa_str} | ROAS {n['roas']:.2f}")
        gt_lines.append("")
    gt_lines.append(f"Total: {len(near)} criativos monitorados")
    gt_lines.append("")
    gt_lines.append("— GPDR Classificador Automático")
    post_chat_gt("\n".join(gt_lines))


def run_tags_retroativo(tasks):
    """Aplica tags retroativas em TODA a lista GT baseado no status atual.
    Não usa dados RT — apenas o status ClickUp para inferir o nível.
    Para tarefas em 'aguardando teste': aplica potential-* se já tiveram
    selo legado ou se vieram de um AD que está em escala/validado.
    """
    print(f"\n{'='*80}")
    print(f"TAGS DE JORNADA — Aplicação retroativa em toda a lista")
    print(f"{'='*80}\n")

    # Mapeamento de status atual → tag(s) que devem ter
    STATUS_TO_TAGS = {
        "pré-escala": ["pré-validado"],
        "validado":   ["pré-validado", "validado"],
        "escala":     ["pré-validado", "validado", "top"],
    }

    # Mapeamento para potential tags em aguardando teste
    STATUS_TO_POTENTIAL = {
        "pré-escala": ["potential-pré-validado"],
        "validado":   ["potential-validado"],
        "escala":     ["potential-top"],
    }

    # Build index of AD refs → highest status (for potential tags)
    ad_status_index = {}
    for t in tasks:
        if t.get("parent"):
            continue
        status = t["status"]["status"].lower()
        if status not in STATUS_TO_TAGS:
            continue
        refs = extract_refs(t["name"])
        for ref in refs:
            # Extract base AD (without version range)
            base = re.match(r"(AD\d+V?\d*|ADC\d+V?\d*|CE\d+|CY\d+|CC\d+|C\d+|IMG\d+)", ref)
            if base:
                key = base.group(1)
                current_best = ad_status_index.get(key)
                rank = {"pré-escala": 1, "validado": 2, "escala": 3}
                if not current_best or rank.get(status, 0) > rank.get(current_best, 0):
                    ad_status_index[key] = status

    tag_count = 0
    selo_cleaned = 0
    tasks_updated = 0
    skipped = 0

    for t in tasks:
        if t.get("parent"):
            continue
        status = t["status"]["status"].lower()
        name = t["name"]
        tid = t["id"]
        current_tags = {tag["name"] for tag in t.get("tags", [])}
        tags_to_add = []

        # 1. Limpar selos legados
        has_selo = any(s in name for s in SELOS_LEGADOS)
        if has_selo:
            clean_legacy_selos(tid, name)
            selo_cleaned += 1
            time.sleep(0.3)

        # 2. Tarefas em status ativos → tags de jornada baseadas no status
        if status in STATUS_TO_TAGS:
            for tag in STATUS_TO_TAGS[status]:
                if tag not in current_tags:
                    tags_to_add.append(tag)

        # 3. Tarefas em aguardando teste → potential tags
        elif status == "aguardando teste":
            refs = extract_refs(name)
            best_parent_status = None
            rank = {"pré-escala": 1, "validado": 2, "escala": 3}
            for ref in refs:
                base = re.match(r"(AD\d+V?\d*|ADC\d+V?\d*|CE\d+|CY\d+|CC\d+|C\d+|IMG\d+)", ref)
                if base:
                    key = base.group(1)
                    parent_status = ad_status_index.get(key)
                    if parent_status:
                        if not best_parent_status or rank.get(parent_status, 0) > rank.get(best_parent_status, 0):
                            best_parent_status = parent_status

            if best_parent_status and best_parent_status in STATUS_TO_POTENTIAL:
                for tag in STATUS_TO_POTENTIAL[best_parent_status]:
                    if tag not in current_tags:
                        tags_to_add.append(tag)

        # 4. Tarefas em em teste → sem potential, sem jornada ainda (precisa RT)
        # Skip — o classificador normal cuida dessas com dados RT

        if tags_to_add:
            added = apply_tags(tid, tags_to_add)
            tag_count += added
            tasks_updated += 1
            tag_str = ", ".join(tags_to_add)
            print(f"  🏷️ [{status}] +{tag_str} → {name[:55]}", flush=True)
        else:
            skipped += 1

    print(f"\n{'='*60}")
    print(f"RESULTADO:")
    print(f"  {tasks_updated} tarefas atualizadas com tags")
    print(f"  {tag_count} tags aplicadas no total")
    print(f"  {selo_cleaned} selos legados limpos")
    print(f"  {skipped} tarefas sem alteração")


def run_report(results):
    """Relatório completo via Telegram."""
    nivels = defaultdict(list)
    for r in results:
        nivels[r["nivel"]].append(r)

    msg = "📊 <b>CLASSIFICAÇÃO DE CRIATIVOS</b>\n"
    msg += f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"

    total_vendas = sum(r["vendas"] for r in results)
    total_custo = sum(r["custo"] for r in results)
    cpa_geral = total_custo / total_vendas if total_vendas > 0 else 0
    msg += f"<b>Geral:</b> {len(results)} criativos | {total_vendas} vendas | CPA R${cpa_geral:.0f}\n\n"

    for nivel in ["top / escala", "validado", "pré-validado", "em teste"]:
        items = nivels.get(nivel, [])
        emoji = {"em teste": "🔵", "pré-validado": "🟡", "validado": "🟢", "top / escala": "🏆"}[nivel]
        n_vendas = sum(r["vendas"] for r in items)
        n_custo = sum(r["custo"] for r in items)
        n_cpa = n_custo / n_vendas if n_vendas > 0 else 0
        msg += f"{emoji} <b>{nivel.upper()}</b>: {len(items)} criativos | {n_vendas} vendas"
        if n_vendas > 0:
            msg += f" | CPA R${n_cpa:.0f}"
        msg += "\n"

        # Top 3 por vendas nesse nível
        top3 = sorted(items, key=lambda x: x["vendas"], reverse=True)[:3]
        for t in top3:
            short = t["name"][:35]
            msg += f"   • {short} ({t['vendas']}v)\n"
        msg += "\n"

    # Quase lá
    near = []
    for r in results:
        if r["vendas"] < 1:
            continue
        dist = distance_to_next(r["vendas"], r["cpa"], r["roas"], r["custo"], r["nicho"])
        if dist and dist[1] <= 3:
            near.append({**r, "next_nivel": dist[0], "faltam": dist[1]})
    if near:
        near.sort(key=lambda x: x["faltam"])
        msg += "⚡ <b>QUASE LÁ</b>\n"
        for n in near[:5]:
            short = n["name"][:30]
            msg += f"   {short} — falta{'m' if n['faltam']>1 else ''} {n['faltam']} → {n['next_nivel'].upper()}\n"

    send_telegram(msg)
    print("Relatório enviado via Telegram.")


# ============================================================
# MAIN
# ============================================================

def main():
    mode = "preview"
    days = 7
    for arg in sys.argv[1:]:
        if arg == "--preview":
            mode = "preview"
        elif arg == "--execute":
            mode = "execute"
        elif arg == "--quase-la":
            mode = "quase-la"
        elif arg == "--report":
            mode = "report"
        elif arg == "--tags-retroativo":
            mode = "tags-retroativo"
        elif arg.startswith("--days="):
            days = int(arg.split("=")[1])

    now = datetime.now()
    print(f"Classificador de Criativos — {now.strftime('%d/%b/%Y %H:%M')}")

    # Modo retroativo: aplica tags baseado no status atual (não precisa de RT)
    if mode == "tags-retroativo":
        print(f"Modo: TAGS RETROATIVO\n")
        print("Buscando tarefas ClickUp...", flush=True)
        tasks = cached_cu_tasks(LIST_TRAFEGO, include_closed=False, ttl=300)
        print(f"  CU: {len(tasks)} tarefas\n")
        run_tags_retroativo(tasks)
        return

    date_from = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    date_to = now.strftime("%Y-%m-%d")
    print(f"Período: {date_from} a {date_to} ({days} dias) | Modo: {mode.upper()}\n")

    # Buscar dados
    print("Buscando dados...", flush=True)
    tasks = cached_cu_tasks(LIST_TRAFEGO, include_closed=False, ttl=1800)
    rt_index = build_rt_index(date_from, date_to)
    print(f"  CU: {len(tasks)} tarefas | RT: {len(rt_index)} refs\n")

    # Analisar
    results = analyze_tasks(tasks, rt_index)
    results.sort(key=lambda x: x["vendas"], reverse=True)

    if not results:
        print("Nenhum criativo ativo encontrado.")
        return

    if mode == "preview":
        run_preview(results)
    elif mode == "execute":
        run_execute(results)
    elif mode == "quase-la":
        run_quase_la(results)
    elif mode == "report":
        run_report(results)


if __name__ == "__main__":
    main()
