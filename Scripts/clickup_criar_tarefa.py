#!/usr/bin/env python3
"""
Super Agente — Criação de Tarefas IMPERA
Cria tarefas na lista COPY (backlog) com nomenclatura automática e checklists de QC.
Pode ser chamado via CLI ou importado pelo Claude Code.
"""

import json
import os
import re
import sys
import urllib.request

# === DATA LAKE: persistir criativos na dimensao ===
try:
    sys.path.insert(0, os.path.expanduser("~/Scripts"))
    from database.impera_db import inserir_criativo_clickup
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
LIST_COPY = "901324556390"

# === MAPEAMENTOS ===

NICHOS = {
    "DA": {"nome": "Dores Articulares", "cf_id": "e4c250cd-4969-46c9-ade2-df544187c295", "oferta": "ARTICURE"},
    "DB": {"nome": "Diabetes", "cf_id": "e326248f-a572-4a28-b765-be5d6e5df9aa", "oferta": "INSULVITA"},
    "ED": {"nome": "Adulto / Aumento", "cf_id": "e4ae63ea-d894-4b95-aa32-7f8f8213cd88", "oferta": "EREMED"},
    "EM": {"nome": "Emagrecimento", "cf_id": "c053d9c8-453d-4d9c-bcbe-cd5d7006849d", "oferta": "GELATINA FIT"},
    "ME": {"nome": "Memória EUA", "cf_id": "71ad290b-e78d-44f3-862b-1b92814c7553", "oferta": "BRAIN HONEY"},
    "MM": {"nome": "Memória BR", "cf_id": "71ad290b-e78d-44f3-862b-1b92814c7553", "oferta": "MEMOFORTE"},
    "NE": {"nome": "Neuropatia", "cf_id": "44ec8b47-9943-4c65-8bdb-3adc5ce45aa3", "oferta": "NEUROCARE"},
    "PT": {"nome": "Próstata", "cf_id": "c0ccb7cd-d9eb-4081-8589-00e0147fdace", "oferta": "PROSTASAFE"},
    "VS": {"nome": "Visão", "cf_id": "4a9ba430-b0c5-4829-ab1c-5ac166fff5e0", "oferta": ""},
    "ZB": {"nome": "Zumbido", "cf_id": "f37178ca-4376-4dc4-8e9e-a2fefb0c6627", "oferta": "NEUROSILENCE"},
}

FONTES = {
    "FB": {"nome": "Facebook", "cf_id": "ae70abff-7bb6-4a4f-b814-59e6913b5fca"},
    "GG": {"nome": "Google", "cf_id": "84497f25-e9f8-483d-85bc-968febf3bd49"},
    "KW": {"nome": "Kwai", "cf_id": "6103dfca-2766-42e2-b6d3-6f85082cf1f4"},
    "MG": {"nome": "MGID", "cf_id": "d949fc60-c911-48e0-806b-a154a924620e"},
    "TB": {"nome": "Taboola", "cf_id": "a6384df0-e115-4017-baeb-2ae846b32722"},
    "TT": {"nome": "TikTok", "cf_id": "d471bbf3-016e-49df-8b53-85673089a585"},
    "VT": {"nome": "Vturb", "cf_id": "37699059-0c04-4645-ab08-684f64ae7e8d"},
    "YT": {"nome": "YouTube", "cf_id": "e3287541-071d-466c-98ee-8ac2b31f7a23"},
}

COPYWRITERS = {
    "ANA": {"cf_id": "b1b2aad1-027f-40da-867e-687d1c22138a", "orderindex": 0},
    "CAROL": {"cf_id": "22a8e8ea-2015-4172-93c7-090c9e6142f0", "orderindex": 1},
    "CRISPIM": {"cf_id": "b83d32b3-7e54-4ea2-8176-f98e45527305", "orderindex": 2},
    "ELIAS": {"cf_id": "e51cac8a-f175-4094-b346-931d4d3d124d", "orderindex": 3},
    "CÁSSIO": {"cf_id": "c79369bf-a651-4f9c-975e-096a1c4ec92c", "orderindex": 4},
    "CASSIO": {"cf_id": "c79369bf-a651-4f9c-975e-096a1c4ec92c", "orderindex": 4},
    "YAN": {"cf_id": "782b0f3d-167b-4a16-bd71-7aae30d22313", "orderindex": 5},
}

