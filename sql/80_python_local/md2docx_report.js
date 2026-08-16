/**
 * 산출물/보고서.md → 산출물/보고서.docx
 *
 * .md가 원본이고 .docx는 파생물이다. 보고서를 고칠 때는 .md만 고치고 이 스크립트를
 * 다시 돌리면 된다 (이전에는 .docx를 손으로 만들어 두 파일이 어긋나 있었다).
 *
 * 서식은 기존 보고서.docx에서 추출한 값을 그대로 재현:
 *   본문 Malgun Gothic 10.5pt(sz 21) / Title 28pt / H1 16pt·H2 13pt 파랑(2E74B5)
 *   A4(11906×16838), 여백 1인치(1440 DXA)
 *
 * 실행: node sql/80_python_local/md2docx_report.js
 */
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, AlignmentType, BorderStyle, LevelFormat, PageBreak
} = require('docx');

const ROOT = path.resolve(__dirname, '..', '..');
const SRC = path.join(ROOT, '산출물', '보고서.md');
const OUT = path.join(ROOT, '산출물', '보고서.docx');

const USABLE = 11906 - 1440 * 2;      // 본문 폭 (DXA)
const ACCENT = '2E74B5';
const MUTED  = '595959';

// ---------- 인라인 파서: **굵게**, `코드`, [텍스트](링크) ----------
function inline(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;
  let last = 0, m;
  const push = (s, extra) => { if (s) out.push(new TextRun({ text: s, ...base, ...extra })); };
  while ((m = re.exec(text)) !== null) {
    push(unesc(text.slice(last, m.index)));
    const tok = m[0];
    if (tok.startsWith('**'))      push(unesc(tok.slice(2, -2)), { bold: true });
    else if (tok.startsWith('`'))  push(unesc(tok.slice(1, -1)), { font: 'Consolas', shading: { type: ShadingType.CLEAR, fill: 'F2F2F2' } });
    else                           push(unesc(tok.replace(/\[([^\]]+)\]\([^)]+\)/, '$1')), { color: ACCENT });
    last = m.index + tok.length;
  }
  push(unesc(text.slice(last)));
  return out.length ? out : [new TextRun({ text: '', ...base })];
}
const unesc = s => s.replace(/\\\|/g, '|').replace(/\\\*/g, '*').replace(/\\_/g, '_');

// 이스케이프되지 않은 | 로 분리
function splitRow(line) {
  return line.replace(/^\s*\|/, '').replace(/\|\s*$/, '')
    .split(/(?<!\\)\|/).map(c => c.trim());
}

