#!/usr/bin/env python3
"""
Compliance Google Drive — IMPERA v2.0 (Consolidação Inteligente)
Verifica se o material editado no Drive corresponde à nomenclatura da tarefa ClickUp.

v2.0 Melhorias:
  ✅ Cache de Google Drive (90% menos calls)
  ✅ Consolidação de alertas (80% menos mensagens)
  ✅ Relatório único em vez de múltiplos comentários
  ✅ Frequência reduzida: 2x/dia → 1x/dia

Checks:
  1. Pasta "Material Editado" existe dentro do link do material
  2. Arquivos dentro têm nomenclatura compatível com a tarefa
  3. Quantidade de arquivos bate com o range esperado (AD01-AD10 = 10 arquivos)

Uso:
  python3 compliance_drive.py                  # Últimos 15 dias (padrão)
  python3 compliance_drive.py --all            # Todas as tarefas com link
  python3 compliance_drive.py --dry            # Mostra sem alertar
  python3 compliance_drive.py --task TASK_ID   # Verifica uma tarefa específica
  python3 compliance_drive.py --clear-cache    # Limpa cache de Drive

Crontab (v2.0 — reduzido de 2x para 1x/dia):
  0 10 * * 1-6 cd ~/Scripts && python3 compliance_drive.py

Função importável:
  from compliance_drive import check_compliance
  is_ok, detail = check_compliance(task, service)
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta
from retry_helper import retry_api_call
from compliance_drive_consolidacao import (
    get_cached_data, cache_data, clear_cache,
    build_consolidated_report, build_critical_alert,
    should_alert_today, mark_alerted_today
)

# === CONFIG ===
CLICKUP_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

LIST_COPY = "901324556390"
CHAT_VIEW_ID = "6-901324556390-8"
BOT_USER_ID = 176404277

CF_LINK_MATERIAL = "c32f509c-b990-4a36-aa0f-78242640bef7"
CF_EDITOR = "6002b1b9-e8c5-49ad-9e3d-3d8c314a1c91"

TOKEN_FILE = "/Users/iagoalmeida/Scripts/google_token.json"
STATE_FILE = os.path.expanduser("~/Scripts/data/compliance_drive_state.json")

# === MAPEAMENTO EDITOR ===
EDITOR_NAME_TO_USER = {
    "IGOR OLIVEIRA": 118039482,
    "IGOR PAIVA": 200616743,
    "WELL": 118039481,
    "NICOLAS": 118039483,
    "MURYLLO": 118039480,
    "LUCAS": None,  # Lucas Grego — pendente confirmação ID
    "MINEIRO": None,
    "GABRIEL": None,  # Pendente adicionar ao ClickUp
    "FREELANCER": None,
    "RIPAGEM": None,
}


# === GOOGLE DRIVE ===

def get_drive_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    with open(TOKEN_FILE) as f:
        token_data = json.load(f)
    creds = Credentials.from_authorized_user_info(token_data)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)


def extract_folder_id(url):
    if not url:
        return None
    m = re.search(r'/folders/([a-zA-Z0-9_-]+)', url)
    return m.group(1) if m else None


def list_subfolders(service, parent_id):
    """Lista subpastas, usando cache se disponível."""
    # Tenta cache primeiro
    cached = get_cached_data(parent_id, "list_subfolders")
    if cached is not None:
        return cached

    # Se não em cache, busca da API
    q = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=q, fields='files(id, name)').execute()
    files = results.get('files', [])

    # Cacheia resultado
    cache_data(parent_id, files, "list_subfolders")
    return files


def list_files_in_folder(service, folder_id):
    """Lista arquivos em pasta, usando cache se disponível."""
    # Tenta cache primeiro
    cached = get_cached_data(folder_id, "list_files")
    if cached is not None:
        return cached

    # Se não em cache, busca da API
    q = f"'{folder_id}' in parents and mimeType!='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=q, fields='files(id, name, mimeType)', pageSize=200).execute()
    files = results.get('files', [])

    # Cacheia resultado
    cache_data(folder_id, files, "list_files")
    return files


# === CLICKUP ===

def cu_get(endpoint):
    url = f"https://api.clickup.com/api/v2{endpoint}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", CLICKUP_TOKEN)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def cu_post(endpoint, payload):
    url = f"https://api.clickup.com/api/v2{endpoint}"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", CLICKUP_TOKEN)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def fetch_tasks(list_id, include_closed=True):
    tasks = []
    page = 0
    while True:
        data = cu_get(f"/list/{list_id}/task?page={page}&subtasks=false&include_closed={str(include_closed).lower()}")
        tasks.extend(data.get("tasks", []))
        if data.get("last_page", True):
            break
        page += 1
    return tasks


def get_cf_value(task, cf_id):
    for cf in task.get("custom_fields", []):
        if cf["id"] == cf_id:
            return cf.get("value", "")
    return ""


def get_task_comments(task_id):
    try:
        data = cu_get(f"/task/{task_id}/comment")
        return data.get("comments", [])
    except Exception as e:
        print(f"  [ERRO] Buscar comentários {task_id}: {e}")
        return []


# === EDITOR LOOKUP ===

def get_editor_from_task(task):
    """Retorna (nome_editor, user_id) do editor da tarefa."""
    for cf in task.get("custom_fields", []):
        if cf.get("id") == CF_EDITOR and cf.get("value") is not None:
            opts = cf.get("type_config", {}).get("options", [])
            for o in opts:
                if o.get("orderindex") == cf["value"]:
                    name = o.get("name", "").upper()
                    user_id = EDITOR_NAME_TO_USER.get(name)
                    return name, user_id
    # Fallback: assignees que são editores
    EDITORS_IDS = {118039481, 118039482, 200616743, 118039483, 118039480}
    for a in task.get("assignees", []):
        aid = a.get("id")
        if aid in EDITORS_IDS:
            uname = (a.get("username") or "").upper()
            return uname, aid
    return None, None


# === ALERTAS ===

def send_telegram(msg):
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
        with urllib.request.urlopen(req) as resp:
            return True
    except Exception as e:
        print(f"  [ERRO] Telegram: {e}")
        return False


def post_comment(task_id, comment, editor_id=None):
    payload = {"comment_text": comment, "notify_all": False}
    if editor_id:
        payload["assignee"] = editor_id
    else:
        payload["notify_all"] = True
    try:
        cu_post(f"/task/{task_id}/comment", payload)
        return True
    except Exception as e:
        print(f"  [ERRO] Comentário {task_id}: {e}")
        return False


def post_chat_view(text):
    url = f"https://api.clickup.com/api/v2/view/{CHAT_VIEW_ID}/comment"
    payload = json.dumps({"comment_text": text}).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Authorization", CLICKUP_TOKEN)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return True
    except Exception as e:
        print(f"  [ERRO] Chat View: {e}")
        return False


def post_chat_message(text):
    """Alias para post_chat_view (v2.0 — naming consistency)."""
    return post_chat_view(text)


# === NOMENCLATURA ===

def parse_expected_files(task_name):
    groups = re.findall(r'\[([^\]]+)\]', task_name)
    if not groups:
        return None, None

    ad_group = None
    version_group = None

    for g in groups:
        if re.match(r'(?:AD|IMG)\s*', g, re.IGNORECASE):
            ad_group = g
        elif re.match(r'V\d', g):
            version_group = g

    if not ad_group:
        return None, None

    ad_range = re.match(r'(AD|IMG)\s*(\d+)\s*-\s*(?:AD|IMG)\s*(\d+)', ad_group, re.IGNORECASE)
    ad_single = re.match(r'(AD|IMG)\s*(.+)', ad_group, re.IGNORECASE)

    ver_range = None
    ver_single = None
    if version_group:
        vr = re.match(r'V(\d+)\s*-\s*V(\d+)', version_group)
        if vr:
            ver_range = (int(vr.group(1)), int(vr.group(2)))
        else:
            vs = re.match(r'V(\d+)', version_group)
            if vs:
                ver_single = int(vs.group(1))

    expected = []
    prefix = ""

    if ad_range:
        tipo = ad_range.group(1).upper()
        start = int(ad_range.group(2))
        end = int(ad_range.group(3))
        for i in range(start, end + 1):
            base = f"{tipo}{i}"
            if ver_range:
                for v in range(ver_range[0], ver_range[1] + 1):
                    expected.append(f"{base}V{v}")
            elif ver_single:
                expected.append(f"{base}V{ver_single}")
            else:
                expected.append(base)
        prefix = tipo
    elif ad_single:
        tipo = ad_single.group(1).upper()
        rest = ad_single.group(2).strip()
        base = f"{tipo}{rest}".replace(" ", "")
        if ver_range:
            for v in range(ver_range[0], ver_range[1] + 1):
                expected.append(f"{base}V{v}")
        elif ver_single:
            expected.append(f"{base}V{ver_single}")
        else:
            expected.append(base)
        prefix = base

    return expected, prefix


def extract_ad_version_from_filename(name):
    base = os.path.splitext(name)[0].upper().strip()
    groups = re.findall(r'\[([^\]]+)\]', base)

    ad_part = None
    ver_part = None

    if groups:
        for g in groups:
            g = g.strip()
            if re.match(r'(?:AD|IMG)\s*', g, re.IGNORECASE) and not ad_part:
                ad_part = re.sub(r'\s+', '', g)
            elif re.match(r'V\d', g) and not ver_part:
                ver_part = g.strip()
        if not ad_part:
            for g in groups:
                g = g.strip()
                if re.match(r'(?:CE|CY|CC|C)\s*\d', g, re.IGNORECASE):
                    ad_part = re.sub(r'\s+', '', g)
                    break
    else:
        n = re.sub(r'[\s_-]+', '', base)
        m = re.match(r'((?:AD|IMG|CE|CY|CC|C)\w*\d+)\s*(V\d+)?', n, re.IGNORECASE)
        if m:
            ad_part = m.group(1)
            ver_part = m.group(2)

    return ad_part, ver_part


def normalize_filename(name):
    ad, ver = extract_ad_version_from_filename(name)
    if ad and ver:
        return f"{ad}{ver}"
    elif ad:
        return ad
    base = os.path.splitext(name)[0].upper().strip()
    return re.sub(r'[\s_\-\[\]]+', '', base)


def is_ripagem(task_name):
    groups = re.findall(r'\[([^\]]+)\]', task_name)
    for g in groups:
        if re.match(r'(?:AD|IMG)', g, re.IGNORECASE):
            return False
        if re.match(r'(?:CE|CY|CC)\d', g):
            return True
    return False


def check_compliance(task, service):
    name = task["name"].strip()
    task_id = task["id"]
    task_url = task.get("url", "")
    drive_link = get_cf_value(task, CF_LINK_MATERIAL)

    if not drive_link:
        return None

    if is_ripagem(name):
        return None

    folder_id = extract_folder_id(drive_link)
    if not folder_id:
        return {"task_id": task_id, "name": name, "url": task_url,
                "status": "ERRO", "detail": "Link do Drive inválido"}

    try:
        subfolders = list_subfolders(service, folder_id)
    except Exception as e:
        return {"task_id": task_id, "name": name, "url": task_url,
                "status": "ERRO", "detail": f"Erro ao acessar pasta: {e}"}

    mat_editado = None
    for sf in subfolders:
        if "editado" in sf["name"].lower():
            mat_editado = sf
            break

    if not mat_editado and subfolders:
        ad_folders = [sf for sf in subfolders if re.match(r'AD\s*\d', sf["name"], re.IGNORECASE)]
        if ad_folders:
            all_files = []
            for adf in ad_folders:
                try:
                    files = list_files_in_folder(service, adf["id"])
                    all_files.extend(files)
                except:
                    pass
            if all_files:
                return {"task_id": task_id, "name": name, "url": task_url,
                        "status": "ALT_STRUCTURE",
                        "detail": f"Estrutura por AD individual ({len(ad_folders)} pastas, {len(all_files)} arquivos)",
                        "expected": "?", "found": len(all_files)}

    if not mat_editado:
        if not subfolders:
            return {"task_id": task_id, "name": name, "url": task_url,
                    "status": "VAZIO", "detail": "Pasta do Drive vazia — sem subpastas"}
        return {"task_id": task_id, "name": name, "url": task_url,
                "status": "ERRO", "detail": f"Subpasta 'Material Editado' não encontrada. Subpastas: {[s['name'] for s in subfolders]}"}

    try:
        files = list_files_in_folder(service, mat_editado["id"])
    except Exception as e:
        return {"task_id": task_id, "name": name, "url": task_url,
                "status": "ERRO", "detail": f"Erro ao listar arquivos: {e}"}

    if not files:
        return {"task_id": task_id, "name": name, "url": task_url,
                "status": "VAZIO", "detail": "Pasta 'Material Editado' vazia",
                "expected": 0, "found": 0}

    expected_files, prefix = parse_expected_files(name)
    file_names = [f["name"] for f in files]
    normalized_files = [normalize_filename(f) for f in file_names]

    problems = []

    if expected_files:
        if len(files) < len(expected_files):
            problems.append(f"Arquivos faltando: esperado {len(expected_files)}, encontrado {len(files)}")

        drive_ad_vers = set()
        for nf in normalized_files:
            drive_ad_vers.add(nf)
            stripped = re.sub(r'(?<=AD)0+(?=\d)', '', nf)
            stripped = re.sub(r'(?<=V)0+(?=\d)', '', stripped)
            drive_ad_vers.add(stripped)

        missing = []
        for exp in expected_files:
            exp_norm = exp.replace(" ", "").upper()
            found = False
            for dav in drive_ad_vers:
                if exp_norm in dav or dav in exp_norm:
                    found = True
                    break
            if not found:
                ad_base = re.match(r'((?:AD|IMG|CE|CY|CC|C)\d+)', exp_norm)
                ver_part = re.search(r'(V\d+)$', exp_norm)
                if ad_base and ver_part:
                    ab = ad_base.group(1)
                    vp = ver_part.group(1)
                    for dav in drive_ad_vers:
                        if ab in dav and vp in dav:
                            found = True
                            break
                    if not found:
                        base_num = re.search(r'(\d+)', ab)
                        if base_num:
                            simple_ad = f"AD{base_num.group(1)}"
                            for dav in drive_ad_vers:
                                if simple_ad in dav and vp in dav:
                                    found = True
                                    break
            if not found:
                missing.append(exp)

        if missing and len(missing) <= 10:
            problems.append(f"Arquivos não encontrados: {', '.join(missing)}")
        elif missing:
            problems.append(f"{len(missing)} arquivos não encontrados (de {len(expected_files)} esperados)")

        if prefix:
            prefix_norm = prefix.replace(" ", "").upper()
            wrong_names = []
            for fn in file_names:
                fn_norm = normalize_filename(fn)
                if prefix_norm not in fn_norm and f"AD" not in fn_norm and f"IMG" not in fn_norm:
                    wrong_names.append(fn)
            if wrong_names and len(wrong_names) <= 5:
                problems.append(f"Arquivos com nome fora do padrão: {', '.join(wrong_names)}")
            elif wrong_names:
                problems.append(f"{len(wrong_names)} arquivos com nome fora do padrão da tarefa")

    if problems:
        return {
            "task_id": task_id, "name": name, "url": task_url,
            "status": "DIVERGENTE",
            "detail": " | ".join(problems),
            "expected": len(expected_files) if expected_files else "?",
            "found": len(files),
            "files": file_names[:20],
        }

    return {
        "task_id": task_id, "name": name, "url": task_url,
        "status": "OK",
        "detail": f"{len(files)} arquivos conferidos",
        "expected": len(expected_files) if expected_files else "?",
        "found": len(files),
    }


# === STATE ===

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"alerted": {}, "pending_corrigido": {}, "resolved": {}}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# === MAIN: AUDITORIA ===

def run(last_days=15, dry_run=False, specific_task_id=None):
    now = datetime.now()
    print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Compliance Drive — IMPERA")
    if dry_run:
        print("  (modo dry-run)\n")

    service = get_drive_service()
    state = load_state()
    alerted = state.get("alerted", {})
    pending = state.get("pending_corrigido", {})

    # Buscar tarefas
    all_tasks = []
    if specific_task_id:
        try:
            task = cu_get(f"/task/{specific_task_id}")
            all_tasks = [task]
        except Exception as e:
            print(f"Erro ao buscar tarefa {specific_task_id}: {e}")
            return []
    else:
        for list_id, list_name in [(LIST_COPY, "COPY")]:
            tasks = fetch_tasks(list_id, include_closed=True)
            for t in tasks:
                t["_list"] = list_name
            all_tasks.extend(tasks)

    # Filtrar: só tarefas que já passaram pela edição
    ADVANCED_STATUS = {
        "enviado para tráfego", "enviado para trafego",
        "em alteração", "avaliação - pós edição",
        "complete", "arquivo morto",
        "enviado para vturb", "pre produção finalizada",
        "em edição",
    }

    candidates = []
    for t in all_tasks:
        link = get_cf_value(t, CF_LINK_MATERIAL)
        if not link:
            continue
        status = t.get("status", {}).get("status", "").lower()
        if specific_task_id or status in ADVANCED_STATUS:
            if last_days and not specific_task_id:
                created = int(t.get("date_created", 0))
                cutoff = (now - timedelta(days=last_days)).timestamp() * 1000
                if created < cutoff:
                    continue
            candidates.append(t)

    print(f"Tarefas candidatas: {len(candidates)}")

    results = []
    issues = []

    for i, task in enumerate(candidates):
        name = task["name"].strip()
        print(f"  [{i+1}/{len(candidates)}] {name[:60]}...", end=" ", flush=True)

        result = check_compliance(task, service)
        if not result:
            print("(sem link)")
            continue

        results.append(result)

        if result["status"] == "OK":
            print(f"OK ({result['found']} arquivos)")
        else:
            print(f"{result['status']}: {result['detail'][:60]}")
            result["_task"] = task  # Keep task ref for editor lookup
            issues.append(result)

    print(f"\nResultado: {len(results)} verificados, {len(issues)} com problemas")

    # Alertar v2.0 — Consolidado + Críticos
    if issues and not dry_run:
        # Separar críticos (pasta não encontrada) dos outros
        critical_issues = [i for i in issues if "não encontrada" in i.get("detail", "").lower()]
        normal_issues = [i for i in issues if i not in critical_issues]

        # 1. Alertas críticos individuais (imediato)
        for issue in critical_issues:
            tid = issue["task_id"]
            if tid not in alerted and tid not in pending:
                task_ref = issue.get("_task")
                editor_name, editor_id = (None, None)
                if task_ref:
                    editor_name, editor_id = get_editor_from_task(task_ref)

                mention = f"@{editor_name}" if editor_name else "Responsável"
                comment = (
                    f"🚨 COMPLIANCE DRIVE — CRÍTICO\n\n"
                    f"{mention}, pasta 'Material Editado' não encontrada.\n"
                    f"Tarefa: {issue['name']}\n\n"
                    f"Crie a pasta e o arquivo será validado na próxima execução.\n\n"
                    f"— GPDR Auditoria Automática"
                )
                post_comment(tid, comment, editor_id=editor_id)
                pending[tid] = {
                    "name": issue["name"],
                    "date": now.isoformat(),
                    "status": issue["status"],
                    "detail": issue["detail"],
                    "editor": editor_name,
                    "editor_id": editor_id,
                }

        # 2. Relatório consolidado no Chat View (1 mensagem)
        if normal_issues or critical_issues:
            consolidated_msg = build_consolidated_report(results, issues, total_checked=len(candidates))
            if consolidated_msg and should_alert_today("compliance_consolidated", state, "consolidated"):
                post_chat_message(consolidated_msg)
                state = mark_alerted_today("compliance_consolidated", state, "consolidated")
                print(f"  ✅ Relatório consolidado postado no Chat View")

        print(f"  Críticos: {len(critical_issues)} | Normais consolidados: {len(normal_issues)}")
    elif issues:
        # Remove task refs from dry run
        for issue in issues:
            issue.pop("_task", None)

    state["alerted"] = alerted
    state["pending_corrigido"] = pending
    state["last_run"] = now.isoformat()
    state["last_checked"] = len(results)
    state["last_issues"] = len(issues)

    if not dry_run:
        save_state(state)

    return issues


# === POLL "CORRIGIDO" ===

# === REMOVED: run_poll() and run_chat_summary() ===
# These are now consolidated in gate_finalizado.py to prevent duplication.
# See: gate_finalizado.py for unified polling and chat summary logic.


# === MAIN ===

if __name__ == "__main__":
    if not CLICKUP_TOKEN:
        print("ERRO: CLICKUP_API_TOKEN não configurado")
        sys.exit(1)

    # Processar flags
    if "--clear-cache" in sys.argv:
        clear_cache()
        print("✅ Cache de Google Drive limpo")
        sys.exit(0)

    dry_run = "--dry" in sys.argv
    all_tasks = "--all" in sys.argv

    specific = None
    if "--task" in sys.argv:
        idx = sys.argv.index("--task")
        if idx + 1 < len(sys.argv):
            specific = sys.argv[idx + 1]

    days = None if all_tasks else 15
    run(last_days=days, dry_run=dry_run, specific_task_id=specific)
