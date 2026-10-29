const fs=require('fs'),zlib=require('zlib');const E2=require('../src/engine2.js'),E=require('../src/engine.js');
const inf=b=>zlib.inflateRawSync(b);
(async()=>{for(const f of process.argv.slice(2)){const h=await E2.parseHwpx(fs.readFileSync(f),inf);
console.log('==',f.split('/').pop(),'grids',h.grids.length,'paras',h.paras.length,'preview',h.preview&&h.preview.length);
h.paras.slice(0,8).forEach(p=>console.log('  P:',p));
for(const g of h.grids){for(let r=0;r<g.nrows;r++)console.log('  ',r,E._internal.rowOrigins(g,r).map(o=>o.text.replace(/\n/g,'/')).join(' | '));}}})();
