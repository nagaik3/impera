#!/usr/bin/env python3
"""
Nova Tarefa IMPERA — Formulário Web
Servidor Flask para criação guiada de tarefas no ClickUp.
"""

import os
import sys
import json
import re
import urllib.request
from datetime import datetime
from flask import Flask, render_template, request, jsonify

sys.path.insert(0, os.path.expanduser("~/Scripts"))
from clickup_criar_tarefa import (
    NICHOS, FONTES, COPYWRITERS, EDITORES, OFERTAS, MESES,
    CF_COPYWRITER, CF_EDITOR, CF_FONTE, CF_OFERTA, CF_NICHO, CF_MES,
    CHECKLIST_COPY, CHECKLIST_EDITOR,
    api_get, api_post, add_checklist,
    get_last_ad_number, get_last_version, LIST_COPY,
)

app = Flask(__name__)

# === OFERTAS POR NICHO COM CÓDIGO ===
# Código é usado na nomenclatura, nome completo é para display e campo ClickUp
# Para nichos internacionais (MM, EM), as ofertas variam por mercado
OFERTAS_POR_NICHO = {
    "DA": {"default": [{"codigo": "OF02", "nome": "ARTICURE"}]},
    "DB": {"default": [
        {"codigo": "C01", "nome": "INSULVITA"},
        {"codigo": "C02", "nome": "GLICO RESET"},
    ]},
    "ED": {"default": [
        {"codigo": "OF01", "nome": "EREMED"},
        {"codigo": "OF022", "nome": "EREPOWER"},
    ]},
    "EM": {
        "BR": [{"codigo": "OF02", "nome": "GELATINA FIT"}],
        "EUA": [{"codigo": "OF01", "nome": "SLIMPIC"}],
    },
    "MM": {
        "BR": [{"codigo": "OF01", "nome": "MEMOFORTE"}],
        "EUA": [{"codigo": "OF01", "nome": "BRAIN HONEY"}],
    },
    "NE": {"default": [{"codigo": "OF03", "nome": "NEUROCARE"}]},
    "PT": {"default": [{"codigo": "OF01", "nome": "PROSTASAFE"}]},
    "ZB": {"default": [{"codigo": "OF01", "nome": "NEUROSILENCE"}]},
}

# Nichos que operam com mercado EUA (precisam de [BR] ou [EUA])
NICHOS_INTERNACIONAIS = {"MM", "EM"}

TIPOS_TAREFA = [
    {"id": "video_novo", "label": "Video - Novo"},
    {"id": "video_var", "label": "Video - Variacao"},
    {"id": "img_novo", "label": "Imagem - Novo"},
    {"id": "img_var", "label": "Imagem - Variacao"},
    {"id": "microlead", "label": "Microlead"},
    {"id": "lead", "label": "Lead"},
    {"id": "vsl", "label": "VSL"},
    {"id": "presell", "label": "Presell"},
    {"id": "rip_criativo", "label": "Ripagem - Criativos"},
    {"id": "rip_mld", "label": "Ripagem - Microlead"},
    {"id": "rip_lead", "label": "Ripagem - Lead"},
    {"id": "rip_vsl", "label": "Ripagem - VSL"},
]

MERCADOS = [
    {"id": "BR", "label": "BR"},
    {"id": "EUA", "label": "EUA"},
]


def get_last_ld_number(nicho, tipo="LD"):
    """Busca o ultimo numero de LD/MLD para um nicho."""
    tasks = []
    page = 0
    while True:
        data = api_get(f"/list/{LIST_COPY}/task?subtasks=true&include_closed=true&page={page}")
        tasks.extend(data.get("tasks", []))
        if data.get("last_page", True):
            break
        page += 1

    max_num = 0
    pattern = re.compile(rf"\[{nicho}\].*{tipo}\s*(\d+)", re.IGNORECASE)
    for t in tasks:
        matches = pattern.findall(t["name"])
        for m in matches:
            num = int(m)
            if num > max_num:
                max_num = num
    return max_num


# Prefixo de ripagem por copywriter
RIP_PREFIX_MAP = {
    "ELIAS": "CE",
    "YAN": "CY",
    "CASSIO": "CC",
    # Se nenhum copywriter selecionado ou outro, usa AD com [RP]
}