EDITORES = {
    "IGOR OLIVEIRA": {"cf_id": "7fcab1f5-162e-46a1-bc85-c118078c8fa7", "orderindex": 0},
    "MINEIRO": {"cf_id": "e46e5849-6769-499e-a189-5fca37385a3e", "orderindex": 1},
    "LUCAS": {"cf_id": "fdad205f-1d62-4fae-a9ee-d152f294c068", "orderindex": 2},
    "WELL": {"cf_id": "f9203f09-1f9c-4dae-ae7d-e2edcfed70ad", "orderindex": 3},
    "GABRIEL": {"cf_id": "87d4740c-777a-4a2b-94ac-e4c3ceeaaf90", "orderindex": 4},
    "MURYLLO": {"cf_id": "87399b17-c06d-4ad3-a7e1-f6d2d2ae5f52", "orderindex": 5},
    "NICOLAS": {"cf_id": "7a5a58e9-098f-41b1-a9ad-4b7e796c26fb", "orderindex": 6},
    "ROBERTO": {"cf_id": "87264303-d93f-461f-b881-18480221e847", "orderindex": 7},
}

OFERTAS = {
    "ARTICURE": "b82e6bd6-071c-49e5-ab68-8392c2bfaec7",
    "EREMED": "d9193c44-d127-4f0e-8262-e8ccb7698853",
    "GELATINA FIT": "9d484dfd-db8f-4b0f-b966-c3cf6704e3a2",
    "GLICO RESET": "c74664f5-f055-4826-a33b-29452baca3f1",
    "NEUROCARE": "ce709c9b-f832-417f-aabb-95ec7d06003a",
    "LIPOLED": "af954a43-ae63-43e3-8137-9bac9f03f04c",
    "PROSTASAFE": "9ea84903-8e7c-4730-b486-a669e6c2acd0",
    "INSULVITA": "32db8f3c-6ddc-4854-a86e-1937c185f6fd",
    "EREPOWER": "345e35ba-c18c-4fab-af4d-dd85f77264b4",
    "NEUROSILENCE": "7bdfcaaa-66bf-4330-9baa-89dffdc10d99",
    "BRAIN HONEY": "cb8f5796-3e9e-418d-8d54-6b897670d1c2",
    "MEMOFORTE": "e1b16038-5d48-45a8-8f71-eb4fab16f970",
    "SLIMPIC": "eb99aaf5-db4b-491c-8370-f539dbc41c0d",
}

MESES = {
    1: "b3092e59-ca29-44f4-8abb-22476e0460bf",   # JANEIRO.26
    2: "e4210070-d758-49a6-8c3b-43521c1fc45e",   # FEVEREIRO.26
    3: "90fabf8f-9981-413a-aef8-71e620dd6edb",   # MARÇO.26
    4: "33e80326-f86c-48fd-abd5-69c91f1f4d9c",   # ABRIL.26
    5: "f0a59a53-8613-43b6-a4f0-912fc1a3e6f6",   # MAIO.26
    6: "5e600767-bb06-4793-ae52-b0c44d2ada4c",   # JUNHO.26
    7: "aaa09357-8746-41f5-91df-3737fe3dd4ce",   # JULHO.26
    8: "7310456c-d505-43df-8599-36a357c000e7",   # AGOSTO.26
    9: "3b063656-35d1-4b87-af5d-623550298500",   # SETEMBRO.26
    10: "9567109d-9e26-458b-9cea-ebca82158ec0",  # OUTUBRO.26
    11: "0fcfe8b6-75c3-4995-98a7-f09f529ecf7d",  # NOVEMBRO.26
    12: "bb172bc9-472d-41f0-8830-e67c6e01fb64",  # DEZEMBRO.25
}

