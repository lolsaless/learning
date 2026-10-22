import os, sys, shutil, json, subprocess, importlib.util, tkinter
from tkinter import messagebox, filedialog, ttk
SC='/tmp/claude-0/-home-claude/81a86257-f3c2-5b6c-91e1-a77386e01165/scratchpad/guitest'
FD=os.path.join(SC,'공문'); shutil.rmtree(FD, ignore_errors=True); shutil.copytree('/home/claude/odt-app/test/odt', FD)
open(os.path.join(FD,'broken.odt'),'wb').write(b'12345')
os.environ['APPDATA']=SC
spec=importlib.util.spec_from_file_location('m','/home/claude/odt-app/py/공문추출기.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
LOG=[]
messagebox.askyesno=lambda t,msg,**k: (LOG.append(('ask',t)), True)[1]
messagebox.showinfo=lambda t,msg,**k: LOG.append(('info',t,msg))
messagebox.showwarning=lambda t,msg,**k: LOG.append(('warn',t,msg))
messagebox.showerror=lambda t,msg,**k: LOG.append(('err',t,msg))
filedialog.asksaveasfilename=lambda **k: os.path.join(SC,'export.xlsx')
def shot(name): subprocess.run(['import','-window','root',os.path.join(SC,name+'.png')])
def widgets(w):
    for c in w.winfo_children():
        yield c; yield from widgets(c)
orig=tkinter.Tk.mainloop
def mainloop(self, n=0):
    root=self
    def find(cls, text=None):
        for w in widgets(root):
            if isinstance(w, cls) and (text is None or str(w.cget('text')).startswith(text)): return w
    def click_chk(tree, iid):
        tree.see(iid); root.update_idletasks(); root.update()
        bb=tree.bbox(iid,'#1')
        if not bb:
            ks=list(tree.get_children()); tree.yview_moveto(max(0,(ks.index(iid)-2)/len(ks))); root.update_idletasks(); root.update(); bb=tree.bbox(iid,'#1')
        x,y,w,h=bb; tree.event_generate('<Button-1>', x=x+w//2, y=y+h//2); root.update()
    def step1():
        print("step1 start", flush=True)
        tree=find(ttk.Treeview); kids=tree.get_children()
        print('rows', len(kids), flush=True); print('first', tree.item(kids[0],'values')[:8])
        st=[w for w in widgets(root) if isinstance(w, ttk.Label)][-1].cget('textvariable'); print('stats', root.getvar(st))
        shot('01_main')
        for k in (0,1):
            firsts=[i for i in tree.get_children() if tree.set(i,'chk') in ('☐','☑')]
            click_chk(tree, firsts[k])
        print('status checked', list(json.load(open(os.path.join(FD,'_처리상태.json'),encoding='utf-8'))['checked']))
        print('btn', find(ttk.Button,'완료 체크한').cget('text'))
        find(ttk.Button,'완료 체크한').invoke(); root.update()
        print('done dir', sorted(os.listdir(os.path.join(FD,'성적처리완료'))), '| last log', LOG[-1][:2])
        # 중복 공문 체크
        tree=find(ttk.Treeview)
        dup=[i for i in tree.get_children() if '7-10-2' in tree.set(i,'시료번호') and tree.set(i,'chk')][0]
        print('dup row', tree.item(dup,'values')[:7], 'bbox', tree.bbox(dup,'#1'), flush=True)
        click_chk(tree, dup); root.update()
        print('status after dup', list(json.load(open(os.path.join(FD,'_처리상태.json'),encoding='utf-8'))['checked']), flush=True)
        print('marks', [tree.item(i,'values')[:7] for i in tree.get_children() if tree.set(i,'chk')=='☑'], flush=True)
        print('checked marks after dup', sum(1 for i in tree.get_children() if tree.set(i,'chk')=='☑'))
        shot('02_checked')
        # 상세 창
        tree.selection_set(tree.get_children()[3]); tree.focus(tree.get_children()[3]); tree.event_generate('<Return>'); root.update()
        shot('03_detail')
        for w in root.winfo_children():
            if isinstance(w, tkinter.Toplevel): w.destroy()
        # 되돌리기
        vb=[w for w in widgets(root) if isinstance(w, ttk.Combobox)][1]
        vb.set(vb['values'][3]); vb.event_generate('<<ComboboxSelected>>'); root.update()
        tree=find(ttk.Treeview); ks=tree.get_children(); print('done view rows', len(ks), tree.set(ks[0],'chk'))
        shot('04_doneview')
        click_chk(tree, ks[0]); root.update()
        print('after restore done dir', sorted(os.listdir(os.path.join(FD,'성적처리완료'))))
        vb.set(vb['values'][0]); vb.event_generate('<<ComboboxSelected>>'); root.update()
        # 엑셀, 기준표
        find(ttk.Button,'엑셀 저장').invoke(); print('excel', os.path.exists(os.path.join(SC,'export.xlsx')), LOG[-1][:2])
        find(ttk.Button,'기준표 양식').invoke(); print('std', LOG[-1][2] if len(LOG[-1])>2 else LOG[-1])
        # 기준표 값 채우기 → 새로고침
        rows=m.read_xlsx_rows(open(os.path.join(FD,'기준표.xlsx'),'rb').read())
        vals={'BOD':'10','TOC':'25','SS':'10','T-N':'20','T-P':'2','n-H(광)':'5','ABS':'5','생태독성':'2'}
        out=[[r[0],r[1],vals.get(r[1],''),r[3]] for r in rows[1:]]
        open(os.path.join(FD,'기준표.xlsx'),'wb').write(m.build_xlsx([{'name':'기준표','columns':[{'header':h} for h in ['지역구분','항목','기준값','단위']],'rows':out}]))
        find(ttk.Button,'새로고침').invoke(); root.update()
        st=[w for w in widgets(root) if isinstance(w, ttk.Label)][-1].cget('textvariable'); print('stats after std', root.getvar(st))
        # 확인필요만
        cb=find(ttk.Checkbutton,'확인필요만'); cb.invoke(); root.update(); print('warn-only rows', len(find(ttk.Treeview).get_children()))
        shot('05_warn')
        # v1.1: 정렬·열 순서·원본 보기
        tree=find(ttk.Treeview)
        print('display cols', list(tree['displaycolumns']))
        firsts=[tree.set(i,'접수일') for i in tree.get_children() if tree.set(i,'접수일')]
        print('접수일 desc', firsts==sorted(firsts, reverse=True), firsts[:3])
        opened=[]
        import webbrowser
        webbrowser.open=lambda u,*a,**k: opened.append(u)
        m.open_with_default_app=lambda p: opened.append('APP:'+p)
        k=[i for i in tree.get_children() if '동두천' in tree.set(i,'시료번호')][0]
        tree.selection_set(k); root.update()
        print('preview btn', find(ttk.Button,'원본 미리보기').cget('state'))
        find(ttk.Button,'원본 미리보기').invoke(); find(ttk.Button,'원본 파일 열기').invoke()
        print('opened', [o[-60:] for o in opened])
        print('동두천 row', tree.item(k,'values')[1:9])
        tree.focus(k); tree.event_generate('<Return>'); root.update(); shot('06_detail11')
        for w in root.winfo_children():
            if isinstance(w, tkinter.Toplevel): w.destroy()
        root.after(200, root.destroy)
    def step_safe():
        try: step1()
        except Exception as e:
            import traceback; traceback.print_exc(); root.destroy()
    root.after(1500, step_safe)
    orig(self, n)
tkinter.Tk.mainloop=mainloop
m.run_gui(FD)
print('LOG', [x[:2] for x in LOG])
