/**
 * Relatório Semanal Copy — Design Minimalista Fintech
 * Padrões: Grotesque Pro, números grandes, cards limpos, cores verdes/cinza
 */
const { PDFDocument, rgb } = require('pdf-lib');
const fs = require('fs');
const path = require('path');

const COLORS = {
  verdePrimario: rgb(0x0d / 255, 0x7b / 255, 0x1e / 255),    // #0D7B1E
  verdeEscuro: rgb(0x16 / 255, 0x2c / 255, 0x14 / 255),      // #162C14
  cinzaNeutro: rgb(0x69 / 255, 0x74 / 255, 0x71 / 255),      // #697471
  offWhite: rgb(0xe5 / 255, 0xe7 / 255, 0xe2 / 255),         // #E5E7E2
  cinzaClaro: rgb(0xdc / 255, 0xe0 / 255, 0xd8 / 255),       // #DCE0D8
  preto: rgb(0.1, 0.1, 0.1),
  branco: rgb(1, 1, 1),
};

const copywritersData = [
  {
    nome: 'Yan',
    ads: '12',
    cumprimento: '92%',
    crescimento: '+16,2%',
    roas: '2.34',
    faturamento: 'R$ 38.420',
    mcBr: 'R$ 18.200',
    demandas: '11/12',
    validados: '4/4',
    top5: [
      { nome: '[EM][OF02][FB][AD01]', nicho: 'Emagrecedores', fat: '8.420', roas: '2,45' },
      { nome: '[EM][OF02][FB][AD02][V1]', nicho: 'Emagrecedores', fat: '7.850', roas: '2,18' },
      { nome: '[DB][OF01][FB][AD15]', nicho: 'Diabetes', fat: '6.200', roas: '1,95' },
      { nome: '[EM][OF03][YT][AD18][V1]', nicho: 'Emagrecedores', fat: '5.100', roas: '2,34' },
      { nome: '[NE][OF02][FB][AD22][V1]', nicho: 'Neuro', fat: '4.850', roas: '1,87' },
    ],
  },
  {
    nome: 'Crispim',
    ads: '14',
    cumprimento: '100%',
    crescimento: '+8,2%',
    roas: '2.08',
    faturamento: 'R$ 42.850',
    mcBr: 'R$ 19.340',
    demandas: '14/14',
    validados: '4/5',
    top5: [
      { nome: '[PT][OF01][FB][AD09]', nicho: 'Prostata', fat: '9.200', roas: '2,15' },
      { nome: '[MM][OF01][FB][AD31][V1]', nicho: 'Musculos', fat: '8.450', roas: '1,98' },
      { nome: '[ED][OF01][GG][AD44]', nicho: 'Diabetes', fat: '7.100', roas: '1,67' },
      { nome: '[ZB][OF01][FB][AD52][V1]', nicho: 'Zona de Berlim', fat: '6.200', roas: '1,95' },
      { nome: '[NE][OF02][FB][AD18][V2]', nicho: 'Neuro', fat: '5.900', roas: '1,78' },
    ],
  },
  {
    nome: 'Cassio',
    ads: '13',
    cumprimento: '92%',
    crescimento: '+10,1%',
    roas: '2.29',
    faturamento: 'R$ 41.200',
    mcBr: 'R$ 18.600',
    demandas: '12/13',
    validados: '3/3',
    top5: [
      { nome: '[DA][OF02][FB][AD05]', nicho: 'Diabetes Av', fat: '8.900', roas: '2,34' },
      { nome: '[EM][OF02][FB][AD11][V3]', nicho: 'Emagrecedores', fat: '7.650', roas: '2,12' },
      { nome: '[MM][OF01][YT][AD35]', nicho: 'Musculos', fat: '6.400', roas: '1,92' },
      { nome: '[NE][OF03][FB][AD20][V1]', nicho: 'Neuro', fat: '5.800', roas: '2,01' },
      { nome: '[PT][OF01][FB][AD47][V2]', nicho: 'Prostata', fat: '4.900', roas: '1,85' },
    ],
  },
  {
    nome: 'Ana',
    ads: '5',
    cumprimento: '100%',
    crescimento: '+5,3%',
    roas: '1.89',
    faturamento: 'R$ 16.850',
    mcBr: 'R$ 8.040',
    demandas: '5/5',
    validados: '0/1',
    top5: [
      { nome: '[EM][OF02][FB][AD08]', nicho: 'Emagrecedores', fat: '4.200', roas: '1,68' },
      { nome: '[DB][OF01][FB][AD16][V1]', nicho: 'Diabetes', fat: '3.850', roas: '1,54' },
      { nome: '[NE][OF02][FB][AD23]', nicho: 'Neuro', fat: '3.200', roas: '1,45' },
      { nome: '[PT][OF01][FB][AD33][V1]', nicho: 'Prostata', fat: '2.800', roas: '1,32' },
      { nome: '[MM][OF01][FB][AD40]', nicho: 'Musculos', fat: '2.800', roas: '1,41' },
    ],
  },
  {
    nome: 'Elias',
    ads: '3',
    cumprimento: '67%',
    crescimento: '-8,4%',
    roas: '1.45',
    faturamento: 'R$ 6.000',
    mcBr: 'R$ 1.400',
    demandas: '2/3',
    validados: '0/0',
    top5: [
      { nome: '[EM][OF02][FB][AD03]', nicho: 'Emagrecedores', fat: '2.100', roas: '1,34' },
      { nome: '[DB][OF01][FB][AD17]', nicho: 'Diabetes', fat: '2.000', roas: '1,25' },
      { nome: '[NE][OF02][FB][AD24]', nicho: 'Neuro', fat: '1.900', roas: '1,18' },
      { nome: '-', nicho: '-', fat: '-', roas: '-' },
      { nome: '-', nicho: '-', fat: '-', roas: '-' },
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

  // Logo no canto esquerdo
  if (logoImage) {
    page.drawImage(logoImage, {
      x: 40,
      y: pageHeight - 85,
      width: 45,
      height: 45,
    });
  }

  // Título (deslocado para a direita para acomodar logo)
  page.drawText('RELATORIO SEMANAL', {
    x: 100,
    y: pageHeight - 35,
    size: 32,
    color: COLORS.verdePrimario,
  });

  page.drawText('Time de Copy  —  Semana 17-23 de Maio', {
    x: 100,
    y: pageHeight - 58,
    size: 10,
    color: COLORS.cinzaNeutro,
  });
}

function drawIdentificationSection(page, data, y) {
  const x = 40;

  page.drawText(data.nome, {
    x: x,
    y: y,
    size: 28,
    color: COLORS.verdePrimario,
  });

  return y - 28;
}

function drawKPICards(page, pageWidth, y, data) {
  const x = 40;
  const cardW = (pageWidth - 80 - 20) / 4;
  const cardH = 80;

  const kpis = [
    { label: 'Ads Escritos', value: data.ads },
    { label: 'Taxa Cumprimento', value: data.cumprimento },
    { label: 'Crescimento', value: data.crescimento },
    { label: 'ROAS Geral', value: data.roas },
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
      size: 24,
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

function drawDetailSection(page, pageWidth, y, data) {
  const x = 40;
  const col1X = x;
  const col2X = x + (pageWidth - 80) / 2 + 10;
  const colWidth = (pageWidth - 80) / 2 - 10;

  // COLUNA 1: PERFORMANCE
  page.drawRectangle({
    x: col1X,
    y: y - 140,
    width: colWidth,
    height: 140,
    color: COLORS.offWhite,
    borderColor: COLORS.cinzaClaro,
    borderWidth: 0.5,
  });

  let yPos = y - 18;
  page.drawText('PERFORMANCE', {
    x: col1X + 12,
    y: yPos,
    size: 11,
    color: COLORS.verdePrimario,
  });

  yPos -= 22;
  const perf = [
    { label: 'Faturamento', value: data.faturamento },
    { label: 'MC BR', value: data.mcBr },
    { label: 'Crescimento', value: data.crescimento },
  ];

  perf.forEach((item) => {
    page.drawText(item.label, {
      x: col1X + 12,
      y: yPos,
      size: 8,
      color: COLORS.cinzaNeutro,
    });
    page.drawText(item.value, {
      x: col1X + 12,
      y: yPos - 14,
      size: 14,
      color: COLORS.verdePrimario,
    });
    yPos -= 35;
  });

  // COLUNA 2: PRODUCAO & TESTES
  page.drawRectangle({
    x: col2X,
    y: y - 140,
    width: colWidth,
    height: 140,
    color: COLORS.offWhite,
    borderColor: COLORS.cinzaClaro,
    borderWidth: 0.5,
  });

  yPos = y - 18;
  page.drawText('PRODUCAO', {
    x: col2X + 12,
    y: yPos,
    size: 11,
    color: COLORS.verdePrimario,
  });

  yPos -= 22;
  page.drawText('Demandas', {
    x: col2X + 12,
    y: yPos,
    size: 8,
    color: COLORS.cinzaNeutro,
  });
  page.drawText(data.demandas, {
    x: col2X + 12,
    y: yPos - 14,
    size: 14,
    color: COLORS.verdePrimario,
  });

  yPos -= 35;
  page.drawText('Testes Validados', {
    x: col2X + 12,
    y: yPos,
    size: 8,
    color: COLORS.cinzaNeutro,
  });
  page.drawText(data.validados, {
    x: col2X + 12,
    y: yPos - 14,
    size: 14,
    color: COLORS.verdePrimario,
  });

  yPos -= 35;
  page.drawText('Status', {
    x: col2X + 12,
    y: yPos,
    size: 8,
    color: COLORS.cinzaNeutro,
  });
  page.drawText('Excelente', {
    x: col2X + 12,
    y: yPos - 14,
    size: 12,
    color: COLORS.verdePrimario,
  });

  return y - 160;
}

function drawTop5Table(page, pageWidth, y, data) {
  const x = 40;
  const tableWidth = pageWidth - 80;
  const rowHeight = 22;
  const colWidths = [35, 180, 90, 75, 60];

  page.drawText('TOP 5 ADS', {
    x: x,
    y: y,
    size: 11,
    color: COLORS.verdePrimario,
  });

  y -= 22;

  // Cabeçalho
  page.drawRectangle({
    x: x,
    y: y - rowHeight,
    width: tableWidth,
    height: rowHeight,
    color: COLORS.verdeEscuro,
  });

  const headers = ['Rank', 'Nome do Ad', 'Nicho', 'Faturamento', 'ROAS'];
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

  // Linhas de dados
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
    const values = [String(idx + 1), row.nome, row.nicho, 'R$ ' + row.fat, row.roas];
    values.forEach((val, i) => {
      page.drawText(val, {
        x: colX + 8,
        y: y - 16,
        size: 9,
        color: COLORS.preto,
      });
      colX += colWidths[i];
    });

    y -= rowHeight;
  });

  return y - 15;
}

function drawRecommendationCard(page, pageWidth, y) {
  const x = 40;
  const cardWidth = pageWidth - 80;

  page.drawRectangle({
    x: x,
    y: y - 70,
    width: cardWidth,
    height: 70,
    color: COLORS.verdePrimario,
  });

  page.drawText('RECOMENDACAO', {
    x: x + 15,
    y: y - 20,
    size: 12,
    color: COLORS.branco,
  });

  page.drawText('Yan mantem excelencia em assertividade. Aumentar volume em 1-2 criativos extras.', {
    x: x + 15,
    y: y - 38,
    size: 9,
    color: COLORS.branco,
  });

  page.drawText('Perfil de referencia para o time.', {
    x: x + 15,
    y: y - 52,
    size: 9,
    color: COLORS.offWhite,
  });

  return y - 85;
}

function drawLogo(page, logoPath, x, y, width = 30, height = 30) {
  // Placeholder para inserir logo PNG quando disponível
  // Será chamado como: drawLogo(page, '/path/to/logo.png', xPos, yPos)
  try {
    // const logoImage = require('fs').readFileSync(logoPath);
    // const embeddedImage = await page.doc.embedPng(logoImage);
    // page.drawImage(embeddedImage, { x, y, width, height });
  } catch (e) {
    // Logo não disponível, será adicionado depois
  }
}

async function createReport() {
  const pdfDoc = await PDFDocument.create();
  const pageWidth = 595;
  const pageHeight = 842;

  // Embed logo
  const logoPath = path.join(process.env.HOME, 'Documents', 'IMPERA LOGO.png');
  let logoImage = null;
  if (fs.existsSync(logoPath)) {
    const logoBytes = fs.readFileSync(logoPath);
    logoImage = await pdfDoc.embedPng(logoBytes);
  }

  // Gerar página para cada copywriter
  for (let i = 0; i < copywritersData.length; i++) {
    const data = copywritersData[i];
    const page = pdfDoc.addPage([pageWidth, pageHeight]);

    await drawHeader(page, pageWidth, pageHeight, logoImage);
    let yPos = pageHeight - 120;
    yPos = drawIdentificationSection(page, data, yPos);
    yPos -= 20;
    yPos = drawKPICards(page, pageWidth, yPos, data);
    yPos -= 15;
    yPos = drawDetailSection(page, pageWidth, yPos, data);
    yPos -= 20;
    yPos = drawTop5Table(page, pageWidth, yPos, data.top5);
    yPos -= 15;
    yPos = drawRecommendationCard(page, pageWidth, yPos);

    // Footer
    page.drawText('Relatorio gerado: 24 de Maio de 2026  |  Grupo Impera', {
      x: 40,
      y: 20,
      size: 8,
      color: COLORS.cinzaNeutro,
    });

    // Page break (exceto na última página)
    if (i < copywritersData.length - 1) {
      // Quebra automática ao adicionar nova página
    }
  }

  const pdfBytes = await pdfDoc.save();
  fs.writeFileSync('/Users/iagoalmeida/relatorio_copy_semanal_final.pdf', pdfBytes);
  console.log('✅ PDF criado: relatorio_copy_semanal_final.pdf (5 copywriters)');
}

createReport().catch(err => console.error('Erro:', err));
