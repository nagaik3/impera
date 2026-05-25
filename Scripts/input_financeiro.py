#!/usr/bin/env python3
"""
Input Financeiro Mensal — Coleta dados de faturas e despesas via terminal.
Salva em ~/Scripts/data/financeiro_mensal.json para leitura pelo Claude Code.
Roda: python3 ~/Scripts/input_financeiro.py
"""

import json
import os
from datetime import datetime

DATA_DIR = os.path.expanduser("~/Scripts/data")
OUTPUT_FILE = os.path.join(DATA_DIR, "financeiro_mensal.json")

# Cartões/despesas fixas conhecidas — adicione ou remova conforme necessário
CARTOES = [
    {"id": "mercado_pago", "nome": "Mercado Pago", "vencimento": 5},
    {"id": "inter", "nome": "Banco Inter", "vencimento": 10},
    {"id": "picpay_cartao", "nome": "PicPay (cartão)", "vencimento": 15},
    {"id": "iti", "nome": "Iti/Itaú", "vencimento": 20},
    {"id": "nubank", "nome": "Nubank", "vencimento": 24},
    {"id": "shopee", "nome": "Shopee", "vencimento": None},
    {"id": "cea", "nome": "C&A", "vencimento": None},
]

DESPESAS_FIXAS = [
    {"id": "aluguel", "nome": "Aluguel"},
    {"id": "emprestimo_picpay", "nome": "Empréstimo PicPay"},
]


def perguntar_valor(label: str):
    """Pergunta um valor. Enter vazio ou 0 = pular."""
    while True:
        raw = input(f"  {label}: R$ ").strip()
        if raw == "" or raw == "0":
            return None
        raw = raw.replace(".", "").replace(",", ".")
        try:
            val = float(raw)
            return val if val > 0 else None
        except ValueError:
            print("    Valor inválido. Use formato: 1234.56 ou 1234,56")


def perguntar_sim_nao(pergunta: str) -> bool:
    resp = input(f"  {pergunta} (s/n): ").strip().lower()
    return resp in ("s", "sim", "y", "yes")


def main():
    print("\n" + "=" * 50)
    print("  INPUT FINANCEIRO MENSAL")
    print("=" * 50)

    # Mês de referência
    hoje = datetime.now()
    mes_default = hoje.month
    ano_default = hoje.year
    mes_input = input(f"\n  Mês de referência ({mes_default:02d}/{ano_default}): ").strip()
    if mes_input:
        partes = mes_input.replace("-", "/").split("/")
        if len(partes) == 2:
            mes_default = int(partes[0])
            ano_default = int(partes[1]) if int(partes[1]) > 100 else 2000 + int(partes[1])
        else:
            mes_default = int(partes[0])

    mes_ref = f"{ano_default}-{mes_default:02d}"
    print(f"\n  Referência: {mes_ref}")

    # Faturas de cartão
    print(f"\n--- FATURAS DE CARTÃO ---")
    print("  (Enter vazio ou 0 para pular)\n")
    faturas = {}
    for c in CARTOES:
        val = perguntar_valor(c["nome"])
        if val is not None:
            faturas[c["id"]] = {"nome": c["nome"], "valor": val}

    # Despesas fixas
    print(f"\n--- DESPESAS FIXAS ---\n")
    despesas_fixas = {}
    for d in DESPESAS_FIXAS:
        val = perguntar_valor(d["nome"])
        if val is not None:
            despesas_fixas[d["id"]] = {"nome": d["nome"], "valor": val}

    # Nubank — separação padrasto
    nubank_padrasto = None
    if "nubank" in faturas:
        print(f"\n--- NUBANK: SEPARAÇÃO PADRASTO ---\n")
        val = perguntar_valor("Quanto do Nubank é do padrasto?")
        if val is not None:
            nubank_padrasto = val

    # Despesas extras
    print(f"\n--- DESPESAS EXTRAS (opcional) ---")
    print("  (Enter vazio para parar)\n")
    extras = []
    while True:
        desc = input("  Descrição: ").strip()
        if not desc:
            break
        val = perguntar_valor(desc)
        if val is not None:
            extras.append({"descricao": desc, "valor": val})

    # Receitas extras
    print(f"\n--- RECEITAS EXTRAS (opcional) ---")
    print("  (Enter vazio para parar)\n")
    receitas_extras = []
    while True:
        desc = input("  Descrição: ").strip()
        if not desc:
            break
        val = perguntar_valor(desc)
        if val is not None:
            receitas_extras.append({"descricao": desc, "valor": val})

    # Notas livres
    print(f"\n--- NOTAS (opcional) ---")
    notas = input("  Alguma observação? ").strip() or None

    # Montar resultado
    total_faturas = sum(f["valor"] for f in faturas.values())
    total_fixas = sum(d["valor"] for d in despesas_fixas.values())
    total_extras = sum(e["valor"] for e in extras)
    total_bruto = total_faturas + total_fixas + total_extras
    total_real = total_bruto - (nubank_padrasto or 0)

    resultado = {
        "mes_referencia": mes_ref,
        "data_input": hoje.isoformat(),
        "faturas_cartao": faturas,
        "despesas_fixas": despesas_fixas,
        "nubank_padrasto": nubank_padrasto,
        "despesas_extras": extras,
        "receitas_extras": receitas_extras,
        "notas": notas,
        "totais": {
            "faturas": round(total_faturas, 2),
            "fixas": round(total_fixas, 2),
            "extras": round(total_extras, 2),
            "bruto": round(total_bruto, 2),
            "real_sem_padrasto": round(total_real, 2),
        },
    }

    # Salvar
    # Carregar histórico existente
    historico = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r") as f:
            historico = json.load(f)

    historico[mes_ref] = resultado

    with open(OUTPUT_FILE, "w") as f:
        json.dump(historico, f, ensure_ascii=False, indent=2)

    # Resumo
    print("\n" + "=" * 50)
    print("  RESUMO")
    print("=" * 50)
    for fid, fdata in faturas.items():
        print(f"  {fdata['nome']:.<30} R$ {fdata['valor']:>10,.2f}")
    for did, ddata in despesas_fixas.items():
        print(f"  {ddata['nome']:.<30} R$ {ddata['valor']:>10,.2f}")
    for e in extras:
        print(f"  {e['descricao']:.<30} R$ {e['valor']:>10,.2f}")
    print(f"  {'':─<42}")
    print(f"  {'Total bruto':.<30} R$ {total_bruto:>10,.2f}")
    if nubank_padrasto:
        print(f"  {'(-) Padrasto Nubank':.<30} R$ {nubank_padrasto:>10,.2f}")
        print(f"  {'Total real (Iago)':.<30} R$ {total_real:>10,.2f}")

    print(f"\n  Salvo em: {OUTPUT_FILE}")
    print(f"  Agora é só abrir o Claude Code!\n")


if __name__ == "__main__":
    main()