PRIORIDADES = {"urgent": 1, "high": 2, "normal": 3, "low": 4}

# === CUSTOM FIELD IDs ===
CF_COPYWRITER = "eeb64866-df57-4dbf-8338-5d4fb58837aa"
CF_EDITOR = "6002b1b9-e8c5-49ad-9e3d-3d8c314a1c91"
CF_FONTE = "796e4880-13f0-4d30-9d3b-1ee72c6df14c"
CF_OFERTA = "1149425c-f3c9-478e-af23-37677d5f7eb3"
CF_NICHO = "f61bfe77-933f-4637-828a-c9d8ef400d60"
CF_MES = "deaa7741-15a9-4368-a88c-7ed4603cff1a"

# === CHECKLISTS ===

CHECKLIST_COPY = {
    "name": "📁 Controle de Qualidade — COPY",
    "groups": [
        {
            "parent": "Pre-Revisão do Head",
            "children": [
                "Briefing recebido e compreendido",
                "Pesquisa de referências/fontes realizada",
                "Copy escrita (headlines, body, CTA)",
                "Nomenclatura conferida (padrão [NICHO][OFERTA][FONTE][AD][V])",
                "Revisão ortográfica e gramatical",
                "Preenchimento do documento de briefing da edição",
                "Orientação clara do Avatar do criativo",
                "Review do Head de Copy",
                "Ajustes pós-review aplicados (se necessário)",
                "Copy finalizada e encaminhada para edição",
            ],
        },
    ],
}

CHECKLIST_EDITOR = {
    "name": "🎬 Checklist de Entrega — EDIÇÃO DE VÍDEO",
    "groups": [
        {
            "parent": "Pre-Produção",
            "children": [
                "Texto está idêntico à copy",
                "Voz IA de acordo com o briefing",
                "Avatar de acordo com o briefing",
                "Lip Sync com qualidade",
                "Revisão antes de enviar ao editor",
            ],
        },
        {
            "parent": "Edição",
            "children": [
                "Leitura do briefing e leitura da copy",
                "Formato solicitado",
                "Cenas nativas (se necessário)",
                "Trilha",
                "VFX / SFX (se necessário)",
                "Não cortei frases importantes",
                "Cortei frases que não deveriam estar (se necessário)",
                "Criativo foi acelerado (se necessário)",
                "Legenda sincronizada e ortograficamente corrigida",
                "✅ 'Se eu fosse o público, eu acreditaria?' — SIM",
                "✅ 'Está exatamente como o copy pediu?' — SIM",
            ],
        },
    ],
}


# === API HELPERS ===

def api_request(method, endpoint, data=None):
    url = f"https://api.clickup.com/api/v2{endpoint}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", API_TOKEN)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def api_get(endpoint):
    return api_request("GET", endpoint)


def api_post(endpoint, data):
    return api_request("POST", endpoint, data)


# === CORE FUNCTIONS ===

def fetch_all_tasks_cached(list_id, include_closed=True):
    """Busca todas as tarefas de uma lista (com cache por execução)."""
    cache_key = f"{list_id}_{include_closed}"
    if not hasattr(fetch_all_tasks_cached, "_cache"):
        fetch_all_tasks_cached._cache = {}
    if cache_key in fetch_all_tasks_cached._cache:
        return fetch_all_tasks_cached._cache[cache_key]

    tasks = []
    page = 0
    while True:
        closed = "true" if include_closed else "false"
        data = api_get(f"/list/{list_id}/task?subtasks=true&include_closed={closed}&page={page}")
        tasks.extend(data.get("tasks", []))
        if data.get("last_page", True):
            break
        page += 1
    fetch_all_tasks_cached._cache[cache_key] = tasks
    return tasks


