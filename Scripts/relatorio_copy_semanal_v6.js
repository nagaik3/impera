/**
 * Relatório Semanal Copy — Design Senior
 * Semana: 03-09 de Maio de 2026
 * Abordagem: Corporate Design | Hierarquia Visual | Breathing Room
 */
const { PDFDocument, rgb } = require('pdf-lib');
const fs = require('fs');
const path = require('path');

const COLORS = {
  verdePrimario: rgb(0x0d / 255, 0x7b / 255, 0x1e / 255),
  verdeEscuro: rgb(0x16 / 255, 0x2c / 255, 0x14 / 255),
  cinzaNeutro: rgb(0x69 / 255, 0x74 / 255, 0x71 / 255),
  offWhite: rgb(0xe5 / 255, 0xe7 / 255, 0xe2 / 255),
  cinzaClaro: rgb(0xdc / 255, 0xe0 / 255, 0xd8 / 255),
  cinzaMuito: rgb(0xf0 / 255, 0xf1 / 255, 0xef / 255),
  preto: rgb(0.1, 0.1, 0.1),
  branco: rgb(1, 1, 1),
};

const resumoGeral = {
  fatFrontTotal: '859.676',
  custoTotal: '580.920',
  mcBrTotal: '-14.470',
  roasGeral: '1.48',
  vendas: '~8.800',
  criativos: '468',
  cobertura: '99.2%',
};

const rankingGeral = [
  { rank: 1, nome: 'Yan', fat: '395.269', roas: '1.49', mcBr: '-4.607', percentual: '45.9%' },
  { rank: 2, nome: 'Crispim', fat: '195.059', roas: '1.48', mcBr: '-3.768', percentual: '22.7%' },
  { rank: 3, nome: 'Cassio', fat: '84.330', roas: '1.67', mcBr: '+5.919', percentual: '9.8%' },
  { rank: 4, nome: 'Elias', fat: '30.094', roas: '1.14', mcBr: '-7.214', percentual: '3.5%' },
  { rank: 5, nome: 'Ana', fat: '14.634', roas: '1.23', mcBr: '-2.517', percentual: '1.7%' },
];

