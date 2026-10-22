const fs=require('fs'),path=require('path'),zlib=require('zlib');
const E=require('../src/engine.js');
const inflate=async d=>zlib.inflateRawSync(Buffer.from(d));
(async()=>{
 const dir=path.join(__dirname,'odt'); const res=[];
 for(const f of fs.readdirSync(dir).sort()) res.push(await E.extractOdt(new Uint8Array(fs.readFileSync(path.join(dir,f))),f,inflate));
 E.markDuplicates(res);
 const rows=res.flatMap(r=>r.rows);
 console.log('docs',res.length,'rows',rows.length,'warn rows',rows.filter(r=>r.확인필요).length);
 console.log('raw table sample:',JSON.stringify(res.find(r=>r.doc.파일명.includes('8-10-1')).tables[0].raw).slice(0,300));
 const miss=E.missingStdPairs(res); console.log('missing pairs',miss.length, miss.slice(0,6));
 const tbl=E.parseStdTable([['지역구분','항목','기준값','단위'],['청정','BOD','10','mg/L'],['나','TOC','40',''],['하수처리구역내','BOD','20',''],['*','생태독성','2','TU'],['가','SS','30','']]);
 const n=E.applyStdTable(res,tbl); console.log('filled',n);
 for(const k of ['8-10-1-1','8-10-1-2','남양주-진접-10-1','2-9-405','2-10-411','4-10-1','7-10-2']) { const r=rows.find(x=>x.시료번호===k); console.log(k,'|',r.지역구분,'|',r.기준,'|',r.기준출처); }
 // xlsx round trip
 const X=require('../src/xlsx.js');
 const b=X.buildXlsx([{name:'기준표',columns:[{header:'지역구분'},{header:'항목'},{header:'기준값'}],rows:[['청정','BOD','10'],['나','T-P','2']]}]);
 console.log('xlsx read', JSON.stringify(await E.readXlsxRows(b,inflate)));
 console.log('csv', JSON.stringify(E.parseCsv('지역구분,항목,기준값\r\n"청정",BOD,10\r\n')));
 console.log('euc-kr', E.decodeText(new Uint8Array([0xc3,0xbb,0xc1,0xa4])));
})();
