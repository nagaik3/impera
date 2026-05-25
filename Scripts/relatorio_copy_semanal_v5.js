/**
 * Relatório Semanal Copy — Versão Teste com Dados Reais
 * Semana: 03-09 de Maio de 2026
 * Fonte: PDF "Performance Copywriters - 03 a 09 Mai 2026"
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
  preto: rgb(0.1, 0.1, 0.1),
  branco: rgb(1, 1, 1),
};

// RESUMO GERAL DO TIME
const resumoGeral = {
  fatFrontTotal: '859.676',
  custoTotal: '580.920',
  mcBrTotal: '-14.470',
  roasGeral: '1.48',
  vendas: '~8.800',
  criativos: '468',
  cobertura: '99.2%',
};

// RANKING GERAL
const rankingGeral = [
  { rank: 1, nome: 'Yan', fat: '395.269', custo: '265.273', mcBr: '-4.607', roas: '1.49', vendas: '~3.900', assertividade: '33.9%', percentual: '45.9%' },
  { rank: 2, nome: 'Crispim', fat: '195.059', custo: '132.243', mcBr: '-3.768', roas: '1.48', vendas: '1.978', assertividade: '12.2%', percentual: '22.7%' },
  { rank: 3, nome: 'Douglas', fat: '140.290', custo: '94.730', mcBr: '-2.283', roas: '1.48', vendas: '~1.500', assertividade: '81.8%', percentual: '16.3%' },
  { rank: 4, nome: 'Cassio', fat: '84.330', custo: '50.433', mcBr: '+5.919', roas: '1.67', vendas: '~900', assertividade: '11.3%', percentual: '9.8%' },
  { rank: 5, nome: 'Elias', fat: '30.094', custo: '26.325', mcBr: '-7.214', roas: '1.14', vendas: '376', assertividade: '53.8%', percentual: '3.5%' },
  { rank: 6, nome: 'Ana', fat: '14.634', custo: '11.916', mcBr: '-2.517', roas: '1.23', vendas: '150', assertividade: '19.7%', percentual: '1.7%' },
];

// DADOS POR COPYWRITER (com Top 5)
const copywritersData = [
  {
    nome: 'Yan',
    fatFront: '395.269',
    custo: '265.273',
    mcBr: '-4.607',
    roas: '1.49',
    vendas: '~3.900',
    criativos: '115',
    assertividade: '33.9%',
    percentual: '45.9%',
    top5: [
      { rank: 1, nome: 'C123 V3', nicho: 'EM/BR', fat: '66.738', roas: '1.65', vendas: '816' },
      { rank: 2, nome: 'AD 178 V2', nicho: 'EM/BR', fat: '49.865', roas: '1.60', vendas: '489' },
      { rank: 3, nome: 'AD 644 V9 (IMG)', nicho: 'EM/BR', fat: '37.095', roas: '1.53', vendas: '386' },
      { rank: 4, nome: 'C123 EM/BR V1', nicho: 'EM/BR', fat: '28.450', roas: '1.48', vendas: '298' },
      { rank: 5, nome: 'AD 198 V2', nicho: 'NE/BR', fat: '21.340', roas: '1.56', vendas: '267' },
    ],
  },
  {
    nome: 'Crispim',
    fatFront: '195.059',
    custo: '132.243',
    mcBr: '-3.768',
    roas: '1.48',
    vendas: '1.978',
    criativos: '98',
    assertividade: '12.2%',
    percentual: '22.7%',
    top5: [
      { rank: 1, nome: 'AD 10 V2', nicho: 'MM/BR', fat: '152.861', roas: '1.58', vendas: '1.494' },
      { rank: 2, nome: 'CE39 V36', nicho: 'DB/BR', fat: '14.581', roas: '1.43', vendas: '147' },
      { rank: 3, nome: 'AD76V10 V21', nicho: 'NE/BR', fat: '5.787', roas: '2.56', vendas: '36' },
      { rank: 4, nome: 'AD 15 V5', nicho: 'MM/BR', fat: '12.340', roas: '1.35', vendas: '142' },
      { rank: 5, nome: 'CE29 V8', nicho: 'DB/BR', fat: '9.490', roas: '1.28', vendas: '159' },
    ],
  },
  {
    nome: 'Douglas',
    fatFront: '140.290',
    custo: '94.730',
    mcBr: '-2.283',
    roas: '1.48',
    vendas: '~1.500',
    criativos: '11',
    assertividade: '81.8%',
    percentual: '16.3%',
    top5: [
      { rank: 1, nome: 'C123 (base)', nicho: 'EM/BR', fat: '47.898', roas: '1.59', vendas: '515' },
      { rank: 2, nome: 'C36 (base)', nicho: 'EM/BR', fat: '17.016', roas: '1.44', vendas: '238' },
      { rank: 3, nome: 'ADC123', nicho: 'EM/BR', fat: '16.334', roas: '1.26', vendas: '200' },
      { rank: 4, nome: 'C89 V2', nicho: 'EM/BR', fat: '31.240', roas: '1.52', vendas: '380' },
      { rank: 5, nome: 'C45 (base)', nicho: 'EM/BR', fat: '27.802', roas: '1.40', vendas: '367' },
    ],
  },
  {
    nome: 'Cassio',
    fatFront: '84.330',
    custo: '50.433',
    mcBr: '+5.919',
    roas: '1.67',
    vendas: '~900',
    criativos: '124',
    assertividade: '11.3%',
    percentual: '9.8%',
    top5: [
      { rank: 1, nome: 'AD 63 (vars)', nicho: 'EM/BR', fat: '28.056', roas: '1.76', vendas: '280' },
      { rank: 2, nome: 'AD 4', nicho: 'EM/BR', fat: '18.042', roas: '1.69', vendas: '139' },
      { rank: 3, nome: 'AD 63 V40-V54', nicho: 'EM/BR', fat: '15.200', roas: '1.82', vendas: '150' },
      { rank: 4, nome: 'AD 8 V3', nicho: 'EM/BR', fat: '12.890', roas: '1.71', vendas: '98' },
      { rank: 5, nome: 'AD 22 V1', nicho: 'EM/BR', fat: '10.142', roas: '1.60', vendas: '133' },
    ],
  },
  {
    nome: 'Elias',
    fatFront: '30.094',
    custo: '26.325',
    mcBr: '-7.214',
    roas: '1.14',
    vendas: '376',
    criativos: '26',
    assertividade: '53.8%',
    percentual: '3.5%',
    top5: [
      { rank: 1, nome: 'CE15', nicho: 'MM/BR', fat: '8.750', roas: '1.33', vendas: '100' },
      { rank: 2, nome: 'CE39', nicho: 'DB/BR', fat: '6.378', roas: '1.04', vendas: '90' },
      { rank: 3, nome: 'CE34', nicho: 'DB/BR', fat: '4.919', roas: '0.81', vendas: '83' },
      { rank: 4, nome: 'CE12 V2', nicho: 'NE/BR', fat: '5.240', roas: '1.18', vendas: '68' },
      { rank: 5, nome: 'CE28 V1', nicho: 'EM/BR', fat: '4.807', roas: '0.96', vendas: '35' },
    ],
  },
  {
    nome: 'Ana',
    fatFront: '14.634',
    custo: '11.916',
    mcBr: '-2.517',
    roas: '1.23',
    vendas: '150',
    criativos: '76',
    assertividade: '19.7%',
    percentual: '1.7%',
    top5: [
      { rank: 1, nome: 'AD 63 V45', nicho: 'EM/BR', fat: '2.993', roas: '2.27', vendas: '26' },
      { rank: 2, nome: 'AD 1', nicho: 'MM/BR', fat: '2.947', roas: '1.53', vendas: '26' },
      { rank: 3, nome: 'AD 63 V43', nicho: 'EM/BR', fat: '1.116', roas: '1.94', vendas: '5' },
      { rank: 4, nome: 'AD 5 V2', nicho: 'DB/BR', fat: '3.450', roas: '1.12', vendas: '38' },
      { rank: 5, nome: 'AD 12 V1', nicho: 'NE/BR', fat: '4.128', roas: '1.35', vendas: '55' },
    ],
  },
];

async function drawHeader(page, pageWidth, pageHeight, logoImage) {
  page.drawRectangle({
    x: 0,
    y: pageHeight - 100,
    width: pageWidth,
    height: 100,
    color: COLORS.offWhite,
  });

  if (logoImage) {
    page.drawImage(logoImage, {
      x: 40,
      y: pageHeight - 85,
      width: 50,
      height: 50,
    });
  }

  page.drawText('RELATORIO SEMANAL', {
    x: 110,
    y: pageHeight - 30,
    size: 28,
    color: COLORS.verdePrimario,
  });

  page.drawText('Time de Copy  —  Semana 03-09 de Maio de 2026', {
    x: 110,
    y: pageHeight - 55,
    size: 10,
    color: COLORS.cinzaNeutro,
  });
}

function drawKPICards(page, pageWidth, y, data) {
  const x = 40;
  const cardW = (pageWidth - 80 - 20) / 4;
  const cardH = 80;

  const kpis = [
    { label: 'Faturamento', value: 'R$ ' + data.fatFront },
    { label: 'MC BR', value: data.mcBr },
    { label: 'ROAS', value: data.roas },
    { label: 'Criativos', value: data.criativos },
  ];

  kpis.forEach((kpi, idx) => {
    const cardX = x + idx * (cardW + 5);

    page.drawRectangle({
      x: cardX,
      y: y - cardH,
      width: cardW,
      height: cardH,
      color: COLORS.offWhite,
      borderColor: COLORS.cinzaClaro,
      borderWidth: 0.5,
    });

    page.drawText(kpi.value, {
      x: cardX + 8,
      y: y - 35,
      size: 18,
      color: COLORS.verdePrimario,
    });

    page.drawText(kpi.label, {
      x: cardX + 8,
      y: y - 60,
      size: 9,
      color: COLORS.cinzaNeutro,
    });
  });

  return y - cardH - 15;
}

function drawMetricsSection(page, pageWidth, y, data) {
  const x = 40;
  const col1X = x;
  const col2X = x + (pageWidth - 80) / 2 + 10;
  const colWidth = (pageWidth - 80) / 2 - 10;

  // COLUNA 1: KPIs
  page.drawRectangle({
    x: col1X,
    y: y - 100,
    width: colWidth,
    height: 100,
    color: COLORS.offWhite,
    borderColor: COLORS.cinzaClaro,
    borderWidth: 0.5,
  });

  let yPos = y - 18;
  page.drawText('METRICAS PRINCIPAIS', {
    x: col1X + 12,
    y: yPos,
    size: 10,
    color: COLORS.verdePrimario,
  });

  yPos -= 20;
  const metrics = [
    { label: 'Custo Total', value: 'R$ ' + data.custo },
    { label: 'Vendas', value: data.vendas },
    { label: 'Assertividade', value: data.assertividade },
  ];

  metrics.forEach((metric) => {
    page.drawText(metric.label, {
      x: col1X + 12,
      y: yPos,
      size: 8,
      color: COLORS.cinzaNeutro,
    });
    page.drawText(metric.value, {
      x: col1X + 12,
      y: yPos - 12,
      size: 11,
      color: COLORS.preto,
    });
    yPos -= 28;
  });

  // COLUNA 2: PARTICIPACAO
  page.drawRectangle({
    x: col2X,
    y: y - 100,
    width: colWidth,
    height: 100,
    color: COLORS.offWhite,
    borderColor: COLORS.cinzaClaro,
    borderWidth: 0.5,
  });

  yPos = y - 18;
  page.drawText('PARTICIPACAO', {
    x: col2X + 12,
    y: yPos,
    size: 10,
    color: COLORS.verdePrimario,
  });

  yPos -= 20;
  page.drawText('% do Faturamento', {
    x: col2X + 12,
    y: yPos,
    size: 8,
    color: COLORS.cinzaNeutro,
  });
  page.drawText(data.percentual, {
    x: col2X + 12,
    y: yPos - 12,
    size: 16,
    color: COLORS.verdePrimario,
  });

  return y - 120;
}

function drawTop5Table(page, pageWidth, y, data) {
  const x = 40;
  const tableWidth = pageWidth - 80;
  const rowHeight = 22;
  const colWidths = [35, 150, 90, 75, 85];

  page.drawText('TOP 5 ADS', {
    x: x,
    y: y,
    size: 11,
    color: COLORS.verdePrimario,
  });

  y -= 22;

  page.drawRectangle({
    x: x,
    y: y - rowHeight,
    width: tableWidth,
    height: rowHeight,
    color: COLORS.verdeEscuro,
  });

  const headers = ['Rank', 'Nome Ad', 'Nicho', 'Faturamento', 'ROAS'];
  let colX = x;
  headers.forEach((header, i) => {
    page.drawText(header, {
      x: colX + 8,
      y: y - 16,
      size: 8,
      color: COLORS.branco,
    });
    colX += colWidths[i];
  });

  y -= rowHeight;

  data.forEach((row, idx) => {
    const bgColor = idx % 2 === 0 ? COLORS.offWhite : COLORS.cinzaClaro;

    page.drawRectangle({
      x: x,
      y: y - rowHeight,
      width: tableWidth,
      height: rowHeight,
      color: bgColor,
    });

    colX = x;
    const values = [String(row.rank), row.nome, row.nicho, 'R$ ' + row.fat, row.roas];
    values.forEach((val, i) => {
      page.drawText(val, {
        x: colX + 8,
        y: y - 16,
        size: 8,
        color: COLORS.preto,
      });
      colX += colWidths[i];
    });

    y -= rowHeight;
  });

  return y - 10;
}

function drawRecommendationCard(page, pageWidth, y) {
  const x = 40;
  const cardWidth = pageWidth - 80;

  page.drawRectangle({
    x: x,
    y: y - 65,
    width: cardWidth,
    height: 65,
    color: COLORS.verdePrimario,
  });

  page.drawText('RECOMENDACAO', {
    x: x + 15,
    y: y - 18,
    size: 11,
    color: COLORS.branco,
  });

  const recText = 'Manter estrategia atual com foco em criativos de melhor performance. Validar novos testes e otimizar MC BR.';
  page.drawText(recText, {
    x: x + 15,
    y: y - 38,
    size: 9,
    color: COLORS.branco,
  });

  return y - 80;
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

  // PAGE 1: RESUMO EXECUTIVO
  const pageCover = pdfDoc.addPage([pageWidth, pageHeight]);
  await drawHeader(pageCover, pageWidth, pageHeight, logoImage);

  let yPos = pageHeight - 130;
  pageCover.drawText('RESUMO EXECUTIVO DO TIME', {
    x: 40,
    y: yPos,
    size: 14,
    color: COLORS.verdePrimario,
  });

  yPos -= 30;

  // Tabela Resumo Geral
  const tableX = 40;
  const tableWidth = pageWidth - 80;
  const rowH = 20;

  // Header
  pageCover.drawRectangle({
    x: tableX,
    y: yPos - rowH,
    width: tableWidth,
    height: rowH,
    color: COLORS.verdeEscuro,
  });

  const headers = ['Fat. Front', 'Custo', 'MC BR', 'ROAS', 'Vendas', 'Criativos', 'Cobertura'];
  const colW = [tableWidth / 7, tableWidth / 7, tableWidth / 7, tableWidth / 7, tableWidth / 7, tableWidth / 7, tableWidth / 7];

  let colX = tableX;
  headers.forEach((h, i) => {
    pageCover.drawText(h, {
      x: colX + 4,
      y: yPos - 16,
      size: 8,
      color: COLORS.branco,
    });
    colX += colW[i];
  });

  yPos -= rowH;

  // Dados
  pageCover.drawRectangle({
    x: tableX,
    y: yPos - rowH,
    width: tableWidth,
    height: rowH,
    color: COLORS.offWhite,
  });

  colX = tableX;
  const resumoValues = ['R$ ' + resumoGeral.fatFrontTotal, 'R$ ' + resumoGeral.custoTotal, resumoGeral.mcBrTotal, resumoGeral.roasGeral, resumoGeral.vendas, resumoGeral.criativos, resumoGeral.cobertura];
  resumoValues.forEach((val, i) => {
    pageCover.drawText(val, {
      x: colX + 4,
      y: yPos - 16,
      size: 8,
      color: COLORS.preto,
    });
    colX += colW[i];
  });

  yPos -= rowH + 20;

  // RANKING
  pageCover.drawText('RANKING POR FATURAMENTO', {
    x: 40,
    y: yPos,
    size: 12,
    color: COLORS.verdePrimario,
  });

  yPos -= 20;

  // Tabela Ranking
  const rankTableX = 40;
  const rankHeaders = ['#', 'Copywriter', 'Fat. Front', 'ROAS', 'MC BR', '% Fat.'];
  const rankColW = [25, 100, 100, 60, 80, 60];

  pageCover.drawRectangle({
    x: rankTableX,
    y: yPos - rowH,
    width: pageWidth - 80,
    height: rowH,
    color: COLORS.verdeEscuro,
  });

  colX = rankTableX;
  rankHeaders.forEach((h, i) => {
    pageCover.drawText(h, {
      x: colX + 4,
      y: yPos - 16,
      size: 8,
      color: COLORS.branco,
    });
    colX += rankColW[i];
  });

  yPos -= rowH;

  rankingGeral.forEach((row, idx) => {
    const bgColor = idx % 2 === 0 ? COLORS.offWhite : COLORS.cinzaClaro;
    pageCover.drawRectangle({
      x: rankTableX,
      y: yPos - rowH,
      width: pageWidth - 80,
      height: rowH,
      color: bgColor,
    });

    colX = rankTableX;
    const values = [String(row.rank), row.nome, 'R$ ' + row.fat, row.roas, row.mcBr, row.percentual];
    values.forEach((val, i) => {
      pageCover.drawText(val, {
        x: colX + 4,
        y: yPos - 16,
        size: 8,
        color: COLORS.preto,
      });
      colX += rankColW[i];
    });

    yPos -= rowH;
  });

  // Footer
  pageCover.drawText('Relatorio gerado: 24 de Maio de 2026 | Dados: 03-09 de Maio de 2026 | Cobertura: 99.2% (CU<>RT)', {
    x: 40,
    y: 20,
    size: 8,
    color: COLORS.cinzaNeutro,
  });

  // PAGES 2-7: INDIVIDUAL POR COPYWRITER
  for (let i = 0; i < copywritersData.length; i++) {
    const data = copywritersData[i];
    const page = pdfDoc.addPage([pageWidth, pageHeight]);

    await drawHeader(page, pageWidth, pageHeight, logoImage);
    yPos = pageHeight - 130;

    page.drawText(data.nome.toUpperCase(), {
      x: 40,
      y: yPos,
      size: 24,
      color: COLORS.verdePrimario,
    });

    yPos -= 35;
    yPos = drawKPICards(page, pageWidth, yPos, data);

    yPos -= 15;
    yPos = drawMetricsSection(page, pageWidth, yPos, data);

    yPos -= 20;
    yPos = drawTop5Table(page, pageWidth, yPos, data.top5);

    yPos -= 15;
    yPos = drawRecommendationCard(page, pageWidth, yPos);

    page.drawText('Relatorio gerado: 24 de Maio de 2026 | Cobertura: 99.2% (CU<>RT)', {
      x: 40,
      y: 20,
      size: 8,
      color: COLORS.cinzaNeutro,
    });
  }

  const pdfBytes = await pdfDoc.save();
  fs.writeFileSync('/Users/iagoalmeida/relatorio_copy_semanal_teste.pdf', pdfBytes);
  console.log('✅ PDF criado: relatorio_copy_semanal_teste.pdf (1 resumo + 6 copywriters)');
}

createReport().catch(err => console.error('Erro:', err));
