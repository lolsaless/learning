// JS 엔진 결과를 JSON으로 (비교용)
const fs=require('fs'),path=require('path'),zlib=require('zlib');
const E=require(process.argv[3]||'../src/engine.js');
const inflate=async d=>zlib.inflateRawSync(Buffer.from(d));
(async()=>{ const dir=process.argv[2]; const res=[];
 for(const f of fs.readdirSync(dir).filter(f=>/\.odt$/i.test(f))) res.push(await E.extractOdt(new Uint8Array(fs.readFileSync(path.join(dir,f))),f,inflate));
 E.markDuplicates(res);
 const tbl=E.parseStdTable([['지역구분','항목','기준값'],['청정','BOD','10'],['나','TOC','40'],['하수처리구역내','BOD','20'],['*','생태독성','2'],['가','SS','30']]);
 E.applyStdTable(res,tbl);
 const out={}; for(const r of res) out[r.doc.파일명]={rows:r.rows.map(x=>{const o={};for(const c of E.COLUMNS)o[c]=x[c]??'';o._items=x._items;return o;}),tables:r.tables,body:r.doc.본문,miss:null};
 out.__miss=E.missingStdPairs(res);
 process.stdout.write(JSON.stringify(out));})();
