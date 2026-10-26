// v2.0 확장 엔진 시험: 특이 공문(HWPX) · 시행공문 · 성적서 PDF · 처리기한
const fs=require('fs'),path=require('path'),zlib=require('zlib');
const E=require('../src/engine.js'),E2=require('../src/engine2.js');const {pdfItems}=require('./pdf_dump.js');
const inf=b=>zlib.inflateRawSync(b);const U='/mnt/user-data/uploads/Claude';
const out={};
(async()=>{
 // 1) 특이 공문
 const sp=U+'/특이 공문 ODT';const odt=fs.readdirSync(sp).find(f=>f.endsWith('.odt'));
 const r=await E.extractOdt(fs.readFileSync(path.join(sp,odt)),odt,inf);
 const names=E2.attachmentNames(r.doc.본문);console.log('붙임:',names);
 const hw=[];for(const f of fs.readdirSync(sp).filter(f=>f.endsWith('.hwpx'))){console.log(' 점수',f,E2.attachScore(f,names).toFixed(2));hw.push({name:f,parsed:await E2.parseHwpx(fs.readFileSync(path.join(sp,f)),inf)});}
 const r2=E2.samplesFromAttachments(r,hw);
 console.log('특이 공문 →',r2.rows.length,'행, 경고',r2.warnings,r2.source);
 r2.rows.forEach(x=>console.log('  ',x.시료번호,'|',x.검사항목,'|',x.채취지점,'|',x.시료채취일,'|',x.확인필요));
 out.special=r2.rows.map(x=>({no:x.시료번호,items:x.검사항목}));
 // 2) 시행공문
 const rp=U+'/성적서 및 시행 공문';
 for(const f of fs.readdirSync(rp).filter(f=>f.endsWith('.odt'))){const x=await E.extractOdt(fs.readFileSync(path.join(rp,f)),f,inf);
   const rr=E2.parseReply(x);console.log(E2.isReply(x)?'R':'-',rr.관련기관.padEnd(6),rr.관련공문번호.padEnd(22),rr.관련공문일,rr.제목코드,rr.부적합?'부적합':'',rr.단계);}
 // 3) 성적서
 const reps=[];
 for(const f of fs.readdirSync(rp).filter(f=>f.endsWith('.pdf'))){const pg=await pdfItems(path.join(rp,f));const R=E2.parseReportPdf(pg,f);reps.push(R);
   const n=(/등\s*(\d+)건/.exec(f)||[0,1])[1];
   console.log(f.slice(0,34).padEnd(34),'쪽',pg.length,'시료',R.samples.length,'(파일명',n+')',R.의뢰기관,R.공문번호,R.samples.map(s=>s.시료명+':'+s.결과.map(x=>x.항목명+'='+x.결과).join(',')+':'+s.판정).slice(0,2).join(' ; '));}
 fs.writeFileSync('/tmp/claude-0/-home-claude/81a86257-f3c2-5b6c-91e1-a77386e01165/scratchpad/reports.json',JSON.stringify(reps,null,1));
 // 4) 처리기한
 const hol=new Set(Object.keys(E2.HOLIDAYS_BUILTIN[2026]));const T=E2.stdDaysTable();
 const cases=[['2026-10-26','SS',false],['2026-10-26','SS',true],['2026-10-26','BOD',false],['2026-10-02','SS',false],['2026-09-23','T-P',false],['2026-10-22','BOD',false],['2026-10-24','SS',false],['2026-10-24','SS',true]];
 for(const [d,it,c] of cases){const due=E2.deadline(d,T[it].days,hol,{countReceiptDay:c});console.log('접수',d,'(요일',E2.toDate(d).getDay()+')',it,T[it].days+'일',c?'13시전':'13시후','→ 기한',due,'요일',E2.toDate(due).getDay());}
 console.log('남은:',JSON.stringify(E2.remaining('2026-10-26','2026-11-02',hol)),JSON.stringify(E2.remaining('2026-11-02','2026-11-02',hol)),JSON.stringify(E2.remaining('2026-11-04','2026-11-02',hol)));
 console.log('시료:',JSON.stringify(E2.sampleDeadline(['BOD','SS','T-N','T-P','TOC','색도','클로로필a'],'2026-10-22',hol,T)));
})().catch(e=>{console.error(e);process.exit(1)});
