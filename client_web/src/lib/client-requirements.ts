import { z } from 'zod';
import { validateProject, type Room } from './engine';

export const wizardSteps = ['الأرض', 'الأسرة', 'الضيافة والخصوصية', 'الفراغات', 'المراجعة'];
export const baseRooms = [
  { key: 'bedroom', name: 'غرف نوم', type: 'bedroom' },
  { key: 'bathroom', name: 'حمامات', type: 'bathroom' },
  { key: 'kitchen', name: 'مطبخ', type: 'kitchen' },
  { key: 'dining', name: 'طعام', type: 'other' },
  { key: 'living', name: 'معيشة', type: 'living' },
  { key: 'services', name: 'خدمات', type: 'other' },
];
const stringFields = z.object({ title: z.string(), type: z.string(), location: z.string(), width: z.string(), depth: z.string(), north: z.string(), frontage: z.string(), streets: z.string(), boundaries: z.string(), floors: z.string(), setbacks: z.string(), source: z.string(), family: z.string(), housing: z.string() });
const roomSchema = z.object({ name: z.string(), room_type: z.string(), quantity: z.number(), width_m: z.number().nullable().optional(), length_m: z.number().nullable().optional(), privacy: z.string() }).passthrough();
const importedSchema = z.object({ fields: z.array(z.object({ sheet: z.string(), row: z.number(), number: z.string(), field: z.string(), value: z.string(), guidance: z.string() })), warnings: z.array(z.string()) });
export const draftSchema = z.object({
  data: stringFields,
  unknown: z.record(z.string(), z.boolean()),
  hospitality: z.object({ majlis: z.boolean(), menEntrance: z.boolean(), guestLobby: z.boolean(), familyEntrance: z.boolean() }),
  counts: z.record(z.string(), z.number().int().min(0)),
  rooms: z.array(roomSchema),
  imported: importedSchema.optional(),
  step: z.number().int().min(0).max(4),
});
export type ClientDraft = z.infer<typeof draftSchema>;
export type DataKey = keyof ClientDraft['data'];
export function newClientDraft(): ClientDraft {
  return { data: { title: '', type: 'سكني', location: '', width: '', depth: '', north: '', frontage: '', streets: '', boundaries: '', floors: '', setbacks: '', source: '', family: '', housing: '' }, unknown: {}, hospitality: { majlis: false, menEntrance: false, guestLobby: false, familyEntrance: false }, counts: Object.fromEntries(baseRooms.map(room => [room.key, 0])), rooms: [], step: 0 };
}
export const draftKey = 'ant-engineer:temporary-client-draft:v1';
export const draftLifetime = 12 * 60 * 60 * 1000;
export function decodeDraft(raw: string | null, now: number): ClientDraft | undefined {
  if (!raw) return;
  try {
    const envelope = z.object({ savedAt: z.number(), draft: draftSchema }).parse(JSON.parse(raw));
    if (envelope.savedAt > now || now - envelope.savedAt >= draftLifetime) return;
    return envelope.draft;
  } catch { return; }
}
export function supplied(draft: ClientDraft, key: DataKey): string { return draft.unknown[key] ? '' : draft.data[key].trim(); }
export function displayValue(draft: ClientDraft, key: DataKey): string { return draft.unknown[key] ? 'لا أعرف' : draft.data[key] || 'غير مزود'; }
export function programRooms(draft: ClientDraft): Room[] {
  const rooms: Room[] = baseRooms.filter(room => (draft.counts[room.key] ?? 0) > 0).map(room => ({ name: room.name, room_type: room.type, quantity: draft.counts[room.key] ?? 0, privacy: room.key === 'bedroom' ? 'private' : 'semi' }));
  if (draft.hospitality.majlis) rooms.push({ name: 'مجلس رجال', room_type: 'living', quantity: 1, privacy: 'public' });
  if (draft.hospitality.guestLobby) rooms.push({ name: 'حمام ضيوف', room_type: 'bathroom', quantity: 1, privacy: 'public' });
  return [...rooms, ...draft.rooms];
}
export function stepErrors(draft: ClientDraft, step: number): Record<string, string> {
  const errors: Record<string, string> = {};
  if (step === 0) {
    for (const key of ['width', 'depth'] as const) {
      const value = supplied(draft, key);
      if (!draft.unknown[key] && (!value || !Number.isFinite(Number(value)) || Number(value) <= 0)) errors[key] = 'أدخل بُعدًا موجبًا بالمتر أو اختر «لا أعرف».';
    }
    for (const key of ['location', 'frontage', 'north'] as const) if (!draft.unknown[key] && !supplied(draft, key)) errors[key] = 'أدخل المعلومة أو اختر «لا أعرف».';
    if (supplied(draft, 'setbacks') && !supplied(draft, 'source')) errors['source'] = 'اذكر مصدر الارتدادات؛ لن نفترض اشتراطات.';
  }
  if (step === 1) {
    if (!draft.data.title.trim()) errors['title'] = 'أدخل اسم المشروع.';
    for (const key of ['family', 'floors'] as const) if (!draft.data[key] || !Number.isInteger(Number(draft.data[key])) || Number(draft.data[key]) < 1) errors[key] = 'أدخل عددًا صحيحًا موجبًا.';
    if (!draft.data.housing) errors['housing'] = 'اختر نوع المسكن.';
  }
  if (step === 2) {
    if ((draft.hospitality.menEntrance || draft.hospitality.guestLobby) && !draft.hospitality.majlis) errors['majlis'] = 'حدد مجلس الرجال أو ألغِ متطلبات الضيوف المرتبطة به.';
  }
  if (step === 3) {
    if (!programRooms(draft).length) errors['program'] = 'حدد فراغًا واحدًا على الأقل.';
    draft.rooms.forEach((room, i) => {
      if (!room.name.trim()) errors[`room-${i}-name`] = 'أدخل اسم الغرفة.';
      if (!Number.isInteger(room.quantity) || room.quantity < 1) errors[`room-${i}-quantity`] = 'العدد يجب أن يكون صحيحًا موجبًا.';
      for (const key of ['width_m', 'length_m'] as const) if (room[key] != null && (!Number.isFinite(room[key]) || Number(room[key]) <= 0)) errors[`room-${i}-${key}`] = 'أدخل بُعدًا موجبًا أو اتركه فارغًا.';
    });
  }
  return errors;
}
export function engineeringChecks(draft: ClientDraft) {
  const number = (key: DataKey) => supplied(draft, key) ? Number(supplied(draft, key)) : undefined;
  return validateProject({ location: supplied(draft, 'location'), width_m: number('width'), depth_m: number('depth'), north: supplied(draft, 'north'), setback_notes: supplied(draft, 'setbacks'), setback_source: supplied(draft, 'source') }, programRooms(draft));
}