def parse_ad_ranges(task_name, nicho_filter=None, fonte_filter=None):
    """
    Extrai todos os números de AD ocupados por uma tarefa.
    Entende ranges como AD180-AD186 → {180,181,182,183,184,185,186}
    Também entende IMG ranges separados.
    Retorna (set_video, set_img).
    """
    upper = task_name.upper()

    # Filtrar por nicho/fonte se fornecidos
    if nicho_filter and f"[{nicho_filter}]" not in upper:
        return set(), set()
    if fonte_filter and f"[{fonte_filter}]" not in upper:
        return set(), set()

    is_img = "-IMG" in upper or "IMG" in upper.split("]")[-1] if "]" in upper else False
    video_ads = set()
    img_ads = set()
    target = img_ads if is_img else video_ads

    # Range: AD180-AD186 ou AD180- AD186 ou AD180-186
    range_pattern = re.compile(r"AD\s*(\d+)\s*-\s*(?:AD)?\s*(\d+)")
    for m in range_pattern.finditer(upper):
        start, end = int(m.group(1)), int(m.group(2))
        for n in range(start, end + 1):
            target.add(n)

    # Single AD: AD232 (mas não parte de um range já capturado)
    single_pattern = re.compile(r"AD\s*(\d+)")
    all_singles = single_pattern.findall(upper)
    if not range_pattern.search(upper):
        for n in all_singles:
            target.add(int(n))

    return video_ads, img_ads


def check_overlap(nicho, fonte, ad_start, ad_end, is_img=False):
    """
    Verifica se o range proposto [ad_start, ad_end] sobrepõe ranges existentes.
    Retorna lista de conflitos: [{"task_name": ..., "overlap_ads": [...]}, ...]
    """
    tasks = fetch_all_tasks_cached(LIST_COPY)
    proposed = set(range(ad_start, ad_end + 1))
    conflicts = []

    for t in tasks:
        if t.get("parent"):
            continue  # Ignorar subtarefas
        video_ads, img_ads = parse_ad_ranges(t["name"], nicho, fonte)
        existing = img_ads if is_img else video_ads
        overlap = proposed & existing
        if overlap:
            conflicts.append({
                "task_name": t["name"],
                "task_id": t["id"],
                "task_status": t.get("status", {}).get("status", "?"),
                "overlap_ads": sorted(overlap),
            })

    return conflicts


def get_last_ad_number(nicho, fonte):
    """Busca o último número de AD usado para um nicho/fonte na lista COPY."""
    tasks = fetch_all_tasks_cached(LIST_COPY)

    max_ad = 0
    pattern = re.compile(rf"\[{nicho}\].*\[{fonte}\].*AD\s*(\d+)", re.IGNORECASE)

    for t in tasks:
        matches = pattern.findall(t["name"])
        for m in matches:
            num = int(m)
            if num > max_ad:
                max_ad = num

    return max_ad


def generate_task_name(nicho, oferta, fonte, ad_start, ad_end, versao="V1", is_img=False):
    """Gera o nome da tarefa seguindo a nomenclatura padrão."""
    if ad_start == ad_end:
        ad_part = f"AD{ad_start:02d}"
        if is_img:
            ad_part += "-IMG"
    else:
        ad_part = f"AD{ad_start:02d}- AD{ad_end:02d}"
        if is_img:
            ad_part += "-IMG"

    return f"[{nicho}][{oferta}][{fonte}][{ad_part}][{versao}]"


def generate_lead_name(nicho, oferta, tipo, num_start, num_end):
    """Gera nome para Lead/Microlead."""
    sigla = "MLD" if tipo.upper() == "MICROLEAD" else "LD"
    return f"[{nicho}][{oferta}][{sigla}{num_start:02d}-{num_end:02d}]"