// ---------- 표 ----------
function makeTable(rows) {
  const nCol = Math.max(...rows.map(r => r.length));
  const norm = rows.map(r => { const c = r.slice(); while (c.length < nCol) c.push(''); return c; });

  // 열 폭: 내용 길이에 비례 (최소 8%)
  const raw = Array.from({ length: nCol }, (_, i) =>
    Math.max(...norm.map(r => (r[i] || '').replace(/\*\*|`/g, '').length), 4));
  const floor = 0.08, sum = raw.reduce((a, b) => a + b, 0);
  let share = raw.map(v => Math.max(v / sum, floor));
  const s2 = share.reduce((a, b) => a + b, 0);
  const widths = share.map(v => Math.round(USABLE * v / s2));
  widths[nCol - 1] += USABLE - widths.reduce((a, b) => a + b, 0);   // 합계 보정

  const cell = (txt, isHead, w) => new TableCell({
    width: { size: w, type: WidthType.DXA },
    shading: isHead ? { type: ShadingType.CLEAR, fill: 'DEEAF6' } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({
      spacing: { before: 20, after: 20 },
      children: inline(txt, isHead ? { bold: true, size: 19 } : { size: 19 })
    })]
  });

  return new Table({
    columnWidths: widths,
    width: { size: USABLE, type: WidthType.DXA },
    rows: norm.map((r, i) => new TableRow({
      tableHeader: i === 0,
      children: r.map((c, j) => cell(c, i === 0, widths[j]))
    }))
  });
}

// ---------- 본문 파싱 ----------
const lines = fs.readFileSync(SRC, 'utf8').split(/\r?\n/);
const kids = [];
let i = 0, frontDone = false;

const para = (opts) => kids.push(new Paragraph(opts));

while (i < lines.length) {
  const line = lines[i];
  const t = line.trim();

  // 빈 줄 / 수평선
  if (!t || /^-{3,}$/.test(t)) { i++; continue; }

  // 표
  if (t.startsWith('|')) {
    const rows = [];
    while (i < lines.length && lines[i].trim().startsWith('|')) {
      const r = lines[i].trim();
      if (!/^\|[\s:|-]+\|$/.test(r)) rows.push(splitRow(r));   // 구분행 제외
      i++;
    }
    if (rows.length) { kids.push(makeTable(rows)); para({ spacing: { after: 160 } }); }
    continue;
  }

  // 코드 펜스
  if (t.startsWith('```')) {
    i++;
    const code = [];
    while (i < lines.length && !lines[i].trim().startsWith('```')) code.push(lines[i]), i++;
    i++;
    code.forEach(c => para({
      spacing: { before: 20, after: 20 },
      shading: { type: ShadingType.CLEAR, fill: 'F5F5F5' },
      indent: { left: 240 },
      children: [new TextRun({ text: c || ' ', font: 'Consolas', size: 18 })]
    }));
    para({ spacing: { after: 120 } });
    continue;
  }

  // 제목
  const h = t.match(/^(#{1,4})\s+(.*)$/);
  if (h) {
    const lvl = h[1].length, txt = h[2];
    if (lvl === 1) {
      para({ heading: HeadingLevel.TITLE, spacing: { after: 80 }, children: inline(txt) });
    } else if (lvl === 3 && !frontDone) {
      // 표지 부제 (본문 ### 소제목과 구분)
      para({ spacing: { after: 60 }, children: inline(txt, { size: 24, color: MUTED }) });
    } else {
      para({
        heading: lvl === 2 ? HeadingLevel.HEADING_1 : lvl === 3 ? HeadingLevel.HEADING_2 : HeadingLevel.HEADING_3,
        spacing: { before: 240, after: 100 }, children: inline(txt)
      });
      frontDone = true;
    }
    i++; continue;
  }

  // 인용 (표지 메타 블록)
  if (t.startsWith('>')) {
    const meta = [];
    while (i < lines.length && lines[i].trim().startsWith('>')) { meta.push(lines[i].trim().replace(/^>\s?/, '')); i++; }
    para({
      spacing: { after: 200 },
      border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: 'BFBFBF', space: 6 } },
      children: inline(meta.filter(Boolean).join('  |  '), { size: 19, color: MUTED })
    });
    continue;
  }

  // 목록
  const ol = t.match(/^(\d+)\.\s+(.*)$/);
  const ul = t.match(/^[-*]\s+(.*)$/);
  if (ol || ul) {
    para({
      numbering: { reference: ol ? 'ol' : 'ul', level: 0 },
      spacing: { before: 40, after: 40 },
      children: inline(ol ? ol[2] : ul[1])
    });
    i++; continue;
  }

  // 일반 문단
  para({ spacing: { before: 60, after: 60 }, children: inline(t) });
  i++;
}

// ---------- 문서 ----------
const doc = new Document({
  creator: 'YBIGTA DA 26-2',
  title: '판촉의 인과 효과와 마진 누수 진단',
  description: 'dunnhumby The Complete Journey — 이탈 방지 및 마케팅 효율 최적화 전략',
  styles: {
    default: {
      document: { run: { font: 'Malgun Gothic', size: 21 } },
      title:     { run: { size: 56, bold: true } },
      heading1:  { run: { size: 32, bold: true, color: ACCENT }, paragraph: { spacing: { before: 240, after: 100 } } },
      heading2:  { run: { size: 26, bold: true, color: ACCENT }, paragraph: { spacing: { before: 200, after: 80 } } },
      heading3:  { run: { size: 23, bold: true, color: ACCENT } }
    }
  },
  numbering: {
    config: [
      { reference: 'ul', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 420, hanging: 220 } } } }] },
      { reference: 'ol', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 420, hanging: 220 } } } }] }
    ]
  },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    children: kids
  }]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  console.log(`OK  ${OUT}  (${buf.length.toLocaleString()} bytes, ${kids.length} blocks)`);
});
