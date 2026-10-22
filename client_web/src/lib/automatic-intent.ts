import {z} from 'zod';
import type {SiteEvidence} from './plot-intake';
export type Edge='top'|'right'|'bottom'|'left';
export interface ArchitectIntent {
 width:number;depth:number;city:string;north_edge:Edge;street_edges:Edge[];main_street:Edge;street_widths:Partial<Record<Edge,number>>;
 family:number;building:'villa'|'house';floors:'auto'|'one'|'two';comfort:'compact'|'balanced'|'generous';majlis:boolean;office:boolean;accessible_bedroom:boolean;notes:string;
 site_evidence?:SiteEvidence;
}
export interface AutomaticDraft {mode:'automatic';intent:ArchitectIntent}

const edge=z.enum(['top','right','bottom','left']);
export const automaticIntentSchema=z.object({
 width:z.number().finite().min(0).max(60),depth:z.number().finite().min(0).max(80),city:z.string().max(100),north_edge:edge,
 street_edges:z.array(edge).max(4),main_street:edge,street_widths:z.record(z.number().finite().min(0).max(100)),
 family:z.number().finite().int().min(0).max(12),building:z.enum(['villa','house']),floors:z.enum(['auto','one','two']),comfort:z.enum(['compact','balanced','generous']),majlis:z.boolean(),office:z.boolean(),accessible_bedroom:z.boolean(),notes:z.string().max(1500),
 site_evidence:z.object({source:z.enum(['scaled_image','gps_corners']),area_m2:z.number().finite().positive(),point_count:z.literal(4),review_required:z.literal(true)}).optional()
});
