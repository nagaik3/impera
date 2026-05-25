#!/usr/bin/env python3
"""
Tunnel Manager — IMPERA
Gerencia túneis Cloudflare para webhooks locais.
Ao iniciar, sobe os túneis e atualiza automaticamente:
  1. Webhook do ClickUp (endpoint do gate-finalizado)
  2. Env vars do Render (URLs dos túneis)

Uso:
  python3 tunnel_manager.py          # Sobe túneis e atualiza endpoints
  python3 tunnel_manager.py --status # Mostra status dos túneis

launchd: com.impera.tunnel-manager
"""

import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request

# === CONFIG ===
CLICKUP_API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
TEAM_ID = "9013620875"

TUNNELS = {
    "gate": {
        "port": 5002,
        # ClickUp aponta para Render (URL fixa). Render faz proxy para este túnel.
        # O tunnel manager atualiza a env var GATE_WEBHOOK_URL no Render
        # para que o proxy saiba para onde encaminhar.
        "render_env_key": "GATE_WEBHOOK_URL",
    },
    "expand-range": {
        "port": 5003,
        "render_env_key": "EXPAND_RANGE_WEBHOOK_URL",
        "render_path": "/webhook/expand-range",
    },
}

STATE_FILE = os.path.expanduser("~/Scripts/data/tunnel_state.json")
LOG_PREFIX = "[TUNNEL]"

# === UTILS ===

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {LOG_PREFIX} {msg}", flush=True)


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}


# === TUNNEL MANAGEMENT ===

def start_tunnel(name, port):
    """Inicia um túnel Cloudflare e retorna (process, url)."""
    log_file = f"/tmp/cloudflared_{name}.log"

    # Limpar log anterior
    with open(log_file, "w") as f:
        f.write("")

    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
        stdout=subprocess.DEVNULL,
        stderr=open(log_file, "w"),
    )

    # Aguardar URL aparecer (max 30s)
    url = None
    for _ in range(60):
        time.sleep(0.5)
        try:
            with open(log_file) as f:
                content = f.read()
            match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', content)
            if match:
                url = match.group(0)
                break
        except:
            pass

    if not url:
        log(f"ERRO: Túnel {name} não conseguiu URL após 30s")
        proc.kill()
        return None, None

    log(f"Túnel {name}: {url} → localhost:{port}")
    return proc, url


# === CLICKUP WEBHOOK UPDATE ===

def update_clickup_webhook(webhook_id, new_url):
    """Atualiza o endpoint de um webhook do ClickUp."""
    url = f"https://api.clickup.com/api/v2/webhook/{webhook_id}"
    body = json.dumps({"endpoint": new_url}).encode()
    req = urllib.request.Request(url, data=body, method="PUT")
    req.add_header("Authorization", CLICKUP_API_TOKEN)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            new_endpoint = data.get("webhook", {}).get("endpoint", "?")
            log(f"ClickUp webhook atualizado: {new_endpoint}")
            return True
    except Exception as e:
        log(f"ERRO ao atualizar ClickUp webhook: {e}")
        return False


# === RENDER ENV UPDATE ===

def update_render_env(key, value):
    """Atualiza UMA env var no Render sem destruir as outras.
    A API do Render (PUT /env-vars) sobrescreve TODAS as vars.
    Por isso lemos todas primeiro, atualizamos a que precisa, e reenviamos.
    """
    render_key = os.environ.get("RENDER_API_KEY", "")
    render_service_id = os.environ.get("RENDER_SERVICE_ID", "")

    if not render_key or not render_service_id:
        log(f"RENDER_API_KEY ou RENDER_SERVICE_ID não configurados — pulando update Render")
        return False

    base_url = f"https://api.render.com/v1/services/{render_service_id}/env-vars"
    headers = {"Authorization": f"Bearer {render_key}", "Content-Type": "application/json"}

    # 1. Ler todas as env vars atuais
    try:
        req = urllib.request.Request(base_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            current = json.loads(resp.read())
    except Exception as e:
        log(f"ERRO ao ler env vars do Render: {e}")
        return False

    # 2. Montar array atualizado
    env_map = {}
    for item in current:
        ev = item.get("envVar", item)
        env_map[ev["key"]] = ev["value"]

    # Verificar se precisa atualizar
    if env_map.get(key) == value:
        log(f"Render env {key} já está correto — sem mudança")
        return True

    env_map[key] = value
    payload = [{"key": k, "value": v} for k, v in env_map.items()]

    # 3. Enviar tudo de volta
    try:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(base_url, data=body, method="PUT", headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            log(f"Render env {key} atualizado → {value[:60]}")
            return True
    except Exception as e:
        log(f"ERRO ao atualizar Render env {key}: {e}")
        return False


# === MAIN ===

def run():
    log("Iniciando Tunnel Manager...")

    processes = {}
    state = {}

    for name, config in TUNNELS.items():
        port = config["port"]
        proc, url = start_tunnel(name, port)
        if not proc or not url:
            continue

        processes[name] = proc
        state[name] = {
            "url": url,
            "port": port,
            "pid": proc.pid,
            "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Atualizar ClickUp webhook
        if "clickup_webhook_id" in config:
            update_clickup_webhook(config["clickup_webhook_id"], url)

        # Atualizar Render env var
        if "render_env_key" in config:
            full_url = url + config.get("render_path", "")
            update_render_env(config["render_env_key"], full_url)

    save_state(state)
    log(f"Todos os túneis ativos: {list(processes.keys())}")

    # Manter vivo e monitorar
    def shutdown(sig, frame):
        log("Encerrando túneis...")
        for name, proc in processes.items():
            proc.terminate()
            log(f"Túnel {name} (PID {proc.pid}) encerrado")
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    while True:
        for name, proc in list(processes.items()):
            if proc.poll() is not None:
                log(f"Túnel {name} caiu (exit {proc.returncode}). Reiniciando...")
                config = TUNNELS[name]
                new_proc, new_url = start_tunnel(name, config["port"])
                if new_proc and new_url:
                    processes[name] = new_proc
                    state[name]["url"] = new_url
                    state[name]["pid"] = new_proc.pid
                    state[name]["restarted"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    save_state(state)

                    # Re-atualizar endpoints
                    if "clickup_webhook_id" in config:
                        update_clickup_webhook(config["clickup_webhook_id"], new_url)
                    if "render_env_key" in config:
                        full_url = new_url + config.get("render_path", "")
                        update_render_env(config["render_env_key"], full_url)
        time.sleep(30)


def show_status():
    state = load_state()
    if not state:
        print("Nenhum túnel ativo")
        return
    for name, info in state.items():
        print(f"  {name}: {info.get('url', '?')} → localhost:{info.get('port', '?')} (PID {info.get('pid', '?')})")
        if info.get("restarted"):
            print(f"    Último restart: {info['restarted']}")


if __name__ == "__main__":
    if "--status" in sys.argv:
        show_status()
    else:
        run()
