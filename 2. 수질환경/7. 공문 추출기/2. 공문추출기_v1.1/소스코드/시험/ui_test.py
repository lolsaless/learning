import asyncio, json, os, sys, threading, http.server, functools, urllib.parse
from playwright.async_api import async_playwright
ROOT = '/home/claude/odt-app'
SHOT = '/tmp/claude-0/-home-claude/81a86257-f3c2-5b6c-91e1-a77386e01165/scratchpad/shots'
os.makedirs(SHOT, exist_ok=True)
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 8767), functools.partial(H, directory=ROOT))
threading.Thread(target=srv.serve_forever, daemon=True).start()
ODT = sorted(os.listdir(f'{ROOT}/test/odt'))

JS_SETUP = """async (names) => {
  const opfs = await navigator.storage.getDirectory();
  try { await opfs.removeEntry('공문', {recursive:true}); } catch(e) {}
  const dir = await opfs.getDirectoryHandle('공문', {create:true});
  for (const n of names) {
    const b = await (await fetch('/test/odt/' + encodeURIComponent(n))).arrayBuffer();
    const w = await (await dir.getFileHandle(n, {create:true})).createWritable(); await w.write(b); await w.close();
  }
  const put = async (n, data) => { const w = await (await dir.getFileHandle(n, {create:true})).createWritable(); await w.write(data); await w.close(); };
  await put('메모.txt', 'memo'); await put('broken.odt', new Uint8Array([1,2,3,4,5])); await put('empty.odt', new Uint8Array(0));
  window.__dir = dir; await window.__odtConnect(dir); return true;
}"""
LIST = """async (sub) => { let d = window.__dir; if (sub) d = await d.getDirectoryHandle(sub); const out=[]; for await (const [n,h] of d.entries()) out.push(n + (h.kind==='directory'?'/':'')); return out.sort(); }"""
READ = """async (n) => { const f = await (await window.__dir.getFileHandle(n)).getFile(); return await f.text(); }"""