def create_task(name, description="", priority=3, copywriter=None, editor=None,
                fonte=None, oferta=None, nicho=None, due_date=None, start_date=None):
    """Cria uma tarefa na lista COPY no status backlog."""
    from datetime import datetime

    payload = {
        "name": name,
        "description": description,
        "status": "backlog copy",
        "priority": priority,
    }

    if due_date:
        payload["due_date"] = int(due_date.timestamp() * 1000)
    if start_date:
        payload["start_date"] = int(start_date.timestamp() * 1000)

    # Custom fields
    custom_fields = []

    if copywriter and copywriter.upper() in COPYWRITERS:
        cw = COPYWRITERS[copywriter.upper()]
        custom_fields.append({"id": CF_COPYWRITER, "value": cw["cf_id"]})

    if editor and editor.upper() in EDITORES:
        ed = EDITORES[editor.upper()]
        custom_fields.append({"id": CF_EDITOR, "value": ed["cf_id"]})

    if fonte and fonte.upper() in FONTES:
        custom_fields.append({"id": CF_FONTE, "value": FONTES[fonte.upper()]["cf_id"]})

    if nicho and nicho.upper() in NICHOS:
        custom_fields.append({"id": CF_NICHO, "value": NICHOS[nicho.upper()]["cf_id"]})

    if oferta:
        oferta_upper = oferta.upper()
        if oferta_upper in OFERTAS:
            custom_fields.append({"id": CF_OFERTA, "value": OFERTAS[oferta_upper]})

    # Mês referente (mês atual)
    mes_atual = datetime.now().month
    if mes_atual in MESES:
        custom_fields.append({"id": CF_MES, "value": MESES[mes_atual]})

    if custom_fields:
        payload["custom_fields"] = custom_fields

    result = api_post(f"/list/{LIST_COPY}/task", payload)
    return result


def add_checklist(task_id, checklist_config):
    """Adiciona um checklist com itens agrupados (pai + filhos) a uma tarefa."""
    # Create checklist
    checklist = api_post(
        f"/task/{task_id}/checklist",
        {"name": checklist_config["name"]}
    )
    checklist_id = checklist["checklist"]["id"]

    # Add grouped items (parent + children)
    for group in checklist_config["groups"]:
        # Create parent item
        parent_resp = api_post(
            f"/checklist/{checklist_id}/checklist_item",
            {"name": group["parent"]}
        )
        # Extract parent item ID from response
        parent_item_id = None
        for item in parent_resp["checklist"]["items"]:
            if item["name"] == group["parent"]:
                parent_item_id = item["id"]
                break

        # Create children under parent
        for child_name in group["children"]:
            payload = {"name": child_name}
            if parent_item_id:
                payload["parent"] = parent_item_id
            api_post(
                f"/checklist/{checklist_id}/checklist_item",
                payload
            )

    return checklist_id


def _persist_to_datalake(task_id, name, nicho=None, fonte=None, oferta=None,
                         copywriter=None, editor=None, ad_start=None, ad_end=None,
                         is_img=False, tipo="CRIATIVO"):
    """
    Persiste criativo(s) na dim_criativos_clickup do Data Lake.
    Expande ranges (AD10-AD15) em registros individuais.
    """
    if not DB_AVAILABLE or not os.getenv("DATABASE_URL"):
        return

    # Detectar mercado
    mercado = "EUA" if "[EUA]" in name.upper() else "BR"

    # Resolver nome da oferta
    oferta_nome = oferta
    if not oferta_nome and nicho and nicho.upper() in NICHOS:
        oferta_nome = NICHOS[nicho.upper()]["oferta"]

    try:
        if ad_start and ad_end:
            # Expandir range em criativos individuais
            for ad_num in range(ad_start, ad_end + 1):
                suffix = "-IMG" if is_img else ""
                id_criativo = f"AD{ad_num}{suffix}"
                inserir_criativo_clickup(
                    id_criativo=id_criativo,
                    task_id=task_id,
                    nome_nomenclatura=name,
                    nicho=nicho or "?",
                    mercado=mercado,
                    oferta=oferta_nome,
                    fonte_trafego=fonte,
                    tipo_tarefa=tipo,
                    copywriter=copywriter,
                    editor=editor,
                    status_atual="backlog copy",
                )
            n = ad_end - ad_start + 1
            print(f"  📊 {n} criativos persistidos no Data Lake")
        else:
            # Criativo unico (Lead, VSL, etc.)
            id_criativo = re.sub(r"[\[\] ]", "", name)[:64]
            inserir_criativo_clickup(
                id_criativo=id_criativo,
                task_id=task_id,
                nome_nomenclatura=name,
                nicho=nicho or "?",
                mercado=mercado,
                oferta=oferta_nome,
                fonte_trafego=fonte,
                tipo_tarefa=tipo,
                copywriter=copywriter,
                editor=editor,
                status_atual="backlog copy",
            )
            print(f"  📊 Criativo persistido no Data Lake")
    except Exception as e:
        print(f"  ⚠️ Data Lake: {e}")


