import { unzipSync, strFromU8 } from 'fflate';

export interface ImportedField { sheet: string; row: number; number: string; field: string; value: string; guidance: string }
export interface ExcelImport { fields: ImportedField[]; warnings: string[] }

const normalize = (text: string) => text.replace(/[\u064B-\u065F\u0670\u200E\u200F\uFEFF]/g, '').replace(/[أإآ]/g, 'ا').replace(/\s+/g, ' ').trim();
const descendants = (node: Document | Element, name: string) => Array.from(node.getElementsByTagNameNS('*', name));
function xml(bytes: Uint8Array | undefined, name: string): Document {
  if (!bytes) throw new Error(`الملف يفتقد جزء Excel المطلوب: ${name}.`);
  const source = strFromU8(bytes);
  if (/<!DOCTYPE|<!ENTITY/i.test(source)) throw new Error('يحتوي الملف على تعريفات XML غير مسموحة.');
  const document = new DOMParser().parseFromString(source, 'application/xml');
  if (descendants(document, 'parsererror').length) throw new Error(`تعذر قراءة XML في ${name}. قد يكون الملف تالفًا.`);
  return document;
}
function text(node: Element | undefined): string {
  return node ? descendants(node, 't').map(t => t.textContent ?? '').join('') : '';
}
function column(reference: string): number | undefined {
  const letters = reference.match(/^[A-Z]+/i)?.[0];
  if (!letters) return undefined;
  let index = 0;
  for (const letter of letters.toUpperCase()) index = index * 26 + letter.charCodeAt(0) - 64;
  return index - 1;
}

export function parseFieldRows(rows: string[][], sheet: string): ExcelImport {
  const fields: ImportedField[] = [];
  const warnings: string[] = [];
  let header = -1;
  let fieldIndex = -1, valueIndex = -1, numberIndex = -1, guidanceIndex = -1;
  for (let i = 0; i < rows.length; i++) {
    const names = (rows[i] ?? []).map(normalize);
    if (names.includes('الحقل') && names.includes('القيمة')) {
      header = i;
      fieldIndex = names.indexOf('الحقل'); valueIndex = names.indexOf('القيمة');
      numberIndex = names.indexOf('الرقم'); guidanceIndex = names.indexOf('ارشادات');
      break;
    }
  }
  if (header < 0) return { fields, warnings: [`الورقة «${sheet}» لا تحتوي عمودي «الحقل» و«القيمة»؛ لم تُستورد.`] };
  for (let i = header + 1; i < rows.length; i++) {
    const row = rows[i] ?? [];
    if (!row.some(cell => cell?.trim())) continue;
    const field = row[fieldIndex]?.trim() ?? '';
    if (!field) { warnings.push(`الورقة «${sheet}»، الصف ${i + 1}: قيمة بلا اسم حقل؛ راجع الملف.`); continue; }
    if (normalize(field) === 'الحقل' && normalize(row[valueIndex] ?? '') === 'القيمة') continue;
    fields.push({ sheet, row: i + 1, field, value: row[valueIndex] ?? '', number: numberIndex < 0 ? '' : row[numberIndex] ?? '', guidance: guidanceIndex < 0 ? '' : row[guidanceIndex] ?? '' });
  }
  return { fields, warnings };
}

export function parseXlsx(buffer: ArrayBuffer): ExcelImport {
  let entries: Record<string, Uint8Array>;
  try {
     let expandedSize = 0;
    entries = unzipSync(new Uint8Array(buffer), { filter: entry => {
      if (entry.originalSize > 20 * 1024 * 1024) throw new Error('جزء من الملف كبير جدًا للقراءة الآمنة.');
       expandedSize += entry.originalSize;
       if (expandedSize > 40 * 1024 * 1024) throw new Error('حجم الملف بعد فك الضغط يتجاوز نطاق القراءة الآمنة.');
      return /^(xl\/workbook\.xml|xl\/_rels\/workbook\.xml\.rels|xl\/sharedStrings\.xml|xl\/worksheets\/[^/]+\.xml)$/.test(entry.name);
    } });
  } catch { throw new Error('تعذر فتح ملف Excel؛ اختر ملف .xlsx سليمًا وغير مشفر، بحجم مناسب.'); }
  const workbook = xml(entries['xl/workbook.xml'], 'workbook.xml');
  const relations = xml(entries['xl/_rels/workbook.xml.rels'], 'workbook.xml.rels');
  const strings = entries['xl/sharedStrings.xml'] ? descendants(xml(entries['xl/sharedStrings.xml'], 'sharedStrings.xml'), 'si').map(text) : [];
  const targets = new Map(descendants(relations, 'Relationship').map(r => [r.getAttribute('Id') ?? '', r.getAttribute('Target') ?? '']));
  const fields: ImportedField[] = [], warnings: string[] = [];
  for (const sheet of descendants(workbook, 'sheet')) {
    const name = sheet.getAttribute('name') ?? 'ورقة غير مسماة';
    const id = Array.from(sheet.attributes).find(a => a.localName === 'id')?.value;
    const target = id ? targets.get(id) : undefined;
    if (!target) { warnings.push(`الورقة «${name}» تفتقد رابط بياناتها؛ لم تُستورد.`); continue; }
    const parts: string[] = [];
    for (const part of (target.startsWith('/') ? target.slice(1) : `xl/${target}`).split('/')) {
      if (part === '..') parts.pop(); else if (part !== '.') parts.push(part);
    }
    const path = parts.join('/');
    if (!entries[path]) { warnings.push(`الورقة «${name}» تفتقد ملف بياناتها؛ لم تُستورد.`); continue; }
    const rows: string[][] = [];
    for (const row of descendants(xml(entries[path], name), 'row')) {
      const cells: string[] = [];
      let sequential = 0;
      for (const cell of descendants(row, 'c')) {
        const index = column(cell.getAttribute('r') ?? '') ?? sequential;
        if (index > 16383) throw new Error('مرجع عمود Excel غير صالح.');
        sequential = index + 1;
        const type = cell.getAttribute('t');
        const raw = descendants(cell, 'v')[0]?.textContent ?? '';
        if (descendants(cell, 'f').length) warnings.push(`الورقة «${name}»: تم استخدام القيمة المخزنة لصيغة Excel؛ لم تُنفذ الصيغة.`);
        cells[index] = type === 'inlineStr' ? text(cell) : type === 's' ? strings[Number(raw)] ?? '' : raw;
        if (type === 'e') warnings.push(`الورقة «${name}»: تحتوي خلية على خطأ Excel (${raw}).`);
      }
      const rowNumber = Number(row.getAttribute('r'));
      const index = Number.isInteger(rowNumber) && rowNumber > 0 ? rowNumber - 1 : rows.length;
      if (index > 100000) throw new Error('عدد الصفوف يتجاوز نطاق القراءة الآمنة.');
      rows[index] = cells;
    }
    const parsed = parseFieldRows(rows, name);
    fields.push(...parsed.fields); warnings.push(...parsed.warnings);
  }
  if (!fields.length) throw new Error(`لم نجد حقولًا قابلة للاستيراد. يلزم عمودا «الحقل» و«القيمة»، مع «الرقم» أو «إرشادات». ${warnings.join(' ')}`);
  return { fields, warnings };
}

