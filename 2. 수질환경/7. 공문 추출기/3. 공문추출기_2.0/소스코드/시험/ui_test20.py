# v2.0 브라우저 통합 시험 (Chromium, OPFS 폴더에 실제 공문·시행공문·성적서·HWPX 복사)
import asyncio, os, threading, http.server, functools, urllib.parse, json, base64, sys
from playwright.async_api import async_playwright
ROOT='/home/claude/odt-app'; FIX=f'{ROOT}/test/v2fix/root'; SHOT='/tmp/claude-0/-home-claude/81a86257-f3c2-5b6c-91e1-a77386e01165/scratchpad/shots'; OUT='/tmp/claude-0/-home-claude/81a86257-f3c2-5b6c-91e1-a77386e01165/scratchpad/out'
os.makedirs(SHOT,exist_ok=True); os.makedirs(OUT,exist_ok=True)
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
srv=http.server.ThreadingHTTPServer(('127.0.0.1',8771),functools.partial(H,directory=ROOT)); threading.Thread(target=srv.serve_forever,daemon=True).start()
files=[]
for dp,dn,fn in os.walk(FIX):
    for f in fn: files.append(os.path.relpath(os.path.join(dp,f),FIX))
SETUP="""async (files) => { const o=await navigator.storage.getDirectory(); try{await o.removeEntry('공문',{recursive:true})}catch(e){}
 const d=await o.getDirectoryHandle('공문',{create:true});
 for (const rel of files){ const parts=rel.split('/'); let dir=d; for(const p of parts.slice(0,-1)) dir=await dir.getDirectoryHandle(p,{create:true});
   const b=await (await fetch('/test/v2fix/root/'+parts.map(encodeURIComponent).join('/'))).arrayBuffer(); const w=await (await dir.getFileHandle(parts.at(-1),{create:true})).createWritable(); await w.write(b); await w.close(); }
 window.__dir=d; window.__odtConnect(d); }"""
