import sys, os, glob, time, json
from playwright.sync_api import sync_playwright
PDF=sys.argv[1]
with sync_playwright() as p:
    b=p.chromium.launch(); ctx=b.new_context(viewport={'width':1600,'height':950}); pg=ctx.new_page()
    errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)[:300])); pg.on('console',lambda m: errs.append('C:'+m.text[:200]) if m.type=='error' else None)
    pg.goto('file://'+os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','gcms_autotune_viewer.html'))
    pg.screenshot(path='u0_empty.png')
    # drag & drop simulation
    data=open(PDF,'rb').read()
    pg.evaluate("""async (arr)=>{const f=new File([new Uint8Array(arr)],'autotune_test.pdf',{type:'application/pdf'});const dt=new DataTransfer();dt.items.add(f);
      window.dispatchEvent(new DragEvent('dragenter',{dataTransfer:dt,bubbles:true}));
      window.dispatchEvent(new DragEvent('drop',{dataTransfer:dt,bubbles:true,cancelable:true}));}""",list(data))
    pg.wait_for_function("window.__app.recs.length && window.__app.recs[0].status==='done'",timeout=300000)
    pg.wait_for_timeout(500)
    pg.screenshot(path='u1_done.png')
    # overlay boxes + click replica field
    pg.click('[data-ov="boxes"]'); pg.wait_for_timeout(300)
    pg.click('#panelReplica .fld[data-f="p.em_volts"]'); pg.wait_for_timeout(700)
    pg.screenshot(path='u2_overlay_sel.png')
    pg.click('[data-ov="values"]'); pg.click('[data-zoom="2.4"]'); pg.wait_for_timeout(400)
    pg.click('#panelReplica .fld[data-f="p.repeller"]'); pg.wait_for_timeout(800)
    pg.screenshot(path='u3_zoom_values.png')
    # edit a field
    pg.dblclick('#panelReplica .fld[data-f="p.repeller"]'); pg.wait_for_timeout(200)
    pg.fill('.fld-input','34.90'); pg.keyboard.press('Enter'); pg.wait_for_timeout(400)
    print('after edit', pg.evaluate("()=>[window.__app.active.report['p.repeller'].text,window.__app.active.eval.rows.find(r=>r.id==='repeller').verdict]"))
    pg.click('.tab[data-tab="judge"]'); pg.click('#btnOpenAll'); pg.wait_for_timeout(300)
    pg.screenshot(path='u4_judge.png')
    pg.click('#btnSaveHist'); pg.click('.tab[data-tab="trend"]'); pg.wait_for_timeout(400)
    pg.screenshot(path='u5_trend.png')
    pg.click('.tab[data-tab="ocr"]'); pg.wait_for_timeout(300); pg.screenshot(path='u6_ocr.png')
    pg.click('.tab[data-tab="replica"]'); pg.click('#btnSplit'); pg.click('#chkRoi'); pg.wait_for_timeout(300)
    pg.screenshot(path='u7_split_roi.png')
    pg.click('#btnSettings'); pg.wait_for_timeout(300); pg.screenshot(path='u8_settings.png'); pg.click('#dlgSettings [data-close]')
    # print
    pg.evaluate("window.print=()=>{}")
    pg.click('#btnPrint'); pg.wait_for_timeout(300)
    pg.pdf(path='print_test.pdf',format='A4',print_background=True,prefer_css_page_size=True)
    # dark mode
    pg.emulate_media(color_scheme='dark'); pg.wait_for_timeout(300); pg.screenshot(path='u9_dark.png')
    # mobile
    pg.set_viewport_size({'width':420,'height':900}); pg.emulate_media(color_scheme='light'); pg.wait_for_timeout(300); pg.screenshot(path='u10_mobile.png')
    print('errors',errs)
    b.close()
