import sys, json, time, os
from playwright.sync_api import sync_playwright
HERE=os.path.dirname(os.path.abspath(__file__)); exec(open(os.path.join(HERE,'truth.py')).read())
TRUTH.update({'p.ion_polarity':'Pos','p.dc_polarity':'Pos','p.hed_enable':'On','p.emission':34.6,'p.mass_gain':-753,'p.electron_energy':70.0,'p.mass_offset':-34,'p.amu_gain':833,'p.amu_offset':124.75,'p.width219':-0.012,'p.entrance_lens':7.5,'p.ent_lens_offset':17.18,'p.ion_body':0.0,'p.scan_speed':3,'p.averages':3,'tp.hivac':8.52e-6,'tt.r0.actual':69.0,'tt.r1.actual':219.0,'tt.r2.actual':502.0,'tt.r0.isomz':70.0,'tt.r1.isomz':220.0,'tt.r2.isomz':503.0,'tt.r0.target':69,'tt.r1.target':219,'tt.r2.target':502})
PDF=sys.argv[1]
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1600,'height':950})
    logs=[]
    pg.on('pageerror',lambda e:logs.append('PAGEERR '+str(e)[:400]))
    pg.on('request',lambda r: logs.append('REQ '+r.url[:100]) if r.url.startswith('http') else None)
    pg.goto('file://'+os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','gcms_autotune_viewer.html'))
    pg.set_input_files('#fileInput',PDF)
    t0=time.time()
    pg.wait_for_function("window.__app.recs.length && ['done','error'].includes(window.__app.recs[0].status)",timeout=300000)
    print('elapsed %.1f'%(time.time()-t0))
    r=pg.evaluate("""()=>{const a=window.__app.recs[0];return {status:a.status,error:a.error,F:a.report&&Object.fromEntries(Object.values(a.report).map(f=>[f.id,{t:f.text,n:f.num,c:f.conf&&Math.round(f.conf),r:f.refined?1:0,d:f.disputed?1:0}])),rows:a.eval&&a.eval.rows.map(r=>[r.id,r.value,r.verdict,r.note]),sum:a.eval&&a.eval.summary,counts:a.eval&&a.eval.counts}}""")
    ok=0;n=0;bad=[]
    for k,t in TRUTH.items():
        f=r['F'].get(k)
        if f is None: bad.append((k,'MISSING')); n+=1; continue
        n+=1
        v=f['n'] if isinstance(t,(int,float)) else f['t']
        good = (v==t) if isinstance(t,str) else (v is not None and abs(v-t)<=1e-6*max(1,abs(t)))
        if good: ok+=1
        else: bad.append((k,f['t'],'conf',f['c'],'disp',f['d']))
    print('truth match %d/%d'%(ok,n))
    for x in bad: print('  BAD',x)
    print('disputed:',[k for k,f in r['F'].items() if f['d']])
    print('counts',r['counts'])
    for x in r['rows']: print(x)
    print('\n'.join(r['sum']))
    print(logs[:10])
    pg.screenshot(path='s1_replica.png')
    b.close()
