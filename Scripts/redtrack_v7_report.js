#!/usr/bin/env node

const https = require('https');
const fs = require('fs');
const path = require('path');
const { PDFDocument, rgb, degrees } = require('pdf-lib');

// ============================================
// 1. DATA EXTRACTION & PARSING
// ============================================

async function getRedTrackData(dateFrom, dateTo) {
  const apiKey = process.env.REDTRACK_API_KEY;
  if (!apiKey) throw new Error('REDTRACK_API_KEY not set');

  const url = `https://api.redtrack.io/report?api_key=${apiKey}&group=campaign&date_from=${dateFrom}&date_to=${dateTo}&total=true&per=200`;

  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(new Error(`Failed to parse RedTrack response: ${e.message}`));
        }
      });
    }).on('error', reject);
  });
}

function parseCampaignFB(name) {
  const match = name.match(/\[FB\]\s*-\s*(?:BR|EUA)\s*-\s*VSL\s*(\d+)\s*-\s*([A-Z0-9\s]+?)\s*\|\s*(\d+\/\d+)\s*-\s*P[.]?\s*(.+?)\s*[\|\-]\s*G[.]?\s*(.+?)(?:\s*[\|\|])?$/i);
  if (!match) return null;

  const [, vsl, niche, date, perfil, gestor] = match;
  // Known suffixes to remove (test markers from gestores)
  const knownSuffixes = ['MM', 'LEM', '1', '2', '3', '4', '5'];
  let nichoBase = niche.trim();

  for (const suffix of knownSuffixes) {
    if (nichoBase.endsWith(suffix) && nichoBase.length > suffix.length) {
      nichoBase = nichoBase.substring(0, nichoBase.length - suffix.length);
      break;
    }
  }

  return {
    source: 'FB',
    vsl: parseInt(vsl),
    niche: nichoBase.trim(),
    date,
    perfil: perfil.trim(),
    gestor: gestor.trim().toLowerCase().replace(/^g\.\s*/, '')
  };
}

function parseCampaignYT(name) {
  const match = name.match(/\[YT\]\s*-\s*(?:BR|EUA)?\s*-?\s*(.+?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)$/i);
  if (!match) return null;

  const [, product, phone, gestor] = match;
  return {
    source: 'YT',
    product: product.trim(),
    phone: phone.trim(),
    gestor: gestor.trim()
  };
}

function parseCampaign(name) {
  if (name.includes('[FB]')) return parseCampaignFB(name);
  if (name.includes('[YT]')) return parseCampaignYT(name);
  return null;
}

async function processRedTrackData(data) {
  const items = data.items || [];
  const activeCampaigns = items.filter(c => c.cost > 0);

  const processed = [];

  for (const campaign of activeCampaigns) {
    const parsed = parseCampaign(campaign.campaign);
    if (!parsed) continue;

    const frontRevenue = (campaign.revenuetype2 || 0) + (campaign.revenuetype3 || 0);
    const roas = campaign.cost > 0 ? (frontRevenue / campaign.cost) : 0;

    processed.push({
      ...parsed,
      cost: campaign.cost,
      frontRevenue,
      vendas_cc: campaign.convtype4 || 0,
      conversions: campaign.conversions || 0,
      roas: parseFloat(roas.toFixed(2))
    });
  }

  return processed;
}

// ============================================
// 2. DATA AGGREGATION
// ============================================

function aggregateByGestorNiche(campaigns) {
  const agg = {};

  for (const camp of campaigns) {
    const gestor = camp.gestor || 'Unknown';
    const niche = camp.niche || camp.product || 'Unknown';
    const key = `${gestor}|${niche}`;

    if (!agg[key]) {
      agg[key] = {
        gestor,
        niche,
        count: 0,
        cost: 0,
        frontRevenue: 0,
        vendas_cc: 0,
        campaigns: []
      };
    }

    agg[key].count++;
    agg[key].cost += camp.cost;
    agg[key].frontRevenue += camp.frontRevenue;
    agg[key].vendas_cc += camp.vendas_cc;
    agg[key].campaigns.push(camp);
  }

  // Add calculated fields
  const result = Object.values(agg).map(row => ({
    ...row,
    roas: row.cost > 0 ? parseFloat((row.frontRevenue / row.cost).toFixed(2)) : 0,
    avgCost: parseFloat((row.cost / row.count).toFixed(2))
  }));

  // Sort by ROAS descending
  return result.sort((a, b) => b.roas - a.roas);
}

// ============================================
// 3. PDF GENERATION
// ============================================

