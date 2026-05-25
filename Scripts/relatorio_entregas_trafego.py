#!/usr/bin/env python3
"""
Relatorio Semanal — Entregas ao Trafego
Gera PDF com breakdown por tipo, nicho, copywriter, editor e pre-producao.
Roda todo domingo as 13h via crontab.

GPDR — Iago Almeida, assistido por Claude
"""

import os
import sys
import json
import re
import urllib.request
import urllib.parse
from collections import defaultdict
from datetime import datetime, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# === CONFIG ===
API_TOKEN = os.environ.get("CLICKUP_API_TOKEN", "")
LIST_COPY = "901324556390"
OUTPUT_DIR = os.path.expanduser("~/Documents")

COPY_MAP = {0: "Ana", 1: "Carol", 2: "Crispim", 3: "Elias", 4: "Reaper", 5: "Yan"}
EDITOR_MAP = {
    0: "Igor Oliveira", 1: "Mineiro", 2: "Lucas", 3: "Well", 4: "Gabriel",
    5: "Muryllo", 6: "Nicolas", 7: "Roberto", 8: "Freelancer", 9: "Ripagem", 10: "Candidato",
}
PREPROD_MAP = {0: "Igor Oliveira", 1: "Lucas", 2: "Mineiro", 3: "Gabriel", 4: "Muryllo", 5: "Nicolas", 6: "Well"}
NICHO_NOME = {
    "DA": "Dores Articulares", "DB": "Diabetes", "ED": "Disfuncao",
    "EM": "Emagrecimento", "MM": "Memoria BR", "NE": "Neuropatia",
    "PT": "Prostata", "ZB": "Zumbido",
}


# === API ===

def api_get(endpoint):
    url = f"https://api.clickup.com/api/v2{endpoint}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", API_TOKEN)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def get_week_range():
    """Retorna (segunda, domingo) da semana atual."""
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return monday, sunday


def fetch_enviado_ao_trafego():
    """Busca tarefas em 'enviado ao trafego' e 'aguardando validação' atualizadas na semana."""
    monday, sunday = get_week_range()
    mon_ms = str(int(monday.timestamp() * 1000))
    sun_ms = str(int(sunday.timestamp() * 1000))

    all_tasks = []
    for status in ["enviado ao tráfego", "aguardando validação"]:
        page = 0
        encoded_status = urllib.parse.quote(status)
        while True:
            data = api_get(
                f"/list/{LIST_COPY}/task?subtasks=true&include_closed=false"
                f"&statuses[]={encoded_status}&page={page}"
            )
            tasks = data.get("tasks", [])
            if not tasks:
                break
            all_tasks.extend(tasks)
            if data.get("last_page", True):
                break
            page += 1

    # Filtrar por data de atualizacao na semana
    filtered = []
    for t in all_tasks:
        updated = int(t.get("date_updated", 0))
        if int(mon_ms) <= updated <= int(sun_ms):
            filtered.append(t)

    # Se nenhuma filtrada por data, usar todas (fallback)
    if not filtered:
        filtered = all_tasks

    return filtered


def fetch_task_details(task_ids):
    """Busca detalhes completos de cada tarefa."""
    results = []
    for tid in task_ids:
        try:
            t = api_get(f"/task/{tid}")
        except Exception as e:
            print(f"  Erro ao buscar {tid}: {e}")
            continue

        name = t.get("name", "")
        upper = name.upper()

        # Custom fields
        cfs = {}
        for cf in t.get("custom_fields", []):
            cf_name = cf.get("name", "")
            cf_val = cf.get("value")
            if cf_val and isinstance(cf_val, dict):
                cf_val = cf_val.get("name", cf_val.get("label", str(cf_val)))
            elif cf_val and isinstance(cf_val, list):
                cf_val = ", ".join([v.get("name", str(v)) if isinstance(v, dict) else str(v) for v in cf_val])
            cfs[cf_name] = cf_val

        # Nicho
        nicho_match = re.search(r"\[(DA|DB|ED|EM|ME|MM|NE|PT|ZB)\]", upper)
        nicho = nicho_match.group(1) if nicho_match else "?"
        mercado = "EUA" if "[EUA]" in upper else "BR"

        # Tipo
        is_rip = "[RP]" in upper or bool(re.search(r"\[C[YEC]\d+", upper))
        is_new = "[V1]" in upper and not is_rip
        tipo = "Ripagem" if is_rip else ("Novo" if is_new else "Variacao")

        # Contagem
        count = 0
        ad_range = re.search(r"AD(\d+)-AD(\d+)", upper)
        v_range = re.search(r"\[V(\d+)-V(\d+)\]", upper)
        v_single = re.search(r"\[V(\d+)\]$", name.strip())
        rip_range = re.search(r"C[YEC](\d+)-C[YEC](\d+)", upper)

        if ad_range and v_range:
            n_ads = int(ad_range.group(2)) - int(ad_range.group(1)) + 1
            n_vers = int(v_range.group(2)) - int(v_range.group(1)) + 1
            count = n_ads * n_vers
        elif ad_range and v_single:
            count = int(ad_range.group(2)) - int(ad_range.group(1)) + 1
        elif v_range and not ad_range:
            count = int(v_range.group(2)) - int(v_range.group(1)) + 1
        elif rip_range:
            count = int(rip_range.group(2)) - int(rip_range.group(1)) + 1
        else:
            count = 1

        # Resolve names
        cv = cfs.get("\u270d\ufe0f Copywritter", "-")
        ev = cfs.get("\ud83c\udfac Editor de Video", "-")
        pv = cfs.get("\ud83d\udc64 Editor - Pré Produção", "-")

        results.append({
            "id": tid,
            "name": name,
            "nicho": nicho,
            "mercado": mercado,
            "tipo": tipo,
            "count": count,
            "cn": COPY_MAP.get(cv, "-") if isinstance(cv, int) else (str(cv) if cv else "-"),
            "en": EDITOR_MAP.get(ev, "-") if isinstance(ev, int) else (str(ev) if ev else "-"),
            "pn": PREPROD_MAP.get(pv, "-") if isinstance(pv, int) else (str(pv) if pv else "-"),
        })

    return results