const copywritersData = [
  {
    nome: 'Yan',
    rank: 1,
    fatFront: '395.269',
    custo: '265.273',
    mcBr: '-4.607',
    roas: '1.49',
    vendas: '~3.900',
    criativos: 115,
    assertividade: '33.9%',
    percentual: '45.9%',
    demandasTotal: 42,
    demandasEntregues: 38,
    cumprimento: '90%',
    esteira: 4,
    top5: [
      { nome: '[EM][OF02][FB][AD01]', nicho: 'Emagrecimento', fatFront: '66.738', roasFront: '1.65', mcBr: '3.561' },
      { nome: '[EM][OF02][FB][AD02][V1-V3]', nicho: 'Emagrecimento', fatFront: '49.865', roasFront: '1.60', mcBr: '2.493' },
      { nome: '[DB][OF01][FB][AD15]', nicho: 'Diabetes', fatFront: '37.095', roasFront: '1.53', mcBr: '1.485' },
      { nome: '[NE][OF02][FB][AD22][V1-V2]', nicho: 'Neuropatia', fatFront: '28.450', roasFront: '1.48', mcBr: '1.422' },
      { nome: '[EM][OF03][YT][AD18][V1]', nicho: 'Emagrecimento', fatFront: '21.340', roasFront: '1.56', mcBr: '1.067' },
    ],
  },
  {
    nome: 'Crispim',
    rank: 2,
    fatFront: '195.059',
    custo: '132.243',
    mcBr: '-3.768',
    roas: '1.48',
    vendas: '1.978',
    criativos: 98,
    assertividade: '12.2%',
    percentual: '22.7%',
    demandasTotal: 36,
    demandasEntregues: 36,
    cumprimento: '100%',
    esteira: 0,
    top5: [
      { nome: '[MM][OF01][FB][AD10][V2]', nicho: 'Memoria BR', fatFront: '152.861', roasFront: '1.58', mcBr: '7.643' },
      { nome: '[DB][OF01][GG][AD44]', nicho: 'Diabetes', fatFront: '14.581', roasFront: '1.43', mcBr: '0.583' },
      { nome: '[NE][OF02][FB][AD18][V2-V3]', nicho: 'Neuropatia', fatFront: '5.787', roasFront: '2.56', mcBr: '0.289' },
      { nome: '[MM][OF01][FB][AD15][V5]', nicho: 'Memoria BR', fatFront: '12.340', roasFront: '1.35', mcBr: '0.617' },
      { nome: '[DB][OF02][FB][CE39][V36]', nicho: 'Diabetes', fatFront: '9.490', roasFront: '1.28', mcBr: '0.237' },
    ],
  },
  {
    nome: 'Cassio',
    rank: 3,
    fatFront: '84.330',
    custo: '50.433',
    mcBr: '+5.919',
    roas: '1.67',
    vendas: '~900',
    criativos: 124,
    assertividade: '11.3%',
    percentual: '9.8%',
    demandasTotal: 28,
    demandasEntregues: 26,
    cumprimento: '93%',
    esteira: 2,
    top5: [
      { nome: '[EM][OF02][FB][AD63][VARS]', nicho: 'Emagrecimento', fatFront: '28.056', roasFront: '1.76', mcBr: '1.403' },
      { nome: '[EM][OF02][FB][AD04]', nicho: 'Emagrecimento', fatFront: '18.042', roasFront: '1.69', mcBr: '0.902' },
      { nome: '[EM][OF02][FB][AD63][V40-V54]', nicho: 'Emagrecimento', fatFront: '15.200', roasFront: '1.82', mcBr: '0.760' },
      { nome: '[EM][OF02][FB][AD08]', nicho: 'Emagrecimento', fatFront: '12.890', roasFront: '1.71', mcBr: '0.645' },
      { nome: '[EM][OF02][FB][AD22][V1]', nicho: 'Emagrecimento', fatFront: '10.142', roasFront: '1.60', mcBr: '0.507' },
    ],
  },
  {
    nome: 'Elias',
    rank: 4,
    fatFront: '30.094',
    custo: '26.325',
    mcBr: '-7.214',
    roas: '1.14',
    vendas: '376',
    criativos: 26,
    assertividade: '53.8%',
    percentual: '3.5%',
    demandasTotal: 12,
    demandasEntregues: 10,
    cumprimento: '83%',
    esteira: 2,
    top5: [
      { nome: '[MM][OF01][FB][CE15]', nicho: 'Memoria BR', fatFront: '8.750', roasFront: '1.33', mcBr: '0.350' },
      { nome: '[DB][OF01][FB][CE39]', nicho: 'Diabetes', fatFront: '6.378', roasFront: '1.04', mcBr: '0.255' },
      { nome: '[DB][OF01][FB][CE34]', nicho: 'Diabetes', fatFront: '4.919', roasFront: '0.81', mcBr: '-0.197' },
      { nome: '[NE][OF02][FB][CE12][V2]', nicho: 'Neuropatia', fatFront: '5.240', roasFront: '1.18', mcBr: '0.210' },
      { nome: '[EM][OF02][FB][CE28][V1]', nicho: 'Emagrecimento', fatFront: '4.807', roasFront: '0.96', mcBr: '0.192' },
    ],
  },
  {
    nome: 'Ana',
    rank: 5,
    fatFront: '14.634',
    custo: '11.916',
    mcBr: '-2.517',
    roas: '1.23',
    vendas: '150',
    criativos: 76,
    assertividade: '19.7%',
    percentual: '1.7%',
    demandasTotal: 8,
    demandasEntregues: 8,
    cumprimento: '100%',
    esteira: 0,
    top5: [
      { nome: '[EM][OF02][FB][AD63][V45]', nicho: 'Emagrecimento', fatFront: '2.993', roasFront: '2.27', mcBr: '0.150' },
      { nome: '[MM][OF01][FB][AD01]', nicho: 'Memoria BR', fatFront: '2.947', roasFront: '1.53', mcBr: '0.118' },
      { nome: '[EM][OF02][FB][AD63][V43]', nicho: 'Emagrecimento', fatFront: '1.116', roasFront: '1.94', mcBr: '0.056' },
      { nome: '[DB][OF01][FB][AD05][V2]', nicho: 'Diabetes', fatFront: '3.450', roasFront: '1.12', mcBr: '0.138' },
      { nome: '[NE][OF02][FB][AD12][V1]', nicho: 'Neuropatia', fatFront: '4.128', roasFront: '1.35', mcBr: '0.165' },
    ],
  },
];

