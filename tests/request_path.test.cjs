const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('../lovable_integration/request-path.js');
const base='https://example.test/client/villa-engine/generate/';
test('V4 query flags still reach the local Python operation',()=>{
 assert.equal(path('/api/v3/auto-design?constitution_v2=true&generation_v3=true&generation_v4=true',base),'/api/v3/auto-design');
});
test('same-origin absolute requests and Request-like objects use the same API route',()=>{
 assert.equal(path({url:'https://example.test/api/v3/auto-design?generation_v4=true'},base),'/api/v3/auto-design');
 assert.equal(path('/api/v3/design',base),'/api/v3/design');
});
test('external-origin paths must not be intercepted as local design requests',()=>{
 assert.equal(path('https://other.test/api/v3/auto-design?generation_v4=true',base),'https://other.test/api/v3/auto-design?generation_v4=true');
});