def generate_pdf(data, monday, sunday):
    """Gera o PDF no estilo card-based."""
    total_c = sum(r["count"] for r in data)
    total_t = len(data)

    by_type = defaultdict(lambda: {"t": 0, "c": 0})
    for r in data:
        by_type[r["tipo"]]["t"] += 1
        by_type[r["tipo"]]["c"] += r["count"]

    by_nicho = defaultdict(lambda: {"t": 0, "c": 0, "nov": 0, "var": 0, "rip": 0})
    for r in data:
        k = r["nicho"] + (" EUA" if r["mercado"] == "EUA" else "")
        by_nicho[k]["t"] += 1
        by_nicho[k]["c"] += r["count"]
        if r["tipo"] == "Novo":
            by_nicho[k]["nov"] += r["count"]
        elif "Varia" in r["tipo"]:
            by_nicho[k]["var"] += r["count"]
        else:
            by_nicho[k]["rip"] += r["count"]

    by_copy = defaultdict(lambda: {"t": 0, "c": 0, "nov": 0, "var": 0, "rip": 0})
    for r in data:
        n = r["cn"]
        by_copy[n]["t"] += 1
        by_copy[n]["c"] += r["count"]
        if r["tipo"] == "Novo":
            by_copy[n]["nov"] += r["count"]
        elif "Varia" in r["tipo"]:
            by_copy[n]["var"] += r["count"]
        else:
            by_copy[n]["rip"] += r["count"]

    by_editor = defaultdict(lambda: {"t": 0, "c": 0})
    for r in data:
        by_editor[r["en"]]["t"] += 1
        by_editor[r["en"]]["c"] += r["count"]

    by_preprod = defaultdict(lambda: {"t": 0, "c": 0})
    for r in data:
        by_preprod[r["pn"]]["t"] += 1
        by_preprod[r["pn"]]["c"] += r["count"]

    # === PDF ===
    week_str = f"{monday.strftime('%d')}-{sunday.strftime('%d_%b_%Y')}"
    filename = f"Entregas_Trafego_{week_str}.pdf"
    output_path = os.path.join(OUTPUT_DIR, filename)

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1 * cm, bottomMargin=1 * cm,
    )
    W = doc.width
    styles = getSampleStyleSheet()

    # Colors
    HEADER_BG = colors.HexColor("#1E1B3A")
    PURPLE = colors.HexColor("#6C5CE7")
    DARK_TEXT = colors.HexColor("#2D3436")
    GRAY_TEXT = colors.HexColor("#636E72")
    LIGHT_GRAY = colors.HexColor("#DFE6E9")
    TABLE_HEADER = colors.HexColor("#2D3436")

    # Styles
    s_kpi_num = ParagraphStyle("KN", fontName="Helvetica-Bold", fontSize=26, textColor=DARK_TEXT, alignment=TA_CENTER, leading=30)
    s_kpi_lbl = ParagraphStyle("KL", fontName="Helvetica", fontSize=8, textColor=GRAY_TEXT, alignment=TA_CENTER, leading=10)
    s_section = ParagraphStyle("Sec", fontName="Helvetica-Bold", fontSize=11, textColor=DARK_TEXT, leading=14, spaceBefore=14, spaceAfter=6)
    s_footer = ParagraphStyle("Ft", fontName="Helvetica", fontSize=7, textColor=GRAY_TEXT, alignment=TA_CENTER)

    period_str = f"{monday.strftime('%d/%m')} - {sunday.strftime('%d/%m/%Y')}"

    def section_title(text):
        return Paragraph(f'<font color="#{PURPLE.hexval()[2:]}">\u25cf</font>&nbsp;&nbsp;<b>{text}</b>', s_section)

    def make_table(header, rows, col_widths=None):
        all_data = [header] + rows
        t = Table(all_data, colWidths=col_widths, repeatRows=1)
        cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("LEFTPADDING", (0, 0), (0, 0), 12),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("TEXTCOLOR", (0, 1), (-1, -1), DARK_TEXT),
            ("TOPPADDING", (0, 1), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 7),
            ("LEFTPADDING", (0, 1), (0, -1), 12),
            ("LINEBELOW", (0, 0), (-1, -2), 0.5, LIGHT_GRAY),
            ("LINEBELOW", (0, -1), (-1, -1), 1, LIGHT_GRAY),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
        ]
        for i in range(1, len(all_data)):
            if i % 2 == 0:
                cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F8F9FA")))
        t.setStyle(TableStyle(cmds))
        return t

    elements = []

    # Header
    hd = [[
        Paragraph(
            '<b>Entregas ao Trafego</b><br/>'
            '<font size="9" color="#B2BEC3">Grupo Impera - Gestao de Producao e Dados Relevantes</font>',
            ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=18, textColor=colors.white, leading=24),
        ),
        Paragraph(
            f'<font color="#B2BEC3">RELATORIO SEMANAL</font><br/>'
            f'<font size="9" color="#B2BEC3">{period_str}</font>',
            ParagraphStyle("hr", fontName="Helvetica-Bold", fontSize=9, textColor=colors.HexColor("#B2BEC3"),
                           alignment=TA_RIGHT, leading=14),
        ),
    ]]
    ht = Table(hd, colWidths=[W * 0.65, W * 0.35])
    ht.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HEADER_BG),
        ("TOPPADDING", (0, 0), (-1, -1), 14), ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING", (0, 0), (0, -1), 16), ("RIGHTPADDING", (-1, 0), (-1, -1), 16),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(ht)
    elements.append(Spacer(1, 10))

    # KPIs
    kpi_items = [
        (str(total_t), "Tarefas"), (str(total_c), "Criativos"),
        (str(by_type.get("Novo", {}).get("c", 0)), "Novos"),
        (str(by_type.get("Variacao", {}).get("c", 0)), "Variacoes"),
        (str(by_type.get("Ripagem", {}).get("c", 0)), "Ripagem"),
    ]
    kpi_t = Table(
        [[Paragraph(f"<b>{v}</b>", s_kpi_num) for v, _ in kpi_items],
         [Paragraph(l, s_kpi_lbl) for _, l in kpi_items]],
        colWidths=[W / 5] * 5,
    )
    kpi_t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 12), ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
        ("BOX", (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0FAF7")),
        ("LINEAFTER", (0, 0), (-2, -1), 0.5, LIGHT_GRAY),
    ]))
    elements.append(kpi_t)
    elements.append(Spacer(1, 6))

    # Tipo + Nicho side by side
    tipo_rows = []
    for tp in ["Novo", "Variacao", "Ripagem"]:
        v = by_type.get(tp, {"t": 0, "c": 0})
        pct = f"{v['c']/total_c*100:.0f}%" if total_c else "0%"
        tipo_rows.append([tp, str(v["t"]), str(v["c"]), pct])
    tipo_tbl = make_table(["TIPO", "TAREFAS", "CRIATIVOS", "%"], tipo_rows, [3.2*cm, 2*cm, 2*cm, 1.5*cm])

    nicho_rows = []
    for k, v in sorted(by_nicho.items(), key=lambda x: x[1]["c"], reverse=True):
        nome = NICHO_NOME.get(k.split()[0], k)
        if "EUA" in k:
            nome += " (EUA)"
        nicho_rows.append([nome, str(v["c"]), str(v["nov"]), str(v["var"]), str(v["rip"])])
    nicho_tbl = make_table(["NICHO", "CRIATIVOS", "NOV", "VAR", "RIP"], nicho_rows, [3.5*cm, 2*cm, 1.5*cm, 1.5*cm, 1.5*cm])

    lc = Table([[section_title("BREAKDOWN POR TIPO")], [tipo_tbl]], colWidths=[W * 0.47])
    lc.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    rc = Table([[section_title("BREAKDOWN POR NICHO")], [nicho_tbl]], colWidths=[W * 0.50])
    rc.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    tc = Table([[lc, rc]], colWidths=[W * 0.48, W * 0.52])
    tc.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(tc)
    elements.append(Spacer(1, 4))

    # Copywriter
    elements.append(section_title("PRODUCAO POR COPYWRITER"))
    cp_rows = []
    for n, v in sorted(by_copy.items(), key=lambda x: x[1]["c"], reverse=True):
        cp_rows.append([n, str(v["t"]), str(v["c"]), str(v["nov"]), str(v["var"]), str(v["rip"])])
    elements.append(make_table(
        ["COPYWRITER", "TAREFAS", "CRIATIVOS", "NOVOS", "VARIACOES", "RIPAGEM"],
        cp_rows, [4*cm] + [2.5*cm] * 5,
    ))
    elements.append(Spacer(1, 4))

    # Editor + Pre-prod side by side
    ed_rows = []
    for n, v in sorted(by_editor.items(), key=lambda x: x[1]["c"], reverse=True):
        if n == "-":
            continue
        ed_rows.append([n, str(v["t"]), str(v["c"]), f"{v['c']/total_c*100:.0f}%"])
    ed_tbl = make_table(["EDITOR VIDEO", "TAREFAS", "CRIATIVOS", "%"], ed_rows, [3.2*cm, 2*cm, 2*cm, 1.5*cm])

    pp_rows = []
    for n, v in sorted(by_preprod.items(), key=lambda x: x[1]["c"], reverse=True):
        if n == "-":
            continue
        pp_rows.append([n, str(v["t"]), str(v["c"]), f"{v['c']/total_c*100:.0f}%"])
    pp_tbl = make_table(["PRE-PRODUCAO", "TAREFAS", "CRIATIVOS", "%"], pp_rows, [3.2*cm, 2*cm, 2*cm, 1.5*cm])

    l2 = Table([[section_title("EDITOR DE VIDEO")], [ed_tbl]], colWidths=[W * 0.47])
    l2.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    r2 = Table([[section_title("EDITOR PRE-PRODUCAO")], [pp_tbl]], colWidths=[W * 0.47])
    r2.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    tc2 = Table([[l2, r2]], colWidths=[W * 0.49, W * 0.51])
    tc2.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(tc2)
    elements.append(Spacer(1, 4))

    # Detalhamento
    elements.append(section_title("DETALHAMENTO - TAREFAS ENTREGUES"))
    det_rows = []
    for r in sorted(data, key=lambda x: (x["nicho"], x["tipo"])):
        sn = r["name"][:40] + ".." if len(r["name"]) > 40 else r["name"]
        tp = "Nov" if r["tipo"] == "Novo" else ("Var" if "Varia" in r["tipo"] else "Rip")
        det_rows.append([
            Paragraph(f'<font size="7">{sn}</font>', styles["Normal"]),
            r["nicho"] + (" EUA" if r["mercado"] == "EUA" else ""),
            tp, str(r["count"]),
            r["cn"][:8], r["en"][:8], r["pn"][:8],
        ])
    elements.append(make_table(
        ["TAREFA", "NICHO", "TIPO", "QTY", "COPY", "EDITOR", "PRE-PROD"],
        det_rows, [6.2*cm, 1.6*cm, 1.2*cm, 1.1*cm, 2.1*cm, 2.1*cm, 2.1*cm],
    ))

    # Footer
    elements.append(Spacer(1, 14))
    ft = Table([[
        Paragraph("Grupo Impera - Uso Interno - Confidencial", s_footer),
        Paragraph(
            f"GPDR - Iago Almeida, assistido por Claude  |  {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            ParagraphStyle("fr", fontName="Helvetica", fontSize=7, textColor=GRAY_TEXT, alignment=TA_RIGHT),
        ),
    ]], colWidths=[W * 0.5, W * 0.5])
    ft.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.5, LIGHT_GRAY), ("TOPPADDING", (0, 0), (-1, -1), 6)]))
    elements.append(ft)

    doc.build(elements)
    return output_path


def main():
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] === Relatorio Entregas ao Trafego ===")

    monday, sunday = get_week_range()
    print(f"  Periodo: {monday.strftime('%d/%m')} - {sunday.strftime('%d/%m/%Y')}")

    # Buscar tarefas
    tasks = fetch_enviado_ao_trafego()
    task_ids = [t["id"] for t in tasks]
    print(f"  Tarefas encontradas: {len(task_ids)}")

    if not task_ids:
        print("  Nenhuma tarefa encontrada. Abortando.")
        return

    # Detalhes
    data = fetch_task_details(task_ids)
    print(f"  Detalhes carregados: {len(data)} tarefas, {sum(r['count'] for r in data)} criativos")

    # Gerar PDF
    path = generate_pdf(data, monday, sunday)
    print(f"  PDF gerado: {path}")


if __name__ == "__main__":
    main()