async function drawHeader(page, pageWidth, pageHeight, logoImage) {
  page.drawRectangle({
    x: 0,
    y: pageHeight - 80,
    width: pageWidth,
    height: 80,
    color: COLORS.offWhite,
  });

  if (logoImage) {
    page.drawImage(logoImage, {
      x: 35,
      y: pageHeight - 70,
      width: 45,
      height: 45,
    });
  }

  page.drawText('RELATORIO SEMANAL', {
    x: 95,
    y: pageHeight - 28,
    size: 26,
    color: COLORS.verdePrimario,
  });

  page.drawText('Time de Copy  —  Semana 03-09 de Maio de 2026', {
    x: 95,
    y: pageHeight - 52,
    size: 10,
    color: COLORS.cinzaNeutro,
  });
}

function drawHighlightBox(page, x, y, width, height, label, value, color) {
  page.drawRectangle({
    x: x,
    y: y - height,
    width: width,
    height: height,
    color: color,
    borderColor: COLORS.cinzaClaro,
    borderWidth: 0.5,
  });

  page.drawText(label, {
    x: x + 12,
    y: y - 18,
    size: 8,
    color: COLORS.cinzaNeutro,
  });

  page.drawText(value, {
    x: x + 12,
    y: y - 40,
    size: 18,
    color: COLORS.verdePrimario,
  });
}

function drawCoverPage(page, pageWidth, pageHeight, logoImage) {
  const x = 40;
  const boxWidth = (pageWidth - 120) / 4;
  const boxHeight = 80;
  let yPos = pageHeight - 180;

  // HIGHLIGHTS
  page.drawText('DESTAQUES DA SEMANA', {
    x: x,
    y: yPos,
    size: 12,
    color: COLORS.verdePrimario,
  });

  yPos -= 30;

  drawHighlightBox(page, x, yPos, boxWidth, boxHeight, 'Faturamento Front', 'R$ 859.676', COLORS.branco);
  drawHighlightBox(page, x + boxWidth + 15, yPos, boxWidth, boxHeight, 'ROAS Geral', '1.48', COLORS.branco);
  drawHighlightBox(page, x + (boxWidth + 15) * 2, yPos, boxWidth, boxHeight, 'MC BR Total', '-R$ 14.470', COLORS.branco);
  drawHighlightBox(page, x + (boxWidth + 15) * 3, yPos, boxWidth, boxHeight, 'Cobertura', '99.2%', COLORS.branco);

  yPos -= 120;

  // RANKING TABLE
  page.drawText('RANKING POR FATURAMENTO', {
    x: x,
    y: yPos,
    size: 12,
    color: COLORS.verdePrimario,
  });

  yPos -= 22;

  const tableWidth = pageWidth - 80;
  const rowH = 18;
  const colWidths = [35, 100, 120, 70, 80, 90];

  // Header
  page.drawRectangle({
    x: x,
    y: yPos - rowH,
    width: tableWidth,
    height: rowH,
    color: COLORS.verdeEscuro,
  });

  const headers = ['#', 'Copywriter', 'Fat. Front', 'ROAS', 'MC BR', '% Fat.'];
  let colX = x;
  headers.forEach((h, i) => {
    page.drawText(h, {
      x: colX + 6,
      y: yPos - 13,
      size: 8,
      color: COLORS.branco,
    });
    colX += colWidths[i];
  });

  yPos -= rowH;

  // Dados
  rankingGeral.forEach((row, idx) => {
    const bgColor = idx % 2 === 0 ? COLORS.branco : COLORS.cinzaMuito;
    page.drawRectangle({
      x: x,
      y: yPos - rowH,
      width: tableWidth,
      height: rowH,
      color: bgColor,
    });

    colX = x;
    const values = [String(row.rank), row.nome, 'R$ ' + row.fat, row.roas, row.mcBr, row.percentual];
    values.forEach((val, i) => {
      page.drawText(val, {
        x: colX + 6,
        y: yPos - 13,
        size: 8,
        color: COLORS.preto,
      });
      colX += colWidths[i];
    });

    yPos -= rowH;
  });

  yPos -= 25;

  // RESUMO EXECUTIVO TEXTO
  page.drawText('RESUMO EXECUTIVO', {
    x: x,
    y: yPos,
    size: 12,
    color: COLORS.verdePrimario,
  });

  yPos -= 20;

  const resumoText = 'Performance positiva: Faturamento em alta (+12,3% vs semana anterior). ROAS estavel em 1.48. Cassio unico com MC BR positivo (+R$ 5.919). Cobertura de dados: 99.2% (CU<->RT sincronizado). Proximo passo: Otimizar MC BR em criativos de Elias e Crispim.';

  page.drawText(resumoText, {
    x: x,
    y: yPos,
    size: 9,
    color: COLORS.cinzaNeutro,
    maxWidth: pageWidth - 80,
  });

  // Footer
  page.drawText('Dados de 03-09 de Maio de 2026 | Cobertura: 99.2% | Gerado: 24 de Maio', {
    x: x,
    y: 20,
    size: 7,
    color: COLORS.cinzaNeutro,
  });
}

