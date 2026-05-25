#!/usr/bin/env python3
"""
Menu interativo para gerenciar a automação "Teve alteração?"
"""

import os
import sys
import subprocess

def print_banner():
    """Exibe banner do menu"""
    print("\n" + "=" * 80)
    print("🔄 AUTOMAÇÃO: 'TEVE ALTERAÇÃO?'")
    print("=" * 80)
    print()

def print_menu():
    """Exibe opções do menu"""
    print("Escolha uma opção:\n")
    print("  1️⃣  Iniciar Webhook (automático)")
    print("  2️⃣  Marcar tarefas manualmente")
    print("  3️⃣  Ver logs do webhook")
    print("  4️⃣  Testar sistema")
    print("  5️⃣  Ver documentação")
    print("  6️⃣  Ver status do webhook")
    print("  0️⃣  Sair")
    print()

def option_start_webhook():
    """Inicia o webhook"""
    print("\n🚀 Iniciando webhook...")
    print("(Deixe rodando em background com ctrl+c para parar)\n")
    try:
        subprocess.run([
            "python3",
            os.path.expanduser("~/Scripts/webhook_auto_alteracao.py")
        ])
    except KeyboardInterrupt:
        print("\n\n⛔ Webhook parado pelo usuário")

def option_mark_tasks():
    """Menu para marcar tarefas"""
    print("\n📌 MARCAR TAREFAS")
    print("-" * 80)
    print("  1. Marcar tarefa específica (precisa do ID)")
    print("  2. Marcar TODAS as tarefas da lista")
    print("  0. Voltar\n")

    choice = input("Escolha: ").strip()

    if choice == "1":
        task_ids = input("\nDigite os IDs das tarefas (separados por espaço):\n> ").strip().split()
        if not task_ids or task_ids == ['']:
            print("❌ Nenhuma tarefa especificada")
            return

        cmd = [
            "python3",
            os.path.expanduser("~/Scripts/mark_teve_alteracao_batch.py"),
            "--task-ids"
        ] + task_ids

        try:
            subprocess.run(cmd)
        except Exception as e:
            print(f"❌ Erro: {e}")

    elif choice == "2":
        confirm = input("\n⚠️  Marcar TODAS as tarefas? (s/n): ").lower()
        if confirm == 's':
            try:
                subprocess.run([
                    "python3",
                    os.path.expanduser("~/Scripts/mark_teve_alteracao_batch.py"),
                    "--all"
                ])
            except Exception as e:
                print(f"❌ Erro: {e}")
        else:
            print("❌ Cancelado")

def option_view_logs():
    """Exibe logs do webhook"""
    print("\n📋 LOGS DO WEBHOOK")
    print("-" * 80)

    try:
        import requests
        response = requests.get("http://localhost:5001/webhook/logs", timeout=2)

        if response.status_code == 200:
            import json
            logs = response.json()
            events = logs.get('events', [])

            if not events:
                print("ℹ️  Nenhum evento registrado ainda")
            else:
                print(f"Total de eventos: {len(events)}\n")
                print("Últimos 5 eventos:\n")

                for event in events[-5:]:
                    print(f"  • {event.get('timestamp')}")
                    print(f"    Task: {event.get('task_name')} ({event.get('task_id')})")
                    print(f"    Ação: {event.get('action')}")
                    print()
        else:
            print("❌ Erro ao conectar ao webhook")
            print("   Verifique se está rodando: python3 ~/Scripts/webhook_auto_alteracao.py")

    except Exception as e:
        print(f"❌ Erro: {e}")
        print("   Webhook não está rodando no momento")

def option_test_system():
    """Executa testes"""
    print("\n🧪 TESTANDO SISTEMA...")
    print("-" * 80)

    try:
        subprocess.run([
            "python3",
            os.path.expanduser("~/Scripts/test_auto_alteracao.py")
        ])
    except Exception as e:
        print(f"❌ Erro: {e}")

def option_view_docs():
    """Exibe documentação"""
    docs_file = os.path.expanduser("~/Scripts/README_TEVE_ALTERACAO.md")

    if os.path.exists(docs_file):
        print("\n📖 DOCUMENTAÇÃO\n")
        with open(docs_file, 'r') as f:
            content = f.read()
            # Limita a saída para 100 linhas
            lines = content.split('\n')[:100]
            for line in lines:
                print(line)
            if len(content.split('\n')) > 100:
                print("\n... (veja o arquivo completo em ~/Scripts/README_TEVE_ALTERACAO.md)")
    else:
        print(f"❌ Arquivo não encontrado: {docs_file}")

def option_webhook_status():
    """Exibe status do webhook"""
    print("\n🔍 STATUS DO WEBHOOK")
    print("-" * 80)

    try:
        import requests
        response = requests.get("http://localhost:5001/webhook/status", timeout=2)

        if response.status_code == 200:
            import json
            status = response.json()
            print("\n✅ Webhook está rodando!\n")
            print(f"  Serviço: {status.get('service')}")
            print(f"  Campo: {status.get('field')}")
            print(f"  Trigger: {status.get('trigger')}")
            print(f"  Status: {status.get('status')}\n")
        else:
            print(f"⚠️  Webhook respondeu com status {response.status_code}")

    except Exception as e:
        print(f"❌ Webhook não está rodando")
        print(f"   Para iniciar: python3 ~/Scripts/webhook_auto_alteracao.py")

def main():
    """Loop principal"""
    while True:
        print_banner()
        print_menu()

        choice = input("Digite a opção (0-6): ").strip()

        if choice == "1":
            option_start_webhook()
        elif choice == "2":
            option_mark_tasks()
        elif choice == "3":
            option_view_logs()
        elif choice == "4":
            option_test_system()
        elif choice == "5":
            option_view_docs()
        elif choice == "6":
            option_webhook_status()
        elif choice == "0":
            print("\n👋 Até logo!")
            sys.exit(0)
        else:
            print("\n❌ Opção inválida. Tente novamente.")

        input("\nPressione ENTER para continuar...")
        print("\n" * 2)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Menu encerrado")
        sys.exit(0)
