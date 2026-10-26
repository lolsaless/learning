// 실제 의뢰공문 38건 ↔ 시행공문 ↔ 성적서 대조
const fs=require('fs'),path=require('path'),zlib=require('zlib');
const E=require('../src/engine.js'),E2=require('../src/engine2.js');
const inf=b=>zlib.inflateRawSync(b);const U='/mnt/user-data/uploads';
(async()=>{
 const reqDir=fs.readdirSync(U).map(d=>path.join(U,d)).find(d=>d.normalize('NFC').endsWith('ODT 파일'));
 const reps=JSON.parse(fs.readFileSync('/tmp/claude-0/-home-claude/81a86257-f3c2-5b6c-91e1-a77386e01165/scratchpad/reports.json'));
 const rp=U+'/Claude/성적서 및 시행 공문';const replies=[];
 for(const f of fs.readdirSync(rp).filter(f=>f.endsWith('.odt')))replies.push(E2.parseReply(await E.extractOdt(fs.readFileSync(path.join(rp,f)),f,inf)));
 let full=0,part=0,none=0;const usedR=new Set(),usedP=new Set();
 for(const f of fs.readdirSync(reqDir).filter(f=>f.endsWith('.odt')).sort()){
  const r=await E.extractOdt(fs.readFileSync(path.join(reqDir,f)),f,inf);const nos=r.rows.map(x=>x.시료번호).filter(Boolean);
  const rr=replies.filter(x=>E2.matchReply(r.doc,x)>0);rr.forEach(x=>usedR.add(x.파일명));
  const mm=reps.map(p=>({p,m:E2.matchReport(r.doc,nos,p)})).filter(x=>x.m.level!=='none');mm.forEach(x=>usedP.add(x.p.파일명));
  const lv=mm.some(x=>x.m.level==='full')&&!mm.some(x=>x.m.level==='partial')?'일치':mm.length?'일부':'—';
  if(lv==='일치')full++;else if(lv==='일부')part++;else none++;
  console.log(lv.padEnd(3),r.doc.의뢰기관.padEnd(6),r.doc.시행.padEnd(20),'시료',nos.length,'| 시행공문',rr.map(x=>x.제목코드||x.파일명.slice(0,20)).join(',')||'-','| 성적서',mm.map(x=>x.p.파일명.replace('시험성적서','').slice(0,22)+'['+x.m.level+' '+x.m.matched.length+'/'+nos.length+(x.m.extra.length?' 외'+x.m.extra.join(','):'')+(x.m.orgGood?'':' 기관?')+']').join(' ')||'-');
  console.log('      ',E2.caseFolderName(r.doc));
 }
 console.log('일치',full,'일부',part,'없음',none);
 console.log('매칭 안 된 시행공문:',replies.filter(x=>!usedR.has(x.파일명)).map(x=>x.파일명+' ('+x.관련공문번호+')'));
 console.log('매칭 안 된 성적서:',reps.filter(x=>!usedP.has(x.파일명)).map(x=>x.파일명+' ('+x.공문번호+')'));
})();