TREE="""async () => { const out=[]; async function rec(dir,pre){ for await (const [n,h] of dir.entries()){ if(h.kind==='directory'){ out.push(pre+n+'/'); await rec(h,pre+n+'/'); } else out.push(pre+n); } } await rec(window.__dir,''); return out.sort(); }"""
READ="""async (path) => { let dir=window.__dir; const p=path.split('/'); for(const x of p.slice(0,-1)) dir=await dir.getDirectoryHandle(x); const f=await (await dir.getFileHandle(p.at(-1))).getFile(); const b=new Uint8Array(await f.arrayBuffer()); let s=''; for(let i=0;i<b.length;i+=0x8000) s+=String.fromCharCode.apply(null,b.subarray(i,i+0x8000)); return btoa(s); }"""
async def main():
    errs=[]
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(viewport={'width':1720,'height':960},accept_downloads=True); pg=await ctx.new_page()
        pg.on('console',lambda m: errs.append(m.text) if m.type=='error' else None); pg.on('pageerror',lambda e: errs.append(str(e)))
        await pg.goto('http://127.0.0.1:8771/dist/'+urllib.parse.quote('공문추출기.html'))
        await pg.evaluate(SETUP, files)
        # 1) 처음: 정리 여부 질문
        await pg.wait_for_selector('#modal:not([hidden])', timeout=120000)
        print('modal:', (await pg.inner_text('#modalTitle')), '|', (await pg.inner_text('#modalBody'))[:120].replace('\n',' '))
        await pg.screenshot(path=f'{SHOT}/20_ask.png')
        await pg.click('#modalOk')
        await pg.wait_for_function("() => document.getElementById('busy').hidden && !document.querySelector('#banner [data-act=organize]') && document.querySelectorAll('#grid tbody tr').length>0", timeout=180000)
        await pg.wait_for_timeout(500)
        tree=await pg.evaluate(TREE)
        dirs=[t for t in tree if t.endswith('/') and t.count('/')==1]
        print('case dirs', len(dirs)); print('  root files left:', [t for t in tree if '/' not in t])
        sp=[t for t in tree if t.startswith('양주시_2026년 한탄강수계')]; print('특이 공문 폴더:', sp)
        print('stats', await pg.inner_text('#stats')); print('banner', await pg.inner_text('#banner'))
        heads=await pg.locator('#grid thead th').all_inner_texts(); print('headers', [h.replace('▲','').replace('▼','').strip() for h in heads])
        await pg.screenshot(path=f'{SHOT}/21_main.png')
        # 2) 특이 공문 13행
        n13=await pg.locator('#grid tbody tr', has_text='환경정책과-18644').count(); n13b=await pg.locator('#grid tbody tr', has_text='BOD, SS, T-N, T-P, TOC, 색도').count(); print('rows with 6 items',n13b); print('특이 공문 rows', n13)
        # 3) TMS 진행
        tms=pg.locator('#grid tbody tr', has_text='TMS 2-10-3(A)').first
        print('TMS row:', (await tms.inner_text()).replace('\t',' | ')[:260])
        # 4) 시료접수일 입력 (파주 14-10-4)
        row=pg.locator('#grid tbody tr', has_text='14-10-4').first
        await row.locator('[data-act=recv]').click(); await pg.wait_for_selector('#datePop:not([hidden])')
        await pg.screenshot(path=f'{SHOT}/22_datepick.png')
        await pg.click('#datePop [data-day="2026-10-26"]'); await pg.wait_for_timeout(300)
        row=pg.locator('#grid tbody tr', has_text='14-10-4').first
        print('14-10-4 after recv 10-26:', (await row.inner_text()).replace('\t',' | ')[:300])
        # 5) 설정: 짧은 항목 기준
        await pg.click('#btnSettings'); await pg.wait_for_selector('#modal:not([hidden]) .cal'); await pg.screenshot(path=f'{SHOT}/23_hol.png')
        await pg.click('#modalBody [data-tab=std]'); await pg.check('#modalBody input[name=basis][value=min]'); await pg.screenshot(path=f'{SHOT}/24_std.png')
        await pg.click('#modalOk'); await pg.wait_for_timeout(500)
        row=pg.locator('#grid tbody tr', has_text='14-10-4').first
        print('14-10-4 basis=min:', (await row.inner_text()).replace('\t',' | ')[:300])
        await pg.click('#btnSettings'); await pg.click('#modalBody [data-tab=std]'); await pg.check('#modalBody input[name=basis][value=max]'); await pg.click('#modalOk'); await pg.wait_for_timeout(400)
        # 지정 휴일: 2026-10-28 클릭 → 기한 하루 늦어짐
        await pg.click('#btnSettings'); await pg.click('#modalBody [data-day="2026-10-28"]'); await pg.click('#modalOk'); await pg.wait_for_timeout(400)
        row=pg.locator('#grid tbody tr', has_text='14-10-4').first
        print('14-10-4 + 10-28 휴일:', (await row.inner_text()).replace('\t',' | ')[:300])
        # 6) 상세 (TMS): 탭·성적서 미리보기
        await pg.locator('#grid tbody tr', has_text='TMS 2-10-3(A)').first.locator('td').nth(6).click()
        await pg.wait_for_selector('#pv .odt-page'); await pg.wait_for_timeout(300)
        tabs=await pg.locator('.pv-tab').all_inner_texts(); print('viewer tabs', tabs)
        await pg.screenshot(path=f'{SHOT}/25_tms_detail.png')
        await pg.click('.pv-tab:has-text("성적서")')
        try: await pg.wait_for_selector('#pv .pdf-page img', timeout=60000)
        except Exception as e: print('PV FAIL', await pg.inner_text('#pv'), await pg.evaluate("() => window.__odtState().viewer"), errs); raise
        await pg.wait_for_timeout(300)
        print('pdf pages shown', await pg.locator('#pv .pdf-page').count()); await pg.screenshot(path=f'{SHOT}/26_tms_pdf.png')
        # 7) 특이 공문 상세: 첨부 HWPX 보기 + 워터마크
        await pg.locator('#grid tbody tr', has_text='환경정책과-18644').first.locator('td').nth(6).click(); await pg.wait_for_selector('#pv .odt-page'); await pg.wait_for_timeout(200)
        await pg.click('#detail [data-act=recv]'); await pg.click('#datePop [data-day="2026-10-22"]'); await pg.wait_for_timeout(400)
        print('watermark shown', await pg.locator('#pv .wm-stamp').count(), await pg.locator('#pv .wm-stamp').inner_text() if await pg.locator('#pv .wm-stamp').count() else '')
        await pg.screenshot(path=f'{SHOT}/27_special_wm.png')
        await pg.click('.pv-tab:has-text("의뢰항목")'); await pg.wait_for_selector('#pv .hwpx-page'); await pg.screenshot(path=f'{SHOT}/28_hwpx.png')
        # 메모·이력
        await pg.fill('#detail textarea.memo','10/22 시료 13병 접수, 2병 라벨 훼손 확인'); await pg.wait_for_timeout(600)
        await pg.fill('#logText','용암교 시료 클로로필a 추가 분석 의뢰 확인'); await pg.select_option('#logSample','용암교(구 세월교)'); await pg.click('[data-act=log-add]'); await pg.wait_for_timeout(500)
        print('log rows', await pg.locator('#detail .mini.log tr').count()-1)
        # 이력 문서 Word (공문 폴더 저장)
        await pg.click('[data-act="hist:docx"]'); await pg.wait_for_selector('#modal:not([hidden]) #hSample'); await pg.click('#modalOk')
        await pg.wait_for_function("() => document.getElementById('busy').hidden", timeout=120000); await pg.wait_for_timeout(500)
        # TMS: Word + PDF
        await pg.locator('#grid tbody tr', has_text='TMS 2-10-3(A)').first.locator('td').nth(6).click(); await pg.wait_for_timeout(500)
        await pg.click('[data-act="hist:pdf"]'); await pg.wait_for_selector('#modal:not([hidden]) #hSample'); await pg.select_option('#hSample','TMS 2-10-3(B)'); await pg.click('#modalOk')
        await pg.wait_for_function("() => document.getElementById('busy').hidden", timeout=180000); await pg.wait_for_timeout(500)
        await pg.click('[data-act="hist:docx"]'); await pg.wait_for_selector('#modal:not([hidden]) #hSample'); await pg.click('#modalOk')
        await pg.wait_for_function("() => document.getElementById('busy').hidden", timeout=180000); await pg.wait_for_timeout(800)
        tree=await pg.evaluate(TREE); hist=[t for t in tree if '/이력_' in t]; print('history docs', hist)
        for h in hist:
            open(f'{OUT}/'+h.split('/')[-1],'wb').write(base64.b64decode(await pg.evaluate(READ,h)))
        # 8) 완료: TMS + 파주 14-10-4 체크 → 처리 완료
        for t in ['TMS 2-10-3(A)','14-10-4']:
            await pg.locator('#grid tbody tr', has_text=t).first.locator('input[data-act=check]').check()
        await pg.click('#btnDone'); await pg.wait_for_selector('#modal:not([hidden]) #optNest'); await pg.screenshot(path=f'{SHOT}/29_done_dlg.png'); await pg.click('#modalOk')
        await pg.wait_for_selector('#modal:not([hidden])', timeout=120000); await pg.wait_for_timeout(300)
        print('result:', (await pg.inner_text('#modalBody'))[:400].replace('\n',' / ')); await pg.click('#modalOk')
        tree=await pg.evaluate(TREE); print('done tree:', [t for t in tree if t.startswith('성적처리완료/')])
        print('stats after', await pg.inner_text('#stats'))
        # 9) 완료 보기 → 되돌리기 (파주)
        await pg.select_option('#fState','done'); await pg.wait_for_function("() => document.getElementById('busy').hidden && window.__odtState().doneDocs.length>0", timeout=60000); await pg.wait_for_timeout(300)
        print('done rows', await pg.locator('#grid tbody tr.grp-first').count(), await pg.evaluate("() => window.__odtState().doneDocs.map(d=>d.nm+' @'+d.dirName)")); await pg.screenshot(path=f'{SHOT}/30_doneview.png')
        await pg.locator('#grid tbody tr', has_text='14-10-4').first.locator('[data-act=restore]').click(); await pg.click('#modalOk'); await pg.wait_for_timeout(1500)
        tree=await pg.evaluate(TREE); print('after restore root dirs with 14-10-4:', [t for t in tree if '31655' in t])
        await pg.select_option('#fState','pending'); await pg.wait_for_timeout(800)
        # 10) 직접 입력 (동두천 공문에 수동 시료)
        await pg.locator('#grid tbody tr', has_text='동두천-10-1').first.locator('td').nth(6).click(); await pg.wait_for_timeout(400)
        await pg.click('#detail [data-act=manual]'); await pg.wait_for_selector('#manText')
        await pg.fill('#manText','하천명\t의뢰항목\n갑천-1\tBOD, SS\n갑천-2\t\n갑천-3\tT-N, T-P'); await pg.wait_for_timeout(200)
        print('manual preview', (await pg.inner_text('#manPrev')).replace('\n',' / ')); await pg.click('#modalOk'); await pg.wait_for_timeout(1500)
        print('동두천 rows now', await pg.locator('#grid tbody tr', has_text='갑천-').count())
        # 엑셀
        await pg.evaluate('() => { window.showSaveFilePicker = undefined; }')
        async with pg.expect_download() as dl: await pg.click('#btnExcel')
        d=await dl.value; await d.save_as(f'{OUT}/excel.xlsx'); print('excel', d.suggested_filename)
        notes=json.loads(base64.b64decode(await pg.evaluate(READ,'_시료이력.json'))); print('notes cases', len(notes['cases']))
        sett=json.loads(base64.b64decode(await pg.evaluate(READ,'_설정.json'))); print('settings', sett['dueBasis'], sett['holidays']['custom'], sett['organize'])
        await b.close()
    print('errors', errs[:10])
asyncio.run(main())
