#!/usr/bin/env node

const https = require('https');
const { promisify } = require('util');

const httpGet = promisify((url, callback) => {
  https.get(url, callback).on('error', (e) => callback(e));
});

// ============================================
// 1. REDTRACK API
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

// ============================================
// 2. CAMPAIGN PARSING
// ============================================

function parseCampaignFB(name) {
  // Pattern: [FB] - (BR|EUA) - VSL XX - NICHO | DD/MM - P. CONTA | G. GESTOR
  // More flexible with spacing variations and multi-word nichos
  const match = name.match(/\[FB\]\s*-\s*(?:BR|EUA)\s*-\s*VSL\s*(\d+)\s*-\s*([A-Z0-9\s]+?)\s*\|\s*(\d+\/\d+)\s*-\s*P[.]?\s*(.+?)\s*[\|\-]\s*G[.]?\s*(.+?)(?:\s*[\|\|])?$/i);

  if (!match) return null;

  const [, vsl, niche, date, perfil, gestor] = match;
  const nichoBase = niche.trim().replace(/[A-Z]{2,}$/, ''); // Remove suffix (MM, LEM, etc)

  return {
    source: 'FB',
    vsl: parseInt(vsl),
    niche: nichoBase.trim(),
    nichoFull: niche.trim(),
    date,
    perfil: perfil.trim(),
    gestor: gestor.trim(),
    originalName: name
  };
}

function parseCampaignYT(name) {
  // Pattern: [YT] - (BR/EUA?) - PRODUTO | NUMERO | GESTOR
  // More flexible - BR/EUA is optional
  const match = name.match(/\[YT\]\s*-\s*(?:BR|EUA)?\s*-?\s*(.+?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)$/i);

  if (!match) return null;

  const [, product, phone, gestor] = match;

  return {
    source: 'YT',
    product: product.trim(),
    phone: phone.trim(),
    gestor: gestor.trim(),
    originalName: name
  };
}

function parseCampaign(name) {
  if (name.includes('[FB]')) return parseCampaignFB(name);
  if (name.includes('[YT]')) return parseCampaignYT(name);
  return null;
}

// ============================================
// 3. CLICKUP API
// ============================================

async function searchClickUpTask(vsl, niche) {
  const token = process.env.CLICKUP_API_TOKEN;
  if (!token) throw new Error('CLICKUP_API_TOKEN not set');

  // List ID para COPY = precisa ser validado
  const listId = '901509976747'; // Ajustar conforme necessário

  const query = `VSL ${vsl} ${niche}`;
  const url = `https://api.clickup.com/api/v2/list/${listId}/task?query=${encodeURIComponent(query)}`;

  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: { 'Authorization': token }
    }, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          const tasks = parsed.tasks || [];
          resolve(tasks.length > 0 ? tasks[0] : null);
        } catch (e) {
          resolve(null);
        }
      });
    });
    req.on('error', reject);
  });
}

// ============================================
// 4. DATA PROCESSING
// ============================================

async function processRedTrackData(data, dateFrom, dateTo) {
  const items = data.items || [];

  // Filter campaigns with cost > 0
  const activeCampaigns = items.filter(c => c.cost > 0);

  console.log(`\n📊 RedTrack Data Summary (${dateFrom} to ${dateTo})`);
  console.log(`   Total campaigns: ${items.length}`);
  console.log(`   Active (cost > 0): ${activeCampaigns.length}`);

  const processed = [];

  for (const campaign of activeCampaigns) {
    const parsed = parseCampaign(campaign.campaign);
    if (!parsed) {
      console.log(`⚠️  Could not parse: ${campaign.campaign}`);
      continue;
    }

    const frontRevenue = (campaign.revenuetype2 || 0) + (campaign.revenuetype3 || 0);
    const roas = campaign.cost > 0 ? (frontRevenue / campaign.cost).toFixed(2) : 0;
    const vendas_cc = campaign.convtype4 || 0;

    let copywriter = 'Unknown';
    if (parsed.source === 'FB') {
      // TODO: Query ClickUp to find copywriter
      copywriter = 'Pending ClickUp';
    }

    processed.push({
      ...parsed,
      cost: campaign.cost,
      frontRevenue,
      vendas_cc,
      conversions: campaign.conversions || 0,
      roas: parseFloat(roas),
      profit: campaign.default_profit || 0,
      copywriter
    });
  }

  return processed;
}

// ============================================
// 5. MAIN
// ============================================

async function main() {
  try {
    // Last 7 days
    const today = new Date();
    const dateTo = today.toISOString().split('T')[0];
    const dateFrom = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

    console.log(`🔄 Fetching RedTrack data from ${dateFrom} to ${dateTo}...`);
    const data = await getRedTrackData(dateFrom, dateTo);

    console.log(`✅ RedTrack API response received`);

    const processed = await processRedTrackData(data, dateFrom, dateTo);

    console.log(`\n📋 Processed ${processed.length} campaigns:`);
    processed.slice(0, 5).forEach(c => {
      console.log(`   [${c.source}] ${c.originalName}`);
      console.log(`      Cost: R$${c.cost.toFixed(2)} | Front Rev: R$${c.frontRevenue.toFixed(2)} | ROAS: ${c.roas}`);
    });

    // Export for validation
    console.log(`\n✅ Data processing complete. Ready for PDF generation.`);
    return processed;

  } catch (error) {
    console.error('❌ Error:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main().catch(console.error);
}

module.exports = { getRedTrackData, parseCampaign, processRedTrackData };
