const assert=require('assert/strict'),{auditRoute}=require('./route_geometry.cjs');
const a={x:0,y:0,w:100,h:60},b={x:200,y:100,w:100,h:60};
const check=points=>auditRoute({id:'test',points},a,b);
assert.deepEqual(check([[100,30],[150,30],[150,130],[200,130]]),[]);
assert(check([[100,30],[200,30],[200,100],[250,100]]).some(i=>i.code==='tangent'));
assert(check([[100,30],[250,30],[250,99],[250,100]]).length===0); // Collinear points are harmless.
assert(check([[100,30],[150,30],[150,99],[250,99],[250,100]]).some(i=>i.code==='lead'));
assert(check([[100,30],[150,30],[150,50],[250,50],[250,80]]).some(i=>i.code==='endpoint'));
const stairs=[[100,30]];for(let i=1;i<=8;i++){stairs.push([100+i*10,stairs.at(-1)[1]],[100+i*10,30+i*10])}stairs.push([180,130],[200,130]);
assert(check(stairs).some(i=>i.code==='bends'));
assert(check([[100,30],[150,31],[150,130],[200,130]]).some(i=>i.code==='diagonal'));
assert.deepEqual(auditRoute({id:'bus',points:[[100,30],[150,30],[150,130],[200,130]],renderPoints:[[100,30],[150,30]],arrow:false},a,b),[]);
console.log('route geometry: 8 positive/negative fixtures passed');
