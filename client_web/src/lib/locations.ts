/** Lists for assisted typing only, not proof of legal jurisdiction.
 * Saudi Arabia: 13 regions; Yemen: 21 governorates + capital municipality.
 */
export type Country='SA'|'YE';
export const countryNames:Record<Country,string>={SA:'المملكة العربية السعودية',YE:'الجمهورية اليمنية'};
export const saudiRegions=['الرياض','مكة المكرمة','المدينة المنورة','القصيم','المنطقة الشرقية','عسير','حائل','تبوك','الباحة','الحدود الشمالية','الجوف','جازان','نجران'] as const;
export const yemeniGovernorates=['أمانة العاصمة','صنعاء','عدن','تعز','إب','الحديدة','ذمار','البيضاء','حجة','المحويت','عمران','صعدة','الجوف','مأرب','شبوة','حضرموت','المهرة','أرخبيل سقطرى','أبين','لحج','الضالع','ريمة'] as const;
export const regionsFor=(country:Country):readonly string[]=>country==='SA'?saudiRegions:yemeniGovernorates;
export const priorities={efficiency:'الاقتصاد في استغلال المساحة وتقليل الهدر',usability:'سهولة الاستخدام ووضوح الحركة',prestige:'الفخامة والرحابة وجودة التكوين المعماري'} as const;
export const outputLevels={economy:'اقتصادي',standard:'متوسط',luxury:'فاخر'} as const;
export const buildingTypes={villa:'فيلا',house:'سكني خاص',investment:'مبنى سكني استثماري'} as const;