async def main():
    errors = []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={'width': 1600, 'height': 900}, accept_downloads=True)
        page = await ctx.new_page()
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.on('pageerror', lambda e: errors.append('PAGEERROR ' + str(e)))
        url = 'http://127.0.0.1:8767/dist/' + urllib.parse.quote('공문추출기.html')
        await page.goto(url)
        await page.screenshot(path=f'{SHOT}/01_welcome.png')
        await page.evaluate(JS_SETUP, ODT)
        await page.wait_for_selector('#grid tbody tr')
        n_tr = await page.locator('#grid tbody tr').count()
        stats = await page.inner_text('#stats')
        print('rows', n_tr, '| stats:', stats)
        await page.screenshot(path=f'{SHOT}/02_main.png')
        # 상세 패널
        await page.locator('#grid tbody tr', has_text='8-10-1-1').first.locator('td').nth(6).click()
        await page.wait_for_selector('#detail:not([hidden])')
        await page.screenshot(path=f'{SHOT}/03_detail.png')
        await page.click('#detail [data-act=close]')
        # 체크 2건 (가평-10-5, 고양 아닌 첫 두 공문)
        cbs = page.locator('#grid tbody input[data-act=check]')
        await cbs.nth(0).check(); await cbs.nth(1).check()
        await page.wait_for_timeout(500)
        st = json.loads(await page.evaluate(READ, '_처리상태.json'))
        print('checked keys', list(st['checked'].keys()))
        btn = await page.inner_text('#btnDone'); print('btnDone:', btn)
        await page.click('#btnDone'); await page.wait_for_selector('#modal:not([hidden])')
        await page.screenshot(path=f'{SHOT}/04_confirm.png')
        await page.click('#modalOk'); await page.wait_for_selector('#modalTitle:text("처리 완료 결과")')
        print('result modal:', (await page.inner_text('#modalBody')).replace('\n', ' '))
        await page.click('#modalOk')
        print('root count', len([x for x in await page.evaluate(LIST, '') if x.endswith('.odt')]), '| done:', await page.evaluate(LIST, '성적처리완료'))
        st = json.loads(await page.evaluate(READ, '_처리상태.json')); print('after move checked', st['checked'], 'history', len(st['history']))
        # 중복 공문: 7-10-2 (1) 체크 -> 두 파일 모두 체크
        row = page.locator('#grid tbody tr', has_text='7-10-2').first
        await row.locator('input[data-act=check]').check(); await page.wait_for_timeout(300)
        n_checked = await page.locator('#grid tbody input[data-act=check]:checked').count(); print('checked boxes after dup check', n_checked)
        # 잠긴 파일 시뮬레이션: 7-10-2.odt 삭제 실패
        await page.evaluate("""() => {
          const orig = FileSystemDirectoryHandle.prototype.removeEntry;
          FileSystemFileHandle.prototype.move = function(){ return Promise.reject(new DOMException('x','NotSupportedError')); };
          FileSystemDirectoryHandle.prototype.removeEntry = function(n, o){ if (this.name === '공문' && n === '폐수배출시설 수질오염도 검사 의뢰(7-10-2).odt') return Promise.reject(new DOMException('locked','NoModificationAllowedError')); return orig.call(this, n, o); };
        }""")
        await page.click('#btnDone'); await page.click('#modalOk'); await page.wait_for_selector('#modalTitle:text("처리 완료 결과")')
        print('locked result:', (await page.inner_text('#modalBody')).replace('\n', ' '))
        await page.screenshot(path=f'{SHOT}/05_locked.png')
        await page.click('#modalOk')
        print('done folder now', await page.evaluate(LIST, '성적처리완료')); print('root has 7-10-2:', '폐수배출시설 수질오염도 검사 의뢰(7-10-2).odt' in await page.evaluate(LIST, ''))
        st = json.loads(await page.evaluate(READ, '_처리상태.json')); print('checked still', list(st['checked'].keys()))
        await page.reload(); await page.evaluate("async () => { const o = await navigator.storage.getDirectory(); window.__dir = await o.getDirectoryHandle('공문'); await window.__odtConnect(window.__dir); }")
        await page.wait_for_selector('#grid tbody tr')
        print('after reload checked boxes', await page.locator('#grid tbody input[data-act=check]:checked').count())
        # 되돌리기
        await page.select_option('#fState', 'done'); await page.wait_for_selector('#grid tbody button[data-act=restore]')
        await page.screenshot(path=f'{SHOT}/06_doneview.png')
        await page.locator('#grid tbody button[data-act=restore]').first.click(); await page.click('#modalOk'); await page.wait_for_timeout(800)
        print('after restore done folder', await page.evaluate(LIST, '성적처리완료'))
        await page.select_option('#fState', 'pending'); await page.wait_for_timeout(300)
        # 엑셀 저장 (다운로드 경로)
        await page.evaluate("() => { window.showSaveFilePicker = undefined; }")
        async with page.expect_download() as dl:
            await page.click('#btnExcel')
        d = await dl.value; xp = f'{SHOT}/export.xlsx'; await d.save_as(xp); print('excel saved', d.suggested_filename)
        # 기준표 양식
        await page.click('#btnStd'); await page.click('#modalOk'); await page.wait_for_selector('#modalTitle:text("기준표 양식")'); await page.click('#modalOk')
        print('root files', [x for x in await page.evaluate(LIST, '') if not x.endswith('.odt')])
        # 기준표 채우기: 생성된 기준표.xlsx 읽어 기준값 채워 다시 저장
        await page.evaluate("""async () => {
          const fh = await window.__dir.getFileHandle('기준표.xlsx'); const b = new Uint8Array(await (await fh.getFile()).arrayBuffer());
          const inflate = async d => new Uint8Array(await new Response(new Blob([d]).stream().pipeThrough(new DecompressionStream('deflate-raw'))).arrayBuffer());
          const rows = await OdtEngine.readXlsxRows(b, inflate);
          const vals = {BOD:'10', TOC:'25', SS:'10', 'T-N':'20', 'T-P':'2', 'n-H(광)':'5', ABS:'5', '생태독성':'2'};
          const out = rows.slice(1).map(r => [r[0], r[1], vals[r[1]] || '', r[3]]);
          out.push(['*','색도','200','도']);
          const x = MiniXlsx.buildXlsx([{name:'기준표', columns:[{header:'지역구분'},{header:'항목'},{header:'기준값'},{header:'단위'}], rows: out}]);
          const w = await fh.createWritable(); await w.write(x); await w.close();
        }""")
        # 새 공문 추가 후 창 포커스 → 자동 새로고침
        await page.evaluate("""async () => { const src = await (await window.__dir.getFileHandle('수질오염도 검사 의뢰(15-9-3).odt')).getFile();
          const w = await (await window.__dir.getFileHandle('새공문 복사본(15-9-3).odt', {create:true})).createWritable(); await w.write(src); await w.close(); }""")
        await page.wait_for_timeout(2100)
        await page.evaluate("() => window.dispatchEvent(new Event('focus'))"); await page.wait_for_timeout(1500)
        print('stats after std+focus:', await page.inner_text('#stats'))
        await page.check('#fWarn'); await page.wait_for_timeout(200)
        print('warn-only docs rows', await page.locator('#grid tbody tr').count())
        await page.screenshot(path=f'{SHOT}/07_warnonly.png')
        await page.uncheck('#fWarn')
        await page.fill('#fSearch', 'TMS'); await page.wait_for_timeout(400)
        print('search TMS rows', await page.locator('#grid tbody tr').count())
        await page.fill('#fSearch', ''); await page.wait_for_timeout(300)
        await page.screenshot(path=f'{SHOT}/08_std.png', full_page=False)
        # file:// 환경 확인
        fpage = await ctx.new_page()
        await fpage.goto('file://' + urllib.parse.quote(f'{ROOT}/dist/공문추출기.html'))
        print('file:// secure', await fpage.evaluate('window.isSecureContext'), 'picker', await fpage.evaluate("'showDirectoryPicker' in window"), 'DS', await fpage.evaluate("typeof DecompressionStream"))
        await b.close()
    print('console errors:', errors)
asyncio.run(main())