def create_task_with_checklists(name, **kwargs):
    """Cria tarefa + adiciona ambos os checklists automaticamente."""
    task = create_task(name, **kwargs)
    task_id = task["id"]

    print(f"  Tarefa criada: {name} (ID: {task_id})")

    # Add checklists
    add_checklist(task_id, CHECKLIST_COPY)
    print(f"  ✅ Checklist COPY adicionado")

    add_checklist(task_id, CHECKLIST_EDITOR)
    print(f"  ✅ Checklist EDIÇÃO adicionado")

    return task


def create_creative_tasks(nicho, oferta, fonte, qtd_ads, copywriter=None,
                          editor=None, priority=3, is_img=False, oferta_nome=None,
                          due_date=None, description="", hooks="V1", batch_size=None):
    """
    Cria tarefa(s) de criativos NOVOS com nomenclatura automática.
    Busca o último AD e continua a sequência.
    Se batch_size for definido, divide em múltiplas tarefas.
    hooks: "V1", "V1-V2", "V1-V3" etc.
    """
    print(f"\nBuscando último AD para [{nicho}][{fonte}]...")
    last_ad = get_last_ad_number(nicho, fonte)
    print(f"  Último AD encontrado: AD{last_ad:02d}")

    # Overlap check
    ad_start_proposed = last_ad + 1
    ad_end_proposed = ad_start_proposed + qtd_ads - 1
    conflicts = check_overlap(nicho, fonte, ad_start_proposed, ad_end_proposed, is_img)
    if conflicts:
        print(f"\n  ⚠️ OVERLAP DETECTADO no range AD{ad_start_proposed:02d}-AD{ad_end_proposed:02d}:")
        for c in conflicts:
            print(f"    → {c['task_name']} (status: {c['task_status']}) | ADs conflitantes: {c['overlap_ads']}")
        print(f"\n  Abortando criação. Resolva o overlap primeiro.")
        return []

    if batch_size and qtd_ads > batch_size:
        # Split into batches
        tasks_created = []
        remaining = qtd_ads
        current_start = last_ad + 1

        while remaining > 0:
            batch = min(remaining, batch_size)
            ad_start = current_start
            ad_end = current_start + batch - 1  # inclusive: 10 ADs = start to start+9
            name = generate_task_name(nicho, oferta, fonte, ad_start, ad_end, hooks, is_img)

            task = create_task_with_checklists(
                name=name, description=description, priority=priority,
                copywriter=copywriter, editor=editor, fonte=fonte,
                oferta=oferta_nome, nicho=nicho, due_date=due_date,
            )
            _persist_to_datalake(task["id"], name, nicho=nicho, fonte=fonte,
                                oferta=oferta_nome, copywriter=copywriter,
                                editor=editor, ad_start=ad_start, ad_end=ad_end,
                                is_img=is_img, tipo="CRIATIVO")
            tasks_created.append((task, name, ad_start, ad_end))
            current_start = ad_end + 1
            remaining -= batch

        print(f"\n  Total: {len(tasks_created)} tarefas criadas ({qtd_ads} ADs)")
        return tasks_created
    else:
        ad_start = last_ad + 1
        ad_end = ad_start + qtd_ads - 1  # inclusive
        name = generate_task_name(nicho, oferta, fonte, ad_start, ad_end, hooks, is_img)

        task = create_task_with_checklists(
            name=name, description=description, priority=priority,
            copywriter=copywriter, editor=editor, fonte=fonte,
            oferta=oferta_nome, nicho=nicho, due_date=due_date,
        )
        _persist_to_datalake(task["id"], name, nicho=nicho, fonte=fonte,
                            oferta=oferta_nome, copywriter=copywriter,
                            editor=editor, ad_start=ad_start, ad_end=ad_end,
                            is_img=is_img, tipo="CRIATIVO")
        print(f"  Novos ADs: AD{ad_start:02d} a AD{ad_end:02d} ({qtd_ads} criativos)")
        return [(task, name, ad_start, ad_end)]