def get_last_rip_number(nicho, prefix):
    """Busca o ultimo numero de um prefixo de ripagem (CE, CY, CC, C)."""
    tasks = []
    page = 0
    while True:
        data = api_get(f"/list/{LIST_COPY}/task?subtasks=true&include_closed=true&page={page}")
        tasks.extend(data.get("tasks", []))
        if data.get("last_page", True):
            break
        page += 1
    max_num = 0
    pattern = re.compile(rf"\[{nicho}\].*{prefix}(\d+)", re.IGNORECASE)
    for t in tasks:
        matches = pattern.findall(t["name"])
        for m in matches:
            num = int(m)
            if num > max_num:
                max_num = num
    return max_num


def build_task_name(data):
    """Constroi o nome da tarefa seguindo a nomenclatura IMPERA."""
    nicho = data["nicho"]
    oferta_codigo = data.get("oferta_codigo", "") or ""
    fonte = data.get("fonte", "") or ""
    tipo = data["tipo"]
    qtd = int(data["quantidade"])
    mercado = data.get("mercado", "")
    copywriter = data.get("copywriter", "-") or "-"

    # Bloco nicho + mercado
    nicho_part = f"[{nicho}]"
    if mercado:
        nicho_part += f"[{mercado}]"
    rp_part = "[RP]" if tipo.startswith("rip_") else ""

    # Bloco oferta (pode ser vazio)
    oferta_part = f"[{oferta_codigo}]" if oferta_codigo else ""

    # === LEADS / MICROLEADS / PRESELL ===
    if tipo in ("lead", "microlead", "rip_lead", "rip_mld", "presell"):
        if tipo == "presell":
            sigla = "PSL"
        elif tipo in ("microlead", "rip_mld"):
            sigla = "MLD"
        else:
            sigla = "LD"
        last = get_last_ld_number(nicho, sigla)
        start = last + 1
        end = start + qtd - 1
        fonte_part = f"[{fonte}]" if fonte else ""
        name = f"{nicho_part}{rp_part}{oferta_part}{fonte_part}[{sigla}{start:02d}-{sigla}{end:02d}]"
        return name, None, {"seq_start": start, "seq_end": end, "seq_type": sigla}

    # === VSL ===
    if tipo in ("vsl", "rip_vsl"):
        fonte_part = f"[{fonte}]" if fonte else ""
        name = f"{nicho_part}{rp_part}{oferta_part}{fonte_part}[VSL]"
        return name, None, {}

    # === RIPAGEM DE CRIATIVOS com prefixo por copywriter ===
    if tipo == "rip_criativo" and copywriter != "-":
        prefix = RIP_PREFIX_MAP.get(copywriter.upper())
        if prefix:
            last = get_last_rip_number(nicho, prefix)
            start = last + 1
            end = start + qtd - 1
            if start == end:
                rip_part = f"{prefix}{start:02d}"
            else:
                rip_part = f"{prefix}{start:02d}-{prefix}{end:02d}"
            name = f"{nicho_part}[RP]{oferta_part}[{fonte}][{rip_part}]"
            return name, None, {"seq_start": start, "seq_end": end, "seq_type": prefix}

    # === CRIATIVOS (video/imagem) ===
    if not fonte:
        return None, "Fonte e obrigatoria para criativos", {}

    is_img = tipo in ("img_novo", "img_var")
    is_new = tipo in ("video_novo", "img_novo", "rip_criativo")
    is_var = tipo in ("video_var", "img_var")

    if is_var:
        # Variação: usa o AD de referência informado pelo usuário
        ad_ref = data.get("ad_ref")
        if not ad_ref:
            return None, "AD de referencia e obrigatorio para variacoes", {}
        ad_num = int(ad_ref)
        ad_part = f"AD{ad_num:02d}"
        if is_img:
            ad_part += "-IMG"
        name = f"{nicho_part}{rp_part}{oferta_part}[{fonte}][{ad_part}]"
        return name, None, {"ad_ref": ad_num}
    else:
        # Criativo novo: auto-sequencia
        last_ad = get_last_ad_number(nicho, fonte)
        ad_start = last_ad + 1
        ad_end = ad_start + qtd - 1

        if ad_start == ad_end:
            ad_part = f"AD{ad_start:02d}"
        else:
            ad_part = f"AD{ad_start:02d}-AD{ad_end:02d}"

        if is_img:
            ad_part += "-IMG"

        name = f"{nicho_part}{rp_part}{oferta_part}[{fonte}][{ad_part}][V1]"
        return name, None, {"seq_start": ad_start, "seq_end": ad_end, "seq_type": "AD"}