async function generatePDF(campaigns, aggregated, dateFrom, dateTo) {
  const doc = await PDFDocument.create();
  const page = doc.addPage([595, 842]); // A4
  const { width, height } = page.getSize();

  const marginX = 40;
  const marginY = 40;
  const contentWidth = width - 2 * marginX;
  let y = height - marginY;

  // Helper to draw text
  const drawText = (text, size = 12, bold = false, color = rgb(0, 0, 0)) => {
    page.drawText(text, {
      x: marginX,
      y: y - size,
      size,
      color
    });
    y -= size + 4;
  };

  const drawLine = (thickness = 1, color = rgb(0.85, 0.85, 0.85)) => {
    page.drawLine({
      start: { x: marginX, y: y },
      end: { x: width - marginX, y: y },
      thickness,
      color
    });
    y -= 8;
  };

  // Header
  drawText('RELATÓRIO DE PERFORMANCE RedTrack', 16, true, rgb(0, 0.4, 0.8));
  drawText(`Período: ${dateFrom} a ${dateTo}`, 10, false, rgb(0.4, 0.4, 0.4));
  y -= 8;
  drawLine(2, rgb(0, 0.4, 0.8));

  // Summary
  const totalCost = campaigns.reduce((sum, c) => sum + c.cost, 0);
  const totalRevenue = campaigns.reduce((sum, c) => sum + c.frontRevenue, 0);
  const totalRoas = totalCost > 0 ? (totalRevenue / totalCost).toFixed(2) : 0;

  drawText(`Total de campanhas: ${campaigns.length}`, 11, true);
  drawText(`Investimento total: R$ ${totalCost.toFixed(2).replace('.', ',')}`, 11);
  drawText(`Faturamento (Front): R$ ${totalRevenue.toFixed(2).replace('.', ',')}`, 11);
  drawText(`ROAS total: ${totalRoas}`, 11, true, rgb(0, 0.5, 0));
  y -= 12;

  // Table header
  drawText('PERFORMANCE POR GESTOR + NICHO', 13, true);
  y -= 4;

  const colWidths = [100, 40, 70, 80, 60, 60];
  const headers = ['Gestor / Nicho', 'Qty', 'Investimento', 'Faturamento', 'ROAS', 'Ticket Médio'];

  // Draw header row
  let x = marginX;
  headers.forEach((h, i) => {
    page.drawText(h, {
      x,
      y: y - 12,
      size: 9,
      color: rgb(1, 1, 1)
    });
    x += colWidths[i];
  });

  page.drawRectangle({
    x: marginX,
    y: y - 18,
    width: contentWidth,
    height: 14,
    color: rgb(0, 0.4, 0.8)
  });

  y -= 22;

  // Table rows
  for (const row of aggregated.slice(0, 15)) {
    const gesture = `${row.gestor}/${row.niche}`.substring(0, 25);
    const investimento = `R$ ${(row.cost / 1000).toFixed(1)}k`;
    const faturamento = `R$ ${(row.frontRevenue / 1000).toFixed(1)}k`;
    const roas = row.roas.toFixed(2);
    const ticket = `R$ ${row.avgCost.toFixed(0)}`;

    x = marginX;
    page.drawText(gesture, { x, y: y - 10, size: 8 });
    x += colWidths[0];
    page.drawText(row.count.toString(), { x, y: y - 10, size: 8 });
    x += colWidths[1];
    page.drawText(investimento, { x, y: y - 10, size: 8 });
    x += colWidths[2];
    page.drawText(faturamento, { x, y: y - 10, size: 8 });
    x += colWidths[3];
    page.drawText(roas, { x, y: y - 10, size: 8, color: row.roas >= 2 ? rgb(0, 0.7, 0) : row.roas >= 1.5 ? rgb(0.7, 0.5, 0) : rgb(1, 0, 0) });
    x += colWidths[4];
    page.drawText(ticket, { x, y: y - 10, size: 8 });

    // Separator line
    page.drawLine({
      start: { x: marginX, y: y - 14 },
      end: { x: width - marginX, y: y - 14 },
      thickness: 0.5,
      color: rgb(0.9, 0.9, 0.9)
    });

    y -= 18;

    if (y < marginY + 30) {
      // New page
      const newPage = doc.addPage([595, 842]);
      page = newPage;
      y = height - marginY;
    }
  }

  // Save PDF
  const pdfPath = path.join(process.env.HOME, 'Desktop', `redtrack_report_${new Date().toISOString().split('T')[0]}.pdf`);
  const bytes = await doc.save();
  fs.writeFileSync(pdfPath, bytes);

  return pdfPath;
}

// ============================================
// 4. MAIN
// ============================================

async function getWeekDates() {
  const today = new Date();
  const dayOfWeek = today.getDay(); // 0 = Sunday, 1 = Monday, ..., 6 = Saturday

  // Calculate Monday (start of week)
  const daysToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
  const monday = new Date(today.getTime() + daysToMonday * 24 * 60 * 60 * 1000);

  // Calculate Sunday (end of week)
  const daysToSunday = dayOfWeek === 0 ? 0 : 7 - dayOfWeek;
  const sunday = new Date(today.getTime() + daysToSunday * 24 * 60 * 60 * 1000);

  return {
    dateFrom: monday.toISOString().split('T')[0],
    dateTo: sunday.toISOString().split('T')[0]
  };
}

async function main() {
  try {
    const { dateFrom, dateTo } = await getWeekDates();

    console.log(`\n🔄 Fetching RedTrack data from ${dateFrom} to ${dateTo}...`);
    const data = await getRedTrackData(dateFrom, dateTo);

    console.log(`✅ Data received. Processing campaigns...`);
    const campaigns = await processRedTrackData(data);

    console.log(`📊 ${campaigns.length} campaigns with cost > 0`);

    const aggregated = aggregateByGestorNiche(campaigns);
    console.log(`📈 Aggregated into ${aggregated.length} groups\n`);

    // Show top 5
    console.log('🏆 Top 5 by ROAS:');
    aggregated.slice(0, 5).forEach((row, i) => {
      console.log(`  ${i+1}. ${row.gestor}/${row.niche}: ROAS ${row.roas} (R$ ${(row.cost/1000).toFixed(1)}k)`);
    });

    console.log(`\n📄 Generating PDF...`);
    const pdfPath = await generatePDF(campaigns, aggregated, dateFrom, dateTo);
    console.log(`✅ PDF saved: ${pdfPath}\n`);

  } catch (error) {
    console.error('❌ Error:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main().catch(console.error);
}

module.exports = { getRedTrackData, parseCampaign, processRedTrackData, aggregateByGestorNiche };