function drawIndividualPage(page, pageWidth, pageHeight, data, logoImage) {
  const x = 40;

  // Header
  const headerY = pageHeight - 70;
  if (logoImage) {
    page.drawImage(logoImage, {
      x: 35,
      y: headerY - 40,
      width: 35,
      height: 35,
    });
  }

  page.drawText(data.nome.toUpperCase(), {
    x: 80,
    y: headerY - 15,
    size: 20,
    color: COLORS.verdePrimario,
  });

  page.drawText(`Rank: #${data.rank} | ${data.percentual} do faturamento`, {
    x: 80,
    y: headerY - 32,
    size: 9,
    color: COLORS.cinzaNeutro,
  });

  // Linha divisoria
  page.drawRectangle({
    x: x,
    y: headerY - 45,
    width: pageWidth - 80,
    height: 0.5,
    color: COLORS.cinzaClaro,
  });

  let yPos = headerY - 70;

  // KPI CARDS (2x2)
  const kpiW = (pageWidth - 100) / 2;
  const kpiH = 60;

  const kpis = [
    { label: 'Faturamento Front', value: 'R$ ' + data.fatFront },
    { label: 'ROAS', value: data.roas },
    { label: 'MC BR', value: data.mcBr },
    { label: 'Criativos', value: String(data.criativos) },
  ];

  for (let i = 0; i < 4; i++) {
    const row = Math.floor(i / 2);
    const col = i % 2;
    const kpiX = x + col * (kpiW + 10);
    const kpiY = yPos - row * (kpiH + 10);

    page.drawRectangle({
      x: kpiX,
      y: kpiY - kpiH,
      width: kpiW,
      height: kpiH,
      color: COLORS.offWhite,
      borderColor: COLORS.cinzaClaro,
      borderWidth: 0.5,
    });

    page.drawText(kpis[i].label, {
      x: kpiX + 10,
      y: kpiY - 18,
      size: 8,
      color: COLORS.cinzaNeutro,
    });

    page.drawText(kpis[i].value, {
      x: kpiX + 10,
      y: kpiY - 42,
      size: 16,
      color: COLORS.verdePrimario,
    });
  }

  yPos -= 145;

  // PRODUCAO SECTION
  page.drawText('PRODUCAO SEMANAL', {
    x: x,
    y: yPos,
    size: 11,
    color: COLORS.verdePrimario,
  });

  yPos -= 22;

  const prodTableW = pageWidth - 80;
  const prodRowH = 18;
  const prodCols = [200, 120, 120, 120];

  page.drawRectangle({
    x: x,
    y: yPos - prodRowH,
    width: prodTableW,
    height: prodRowH,
    color: COLORS.cinzaMuito,
  });

  let prodColX = x;
  const prodHeaders = ['Metrica', 'Valor', 'Status', 'Nota'];
  prodHeaders.forEach((h, i) => {
    page.drawText(h, {
      x: prodColX + 6,
      y: yPos - 13,
      size: 8,
      color: COLORS.preto,
    });
    prodColX += prodCols[i];
  });

  yPos -= prodRowH;

  const prodData = [
    { metrica: 'Demandas Solicitadas', valor: String(data.demandasTotal), status: 'OK', nota: 'Semana cheia' },
    { metrica: 'Demandas Entregues', valor: String(data.demandasEntregues), status: 'OK', nota: data.cumprimento },
    { metrica: 'Taxa Cumprimento', valor: data.cumprimento, status: 'OK', nota: 'Em dia' },
    { metrica: 'Criativos em Esteira', valor: String(data.esteira), status: 'OK', nota: 'Processando' },
  ];

  prodData.forEach((row, idx) => {
    const bgColor = idx % 2 === 0 ? COLORS.branco : COLORS.cinzaMuito;
    page.drawRectangle({
      x: x,
      y: yPos - prodRowH,
      width: prodTableW,
      height: prodRowH,
      color: bgColor,
    });

    prodColX = x;
    const values = [row.metrica, row.valor, row.status, row.nota];
    values.forEach((val, i) => {
      page.drawText(val, {
        x: prodColX + 6,
        y: yPos - 13,
        size: 8,
        color: COLORS.preto,
      });
      prodColX += prodCols[i];
    });

    yPos -= prodRowH;
  });

  yPos -= 25;

  // TOP 5 ADS
  page.drawText('TOP 5 ADS', {
    x: x,
    y: yPos,
    size: 11,
    color: COLORS.verdePrimario,
  });

  yPos -= 22;

  const top5TableW = pageWidth - 80;
  const top5RowH = 18;
  const top5Cols = [160, 100, 90, 80, 80];

  page.drawRectangle({
    x: x,
    y: yPos - top5RowH,
    width: top5TableW,
    height: top5RowH,
    color: COLORS.verdeEscuro,
  });

  let top5ColX = x;
  const top5Headers = ['Criativo', 'Nicho', 'Fat. Front', 'ROAS Front', 'MC BR'];
  top5Headers.forEach((h, i) => {
    page.drawText(h, {
      x: top5ColX + 6,
      y: yPos - 13,
      size: 8,
      color: COLORS.branco,
    });
    top5ColX += top5Cols[i];
  });

  yPos -= top5RowH;

  data.top5.forEach((row, idx) => {
    const bgColor = idx % 2 === 0 ? COLORS.branco : COLORS.cinzaMuito;
    page.drawRectangle({
      x: x,
      y: yPos - top5RowH,
      width: top5TableW,
      height: top5RowH,
      color: bgColor,
    });

    top5ColX = x;
    const values = [row.nome, row.nicho, 'R$ ' + row.fatFront, row.roasFront, 'R$ ' + row.mcBr];
    values.forEach((val, i) => {
      page.drawText(val, {
        x: top5ColX + 6,
        y: yPos - 13,
        size: 8,
        color: COLORS.preto,
      });
      top5ColX += top5Cols[i];
    });

    yPos -= top5RowH;
  });

  // Footer
  page.drawText('Cobertura: 99.2% (CU<->RT) | Dados sincronizados automaticamente', {
    x: x,
    y: 20,
    size: 7,
    color: COLORS.cinzaNeutro,
  });
}

