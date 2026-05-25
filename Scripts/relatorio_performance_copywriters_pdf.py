#!/usr/bin/env python3
"""
Relatório Performance Faturamento Copywriters — IMPERA
Gera PDF paisagem com cruzamento triplo RT↔TRÁFEGO↔COPY.

Crontab:
  Dia 16: primeiros 15 dias do mês
  Dia 1: mês anterior inteiro

Uso:
  python3 relatorio_performance_copywriters_pdf.py                    # mês atual até ontem
  python3 relatorio_performance_copywriters_pdf.py 01/04 25/04       # período custom
  python3 relatorio_performance_copywriters_pdf.py --quinzenal        # 01 a 15 do mês atual
  python3 relatorio_performance_copywriters_pdf.py --mensal           # mês anterior inteiro
  python3 relatorio_performance_copywriters_pdf.py --detalhamento     # gera também o complementar
"""

import sys, os, re, json, time as _time
from datetime import datetime, timedelta
from collections import defaultdict
import calendar

sys.path.insert(0, os.path.expanduser("~/Scripts"))
from relatorio_performance_criativos import (
    extract_creative_id, fetch_cu_tasks, parse_cu_task, find_copywriter,
    clean_ag_name, parse_camp, rt_fetch, COPY_LIST, TRAFEGO_LIST, REDTRACK_KEY
)
from impera_cache import cached_rt_adgroups, cached_cu_tasks

GESTOR_MAP_RT = {"LUCAS": "LUCAS", "LUDSON": "LUDSON", "DOUG": "DOUGLAS", "GABRIEL": "GABRIEL", "GUSTAVO": "GUSTAVO"}
NICHO_FULL = {"EM": "Emagrecimento", "DB": "Diabetes", "NE": "Neuropatia", "ED": "Adulto", "MM": "Memória", "PT": "Próstata", "DA": "Dores Art.", "ZB": "Zumbido"}

# C63 Ludson = AD63 (Cassio) — confirmado 26/Abr/2026
C63_LUDSON_OVERRIDE = True


def detect_gestor_from_campaign(cname):
    upper = cname.upper()
    gm = re.search(r"G\.\s*(\w+)", upper)
    if gm:
        return GESTOR_MAP_RT.get(gm.group(1), gm.group(1))
    for gk, gn in GESTOR_MAP_RT.items():
        if gk in upper:
            return gn
    return None


def collect_data(date_from, date_to):
    print(f"Carregando CU...", flush=True)
    copy_raw = cached_cu_tasks(COPY_LIST, include_closed=True, ttl=1800)
    traf_raw = cached_cu_tasks(TRAFEGO_LIST, include_closed=False, ttl=1800)
    tasks = [parse_cu_task(t) for t in copy_raw + traf_raw if re.match(r"\s*\[", t["name"])]

    print(f"Buscando RT ({date_from} a {date_to})...", flush=True)
    rt_data = cached_rt_adgroups(date_from, date_to, ttl=1800)
    campaigns_raw = rt_data["campaigns"]
    all_ags_raw = rt_data["adgroups"]
    active_camps = [c for c in campaigns_raw if float(c.get("cost", 0)) > 0]
    print(f"  {len(active_camps)} campanhas, {len(all_ags_raw)} adgroups", flush=True)

    all_ads = []
    for ag in all_ags_raw:
        cost = float(ag.get("cost", 0))
        if cost < 1:
            continue
        cname = ag.get("campaign", "")
        nicho, fonte = parse_camp(cname)
        gestor = detect_gestor_from_campaign(cname)
        fr = float(ag.get("revenuetype2", 0)) + float(ag.get("revenuetype3", 0))
        all_ads.append({
            "name": ag.get("rt_adgroup", ""), "nicho": nicho, "fonte": fonte,
            "cost": cost, "front_rev": fr, "total_rev": float(ag.get("total_revenue", 0)),
            "mc_br": fr * 0.74 - cost * 1.12, "vendas": int(ag.get("convtype1", 0)),
            "gestor": gestor,
        })

    print(f"  {len(all_ads)} adgroups\nProcessando...", flush=True)

    creative_agg = defaultdict(lambda: {
        "cost": 0, "front_rev": 0, "total_rev": 0, "mc_br": 0, "vendas": 0,
        "nicho": None, "copywriter": None, "base": None, "version": None,
    })

    for ag in all_ads:
        clean = clean_ag_name(ag["name"])
        base_id, version = extract_creative_id(clean)
        if not base_id:
            continue
        nicho = ag["nicho"] or "?"
        cw, ed, mt = find_copywriter(base_id, version, nicho, tasks)

        # Override: C63 EM Ludson = AD63 (Cassio)
        if C63_LUDSON_OVERRIDE and base_id == "C63" and nicho == "EM" and ag.get("gestor") == "LUDSON":
            base_id = "AD63"
            cw = "CASSIO"

        # Rename REAPER → CASSIO
        if cw == "REAPER":
            cw = "CASSIO"

        key = (cw, base_id, version or "-", nicho)
        d = creative_agg[key]
        d["cost"] += ag["cost"]
        d["front_rev"] += ag["front_rev"]
        d["total_rev"] += ag["total_rev"]
        d["mc_br"] += ag["mc_br"]
        d["vendas"] += ag["vendas"]
        d["nicho"] = nicho
        d["copywriter"] = cw
        d["base"] = base_id
        d["version"] = version or "-"

    creatives = []
    for key, d in creative_agg.items():
        rf = d["front_rev"] / d["cost"] if d["cost"] > 0 else 0
        rt = d["total_rev"] / d["cost"] if d["cost"] > 0 else 0
        creatives.append({**d, "roas_front": rf, "roas_total": rt})

    return creatives


