#!/usr/bin/env python3
"""
Detector de Criativos Orfaos v3 — IMPERA
1. Consulta view_criativos_orfaos no Data Lake
2. Envia alerta informativo para chat da lista Gestão de Tráfego
3. Notifica via Telegram

Modulo de monitoramento: identifica criativos nao vinculados no ClickUp.
Notificacao apenas (sem criacao automatica de tarefas).

Crontab: 2x diario (11h e 16h)
  0 11 * * * python3 ~/Scripts/detectar_criativos_orfaos_v2.py
  0 16 * * * python3 ~/Scripts/detectar_criativos_orfaos_v2.py

GPDR - Iago Almeida, assistido por Claude
"""

import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.expanduser("~/Scripts"))
from database.impera_db import query_orfaos

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
LIST_GT = "901324476398"

CUSTO_MINIMO = 50.0

# Inferir nicho pelo prefixo do ad ou pelo gestor
GESTOR_FONTE = {
    "Lucas Cavalcanti": "FB",
    "Ludson Chaves": "FB",
    "Douglas Oliveira": "FB",
    "Gabriel Fraza": "YT",
    "Gustavo Lisner": "KW",
}

# Nicho default quando nao consegue inferir
NICHO_DEFAULT = "EM"

# Custom field IDs
CF_NICHO = "f61bfe77-933f-4637-828a-c9d8ef400d60"
CF_FONTE = "796e4880-13f0-4d30-9d3b-1ee72c6df14c"

NICHOS_CF = {
    "DA": "e4c250cd-4969-46c9-ade2-df544187c295",
    "DB": "e326248f-a572-4a28-b765-be5d6e5df9aa",
    "ED": "e4ae63ea-d894-4b95-aa32-7f8f8213cd88",
    "EM": "c053d9c8-453d-4d9c-bcbe-cd5d7006849d",
    "MM": "71ad290b-e78d-44f3-862b-1b92814c7553",
    "NE": "44ec8b47-9943-4c65-8bdb-3adc5ce45aa3",
    "PT": "c0ccb7cd-d9eb-4081-8589-00e0147fdace",
    "ZB": "f37178ca-4376-4dc4-8e9e-a2fefb0c6627",
}

FONTES_CF = {
    "FB": "ae70abff-7bb6-4a4f-b814-59e6913b5fca",
    "GG": "84497f25-e9f8-483d-85bc-968febf3bd49",
    "KW": "6103dfca-2766-42e2-b6d3-6f85082cf1f4",
    "YT": "e3287541-071d-466c-98ee-8ac2b31f7a23",
    "TB": "a6384df0-e115-4017-baeb-2ae846b32722",
}

OFERTA_PADRAO = {
    "EM": "OF02", "DB": "C01", "ED": "OF01", "NE": "OF03",
    "MM": "OF01", "PT": "OF01", "DA": "OF02", "ZB": "OF01",
}


def api_post_cu(endpoint, data):
    url = f"https://api.clickup.com/api/v2{endpoint}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", API_TOKEN)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def infer_nicho(nome_ad):
    """Tenta inferir nicho pelo nome do ad no RT."""
    upper = nome_ad.upper()
    # Extrair nicho de nomenclatura completa: [EM][OF02][FB]...
    m = re.search(r"\[(DA|DB|ED|EM|ME|MM|NE|PT|ZB)\]", upper)
    if m:
        return m.group(1)
    return NICHO_DEFAULT


def infer_fonte(nome_ad, gestor):
    """Tenta inferir fonte pelo nome do ad ou pelo gestor."""
    upper = nome_ad.upper()
    m = re.search(r"\[(FB|GG|KW|YT|TB|TT|MG|OB)\]", upper)
    if m:
        return m.group(1)
    return GESTOR_FONTE.get(gestor, "FB")


def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = json.dumps({"chat_id": TELEGRAM_CHAT, "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception:
        pass


def post_chat_message(text):
    """Envia mensagem para o chat da lista GT (Gestão de Tráfego)."""
    try:
        url = f"https://api.clickup.com/api/v2/list/{LIST_GT}/chat/message"
        body = json.dumps({"comment": text}).encode()
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Authorization", API_TOKEN)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  ERRO ao postar chat: {e}")
        return None


def main():
    if not os.getenv("DATABASE_URL"):
        print("ERRO: DATABASE_URL nao configurada")
        sys.exit(1)
    if not API_TOKEN:
        print("ERRO: CLICKUP_API_TOKEN nao configurado")
        sys.exit(1)

    preview = "--preview" in sys.argv

    print("=== DETECCAO DE CRIATIVOS ORFAOS — Monitoramento ===\n", flush=True)

    df = query_orfaos(limite=500)
    df = df[df["custo"] >= CUSTO_MINIMO]

    if df.empty:
        print("Nenhum orfao com custo >= R$50. Tudo cruzado.")
        return

    total = len(df)
    custo_total = float(df["custo"].sum())
    print(f"  {total} orfaos encontrados | R${custo_total:,.0f} total\n")

    orfaos = []

    for _, row in df.iterrows():
        nome_ad = str(row["nome_ad_rt"])
        base_ref = str(row.get("base_ref", nome_ad))
        gestor = str(row["gestor"])
        custo = float(row["custo"])
        vendas = int(row["vendas"])
        roas = float(row.get("roas_front", 0) or 0)

        nicho = infer_nicho(nome_ad)
        fonte = infer_fonte(nome_ad, gestor)

        orfaos.append({
            "nome_ad": nome_ad,
            "gestor": gestor,
            "custo": custo,
            "vendas": vendas,
            "roas": roas,
            "nicho": nicho,
            "fonte": fonte,
        })

        if preview:
            print(f"  [PREVIEW] {nome_ad} | {gestor} | R${custo:,.0f} | {vendas}v")

    if preview:
        print(f"\n{total} orfaos para alerta")
        return

    # Compilar mensagem e enviar para chat
    if orfaos:
        lines = ["🔍 <b>Criativos Orfaos Detectados</b>"]
        lines.append(f"Total: {total} | Custo: R${custo_total:,.0f}\n")

        # Agrupar por gestor
        gestores = {}
        for orphan in orfaos:
            g = orphan["gestor"]
            if g not in gestores:
                gestores[g] = []
            gestores[g].append(orphan)

        for gestor in sorted(gestores.keys()):
            lines.append(f"<b>{gestor}</b>")
            for o in gestores[gestor]:
                lines.append(
                    f"  • {o['nome_ad'][:50]}\n"
                    f"    R${o['custo']:,.0f} | {o['vendas']}v | ROAS {o['roas']:.1f}"
                )
            lines.append("")

        lines.append("<i>Mensagem automatizada — revisar cruzamento ClickUp/RedTrack</i>")
        msg = "\n".join(lines)

        if not preview:
            post_chat_message(msg)
            send_telegram(
                f"<b>Criativos Orfaos</b>\n"
                f"{total} encontrados | R${custo_total:,.0f}\n\n"
                f"Alerta enviado para Gestão de Tráfego"
            )
            print(f"\n=== RESULTADO ===")
            print(f"  Orfaos encontrados: {total}")
            print(f"  Custo: R${custo_total:,.0f}")
            print(f"  Alerta enviado para chat GT + Telegram")


if __name__ == "__main__":
    main()
