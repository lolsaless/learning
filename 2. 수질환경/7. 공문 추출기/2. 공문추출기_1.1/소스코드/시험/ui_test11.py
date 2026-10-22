import asyncio, os, threading, http.server, functools, urllib.parse
from playwright.async_api import async_playwright
ROOT='/home/claude/odt-app'; SHOT='/tmp/claude-0/-home-claude/81a86257-f3c2-5b6c-91e1-a77386e01165/scratchpad/shots'
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
srv=http.server.ThreadingHTTPServer(('127.0.0.1',8766),functools.partial(H,directory=ROOT)); threading.Thread(target=srv.serve_forever,daemon=True).start()
ODT=sorted(os.listdir(f'{ROOT}/test/odt'))
SETUP="""async (names) => { const o=await navigator.storage.getDirectory(); try{await o.removeEntry('공문',{recursive:true})}catch(e){}
 const d=await o.getDirectoryHandle('공문',{create:true});
 for (const n of names){ const b=await (await fetch('/test/odt/'+encodeURIComponent(n))).arrayBuffer(); const w=await (await d.getFileHandle(n,{create:true})).createWritable(); await w.write(b); await w.close(); }
 window.__dir=d; await window.__odtConnect(d); }"""
async def main():
    errs=[]
    async with async_playwright() as p:
        b=await p.chromium.launch(); ctx=await b.new_context(viewport={'width':1680,'height':940},accept_downloads=True); pg=await ctx.new_page()
        pg.on('console',lambda m: errs.append(m.text) if m.type=='error' else None); pg.on('pageerror',lambda e: errs.append(str(e)))
        await pg.goto('http://127.0.0.1:8766/dist/'+urllib.parse.quote('공문추출기.html'))
        await pg.evaluate(SETUP, ODT); await pg.wait_for_selector('#grid tbody tr')
        heads=await pg.locator('#grid thead th').all_inner_texts(); print('headers', [h.replace('▲','').replace('▼','').strip() for h in heads])
        dates=await pg.evaluate("() => [...document.querySelectorAll('#grid tbody tr.grp-first')].map(tr=>tr.children[1].innerText)")
        print('접수일 order (first 8)', dates[:8], '| sorted desc:', dates==sorted(dates, reverse=True))
        print('stats', await pg.inner_text('#stats'))
        r=pg.locator('#grid tbody tr', has_text='동두천-10-1').first
        print('동두천 row', (await r.inner_text()).replace('\t',' | ')[:200])
        await r.locator('td').nth(6).click(); await pg.wait_for_selector('#pv .odt-page')
        await pg.wait_for_timeout(300); await pg.screenshot(path=f'{SHOT}/11_side.png')
        await pg.click('[data-act=mode-org]'); await pg.wait_for_selector('#pv .odt-page'); await pg.screenshot(path=f'{SHOT}/12_org.png')
        await pg.click('[data-act=mode-ext]'); print('ext mode has pv:', await pg.locator('#pv').count())
        await pg.click('[data-act=mode-side]'); await pg.wait_for_selector('#pv .odt-page')
        async with ctx.expect_page() as np:
            await pg.click('[data-act=pv-big]')
        big=await np.value; await big.wait_for_load_state(); await big.set_viewport_size({'width':1000,'height':1300}); await big.screenshot(path=f'{SHOT}/13_big.png')
        print('big title', await big.title())
        async with pg.expect_download() as dl:
            await pg.click('[data-act=pv-download]')
        d=await dl.value; print('download', d.suggested_filename)
        # 체크 후 상세 유지(스크롤 유지) 및 다른 공문 클릭
        await pg.click('[data-act=check-toggle]'); await pg.wait_for_timeout(300)
        print('checked after toggle', await pg.locator('#grid tbody input[data-act=check]:checked').count())
        await pg.locator('#grid tbody tr', has_text='TMS 2-10-3(A)').first.locator('td').nth(6).click(); await pg.wait_for_selector('#pv .odt-page'); await pg.wait_for_timeout(300)
        await pg.screenshot(path=f'{SHOT}/14_tms.png')
        # 정렬 토글
        await pg.click('#grid thead th[data-k=접수일]'); dates2=await pg.evaluate("() => [...document.querySelectorAll('#grid tbody tr.grp-first')].map(tr=>tr.children[1].innerText)")
        print('after click asc:', dates2==sorted(dates2))
        await b.close()
    print('errors', errs)
asyncio.run(main())