def get_last_version(nicho, creative_ref):
    """
    Busca a última versão usada para um criativo específico.
    creative_ref: ex. "IMG 644 V9", "ADC88V2", "ADC71V12"
    """
    tasks = []
    page = 0
    while True:
        data = api_get(f"/list/{LIST_COPY}/task?subtasks=true&include_closed=true&page={page}")
        tasks.extend(data.get("tasks", []))
        if data.get("last_page", True):
            break
        page += 1

    max_version = 0
    for t in tasks:
        name = t["name"]
        # Check if this task references the same creative
        if f"[{nicho}]" in name and creative_ref in name:
            # Extract version range [V95-V111], [V112-V128], etc.
            m = re.search(r"\[V(\d+)\s*-\s*V?(\d+)\]", name)
            if m:
                v_end = int(m.group(2))
                if v_end > max_version:
                    max_version = v_end
            # Single version [V1]
            m2 = re.search(r"\[V(\d+)\]", name)
            if m2:
                v = int(m2.group(1))
                if v > max_version:
                    max_version = v

    return max_version


def create_variation_tasks(nicho, oferta, fonte, creative_ref, qtd_variacoes,
                           batch_size, copywriter=None, editor=None, priority=3,
                           is_img=False, oferta_nome=None, due_date=None, description=""):
    """
    Cria tarefas de VARIAÇÕES para um criativo existente.
    creative_ref: referência do criativo original (ex: "IMG 644 V9", "ADC88V2")
    batch_size: quantas variações por tarefa
    """
    print(f"\nBuscando última versão para [{nicho}][{creative_ref}]...")
    last_version = get_last_version(nicho, creative_ref)
    print(f"  Última versão encontrada: V{last_version}")

    tasks_created = []
    remaining = qtd_variacoes
    current_v = last_version + 1

    while remaining > 0:
        batch = min(remaining, batch_size)
        v_start = current_v
        v_end = current_v + batch - 1

        name = f"[{nicho}][{oferta}][{fonte}][{creative_ref}][V{v_start}-V{v_end}]"

        task = create_task_with_checklists(
            name=name, description=description, priority=priority,
            copywriter=copywriter, editor=editor, fonte=fonte,
            oferta=oferta_nome, nicho=nicho, due_date=due_date,
        )
        _persist_to_datalake(task["id"], name, nicho=nicho, fonte=fonte,
                            oferta=oferta_nome, copywriter=copywriter,
                            editor=editor, is_img=is_img, tipo="VARIACAO")
        tasks_created.append((task, name, v_start, v_end))
        current_v = v_end + 1
        remaining -= batch

    print(f"\n  Total: {len(tasks_created)} tarefas criadas ({qtd_variacoes} variações)")
    return tasks_created


# === CLI ===

if __name__ == "__main__":
    if not API_TOKEN:
        print("ERRO: CLICKUP_API_TOKEN não configurado")
        sys.exit(1)

    print("Super Agente IMPERA — Criação de Tarefas")
    print("Use via Claude Code para criação inteligente com linguagem natural.")
    print(f"API Token: ...{API_TOKEN[-6:]}")
    print(f"Lista: COPY ({LIST_COPY})")
