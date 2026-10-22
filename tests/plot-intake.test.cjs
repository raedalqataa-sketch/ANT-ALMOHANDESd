const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const {resolve}=require('node:path');
const ts=require('../client_web/node_modules/typescript');

const source=readFileSync(resolve(__dirname,'../client_web/src/lib/plot-intake.ts'),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022},reportDiagnostics:true});
assert.equal(compiled.diagnostics?.length||0,0);
const m={exports:{}};
new Function('module','exports',compiled.outputText)(m,m.exports);
const {measureImageCorners,measureGeoCorners}=m.exports;

test('scales image corners using natural aspect ratio, not normalized square',()=>{
 const r=measureImageCorners([{x:.1,y:.1},{x:.5,y:.1},{x:.5,y:.6},{x:.1,y:.6}],24,2);
 assert.equal(r.width,24);
 assert.equal(r.depth,15);
 assert.equal(r.area,360);
 assert.equal(r.evidence.source,'scaled_image');
 assert.equal(r.evidence.review_required,true);
});
test('rejects crossed and perspectively distorted image corners',()=>{
 assert.throws(()=>measureImageCorners([{x:0,y:0},{x:1,y:1},{x:1,y:0},{x:0,y:1}],20),/متقاطعة|ترتيب/);
 assert.throws(()=>measureImageCorners([{x:0,y:0},{x:.5,y:0},{x:.6,y:.5},{x:.1,y:.5}],20),/قائمة|مستطيلة/);
});
test('requires a known real-world dimension for image scaling',()=>{
 assert.throws(()=>measureImageCorners([{x:0,y:0},{x:.5,y:0},{x:.5,y:.5},{x:0,y:.5}],0),/الطول الحقيقي/);
});
test('derives 20m by 30m north-aligned rectangle from GPS surveyed corners',()=>{
 const radius=6371008.8,lat=15,lon=44,rad=Math.PI/180;
 const dLat=30/(radius*rad),dLon=20/(radius*Math.cos(lat*rad)*rad);
 const result=measureGeoCorners([
  {lat:lat+dLat,lon},{lat:lat+dLat,lon:lon+dLon},
  {lat,lon:lon+dLon},{lat,lon}
 ]);
 assert.ok(Math.abs(result.width-20)<.08);
 assert.ok(Math.abs(result.depth-30)<.08);
 assert.equal(result.north_edge,'top');
 assert.equal(result.evidence.source,'gps_corners');
});
test('rejects invented bounds from a single point or invalid latitude',()=>{
 assert.throws(()=>measureGeoCorners([{lat:15,lon:44}]),/أركان|نقاط/);
 assert.throws(()=>measureGeoCorners([{lat:99,lon:44},{lat:15,lon:44},{lat:15,lon:44},{lat:15,lon:44}]),/إحداثيات/);
});
test('does not silently flatten a rotated parcel into the cardinal-only engine',()=>{
 const center={lat:15,lon:44},rad=Math.PI/180,radius=6371008.8;
 const rotation=20*rad;
 const base=[[-10,-15],[10,-15],[10,15],[-10,15]];
 const points=base.map(([x,y])=>{
  const east=x*Math.cos(rotation)-y*Math.sin(rotation);
  const south=x*Math.sin(rotation)+y*Math.cos(rotation);
  return {lat:center.lat-south/(radius*rad),lon:center.lon+east/(radius*Math.cos(center.lat*rad)*rad)};
 });
 assert.throws(()=>measureGeoCorners(points),/مائلة/);
});
