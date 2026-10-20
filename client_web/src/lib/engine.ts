// محرك التحقق الدستوري — لا يولّد هندسة، بل يتحقق من المدخلات ويمنع اختراع الأبعاد.
export type Severity = "error" | "warning" | "info";
export interface Check { code: string; severity: Severity; message: string }
export interface Site { location?: string; width_m?: number | undefined; depth_m?: number | undefined; north?: string; streets?: string[]; setbacks?: Record<string, number> | undefined; setback_notes?: string; setback_source?: string }
export interface Room { name: string; room_type: string; quantity: number; width_m?: number | null | undefined; length_m?: number | null | undefined; privacy: string; light_shaft?: boolean; light_shaft_justification?: string; redistribution_failed?: boolean; engineer_approved?: boolean }

const NEEDS_DAYLIGHT = ["bedroom", "kitchen", "bathroom"];

export function validateProject(site: Site, rooms: Room[]): Check[] {
  const c: Check[] = [];
  if (!site.location) c.push({ code: "SITE_LOCATION", severity: "error", message: "الموقع غير محدد" });
  for (const k of ["width_m", "depth_m"] as const) {
    const v = site[k];
    if (v == null) c.push({ code: `SITE_${k}`, severity: "error", message: "أبعاد الأرض غير مزودة — لن تُفترض أي قيمة" });
    else if (!Number.isFinite(v) || !(v > 0)) c.push({ code: `SITE_${k}_INVALID`, severity: "error", message: "بُعد الأرض يجب أن يكون رقمًا موجبًا ومحدودًا" });
  }
  if (!site.north) c.push({ code: "SITE_NORTH", severity: "error", message: "اتجاه الشمال مطلوب" });
  if (!site.setbacks && !site.setback_notes?.trim()) c.push({ code: "SETBACKS_NONE", severity: "info", message: "لم تُزوَّد ارتدادات — لن يتم اختراع اشتراطات" });
  else if (!site.setback_source?.trim()) c.push({ code: "SETBACK_SOURCE", severity: "error", message: "مصدر الارتدادات والاشتراطات مطلوب" });
  if (rooms.length === 0) c.push({ code: "PROGRAM_EMPTY", severity: "error", message: "البرنامج المعماري فارغ" });
  for (const r of rooms) {
    if (!(Number.isInteger(r.quantity) && r.quantity >= 1)) c.push({ code: "ROOM_QTY", severity: "error", message: `عدد «${r.name}» غير صالح` });
    if (r.width_m == null || r.length_m == null) c.push({ code: "ROOM_DIM_MISSING", severity: "warning", message: `أبعاد «${r.name}» غير محددة — تبقى غير محددة حتى يحددها المهندس` });
    else if (!Number.isFinite(r.width_m) || !Number.isFinite(r.length_m) || r.width_m <= 0 || r.length_m <= 0) c.push({ code: "ROOM_DIM_INVALID", severity: "error", message: `أبعاد «${r.name}» غير صالحة` });
    if (NEEDS_DAYLIGHT.includes(r.room_type)) {
      c.push({ code: "DAYLIGHT_REQUIRED", severity: "info", message: `«${r.name}» يتطلب نافذة مباشرة على واجهة خارجية` });
      c.push({ code: "VENTILATION_REQUIRED", severity: "info", message: `«${r.name}» يتطلب تهوية طبيعية مباشرة على واجهة خارجية` });
      if (r.light_shaft && !r.light_shaft_justification)
        c.push({ code: "LIGHT_SHAFT_UNJUSTIFIED", severity: "error", message: `المنور في «${r.name}» مرفوض دون تعليل وموافقة المهندس بعد فشل بدائل إعادة التوزيع` });
      if (r.light_shaft && (!r.redistribution_failed || !r.engineer_approved))
        c.push({ code: "LIGHT_SHAFT_APPROVAL", severity: "error", message: `المنور في «${r.name}» يحتاج توثيق فشل إعادة التوزيع وموافقة المهندس` });
    }
  }
  return c;
}
export const canSubmit = (checks: Check[]) => !checks.some((x) => x.severity === "error");
