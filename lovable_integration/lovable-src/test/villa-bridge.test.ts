import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { newClientDraft, type ClientDraft } from '@/lib/client-requirements';

type Brief = { plot_width: number | ''; plot_depth: number | ''; floors: number | ''; setbacks: Record<string, number | ''>; rooms: { floor: number | ''; min_area: number | ''; min_side: number | ''; capacity: number | ''; count: number; kind: string }[]; notes: string };
const sandbox = { module: { exports: {} as { convert: (draft: ClientDraft) => { brief: Brief; warnings: string[] } } } };
runInNewContext(readFileSync('public/villa-engine/generate/client-bridge.js', 'utf8'), sandbox);
const convert = sandbox.module.exports.convert;

describe('actual bundled client conversion', () => {
  it('leaves missing plot dimensions, room floors, setbacks and sleeping capacity blank', () => {
    const draft = newClientDraft(); draft.counts['bedroom'] = 3;
    const { brief } = convert(draft);
    expect([brief.plot_width, brief.plot_depth, brief.floors]).toEqual(['', '', '']);
    expect(brief.setbacks).toEqual({ north: '', south: '', east: '', west: '' });
    expect(brief.rooms[0]).toMatchObject({ count: 3, floor: '', min_area: '', min_side: '', capacity: '' });
  });
  it('ignores previously entered dimensions marked unknown', () => {
    const draft = newClientDraft(); draft.data.width = '20'; draft.unknown['width'] = true;
    expect(convert(draft).brief.plot_width).toBe('');
  });
  it('preserves original Excel fields and explicitly flags requirements needing review', () => {
    const draft = newClientDraft();
    draft.imported = { fields: [{ sheet: 'فيلا', row: 2, number: '1', field: 'مطلب خاص', value: 'مكتبة', guidance: 'راجع' }], warnings: [] };
    const original = JSON.stringify(draft);
    const result = convert(draft);
    expect(JSON.stringify(draft)).toBe(original);
    expect(result.brief.notes).toContain('1 حقلًا');
    expect(result.warnings.some(warning => warning.includes('غير المحولة'))).toBe(true);
  });
  it('keeps guest bathroom separate from family bathrooms', () => {
    const draft = newClientDraft(); draft.counts['bathroom'] = 2;
    draft.hospitality.majlis = true; draft.hospitality.guestLobby = true;
    expect(convert(draft).brief.rooms.map(room => [room.kind, room.count])).toEqual([['bathroom', 2], ['majlis', 1], ['bathroom', 1]]);
  });
  it('rejects unsupported housing, commercial use and more than two floors instead of changing them', () => {
    for (const [key, value] of [['housing', 'شقة'], ['type', 'تجاري'], ['floors', '3']] as const) {
      const draft = newClientDraft(); draft.data[key] = value;
      expect(() => convert(draft)).toThrow();
      expect(draft.data[key]).toBe(value);
    }
  });
  it('converts supplied room dimensions into stated minimums without assigning a floor or unknown type', () => {
    const draft = newClientDraft();
    draft.rooms = [{ name: 'مكتبة', room_type: 'other', quantity: 1, width_m: 4, length_m: 5, privacy: 'private' }];
    const result = convert(draft);
    expect(result.brief.rooms[0]).toMatchObject({ min_area: 20, min_side: 4, floor: '', kind: '' });
    expect(result.warnings.some(warning => warning.includes('حد أدنى'))).toBe(true);
    expect(result.warnings.some(warning => warning.includes('التصنيف الهندسي'))).toBe(true);
  });
});
