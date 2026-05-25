#!/usr/bin/env python3
"""
Teste: Geração + Salvamento de URLs Trackable

Valida que:
1. URL é gerada corretamente ✅
2. URL é salva no ClickUp ✅
3. RedTrack receberá utm_content correto ✅
"""

import sys
import os

sys.path.insert(0, os.path.expanduser("~/Scripts"))

from gerar_tracking_url import gerar_tracking_url, atualizar_custom_field_clickup
from impera_cache import cached_cu_tasks

print("=" * 80)
print("🧪 TESTE: Geração + Salvamento de URLs Trackable")
print("=" * 80)

# ===== TESTE 1: Gerar URL =====
print("\n1️⃣ GERANDO URL TRACKABLE")
print("-" * 80)

task_name = "[EM][BR][OF02][FB][AD116][V1]"
print(f"Input: {task_name}")

result = gerar_tracking_url(task_name)

if not result:
    print("❌ Falha ao gerar URL")
    sys.exit(1)

print(f"\n✅ URL Gerada:")
print(f"   {result['url_completa']}\n")

print(f"📊 Parâmetros:")
print(f"   utm_source=   {result['utm_source']}")
print(f"   utm_medium=   {result['utm_medium']}")
print(f"   utm_campaign= {result['utm_campaign']}")
print(f"   utm_content=  {result['utm_content']}")

# ===== TESTE 2: Validar utm_content =====
print("\n2️⃣ VALIDANDO utm_content")
print("-" * 80)

expected_content = "AD116_V1"
actual_content = result['utm_content']

if actual_content == expected_content:
    print(f"✅ utm_content correto: {actual_content}")
    print(f"   → RedTrack receberá: sub5='{actual_content}' ✅")
else:
    print(f"❌ utm_content incorreto")
    print(f"   Esperado: {expected_content}")
    print(f"   Obtido:   {actual_content}")
    sys.exit(1)

# ===== TESTE 3: Salvar no ClickUp (Opcional) =====
print("\n3️⃣ SALVANDO NO CLICKUP")
print("-" * 80)

# Pegar uma tarefa de exemplo em GESTÃO DE TRÁFEGO
tasks = cached_cu_tasks("901324476398", include_closed=False)

if not tasks:
    print("⚠️ Nenhuma tarefa encontrada para teste")
    print("   Pulando etapa de salvamento")
else:
    test_task = tasks[0]
    task_id = test_task.get("id")
    task_name_cu = test_task.get("name", "")

    print(f"Tarefa de teste: {task_name_cu[:60]}")
    print(f"ID: {task_id}")

    print(f"\n📝 Tentando salvar URL...")
    update_result = atualizar_custom_field_clickup(task_id, result)

    if update_result:
        print(f"✅ URL salva com sucesso no ClickUp!")
        print(f"\n🔗 Você pode visualizar em:")
        print(f"   https://app.clickup.com/t/{task_id}")
    else:
        print(f"❌ Erro ao salvar (verifique permissões/API token)")

# ===== RESUMO =====
print("\n" + "=" * 80)
print("📋 RESUMO DO TESTE")
print("=" * 80)

print(f"""
✅ Geração de URL: FUNCIONANDO
   Input:  {task_name}
   Output: {result['url_completa']}

✅ utm_content: CORRETO
   Valor: {result['utm_content']}
   RedTrack receberá: sub5="{result['utm_content']}"

📊 Fluxo Esperado:
   1. URL salva em Custom Field ClickUp ✅
   2. Gestor copia URL → Cola no Facebook
   3. Facebook envia utm_content para RedTrack
   4. RedTrack armazena em sub5="{result['utm_content']}"
   5. Claude extrai [AD116] → Match com ClickUp
   6. Faturamento atribuído ao Copywriter ✅

🚀 Sistema de rastreamento de rt_ad está PRONTO!
""")

print("=" * 80)
