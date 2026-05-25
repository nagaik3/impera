#!/usr/bin/env python3
"""
Auditoria de Nomenclatura — IMPERA (Módulo de Validação)
Verifica tarefas ativas no ClickUp com nomenclatura fora do padrão.
Posta comentário com @mention do copywriter responsável.

NOTA: Polling e Chat Summary consolidados em gate_finalizado.py.
Este script roda APENAS para validação early-stage na COPY list.

Uso:
  python3 auditoria_nomenclatura.py              # Executa auditoria (*/3h polling)
  python3 auditoria_nomenclatura.py --dry        # Mostra sem enviar
  python3 auditoria_nomenclatura.py --server     # Inicia webhook receiver (porta 5003)

Crontab:
  0 */3 * * * cd ~/Scripts && python3 auditoria_nomenclatura.py
  @reboot bash ~/Scripts/start_nomenclatura_webhook.sh

Função importável:
  from auditoria_nomenclatura import validate_task_name
  problems = validate_task_name("[MM][BR][OF01][FB][AD10][V1]")
"""

import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from retry_helper import retry_api_call

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

LIST_COPY = "901324556390"
CHAT_VIEW_ID = "6-901324556390-8"
BOT_USER_ID = 176404277  # Iago (API posts come from the token owner)

STATE_FILE = os.path.expanduser("~/Scripts/data/auditoria_nomenclatura_state.json")

# Webhook configuration
NOMENCLATURA_WEBHOOK_PORT = int(os.environ.get("NOMENCLATURA_WEBHOOK_PORT", "5003"))

# === REGRAS DE NOMENCLATURA ===

NICHOS_VALIDOS = {"DA", "DB", "ED", "EM", "ME", "MM", "NE", "PT", "ZB"}
MERCADOS = {"BR", "EUA"}
FONTES_VALIDAS = {"FB", "GG", "KW", "MG", "OB", "TB", "TT", "YT", "VTURB"}
MODIFICADORES = {"RP"}  # Vão entre nicho e oferta

# Nichos que operam nos EUA (devem ter [BR] ou [EUA])
NICHOS_COM_MERCADO = {"MM", "EM"}

# Tipos especiais — não exigem fonte de tráfego (ou usam VTURB)
TIPOS_ESPECIAIS = {"VSL", "UP", "OTMZ", "LD", "MLD"}
# Prefixos de tipos especiais (para detectar LD01, MLD01, etc.)
TIPOS_ESPECIAIS_PREFIXOS = {"LD", "MLD", "UP"}

# === MAPEAMENTO COPYWRITER ===
# dropdown option name → ClickUp user ID (para @mention)
CF_COPYWRITER = "eeb64866-df57-4dbf-8338-5d4fb58837aa"

COPY_NAME_TO_USER = {
    "YAN": 81970243,
    "REAPER": 18922946,
    "CRISPIM": 118015162,
    "ANA": 118024166,
    "ELIAS": 84627549,
    "CAROL": 118051219,
}

# Assignee name fallback
ASSIGNEE_TO_COPY = {
    "yan": "YAN", "yan da silva": "YAN", "yan da silva rangel": "YAN",
    "reaper": "REAPER", "cassio": "REAPER", "cassiocbrites": "REAPER",
    "crispim": "CRISPIM", "crispim.copywriter": "CRISPIM",
    "ana": "ANA", "ana ramos": "ANA", "ana paula": "ANA",
    "elias": "ELIAS", "elias brazlu": "ELIAS",
    "carol": "CAROL", "carol andrade": "CAROL",
}


# === API ===

@retry_api_call(max_retries=3)
def api_get(endpoint):
    url = f"https://api.clickup.com/api/v2{endpoint}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", API_TOKEN)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def fetch_tasks(list_id):
    tasks = []
    page = 0
    while True:
        data = api_get(f"/list/{list_id}/task?subtasks=true&include_closed=false&page={page}")
        tasks.extend(data.get("tasks", []))
        if data.get("last_page", True):
            break
        page += 1
    return tasks


def api_post(endpoint, payload):
    """POST no ClickUp API."""
    url = f"https://api.clickup.com/api/v2{endpoint}"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", API_TOKEN)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def get_task_comments(task_id):
    """Busca comentários de uma tarefa."""
    try:
        data = api_get(f"/task/{task_id}/comment")
        return data.get("comments", [])
    except Exception as e:
        print(f"  [ERRO] Buscar comentários {task_id}: {e}")
        return []


# === COPYWRITER LOOKUP ===