/** Preflight all XML before loading the free, locally bundled ExcelJS reader. */
export async function readExcelWorkbook(buffer: ArrayBuffer): Promise<ExcelImport> {
  const safe = parseXlsx(buffer);
  try {
    const { Workbook } = await import('exceljs');
    const workbook = new Workbook();
    await workbook.xlsx.load(buffer);
    const fields: ImportedField[] = [];
    const warnings = [...safe.warnings];
    workbook.eachSheet(worksheet => {
      const rows: string[][] = [];
      worksheet.eachRow({ includeEmpty: true }, (row, rowNumber) => {
        const values: string[] = [];
        row.eachCell({ includeEmpty: true }, (cell, columnNumber) => {
          const value = cell.value;
          values[columnNumber - 1] = value == null ? ''
            : typeof value === 'object' && 'richText' in value ? value.richText.map(part => part.text).join('')
            : typeof value === 'object' && ('formula' in value || 'sharedFormula' in value) ? String(value.result ?? '')
            : value instanceof Date ? cell.text
            : cell.text;
        });
        rows[rowNumber - 1] = values;
      });
      const parsed = parseFieldRows(rows, worksheet.name);
      fields.push(...parsed.fields);
      warnings.push(...parsed.warnings);
    });
    // Some valid prefixed XML formats are not recognized by ExcelJS. Never lose their fields.
    if (fields.length !== safe.fields.length || fields.some((field, i) => field.field !== safe.fields[i]?.field)) return safe;
    return { fields, warnings: [...new Set(warnings)] };
  } catch {
    return { ...safe, warnings: [...safe.warnings, 'قُرئ الملف بالقارئ المحلي البديل للحفاظ على الحقول؛ راجع القيم والإرشادات قبل استخدامها.'] };
  }
}

export function importSummary(fields: ImportedField[]) {
  return {
    total: fields.length,
    filled: fields.filter(field => field.value.trim()).length,
    empty: fields.filter(field => !field.value.trim()).length,
    sheets: new Set(fields.map(field => field.sheet)).size,
    requirements: fields.filter(field => /غرف|غرفة|نوم|مطبخ|حمام|مجلس|معيشة|خصوصية|تهوية|اضاءة|فراغ|متطلبات/.test(normalize(field.field))),
  };
}

const aliases: Record<string, string[]> = {
  title: ['اسم المشروع', 'اسم الفيلا'], type: ['نوع المشروع'], location: ['الموقع', 'موقع المشروع', 'موقع الارض'],
  width: ['عرض الارض (م)', 'عرض الارض بالمتر'], depth: ['عمق الارض (م)', 'طول الارض (م)', 'عمق الارض بالمتر'],
  north: ['اتجاه الشمال'], streets: ['الشوارع', 'الشوارع المحيطة'], boundaries: ['حدود الارض', 'وصف حدود الارض'],
  floors: ['عدد الادوار', 'عدد الطوابق'], setbacks: ['الارتدادات', 'الارتدادات والاشتراطات', 'الارتدادات والاشتراطات (اختياري)'], source: ['مصدر الارتدادات', 'مصدر الارتدادات والاشتراطات'],
};
export function emptyFieldUpdates(fields: ImportedField[], current: Record<string, string>): Record<string, string> {
  const updates: Record<string, string> = {};
  for (const [key, names] of Object.entries(aliases)) {
    if (current[key]?.trim()) continue;
    const matches = fields.filter(f => names.includes(normalize(f.field)) && f.value.trim());
    if (matches.length !== 1) continue;
    const value = matches[0]?.value.trim();
    if (!value) continue;
    if (['width', 'depth', 'floors'].includes(key) && (!Number.isFinite(Number(value)) || Number(value) <= 0)) continue;
    if (key === 'type' && !['سكني', 'تجاري', 'متعدد الاستخدامات', 'أخرى'].includes(value)) continue;
    updates[key] = value;
  }
  return updates;
}
