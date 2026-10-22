import sys, os, json, importlib.util
spec=importlib.util.spec_from_file_location('m', sys.argv[3] if len(sys.argv)>3 else '/home/claude/odt-app/py/공문추출기.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
d=sys.argv[1]; res=[]
for f in os.listdir(d):
    if f.lower().endswith('.odt'):
        res.append(m.extract_odt(open(os.path.join(d,f),'rb').read(), f))
m.mark_duplicates(res)
tbl=m.parse_std_table([['지역구분','항목','기준값'],['청정','BOD','10'],['나','TOC','40'],['하수처리구역내','BOD','20'],['*','생태독성','2'],['가','SS','30']])
m.apply_std_table(res,tbl)
py={r['doc']['파일명']:{'rows':[{**{c:r2.get(c,'') for c in m.COLUMNS},'_items':r2['_items']} for r2 in r['rows']],'tables':r['tables'],'body':r['doc']['본문']} for r in res}
py['__miss']=m.missing_std_pairs(res)
js=json.load(open(sys.argv[2],encoding='utf-8'))
diff=0; n=0
for k in js:
    if k=='__miss': continue
    a,b=js[k],py.get(k)
    if b is None: print('MISSING',k); diff+=1; continue
    if len(a['rows'])!=len(b['rows']): print('ROWCOUNT',k); diff+=1; continue
    for x,y in zip(a['rows'],b['rows']):
        for c in x:
            n+=1
            if x[c]!=y[c]:
                diff+=1
                if diff<15: print('DIFF',k[:30],x.get('시료번호'),c,'|',str(x[c])[:80],'→',str(y[c])[:80])
    if a['tables']!=b['tables']: diff+=1; print('TABLES',k[:30])
    if a['body']!=b['body']: diff+=1; print('BODY',k[:30])
jm=sorted(json.dumps(x,ensure_ascii=False,sort_keys=True) for x in js['__miss']); pm=sorted(json.dumps(x,ensure_ascii=False,sort_keys=True) for x in py['__miss'])
print('docs',len(js)-1,'compared fields',n,'diffs',diff,'| missing-pairs equal:',jm==pm)