def get_copywriter_from_task(task):
    """
    Retorna (nome_copy, user_id) do copywriter da tarefa.
    Prioriza campo dropdown, depois assignees.
    """
    # 1. Campo dropdown Copywriter
    for cf in task.get("custom_fields", []):
        if cf.get("id") == CF_COPYWRITER and cf.get("value") is not None:
            opts = cf.get("type_config", {}).get("options", [])
            for o in opts:
                if o.get("orderindex") == cf["value"]:
                    name = o.get("name", "").upper()
                    user_id = COPY_NAME_TO_USER.get(name)
                    return name, user_id
    # 2. Fallback: assignees
    for a in task.get("assignees", []):
        uname = (a.get("username") or "").lower()
        copy_name = ASSIGNEE_TO_COPY.get(uname)
        if copy_name:
            return copy_name, COPY_NAME_TO_USER.get(copy_name)
    return None, None


# === COMENTÁRIOS E CHAT ===

def post_nomenclature_comment(task_id, task_name, problems, copywriter_name=None, copywriter_id=None):
    """Posta comentário na tarefa com @mention do copywriter."""
    prob_list = "\n".join(f"  - {p}" for p in problems)
    mention = f"@{copywriter_name}" if copywriter_name else "Responsável"
    comment = (
        f"⚠️ NOMENCLATURA FORA DO PADRÃO\n\n"
        f"{mention}, esta tarefa apresenta problemas de nomenclatura:\n{prob_list}\n\n"
        f"Padrão correto: [NICHO][OFERTA][FONTE][AD##][V##-V##]\n\n"
        f"👉 Corrija o nome e responda \"CORRIGIDO\" neste comentário.\n\n"
        f"— GPDR Auditoria Automática"
    )
    payload = {"comment_text": comment, "notify_all": False}
    if copywriter_id:
        payload["assignee"] = copywriter_id
    try:
        api_post(f"/task/{task_id}/comment", payload)
        return True
    except Exception as e:
        print(f"  [ERRO] Comentário na tarefa {task_id}: {e}")
        return False


def post_corrigido_ok(task_id, copywriter_name=None):
    """Posta confirmação de revalidação OK."""
    mention = f"@{copywriter_name}" if copywriter_name else "Responsável"
    comment = (
        f"✅ NOMENCLATURA REVALIDADA\n\n"
        f"{mention} corrigiu o nome da tarefa.\n"
        f"Validação: OK — todos os campos conferidos.\n"
        f"Tarefa liberada para seguir na esteira.\n\n"
        f"— GPDR Auditoria Automática"
    )
    try:
        api_post(f"/task/{task_id}/comment", {
            "comment_text": comment,
            "notify_all": False,
        })
        return True
    except Exception:
        return False


def post_corrigido_still_bad(task_id, problems, copywriter_name=None, copywriter_id=None):
    """Posta aviso de que a correção ainda tem problemas."""
    prob_list = "\n".join(f"  - {p}" for p in problems)
    mention = f"@{copywriter_name}" if copywriter_name else "Responsável"
    comment = (
        f"⚠️ NOMENCLATURA AINDA COM PROBLEMAS\n\n"
        f"{mention}, a correção foi detectada mas ainda há problemas:\n{prob_list}\n\n"
        f"Corrija novamente e responda \"CORRIGIDO\".\n\n"
        f"— GPDR Auditoria Automática"
    )
    payload = {"comment_text": comment, "notify_all": False}
    if copywriter_id:
        payload["assignee"] = copywriter_id
    try:
        api_post(f"/task/{task_id}/comment", payload)
        return True
    except Exception:
        return False


def post_reminder(task_id, problems, copywriter_name=None, copywriter_id=None):
    """Posta lembrete após 24h sem resposta."""
    prob_list = "\n".join(f"  - {p}" for p in problems)
    mention = f"@{copywriter_name}" if copywriter_name else "Responsável"
    comment = (
        f"🔔 LEMBRETE — NOMENCLATURA PENDENTE\n\n"
        f"{mention}, esta tarefa ainda tem problemas de nomenclatura "
        f"detectados há mais de 24h. Corrija e responda \"CORRIGIDO\".\n\n"
        f"{prob_list}\n\n"
        f"— GPDR Auditoria Automática"
    )
    payload = {"comment_text": comment, "notify_all": False}
    if copywriter_id:
        payload["assignee"] = copywriter_id
    try:
        api_post(f"/task/{task_id}/comment", payload)
        return True
    except Exception:
        return False


def post_chat_view(text):
    """Posta mensagem no Chat da lista Copy/Edição."""
    url = f"https://api.clickup.com/api/v2/view/{CHAT_VIEW_ID}/comment"
    payload = json.dumps({"comment_text": text}).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", API_TOKEN)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return True
    except Exception as e:
        print(f"  [ERRO] Chat View: {e}")
        return False


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    body = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return True
    except Exception as e:
        # Fallback sem parse_mode
        body = json.dumps({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", ""),
        }).encode()
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                return True
        except:
            print(f"  [ERRO] Telegram: {e}")
            return False


