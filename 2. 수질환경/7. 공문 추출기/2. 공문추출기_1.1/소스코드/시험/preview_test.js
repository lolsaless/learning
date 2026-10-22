const fs=require('fs'),path=require('path'),zlib=require('zlib');
const E=require('../src/engine.js');
const inflate=async d=>zlib.inflateRawSync(Buffer.from(d));
(async()=>{
  const dir=path.join(__dirname,'odt'); const out=path.join(__dirname,'preview'); fs.mkdirSync(out,{recursive:true});
  let n=0;
  for(const f of fs.readdirSync(dir)){ const b=new Uint8Array(fs.readFileSync(path.join(dir,f)));
    const r=await E.renderOdtHtml(b,inflate); n++;
    fs.writeFileSync(path.join(out,f+'.html'),`<!doctype html><meta charset=utf-8><style>body{background:#888;margin:0;padding:20px}${r.css}</style>${r.html}`);
  }
  console.log('rendered',n);
  const nw=fs.readdirSync(dir).find(f=>f.includes('동두천'));
  const r=await E.extractOdt(new Uint8Array(fs.readFileSync(path.join(dir,nw))),nw,inflate);
  console.log(r.warnings, r.rows.map(x=>[x.시료번호,x.검사항목,x.지역구분,x.시료채취일,x['업종/성상'],x.기타]));
  for (const t of ['BOD(20이하)','SS(20 이하)','BOD (20㎎/L 이하)','T-P(0.5미만)','BOD(기준 20)','pH(5.8~8.6)','대장균군(3,000개/mL)','BOD 20이하','SS: 20','n-H(광)(5)','n-H(광)','6가크롬','BOD5','TOC(≤25)'])
    console.log(t,'→',JSON.stringify(E.parseItems(t).items.map(i=>[i.name,i.std,i.known])));
})();