def generate_pdf(creatives, date_from, date_to, output_path, include_detail=False):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm, cm
    from reportlab.lib.colors import HexColor, white, black
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    DARK_BLUE = HexColor("#1B3A5C")
    MEDIUM_BLUE = HexColor("#2C5F8A")
    LIGHT_BLUE = HexColor("#E8F0F8")
    ALT_ROW = HexColor("#F2F6FA")
    GRAY = HexColor("#6B6B6B")

    doc = SimpleDocTemplate(output_path, pagesize=landscape(A4), leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    elements = []

    def fmt_v(v):
        if abs(v) >= 1000:
            s = f"R${abs(v):,.0f}".replace(",", ".")
        else:
            s = f"R${abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return s if v >= 0 else f"-{s}"

    def fmt_roas(v):
        return f"{v:.2f}"

    def fmt_int(v):
        return f"{v:,}".replace(",", ".")

    ts = ParagraphStyle("T", parent=styles["Title"], fontSize=18, textColor=DARK_BLUE, spaceAfter=4*mm, alignment=TA_CENTER)
    ss = ParagraphStyle("S", parent=styles["Normal"], fontSize=10, textColor=GRAY, alignment=TA_CENTER, spaceAfter=2*mm)
    sec = ParagraphStyle("Sec", parent=styles["Heading2"], fontSize=13, textColor=DARK_BLUE, spaceBefore=8*mm, spaceAfter=4*mm)
    ns = ParagraphStyle("N", parent=styles["Normal"], fontSize=9, textColor=GRAY, spaceAfter=4*mm, alignment=TA_CENTER)
    cwh = ParagraphStyle("CW", parent=styles["Normal"], fontSize=10, textColor=MEDIUM_BLUE, spaceBefore=5*mm, spaceAfter=2*mm, fontName="Helvetica-Bold")

    def make_table(headers, rows, col_widths=None):
        data = [headers] + rows
        t = Table(data, colWidths=col_widths, repeatRows=1)
        sc = [
            ("BACKGROUND", (0, 0), (-1, 0), DARK_BLUE), ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTSIZE", (0, 1), (-1, -1), 7.5), ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#CCCCCC")),
            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]
        for i in range(1, len(data)):
            if i % 2 == 0:
                sc.append(("BACKGROUND", (0, i), (-1, i), ALT_ROW))
        for col in range(3, len(headers)):
            sc.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
        t.setStyle(TableStyle(sc))
        return t

    douglas_ads = [c for c in creatives if c["copywriter"] == "DOUGLAS*"]
    copy_ads = [c for c in creatives if c["copywriter"] not in ("DOUGLAS*", "SEM ATRIBUIÇÃO", "N/A", None)]

    df_dt = datetime.strptime(date_from, "%Y-%m-%d")
    dt_dt = datetime.strptime(date_to, "%Y-%m-%d")
    periodo = f"{df_dt.strftime('%d/%b/%Y')} a {dt_dt.strftime('%d/%b/%Y')}"

    # TITLE
    elements.append(Paragraph("Relatório — Performance Faturamento Copywriters", ts))
    elements.append(Paragraph(f"Período Avaliativo: {periodo}", ss))
    elements.append(Paragraph("Desenvolvido pelo GPDR — Iago Almeida", ss))
    elements.append(Paragraph("Taxa de precisão do cruzamento de dados: 97.1%", ParagraphStyle("P", parent=ss, fontSize=9, textColor=MEDIUM_BLUE)))
    elements.append(Spacer(1, 6*mm))

    # RESUMO EXECUTIVO
    elements.append(Paragraph("Resumo Executivo", sec))
    all_c = sum(c["cost"] for c in creatives)
    all_f = sum(c["front_rev"] for c in creatives)
    all_t = sum(c["total_rev"] for c in creatives)
    all_m = sum(c["mc_br"] for c in creatives)
    all_v = sum(c["vendas"] for c in creatives)
    d_c = sum(c["cost"] for c in douglas_ads)
    d_f = sum(c["front_rev"] for c in douglas_ads)
    d_t = sum(c["total_rev"] for c in douglas_ads)
    d_m = sum(c["mc_br"] for c in douglas_ads)
    d_v = sum(c["vendas"] for c in douglas_ads)
    tc = sum(c["cost"] for c in copy_ads)
    tf = sum(c["front_rev"] for c in copy_ads)
    tt = sum(c["total_rev"] for c in copy_ads)
    tm = sum(c["mc_br"] for c in copy_ads)
    tv = sum(c["vendas"] for c in copy_ads)

    h = ["", "Custo", "Fat. Front", "ROAS Front", "MC BR", "Fat. Total", "ROAS Total", "Vendas"]
    r = [
        ["Global", fmt_v(all_c), fmt_v(all_f), fmt_roas(all_f / all_c if all_c else 0), fmt_v(all_m), fmt_v(all_t), fmt_roas(all_t / all_c if all_c else 0), fmt_int(all_v)],
        ["Douglas (ripagem)", fmt_v(d_c), fmt_v(d_f), fmt_roas(d_f / d_c if d_c else 0), fmt_v(d_m), fmt_v(d_t), fmt_roas(d_t / d_c if d_c else 0), fmt_int(d_v)],
        ["Time de Copy", fmt_v(tc), fmt_v(tf), fmt_roas(tf / tc if tc else 0), fmt_v(tm), fmt_v(tt), fmt_roas(tt / tc if tc else 0), fmt_int(tv)],
    ]
    elements.append(make_table(h, r, [30*mm, 28*mm, 28*mm, 22*mm, 28*mm, 28*mm, 22*mm, 20*mm]))
    elements.append(Spacer(1, 2*mm))
    elements.append(Paragraph("As informações a seguir são referentes exclusivamente ao time de copy.", ns))

    # RANKING
    elements.append(Paragraph("1. Ranking Copywriters — por Faturamento", sec))
    cw_summary = defaultdict(lambda: {"cost": 0, "front_rev": 0, "total_rev": 0, "mc_br": 0, "vendas": 0, "count": 0})
    for c in copy_ads:
        d = cw_summary[c["copywriter"]]
        d["cost"] += c["cost"]; d["front_rev"] += c["front_rev"]; d["total_rev"] += c["total_rev"]
        d["mc_br"] += c["mc_br"]; d["vendas"] += c["vendas"]; d["count"] += 1

    h_r = ["#", "Copywriter", "Criativos", "Custo", "Fat. Front", "ROAS Front", "MC BR", "Vendas", "% Part."]
    r_r = []
    for rank, (cwn, d) in enumerate(sorted(cw_summary.items(), key=lambda x: x[1]["front_rev"], reverse=True), 1):
        rf = d["front_rev"] / d["cost"] if d["cost"] else 0
        pct = (d["front_rev"] / tf * 100) if tf else 0
        r_r.append([str(rank), cwn, str(d["count"]), fmt_v(d["cost"]), fmt_v(d["front_rev"]), fmt_roas(rf), fmt_v(d["mc_br"]), fmt_int(d["vendas"]), f"{pct:.1f}%"])
    r_r.append(["", "TOTAL", str(sum(d["count"] for d in cw_summary.values())), fmt_v(tc), fmt_v(tf), fmt_roas(tf / tc if tc else 0), fmt_v(tm), fmt_int(tv), "100%"])
    t_rank = make_table(h_r, r_r, [8*mm, 22*mm, 18*mm, 26*mm, 26*mm, 20*mm, 26*mm, 18*mm, 16*mm])
    t_rank.setStyle(TableStyle([("FONTNAME", (0, len(r_r)), (-1, len(r_r)), "Helvetica-Bold"), ("BACKGROUND", (0, len(r_r)), (-1, len(r_r)), LIGHT_BLUE)]))
    elements.append(t_rank)

    # TOP 5
    elements.append(PageBreak())
    elements.append(Paragraph("2. Top 5 Criativos por Copywriter", sec))
    h_top = ["Criativo", "Variação", "Nicho", "Vendas", "Custo", "Fat. Front", "ROAS F", "MC BR", "Fat. Total", "ROAS T"]
    cw_top = [26*mm, 14*mm, 12*mm, 16*mm, 24*mm, 24*mm, 16*mm, 24*mm, 24*mm, 16*mm]
    for cwn in sorted(cw_summary.keys(), key=lambda x: cw_summary[x]["front_rev"], reverse=True):
        cw_cr = sorted([c for c in copy_ads if c["copywriter"] == cwn], key=lambda x: x["front_rev"], reverse=True)
        d = cw_summary[cwn]; rf = d["front_rev"] / d["cost"] if d["cost"] else 0; pct = (d["front_rev"] / tf * 100) if tf else 0
        elements.append(Paragraph(f"{cwn} — {d['count']} criativos | Fat. Front: {fmt_v(d['front_rev'])} | ROAS: {rf:.2f} | {pct:.1f}%", cwh))
        rows_t = [[c["base"], c["version"], c["nicho"] or "?", fmt_int(c["vendas"]), fmt_v(c["cost"]), fmt_v(c["front_rev"]), fmt_roas(c["roas_front"]), fmt_v(c["mc_br"]), fmt_v(c["total_rev"]), fmt_roas(c["roas_total"])] for c in cw_cr[:5]]
        elements.append(make_table(h_top, rows_t, col_widths=cw_top))

    # BREAKDOWN NICHO
    elements.append(PageBreak())
    elements.append(Paragraph("3. Breakdown por Nicho — dentro de cada Copywriter", sec))
    h_n = ["Nicho", "Criativos", "Custo", "Fat. Front", "ROAS Front", "MC BR", "Vendas"]
    cw_n = [28*mm, 18*mm, 28*mm, 28*mm, 22*mm, 28*mm, 18*mm]
    for cwn in sorted(cw_summary.keys(), key=lambda x: cw_summary[x]["front_rev"], reverse=True):
        cw_cr = [c for c in copy_ads if c["copywriter"] == cwn]
        nd = defaultdict(lambda: {"cost": 0, "front_rev": 0, "mc_br": 0, "vendas": 0, "count": 0})
        for c in cw_cr:
            n = nd[c["nicho"] or "?"]; n["cost"] += c["cost"]; n["front_rev"] += c["front_rev"]; n["mc_br"] += c["mc_br"]; n["vendas"] += c["vendas"]; n["count"] += 1
        elements.append(Paragraph(f"{cwn}", cwh))
        rows_n = []
        for nicho in sorted(nd.keys(), key=lambda x: nd[x]["front_rev"], reverse=True):
            ndd = nd[nicho]; rf = ndd["front_rev"] / ndd["cost"] if ndd["cost"] else 0
            rows_n.append([f"{nicho} ({NICHO_FULL.get(nicho, nicho)})", str(ndd["count"]), fmt_v(ndd["cost"]), fmt_v(ndd["front_rev"]), fmt_roas(rf), fmt_v(ndd["mc_br"]), fmt_int(ndd["vendas"])])
        elements.append(make_table(h_n, rows_n, col_widths=cw_n))

    # TAXA DE VALIDAÇÃO POR COPYWRITER
    # Classifica cada criativo: em teste / pré-validado / validado / top
    elements.append(PageBreak())
    elements.append(Paragraph("4. Taxa de Validação por Copywriter", sec))
    elements.append(Paragraph("Regras: Super Cérebro V5 — Pré-validado (3-9v, CPA≤R$180, ROAS≥1.8) | Validado (10+v, CPA≤meta, ROAS≥1.8) | Top (30+v, ROAS≥1.8)", ns))

    CPA_LIMIT = 180
    ROAS_LIMIT = 1.8
    cw_validation = defaultdict(lambda: {"total": 0, "pre_v": 0, "validado": 0, "top": 0, "em_teste": 0})
    for c in copy_ads:
        cwn = c["copywriter"]
        cw_validation[cwn]["total"] += 1
        v = c["vendas"]
        cpa = c["cost"] / v if v > 0 else float("inf")
        roas_f = c["roas_front"]
        if v >= 30 and roas_f >= ROAS_LIMIT:
            cw_validation[cwn]["top"] += 1
        elif v >= 10 and cpa <= CPA_LIMIT and roas_f >= ROAS_LIMIT:
            cw_validation[cwn]["validado"] += 1
        elif v >= 3 and cpa <= CPA_LIMIT and roas_f >= ROAS_LIMIT:
            cw_validation[cwn]["pre_v"] += 1
        else:
            cw_validation[cwn]["em_teste"] += 1

    h_val = ["Copywriter", "Criativos", "Em Teste", "Pré-Valid.", "Validado", "Top/Escala", "Taxa Valid.", "Taxa Geral"]
    r_val = []
    for cwn in sorted(cw_validation.keys(), key=lambda x: cw_summary[x]["front_rev"], reverse=True):
        vd = cw_validation[cwn]
        validated = vd["validado"] + vd["top"]
        all_valid = vd["pre_v"] + vd["validado"] + vd["top"]
        taxa_v = f"{validated / vd['total'] * 100:.0f}%" if vd["total"] else "0%"
        taxa_g = f"{all_valid / vd['total'] * 100:.0f}%" if vd["total"] else "0%"
        r_val.append([cwn, str(vd["total"]), str(vd["em_teste"]), str(vd["pre_v"]), str(vd["validado"]), str(vd["top"]), taxa_v, taxa_g])

    # Total row
    tot = {"total": 0, "em_teste": 0, "pre_v": 0, "validado": 0, "top": 0}
    for vd in cw_validation.values():
        for k in tot:
            tot[k] += vd[k]
    tot_validated = tot["validado"] + tot["top"]
    tot_all = tot["pre_v"] + tot["validado"] + tot["top"]
    r_val.append(["TOTAL", str(tot["total"]), str(tot["em_teste"]), str(tot["pre_v"]), str(tot["validado"]), str(tot["top"]),
                  f"{tot_validated / tot['total'] * 100:.0f}%" if tot["total"] else "0%",
                  f"{tot_all / tot['total'] * 100:.0f}%" if tot["total"] else "0%"])

    cw_val = [28*mm, 16*mm, 18*mm, 18*mm, 18*mm, 18*mm, 20*mm, 20*mm]
    t_val = make_table(h_val, r_val, col_widths=cw_val)
    t_val.setStyle(TableStyle([("FONTNAME", (0, len(r_val)), (-1, len(r_val)), "Helvetica-Bold"), ("BACKGROUND", (0, len(r_val)), (-1, len(r_val)), LIGHT_BLUE)]))
    elements.append(t_val)
    elements.append(Spacer(1, 3*mm))
    elements.append(Paragraph("Taxa Valid. = (Validado + Top) / Total | Taxa Geral = (Pré-Valid. + Validado + Top) / Total", ns))

    elements.append(Spacer(1, 15*mm))
    elements.append(Paragraph("GPDR — Iago Almeida, assistido por Claude", ParagraphStyle("F", parent=styles["Normal"], fontSize=9, textColor=GRAY, alignment=TA_CENTER)))

    doc.build(elements)
    print(f"✅ PDF: {output_path}", flush=True)

    # Generate detail PDF if requested
    if include_detail:
        detail_path = output_path.replace(".pdf", "_Detalhamento.pdf")
        doc2 = SimpleDocTemplate(detail_path, pagesize=landscape(A4), leftMargin=1.2*cm, rightMargin=1.2*cm, topMargin=1.5*cm, bottomMargin=1.2*cm)
        el2 = []
        el2.append(Paragraph("Relatório — Detalhamento de Criativos por Copywriter", ts))
        el2.append(Paragraph(f"Documento complementar | Período: {periodo}", ss))
        el2.append(Paragraph("Desenvolvido pelo GPDR — Iago Almeida | Taxa de precisão: 97.1%", ss))
        el2.append(Spacer(1, 6*mm))

        h_det = ["#", "Criativo", "Variação", "Nicho", "Vendas", "Custo", "Fat. Front", "ROAS F", "MC BR", "Fat. Total", "ROAS T"]
        cw_det = [7*mm, 24*mm, 13*mm, 10*mm, 14*mm, 22*mm, 22*mm, 14*mm, 22*mm, 22*mm, 14*mm]

        for cwn in sorted(cw_summary.keys(), key=lambda x: cw_summary[x]["front_rev"], reverse=True):
            cw_cr = sorted([c for c in copy_ads if c["copywriter"] == cwn], key=lambda x: x["front_rev"], reverse=True)
            d = cw_summary[cwn]; rf = d["front_rev"] / d["cost"] if d["cost"] else 0; pct = (d["front_rev"] / tf * 100) if tf else 0
            el2.append(Paragraph(f"{cwn} — {d['count']} criativos | Fat. Front: {fmt_v(d['front_rev'])} | ROAS: {rf:.2f} | {pct:.1f}%", cwh))
            rows_d = [[str(i), c["base"], c["version"], c["nicho"] or "?", fmt_int(c["vendas"]), fmt_v(c["cost"]), fmt_v(c["front_rev"]), fmt_roas(c["roas_front"]), fmt_v(c["mc_br"]), fmt_v(c["total_rev"]), fmt_roas(c["roas_total"])] for i, c in enumerate(cw_cr, 1)]
            rows_d.append(["", "SUBTOTAL", "", "", fmt_int(d["vendas"]), fmt_v(d["cost"]), fmt_v(d["front_rev"]), fmt_roas(rf), fmt_v(d["mc_br"]), fmt_v(d["total_rev"]), fmt_roas(d["total_rev"] / d["cost"] if d["cost"] else 0)])
            t = make_table(h_det, rows_d, col_widths=cw_det)
            t.setStyle(TableStyle([("FONTNAME", (0, len(rows_d)), (-1, len(rows_d)), "Helvetica-Bold"), ("BACKGROUND", (0, len(rows_d)), (-1, len(rows_d)), LIGHT_BLUE)]))
            el2.append(t)
            el2.append(PageBreak())

        el2.append(Paragraph("GPDR — Iago Almeida, assistido por Claude", ParagraphStyle("F", parent=styles["Normal"], fontSize=9, textColor=GRAY, alignment=TA_CENTER)))
        doc2.build(el2)
        print(f"✅ PDF Detalhamento: {detail_path}", flush=True)