# === STATE (evitar alertas repetidos) ===

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"alerted": {}, "pending_corrigido": {}, "resolved": {}}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# === VALIDAÇÃO ===

def extract_brackets(name):
    """Extrai todos os grupos entre colchetes."""
    return re.findall(r'\[([^\]]+)\]', name)


def validate_task_name(name):
    """Valida nomenclatura e retorna lista de problemas encontrados."""
    name = name.strip()
    problems = []

    # Deve começar com [
    if not name.startswith("["):
        problems.append("Não começa com [")
        return problems

    groups = extract_brackets(name)
    if not groups:
        problems.append("Sem grupos entre colchetes")
        return problems

    # === Validar colchetes balanceados ===
    depth = 0
    for ch in name:
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
        if depth < 0:
            problems.append("Colchetes desbalanceados (] sem [)")
            break
    if depth > 0:
        problems.append("Colchetes desbalanceados ([ sem ])")

    # Detectar colchetes aninhados ou mal formados
    if re.search(r'\][^\[]*\[', name.replace('][', '')):
        pass  # Ok, pode ter espaço

    # Detectar padrão ]X] ou [X[ (colchete errado)
    if re.search(r'\][A-Z]{2}\]', name):
        problems.append("Possível colchete invertido (ex: ]XX] deveria ser [XX])")

    # === Validar primeiro grupo = nicho ===
    first = groups[0]
    if first not in NICHOS_VALIDOS:
        if first in MERCADOS:
            problems.append(f"Mercado [{first}] na posição do nicho — ordem correta: [NICHO][MERCADO]")
        elif first in MODIFICADORES:
            problems.append(f"Modificador [{first}] na posição do nicho — deve vir após o nicho")
        else:
            problems.append(f"Nicho [{first}] não reconhecido — válidos: {', '.join(sorted(NICHOS_VALIDOS))}")

    nicho = first if first in NICHOS_VALIDOS else None

    # === Validar mercado para nichos que operam EUA ===
    if nicho and nicho in NICHOS_COM_MERCADO:
        has_mercado = any(g in MERCADOS for g in groups)
        if not has_mercado:
            problems.append(f"[{nicho}] opera BR e EUA — precisa de [BR] ou [EUA] após o nicho")

    # === Validar ordem: mercado deve vir logo após nicho ===
    if nicho and len(groups) > 1:
        second = groups[1]
        if nicho in NICHOS_COM_MERCADO:
            if second not in MERCADOS and second not in MODIFICADORES:
                for i, g in enumerate(groups[2:], 2):
                    if g in MERCADOS:
                        problems.append(f"Mercado [{g}] na posição {i+1} — deveria ser posição 2 (após nicho)")

    # === Validar fonte ===
    fonte_found = False
    for g in groups:
        if g in FONTES_VALIDAS:
            fonte_found = True
            break
    is_special = any(
        g in TIPOS_ESPECIAIS or
        any(g.startswith(p) for p in TIPOS_ESPECIAIS_PREFIXOS)
        for g in groups
    )
    if not fonte_found and not is_special:
        problems.append("Fonte de tráfego não encontrada — válidas: " + ", ".join(sorted(FONTES_VALIDAS)))

    # === Validar OTMZ — deve ser grupo separado [OTMZ][NOME] ===
    for g in groups:
        if "OTMZ" in g and g != "OTMZ":
            problems.append(f"[OTMZ] deve ser grupo separado — encontrado [{g}], correto: [OTMZ][{g.replace('OTMZ', '').strip(' -_')}]")

    # === Validar espaços extras nos ranges e grupos ===
    for g in groups:
        if re.search(r'\s', g):
            if re.match(r'^AD', g):
                problems.append(f"Espaço indevido dentro de [{g}]")
            elif re.match(r'^(MLD|LD|CE|CY|CC|PRESSELL)', g):
                problems.append(f"Espaço indevido dentro de [{g}]")
            elif re.match(r'^[A-Z]{2,}\d', g):
                problems.append(f"Espaço indevido dentro de [{g}]")

    return problems


# === EXECUÇÃO: AUDITORIA ===