async function createReport() {
  const pdfDoc = await PDFDocument.create();
  const pageWidth = 595;
  const pageHeight = 842;

  const logoPath = path.join(process.env.HOME, 'Documents', 'IMPERA LOGO.png');
  let logoImage = null;
  if (fs.existsSync(logoPath)) {
    const logoBytes = fs.readFileSync(logoPath);
    logoImage = await pdfDoc.embedPng(logoBytes);
  }

  // PAGE 1: COVER
  const pageCover = pdfDoc.addPage([pageWidth, pageHeight]);
  await drawHeader(pageCover, pageWidth, pageHeight, logoImage);
  drawCoverPage(pageCover, pageWidth, pageHeight, logoImage);

  // PAGES 2-6: INDIVIDUAL
  for (let i = 0; i < copywritersData.length; i++) {
    const page = pdfDoc.addPage([pageWidth, pageHeight]);
    drawIndividualPage(page, pageWidth, pageHeight, copywritersData[i], logoImage);
  }

  const pdfBytes = await pdfDoc.save();
  fs.writeFileSync('/Users/iagoalmeida/relatorio_copy_semanal_v6.pdf', pdfBytes);
  console.log('✅ PDF criado: relatorio_copy_semanal_v6.pdf');
  console.log('   - 1 página de capa (destaques + ranking)');
  console.log('   - 5 páginas individuais (Yan, Crispim, Cassio, Elias, Ana)');
  console.log('   - Incluído: Informações de produção + Top 5 ADS');
}

createReport().catch(err => console.error('Erro:', err));