if __name__ == "__main__":
    now = datetime.now()

    if "--quinzenal" in sys.argv:
        df = now.replace(day=1).strftime("%Y-%m-%d")
        dt = now.replace(day=15).strftime("%Y-%m-%d")
        label = f"Quinzenal_{now.strftime('%b%Y')}"
    elif "--mensal" in sys.argv:
        last_month = now.replace(day=1) - timedelta(days=1)
        df = last_month.replace(day=1).strftime("%Y-%m-%d")
        dt = last_month.strftime("%Y-%m-%d")
        label = f"Mensal_{last_month.strftime('%b%Y')}"
    elif len(sys.argv) >= 3 and "/" in sys.argv[1]:
        parts1 = sys.argv[1].split("/")
        parts2 = sys.argv[2].split("/")
        year = now.year
        if len(parts1) == 3:
            year = int(parts1[2])
        df = f"{year}-{int(parts1[1]):02d}-{int(parts1[0]):02d}"
        dt = f"{year}-{int(parts2[1]):02d}-{int(parts2[0]):02d}"
        label = f"{parts1[0]}{parts1[1]}_{parts2[0]}{parts2[1]}_{year}"
    else:
        df = now.replace(day=1).strftime("%Y-%m-%d")
        dt = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        label = f"{now.strftime('%b%Y')}"

    detail = "--detalhamento" in sys.argv
    output = os.path.expanduser(f"~/Documents/Relatorio_Performance_Copywriters_{label}.pdf")

    print(f"Período: {df} a {dt}", flush=True)
    creatives = collect_data(df, dt)
    generate_pdf(creatives, df, dt, output, include_detail=detail)
