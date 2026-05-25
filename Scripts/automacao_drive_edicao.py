#!/usr/bin/env python3
"""
Automação: ClickUp EDIÇÃO DE VIDEO → Google Drive
Monitora tarefas novas no backlog da lista EDIÇÃO DE VIDEO.
Para cada nova tarefa: cria pasta no Drive e insere link no campo "Link do material".
Roda via crontab a cada 15 minutos.
"""

import json
import os
import urllib.request
from datetime import datetime
from retry_helper import retry_api_call

# === CONFIG ===
CLICKUP_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
LIST_EDICAO = "901324556390"  # Lista unificada — EDIÇÃO agora na COPY
CF_LINK_MATERIAL = "c32f509c-b990-4a36-aa0f-78242640bef7"
CF_LINK_COPY = "275990a0-b10d-45bd-abc2-f3ed26059d58"
DRIVE_PARENT_FOLDER = "1YvBsNt95Ne-C_r83vKJ13wxG8FqqMqH0"
TOKEN_FILE = "/Users/iagoalmeida/Scripts/google_token.json"
PROCESSED_FILE = "/Users/iagoalmeida/Scripts/drive_edicao_processed.json"
SCRIPTS_DIR = "/Users/iagoalmeida/Scripts"


def load_processed():
    """Carrega IDs de tarefas já processadas."""
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE) as f:
            return json.load(f)
    return {}


def save_processed(data):
    with open(PROCESSED_FILE, 'w') as f:
        json.dump(data, f, indent=2)


@retry_api_call(max_retries=3)
def cu_fetch_backlog():
    """Busca todas as tarefas no backlog da lista EDIÇÃO DE VIDEO."""
    tasks = []
    page = 0
    while True:
        url = (
            f"https://api.clickup.com/api/v2/list/{LIST_EDICAO}/task"
            f"?statuses%5B%5D=backlog&subtasks=true&include_closed=false&page={page}"
        )
        req = urllib.request.Request(url, headers={"Authorization": CLICKUP_TOKEN}, timeout=30)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        tasks.extend(data.get('tasks', []))
        if data.get('last_page', True):
            break
        page += 1
    return tasks


@retry_api_call(max_retries=3)
def cu_fetch_all_open():
    """Busca todas as tarefas abertas (qualquer status) da lista EDIÇÃO DE VIDEO."""
    tasks = []
    page = 0
    while True:
        url = (
            f"https://api.clickup.com/api/v2/list/{LIST_EDICAO}/task"
            f"?subtasks=true&include_closed=false&page={page}"
        )
        req = urllib.request.Request(url, headers={"Authorization": CLICKUP_TOKEN}, timeout=30)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        tasks.extend(data.get('tasks', []))
        if data.get('last_page', True):
            break
        page += 1
    return tasks


def cu_update_link(task_id, drive_link):
    """Atualiza o campo 'Link do material' no ClickUp."""
    url = f"https://api.clickup.com/api/v2/task/{task_id}/field/{CF_LINK_MATERIAL}"
    payload = json.dumps({"value": drive_link}).encode()
    req = urllib.request.Request(url, data=payload, method='POST')
    req.add_header("Authorization", CLICKUP_TOKEN)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def get_task_link_value(task):
    """Verifica se a tarefa já tem um link do material preenchido."""
    for cf in task.get('custom_fields', []):
        if cf.get('id') == CF_LINK_MATERIAL:
            return cf.get('value', '')
    return ''


def get_task_copy_link(task):
    """Pega o link da copy da tarefa."""
    for cf in task.get('custom_fields', []):
        if cf.get('id') == CF_LINK_COPY:
            return cf.get('value', '')
    return ''


def drive_create_folder(service, folder_name):
    """Cria pasta principal + subpastas (COPY, material base, material editado)."""
    # Pasta principal
    metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [DRIVE_PARENT_FOLDER],
    }
    folder = service.files().create(body=metadata, fields='id, webViewLink').execute()
    parent_id = folder.get('id')
    parent_link = folder.get('webViewLink')

    # Subpastas
    for sub_name in ['COPY', 'material base', 'material editado']:
        sub_metadata = {
            'name': sub_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id],
        }
        service.files().create(body=sub_metadata, fields='id').execute()

    return parent_id, parent_link