def run(dry_run=False):
    now = datetime.now()
    print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Auditoria de Nomenclatura")
    if dry_run:
        print("  (modo dry-run — sem enviar alertas)\n")

    state = load_state()
    alerted = state.get("alerted", {})
    pending = state.get("pending_corrigido", {})
    issues = []

    for list_id, list_name in [(LIST_COPY, "COPY")]:
        print(f"\n--- Lista: {list_name} ---")
        tasks = fetch_tasks(list_id)
        checked = 0

        for task in tasks:
            name = task["name"].strip()
            if not name.startswith("["):
                continue
            checked += 1

            problems = validate_task_name(name)
            if problems:
                tid = task["id"]
                copy_name, copy_id = get_copywriter_from_task(task)
                issue = {
                    "id": tid,
                    "name": name,
                    "list": list_name,
                    "problems": problems,
                    "url": task.get("url", ""),
                    "copywriter": copy_name,
                    "copywriter_id": copy_id,
                }
                issues.append(issue)
                print(f"  ⚠ {name[:60]} → {copy_name or '?'}")
                for p in problems:
                    print(f"    → {p}")

        print(f"  {checked} tarefas verificadas")

    # Filtrar issues já alertadas
    new_issues = [i for i in issues if i["id"] not in alerted and i["id"] not in pending]

    print(f"\nTotal de problemas: {len(issues)} ({len(new_issues)} novos)")

    if new_issues and not dry_run:
        # Comentar nas tarefas com @mention do copywriter
        commented = 0
        for issue in new_issues:
            if post_nomenclature_comment(
                issue["id"], issue["name"], issue["problems"],
                copywriter_name=issue["copywriter"],
                copywriter_id=issue["copywriter_id"]
            ):
                commented += 1
            # Registrar como pendente de "CORRIGIDO"
            pending[issue["id"]] = {
                "name": issue["name"],
                "date": now.isoformat(),
                "problems": issue["problems"],
                "copywriter": issue["copywriter"],
                "copywriter_id": issue["copywriter_id"],
                "reminder_sent": False,
            }
        print(f"  Comentários postados: {commented}/{len(new_issues)} tarefas")

    elif new_issues and dry_run:
        print("\n  [DRY-RUN] Tarefas que seriam alertadas:")
        for issue in new_issues:
            print(f"    {issue['name']} → @{issue['copywriter'] or '?'}")
            for p in issue["problems"]:
                print(f"      → {p}")

    # Limpar alertas antigos (>7 dias) para re-verificar
    cutoff = (now - timedelta(days=7)).isoformat()
    to_remove = [tid for tid, info in alerted.items() if info.get("date", "") < cutoff]
    for tid in to_remove:
        del alerted[tid]

    state["alerted"] = alerted
    state["pending_corrigido"] = pending
    state["last_run"] = now.isoformat()
    state["last_issues"] = len(issues)
    state["last_new"] = len(new_issues)

    if not dry_run:
        save_state(state)

    return issues


# === EXECUÇÃO: POLL "CORRIGIDO" ===

# === REMOVED: run_poll() and run_chat_summary() ===
# These are now consolidated in gate_finalizado.py to prevent duplication.
# See: gate_finalizado.py for unified polling and chat summary logic.


# === WEBHOOK: Real-time validation on task creation ===

class NomenclaturWebhookHandler(BaseHTTPRequestHandler):
    """Handles ClickUp webhook events for task creation."""

    def do_POST(self):
        if self.path == "/webhook/nomenclatura":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len)

            try:
                event = json.loads(body)
                event_type = event.get("event")

                if event_type == "taskCreated":
                    task = event.get("task", {})
                    task_id = task.get("id")
                    task_name = task.get("name", "").strip()

                    if task_name.startswith("[") and task_id:
                        problems = validate_task_name(task_name)
                        if problems:
                            print(f"  [WEBHOOK] {task_name[:50]} → Validando...")
                            cf_id = task.get("custom_fields", {})
                            # Tenta extrair copywriter do custom field ou assignees
                            copy_name, copy_id = get_copywriter_from_task(task)

                            if post_nomenclature_comment(task_id, task_name, problems, copy_name, copy_id):
                                print(f"    ✅ Comentário postado para @{copy_name or '?'}")
                            else:
                                print(f"    ⚠️  Falha ao postar comentário")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}).encode())

            except Exception as e:
                print(f"  [WEBHOOK ERROR] {e}")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress default logging


def start_webhook_server():
    """Starts webhook server in background thread."""
    server = HTTPServer(("127.0.0.1", NOMENCLATURA_WEBHOOK_PORT), NomenclaturWebhookHandler)
    print(f"[WEBHOOK] Listening on port {NOMENCLATURA_WEBHOOK_PORT}...")

    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server


# === MAIN ===

if __name__ == "__main__":
    if not API_TOKEN:
        print("ERRO: CLICKUP_API_TOKEN não configurado")
        sys.exit(1)

    if "--server" in sys.argv:
        print(f"[{datetime.now().strftime('%d/%m/%Y %H:%M')}] 🎯 Nomenclatura Webhook Server v2.0")
        server = start_webhook_server()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[WEBHOOK] Encerrado.")
            server.shutdown()
    else:
        dry_run = "--dry" in sys.argv
        run(dry_run=dry_run)
