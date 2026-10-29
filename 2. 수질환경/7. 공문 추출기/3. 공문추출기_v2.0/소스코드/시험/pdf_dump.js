// Node에서 pdf.js(legacy)로 텍스트 항목 추출 → 브라우저 앱과 같은 형태 {s,x,y,w}
const fs=require('fs');const pdfjs=require('/home/claude/v12/pdfjs/package/legacy/build/pdf.js');
async function pdfItems(path){const doc=await pdfjs.getDocument({data:new Uint8Array(fs.readFileSync(path)),disableFontFace:true,useSystemFonts:false,isEvalSupported:false}).promise;
const pages=[];for(let i=1;i<=doc.numPages;i++){const p=await doc.getPage(i);const vp=p.getViewport({scale:1});const tc=await p.getTextContent();
pages.push({w:vp.width,h:vp.height,items:tc.items.filter(t=>t.str!=null).map(t=>({s:t.str,x:t.transform[4],y:vp.height-t.transform[5],w:t.width,h:Math.abs(t.transform[3])}))});}return pages;}
module.exports={pdfItems};
if(require.main===module)(async()=>{const pg=await pdfItems(process.argv[2]);console.log('pages',pg.length);const it=pg[+process.argv[3]||0].items;console.log(it.length);console.log(JSON.stringify(it.slice(0,+process.argv[4]||80)));})();
