const fs=require('fs'),path=require('path'),zlib=require('zlib');const S=process.env.SRC;
const E=require(S+'/engine.js'),E2=require(S+'/engine2.js');const inf=b=>zlib.inflateRawSync(b);
(async()=>{const reps=JSON.parse(fs.readFileSync(process.env.REPS,'utf8'));const RD=process.env.RD,QD=process.env.QD;
const replies=[];for(const f of fs.readdirSync(RD).filter(f=>f.endsWith('.odt'))){const r=await E.extractOdt(fs.readFileSync(path.join(RD,f)),f,inf);if(!E2.isReply(r))console.log('NOT REPLY',f);replies.push(E2.parseReply(r));}
console.log('replies',replies.length,'with rel no',replies.filter(x=>x.관련공문번호).length);
let full=0,part=0,none=0;const uR=new Set(),uP=new Set();
for(const f of fs.readdirSync(QD).filter(f=>f.endsWith('.odt')).sort()){const r=await E.extractOdt(fs.readFileSync(path.join(QD,f)),f,inf);const nos=r.rows.map(x=>x.시료번호).filter(Boolean);
 const rr=replies.filter(x=>E2.matchReply(r.doc,x)>0);rr.forEach(x=>uR.add(x.파일명));const mm=reps.map(p=>({p,m:E2.matchReport(r.doc,nos,p)})).filter(x=>x.m.level!=='none');mm.forEach(x=>uP.add(x.p.파일명));
 const got=new Set();mm.forEach(x=>x.m.matched.forEach(n=>got.add(n)));const ex=mm.flatMap(x=>x.m.extra);
 const lv=!mm.length?'—':(got.size===nos.length&&!ex.length)?'일치':'일부';if(lv==='일치')full++;else if(lv==='일부')part++;else none++;
 if(lv!=='—'||rr.length)console.log(lv,r.doc.시행.padEnd(18),'시료',nos.length,'시행',rr.length,'성적서',got.size+'/'+nos.length,ex.length?'외'+ex.join(','):'',mm.map(x=>x.p.파일명.slice(5,21)).join(' '));}
console.log('일치',full,'일부',part,'없음',none);
console.log('미매칭 시행공문',replies.filter(x=>!uR.has(x.파일명)).map(x=>x.제목코드+'('+x.관련공문번호+')').join(' | '));
console.log('미매칭 성적서',reps.filter(x=>!uP.has(x.파일명)).map(x=>x.파일명.slice(5,22)).join(' | '));})();
