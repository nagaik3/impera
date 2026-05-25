#!/usr/bin/env python3
"""
Gerador de URLs Trackable com utm_content
Converte nomenclatura de criativo [EM][BR][OF02][FB][AD116][V1] em URL com parameters.

Uso:
  python3 gerar_tracking_url.py "[EM][BR][OF02][FB][AD116][V1]"

  Retorna:
  https://seu-dominio.com/?utm_source=facebook&utm_medium=cpc&utm_campaign=EM_OF02&utm_content=AD116_V1
"""

import os
import sys
import re
from urllib.parse import urlencode, quote

sys.path.insert(0, os.path.expanduser("~/Scripts"))
from impera_utils import detect_nicho

# Configuração
DOMINIO_BASE = os.environ.get("DOMINIO_BASE", "https://seu-dominio.com")


def parse_nomenclatura(task_name):
    """
    Extrai componentes da nomenclatura de criativo.

    Entrada: [EM][BR][OF02][FB][AD116][V1]

    Retorna:
    {
        "nicho": "EM",
        "mercado": "BR",
        "oferta": "OF02",
        "fonte": "FB",
        "ad": "AD116",
        "version": "V1",
        "nome_completo": "[EM][BR][OF02][FB][AD116][V1]"
    }
    """
    pattern = r'\[([A-Z]{2})\]\[([A-Z]{2})\]\[([A-Z]{2}\d{2})\]\[([A-Z]{2})\]\[([A-Z]{2}\d+)\]\[([A-Z]\d+)\]'

    match = re.search(pattern, task_name)
    if not match:
        return None

    return {
        "nicho": match.group(1),
        "mercado": match.group(2),
        "oferta": match.group(3),
        "fonte": match.group(4),
        "ad": match.group(5),
        "version": match.group(6),
        "nome_completo": task_name
    }


def gerar_tracking_url(task_name):
    """
    Gera URL trackable com utm_content baseado na nomenclatura.

    Exemplo:
    [EM][BR][OF02][FB][AD116][V1]

    ↓

    https://seu-dominio.com/?
    utm_source=facebook&
    utm_medium=cpc&
    utm_campaign=EM_OF02&
    utm_content=AD116_V1
    """
    parsed = parse_nomenclatura(task_name)

    if not parsed:
        return None

    # Mapa fonte → utm_source
    fonte_map = {
        "FB": "facebook",
        "GG": "google",
        "YT": "youtube",
        "TT": "tiktok",
        "KW": "kwai",
        "TB": "taboola",
        "MG": "mgid",
        "VT": "vturb",
    }

    # Mapa fonte → utm_medium
    medium_map = {
        "FB": "cpc",
        "GG": "cpc",
        "YT": "cpc",
        "TT": "cpc",
        "KW": "cpc",
        "TB": "display",
        "MG": "display",
        "VT": "email",
    }

    utm_params = {
        "utm_source": fonte_map.get(parsed["fonte"], "display"),
        "utm_medium": medium_map.get(parsed["fonte"], "cpc"),
        "utm_campaign": f"{parsed['nicho']}_{parsed['oferta']}",  # EM_OF02
        "utm_content": f"{parsed['ad']}_{parsed['version']}",      # AD116_V1
    }

    # Construir URL
    query_string = urlencode(utm_params)
    tracking_url = f"{DOMINIO_BASE}/?{query_string}"

    return {
        "url_completa": tracking_url,
        "utm_params": utm_params,
        "utm_source": utm_params["utm_source"],
        "utm_medium": utm_params["utm_medium"],
        "utm_campaign": utm_params["utm_campaign"],
        "utm_content": utm_params["utm_content"],
        "parsed": parsed
    }


def atualizar_custom_field_clickup(task_id, tracking_url_data):
    """
    Atualiza o custom field 'URL Trackable' na tarefa do ClickUp.

    Field ID: 62e048e3-1c20-4464-8b9a-04d780e6a983
    """
    import json
    import urllib.request

    API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
    TRACKING_URL_FIELD_ID = "62e048e3-1c20-4464-8b9a-04d780e6a983"

    headers = {
        "Authorization": API_TOKEN,
        "Content-Type": "application/json"
    }

    # Atualizar via API do ClickUp
    url = f"https://api.clickup.com/api/v2/task/{task_id}"

    data = {
        "custom_fields": [
            {
                "id": TRACKING_URL_FIELD_ID,
                "value": tracking_url_data["url_completa"]
            }
        ]
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method='PUT'
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            return result
    except Exception as e:
        print(f"Erro ao atualizar custom field: {e}")
        return None


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 gerar_tracking_url.py '[EM][BR][OF02][FB][AD116][V1]'")
        print()
        print("Exemplos:")
        print("  python3 gerar_tracking_url.py '[EM][BR][OF02][FB][AD116][V1]'")
        print("  python3 gerar_tracking_url.py '[MM][BR][OF01][FB][AD088][V1]'")
        sys.exit(1)

    task_name = sys.argv[1]
    result = gerar_tracking_url(task_name)

    if not result:
        print(f"❌ Nomenclatura inválida: {task_name}")
        print("   Esperado: [NICHO][MERCADO][OFERTA][FONTE][AD###][VERSION]")
        print("   Exemplo:  [EM][BR][OF02][FB][AD116][V1]")
        sys.exit(1)

    print(f"✅ URL Trackable Gerada:\n")
    print(f"URL Completa:\n{result['url_completa']}\n")
    print(f"Parâmetros UTM:")
    print(f"  utm_source=   {result['utm_source']}")
    print(f"  utm_medium=   {result['utm_medium']}")
    print(f"  utm_campaign= {result['utm_campaign']}")
    print(f"  utm_content=  {result['utm_content']}")
    print()
    print(f"📋 Para colar no Facebook:")
    print(f"\n{result['utm_source']}")
    print(f"{result['utm_medium']}")
    print(f"{result['utm_campaign']}")
    print(f"{result['utm_content']}")


if __name__ == "__main__":
    main()
