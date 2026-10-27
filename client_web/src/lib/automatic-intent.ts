import {z} from 'zod';
import type {SiteEvidence} from './plot-intake';
import type {Country} from './locations';
export type Edge='top'|'right'|'bottom'|'left';
export interface ArchitectIntent {
 width:number;depth:number;country:Country;region:string;city:string;district:string;neighborhood:string;investment_units:number;investment_unit_area:number;north_edge:Edge;street_edges:Edge[];main_street:Edge;street_widths:Partial<Record<Edge,number>>;
 family:number;building:'villa'|'house'|'investment';output_level:'economy'|'standard'|'luxury';design_priority:'efficiency'|'usability'|'prestige';floors:'auto'|'one'|'two';comfort:'compact'|'balanced'|'generous';majlis:boolean;office:boolean;accessible_bedroom:boolean;notes:string;
 site_evidence?:SiteEvidence;
}
export interface AutomaticDraft {mode:'automatic';intent:ArchitectIntent;generator?:'legacy'|'intelligence'|'gemini';remoteConsent?:boolean}

const edge=z.enum(['top','right','bottom','left']);
export const automaticIntentSchema=z.object({
 width:z.number().finite().min(0).max(60),depth:z.number().finite().min(0).max(80),country:z.enum(['SA','YE']).default('SA'),region:z.string().max(100).default(''),district:z.string().max(100).default(''),neighborhood:z.string().max(100).default(''),investment_units:z.number().int().min(2).max(40).default(4),investment_unit_area:z.number().finite().min(30).max(400).default(100),city:z.string().max(100),north_edge:edge,
 street_edges:z.array(edge).max(4),main_street:edge,street_widths:z.record(z.number().finite().min(0).max(100)),
 family:z.number().finite().int().min(0).max(12),building:z.enum(['villa','house','investment']),output_level:z.enum(['economy','standard','luxury']).default('standard'),design_priority:z.enum(['efficiency','usability','prestige']).default('usability'),floors:z.enum(['auto','one','two']),comfort:z.enum(['compact','balanced','generous']),majlis:z.boolean(),office:z.boolean(),accessible_bedroom:z.boolean(),notes:z.string().max(1500),
 site_evidence:z.object({source:z.enum(['scaled_image','gps_corners']),area_m2:z.number().finite().positive(),point_count:z.literal(4),review_required:z.literal(true)}).optional()
});