def drive_copy_file_to_folder(service, file_url, dest_folder_id):
    """Copia um arquivo do Google Drive para a subpasta COPY, dado um URL."""
    # Extrai file ID do URL do Google Drive/Docs
    import re
    m = re.search(r'/d/([a-zA-Z0-9_-]+)', file_url)
    if not m:
        m = re.search(r'id=([a-zA-Z0-9_-]+)', file_url)
    if not m:
        return None

    file_id = m.group(1)

    try:
        # Get original file name
        original = service.files().get(fileId=file_id, fields='name').execute()
        original_name = original.get('name', 'Copy')

        # Create a shortcut (link) to the original in the COPY subfolder
        shortcut_metadata = {
            'name': original_name,
            'mimeType': 'application/vnd.google-apps.shortcut',
            'shortcutDetails': {'targetId': file_id},
            'parents': [dest_folder_id],
        }
        shortcut = service.files().create(body=shortcut_metadata, fields='id').execute()
        return shortcut.get('id')
    except Exception as e:
        print(f"     ⚠️ Não foi possível linkar copy: {e}")
        return None


def get_drive_service():
    """Retorna Google Drive service autenticado."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    with open(TOKEN_FILE) as f:
        token_data = json.load(f)

    creds = Credentials.from_authorized_user_info(token_data)

    # Refresh token if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)


def main():
    if not CLICKUP_TOKEN:
        print("ERRO: CLICKUP_API_TOKEN não configurado")
        return

    now = datetime.now()
    date_str = now.strftime('%d.%m')
    print(f"[{now.strftime('%d/%m/%Y %H:%M')}] Verificando tarefas na EDIÇÃO DE VIDEO...")

    # Load already processed tasks
    processed = load_processed()

    # Fetch all open tasks (not just backlog, so we catch tasks in any status)
    all_tasks = cu_fetch_all_open()
    print(f"  {len(all_tasks)} tarefas abertas encontradas")

    # Find new tasks (not yet processed and without link do material)
    new_tasks = []
    for t in all_tasks:
        tid = t['id']
        if tid in processed:
            continue  # Already processed
        existing_link = get_task_link_value(t)
        if existing_link:
            # Already has a link, mark as processed and skip
            processed[tid] = {
                'name': t['name'],
                'date': now.strftime('%d/%m/%Y %H:%M'),
                'link': existing_link,
                'skipped': True,
            }
            continue
        new_tasks.append(t)

    if not new_tasks:
        print("  Nenhuma tarefa nova para processar.")
        save_processed(processed)
        return

    print(f"  {len(new_tasks)} tarefas novas para criar pastas no Drive")

    # Init Google Drive
    service = get_drive_service()

    for t in new_tasks:
        tid = t['id']
        name = t['name']
        folder_name = f"{date_str} - {name}"

        try:
            # Create Drive folder + subfolders
            folder_id, folder_link = drive_create_folder(service, folder_name)
            print(f"  ✅ {folder_name}")
            print(f"     Drive: {folder_link}")

            # Copy link da copy to COPY subfolder
            copy_link = get_task_copy_link(t)
            if copy_link:
                # Find COPY subfolder ID
                results = service.files().list(
                    q=f"'{folder_id}' in parents and name='COPY' and mimeType='application/vnd.google-apps.folder'",
                    fields='files(id)'
                ).execute()
                copy_folders = results.get('files', [])
                if copy_folders:
                    drive_copy_file_to_folder(service, copy_link, copy_folders[0]['id'])
                    print(f"     Copy linkada na subpasta COPY")
            else:
                print(f"     ℹ️ Sem Link da Copy para linkar")

            # Update ClickUp task
            cu_update_link(tid, folder_link)
            print(f"     ClickUp: Link do material atualizado")

            # Mark as processed
            processed[tid] = {
                'name': name,
                'folder_name': folder_name,
                'folder_id': folder_id,
                'link': folder_link,
                'copy_linked': bool(copy_link),
                'date': now.strftime('%d/%m/%Y %H:%M'),
            }

        except Exception as e:
            print(f"  ❌ Erro em {name}: {e}")

    save_processed(processed)
    print(f"\nConcluído! {len(new_tasks)} pastas criadas.")


if __name__ == "__main__":
    main()
