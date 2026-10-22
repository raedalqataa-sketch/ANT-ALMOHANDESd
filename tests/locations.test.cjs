const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const {resolve}=require('node:path');
const ts=require('../client_web/node_modules/typescript');
const code=readFileSync(resolve(__dirname,'../client_web/src/lib/locations.ts'),'utf8');
const compiled=ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}});
const exports_={};new Function('exports',compiled.outputText)(exports_);
const {regionsFor,saudiRegions,yemeniGovernorates,outputLevels,priorities,buildingTypes}=exports_;
test('Saudi regions list is 13 and has major regions',()=>{
 assert.equal(saudiRegions.length,13);assert.ok(saudiRegions.includes('الرياض'));assert.ok(saudiRegions.includes('المنطقة الشرقية'));
 assert.deepEqual(regionsFor('SA'),saudiRegions);
});
test('Yemen has 21 governorates and the capital municipality (22)',()=>{
 assert.equal(yemeniGovernorates.length,22);
 for(const n of ['أمانة العاصمة','صنعاء','إب','الحديدة','حضرموت','أرخبيل سقطرى','المهرة'])assert.ok(yemeniGovernorates.includes(n),n);
 assert.deepEqual(regionsFor('YE'),yemeniGovernorates);
});
test('three output levels, three independent goals, three residential types',()=>{
 assert.deepEqual(Object.keys(outputLevels),['economy','standard','luxury']);
 assert.deepEqual(Object.keys(priorities),['efficiency','usability','prestige']);
 assert.deepEqual(Object.keys(buildingTypes),['villa','house','investment']);
});