def create_full_task(data):
    """Cria a tarefa completa no ClickUp."""
    name = data["task_name"]
    nicho = data["nicho"]
    oferta_nome = data.get("oferta_nome", "")
    fonte = data["fonte"]
    copywriter = data.get("copywriter")
    editor = data.get("editor")

    payload = {
        "name": name,
        "status": "backlog copy",
        "priority": 3,
    }

    custom_fields = []

    if copywriter and copywriter != "-":
        cw = COPYWRITERS.get(copywriter.upper())
        if cw:
            custom_fields.append({"id": CF_COPYWRITER, "value": cw["cf_id"]})

    if editor and editor != "-":
        ed = EDITORES.get(editor.upper())
        if ed:
            custom_fields.append({"id": CF_EDITOR, "value": ed["cf_id"]})

    if fonte and fonte in FONTES:
        custom_fields.append({"id": CF_FONTE, "value": FONTES[fonte]["cf_id"]})

    if nicho and nicho in NICHOS:
        custom_fields.append({"id": CF_NICHO, "value": NICHOS[nicho]["cf_id"]})

    if oferta_nome:
        oferta_upper = oferta_nome.upper()
        if oferta_upper in OFERTAS:
            custom_fields.append({"id": CF_OFERTA, "value": OFERTAS[oferta_upper]})

    mes_atual = datetime.now().month
    if mes_atual in MESES:
        custom_fields.append({"id": CF_MES, "value": MESES[mes_atual]})

    if custom_fields:
        payload["custom_fields"] = custom_fields

    result = api_post(f"/list/{LIST_COPY}/task", payload)
    task_id = result["id"]

    add_checklist(task_id, CHECKLIST_COPY)
    add_checklist(task_id, CHECKLIST_EDITOR)

    return result


# === ROUTES ===

@app.route("/")
def index():
    # Filtra ME (removido — só existe MM para Memória)
    nichos_filtrados = {k: v for k, v in NICHOS.items() if k != "ME"}
    return render_template("index.html",
        nichos=nichos_filtrados,
        fontes=FONTES,
        copywriters=COPYWRITERS,
        editores=EDITORES,
        tipos=TIPOS_TAREFA,
        ofertas_por_nicho=OFERTAS_POR_NICHO,
        nichos_internacionais=list(NICHOS_INTERNACIONAIS),
        mercados=MERCADOS,
    )


@app.route("/api/preview", methods=["POST"])
def preview():
    """Gera preview do nome da tarefa."""
    data = request.json
    required = ["nicho", "tipo", "quantidade"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Campo obrigatorio: {field}"}), 400

    name, error, seq_info = build_task_name(data)
    if error:
        return jsonify({"error": error}), 400

    tipo_info = next((t for t in TIPOS_TAREFA if t["id"] == data["tipo"]), {})
    nicho_info = NICHOS.get(data["nicho"], {})
    fonte_info = FONTES.get(data["fonte"], {})

    return jsonify({
        "task_name": name,
        "nicho_nome": nicho_info.get("nome", data["nicho"]),
        "fonte_nome": fonte_info.get("nome", data["fonte"]),
        "tipo_label": tipo_info.get("label", data["tipo"]),
        "oferta_codigo": data["oferta_codigo"],
        "oferta_nome": data.get("oferta_nome", ""),
        "quantidade": data["quantidade"],
        "copywriter": data.get("copywriter", "-"),
        "editor": data.get("editor", "-"),
        "mercado": data.get("mercado", ""),
        "seq_info": seq_info,
    })


@app.route("/api/criar", methods=["POST"])
def criar():
    """Cria a tarefa no ClickUp."""
    data = request.json
    if not data.get("task_name"):
        return jsonify({"error": "Nome da tarefa nao definido"}), 400

    try:
        result = create_full_task(data)
        return jsonify({
            "success": True,
            "task_id": result["id"],
            "task_url": result.get("url", ""),
            "task_name": data["task_name"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    if not os.environ.get("CLICKUP_API_TOKEN"):
        print("ERRO: CLICKUP_API_TOKEN nao configurado")
        sys.exit(1)
    app.run(host="0.0.0.0", port=5050, debug=False)
