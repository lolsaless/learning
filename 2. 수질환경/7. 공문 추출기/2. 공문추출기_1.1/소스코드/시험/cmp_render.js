const fs=require('fs'),path=require('path'),zlib=require('zlib');const E=require('../src/engine.js');
(async()=>{const o={};for(const f of fs.readdirSync('odt'))o[f]=(await E.renderOdtHtml(new Uint8Array(fs.readFileSync(path.join('odt',f))),async d=>zlib.inflateRawSync(Buffer.from(d)))).html;process.stdout.write(JSON.stringify(o));})();
