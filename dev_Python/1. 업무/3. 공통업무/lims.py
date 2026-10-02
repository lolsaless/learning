# -*- coding: utf-8 -*-
"""
장비입력 도우미
- 엑셀(.xlsx/.csv)을 불러와, 선택한 행을 장비관리 시스템의 [장비코드 등록] 창에 채워 넣습니다.
- [추가]와 [저장]은 사용자가 직접 누릅니다.
- Edge IE 모드 화면을 윈도우 COM으로 찾아 페이지 안에서 값을 입력합니다.

필요: Windows, Python 3, pywin32, openpyxl
    (확인)  python -c "import win32com, openpyxl"
"""
import csv
import datetime as dt
import json
import os
import re
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import pythoncom
    import win32con
    import win32gui
    import win32com.client
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

# ------------------------------------------------------------------ 설정
TARGET_HOST = "105.0.1.35"          # 장비관리 시스템 주소

# 엑셀 머리글 → 시스템 입력칸 id (보내주신 소스 기준)
TEXT_ID = {
    "품명": "EQUIP_NM",
    "모델명": "MODEL_NM",
    "관리번호": "MGMT_NO",
    "제조사": "MAKR_NM",
    "도입일": "INST_DT",
    "도입가": "INST_AMT",
    "용도및특이사항": "USE_PURP",
    "주요성능및특징": "MAIN_PERF",
    "비고": "REMARK",
}
SELECT_FIELDS = ["상태구분", "도입처"]           # 상태구분=STAT_TY, 도입처=ENTP_ID(select2)
AUTO_FIELDS = ["전화", "주소"]                  # 도입처를 고르면 시스템이 자동으로 채움(읽기전용)
ALL_FIELDS = list(TEXT_ID) + SELECT_FIELDS + AUTO_FIELDS

ALIAS = {
    "장비명": "품명", "제조회사": "제조사", "구입일": "도입일", "구입가": "도입가",
    "구입처": "도입처", "상태": "상태구분", "연락처": "전화", "전화번호": "전화",
    "용도": "용도및특이사항", "특이사항": "용도및특이사항", "주요성능": "주요성능및특징",
    "비고사항": "비고",
}
MAXLEN = {"EQUIP_NM": 50, "MODEL_NM": 50, "MGMT_NO": 50, "MAKR_NM": 50, "REMARK": 50}


def norm(s):
    return re.sub(r"[\s\*\(\)（）:：]", "", str(s if s is not None else ""))


def cell_str(v):
    if v is None:
        return ""
    if isinstance(v, (dt.datetime, dt.date)):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def fmt_date(s):
    m = re.match(r"^\s*(\d{4})[.\-/년\s]*(\d{1,2})[.\-/월\s]*(\d{1,2})", s)
    if m:
        return "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3)))
    return s


def fmt_amt(s):
    digits = re.sub(r"[^\d]", "", s.split(".")[0])
    return "{:,}".format(int(digits)) if digits else ""


# ------------------------------------------------------------------ 엑셀 읽기
def read_rows(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        for enc in ("utf-8-sig", "cp949"):
            try:
                with open(path, newline="", encoding=enc) as f:
                    return [row for row in csv.reader(f)]
            except UnicodeDecodeError:
                continue
        raise ValueError("CSV 인코딩을 읽을 수 없습니다.")
    if ext == ".xls":
        raise ValueError(".xls(구버전)는 지원하지 않습니다. 엑셀에서 .xlsx로 다른 이름 저장 후 불러오세요.")
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb.worksheets[0]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    return rows


def load_records(path):
    rows = [[cell_str(c) for c in r] for r in read_rows(path)]
    rows = [r for r in rows if any(c for c in r)]
    if len(rows) < 2:
        raise ValueError("머리글 행과 데이터 행이 필요합니다.")
    header, cols, unknown = rows[0], [], []
    for h in header:
        n = norm(h)
        n = ALIAS.get(n, n)
        if n in ALL_FIELDS:
            cols.append(n)
        else:
            cols.append(None)
            if n:
                unknown.append(h)
    if not any(cols):
        raise ValueError("첫 행에서 항목명(품명, 모델명 …)을 찾지 못했습니다.")
    recs = []
    for r in rows[1:]:
        d = {}
        for i, f in enumerate(cols):
            if f and i < len(r):
                d[f] = r[i]
        if any(d.values()):
            recs.append(d)
    return recs, unknown, [c for c in cols if c]


# ------------------------------------------------------------------ IE 모드 화면 연결
def find_ie_docs():
    """열려 있는 IE(IE 모드) 화면 중 장비관리 시스템 문서를 찾는다."""
    hwnds = []

    def _child(h, _):
        try:
            if win32gui.GetClassName(h) == "Internet Explorer_Server":
                hwnds.append(h)
        except Exception:
            pass
        return True

    def _top(h, _):
        try:
            win32gui.EnumChildWindows(h, _child, None)
        except Exception:
            pass
        return True

    win32gui.EnumWindows(_top, None)
    msg = win32gui.RegisterWindowMessage("WM_HTML_GETOBJECT")
    docs = []
    for h in dict.fromkeys(hwnds):
        try:
            _, res = win32gui.SendMessageTimeout(h, msg, 0, 0, win32con.SMTO_ABORTIFHUNG, 1000)
            if not res:
                continue
            obj = pythoncom.ObjectFromLresult(res, pythoncom.IID_IDispatch, 0)
            doc = win32com.client.Dispatch(obj)
            url = str(doc.url)
            docs.append((url, doc))
        except Exception:
            continue
    return docs


def run_js(doc, code):
    """문서 안에서 자바스크립트를 실행하고, 결과(data-eqh 속성)를 돌려받는다."""
    root = doc.documentElement
    root.setAttribute("data-eqh", "")
    try:
        s = doc.createElement("script")
        s.text = code
        heads = doc.getElementsByTagName("head")
        parent = heads.item(0) if heads.length else root
        parent.appendChild(s)
        parent.removeChild(s)
    except Exception:
        pass
    res = root.getAttribute("data-eqh")
    if not res:
        try:
            doc.parentWindow.execScript(code, "JavaScript")
        except Exception:
            pass
        for _ in range(5):
            res = root.getAttribute("data-eqh")
            if res:
                break
            time.sleep(0.1)
    return str(res or "")


JS_COMMON = r"""
function norm(s){return String(s==null?'':s).replace(/[\s\*\(\)]/g,'');}
function findWin(w){
 try{if(w.document&&w.document.getElementById('authModal')){return w;}}catch(e){}
 try{for(var i=0;i<w.frames.length;i++){var r=findWin(w.frames[i]);if(r){return r;}}}catch(e){}
 return null;}
"""

JS_FILL = r"""(function(){
var D=__DATA__,out='';
""" + JS_COMMON + r"""
function pick(sel,txt){
 var o=sel.options,i,n=norm(txt);
 for(i=0;i<o.length;i++){if(o[i].value!==''&&(norm(o[i].text)===n||o[i].value===txt)){return o[i].value;}}
 for(i=0;i<o.length;i++){if(o[i].value!==''&&n&&norm(o[i].text).indexOf(n)>=0){return o[i].value;}}
 return null;}
try{
 var w=findWin(window);
 if(!w){out='NOTFOUND';}
 else{
  var d=w.document,jq=w.jQuery,m=d.getElementById('authModal');
  if(m.style.display==='none'||!m.offsetWidth){
   out='ERR|[장비코드 등록] 창이 열려 있지 않습니다.\n시스템에서 [추가]를 먼저 눌러주세요.';}
  else if(d.getElementById('EQUIP_ID').value){
   out='ERR|지금 창은 이미 저장된 장비(또는 수정 화면)입니다.\n덮어쓰기를 막기 위해 입력하지 않았습니다.\n창을 닫고 [추가]를 다시 눌러주세요.';}
  else{
   var warn=[],k,el,v;
   if(D.stat){v=pick(d.getElementById('STAT_TY'),D.stat);
    if(v!==null){jq('#STAT_TY').val(v).trigger('change');}else{warn.push('상태구분 "'+D.stat+'" 이(가) 목록에 없음');}}
   if(D.entp){v=pick(d.getElementById('ENTP_ID'),D.entp);
    if(v!==null){jq('#ENTP_ID').val(v).trigger('change');}else{warn.push('도입처 "'+D.entp+'" 이(가) 목록에 없음 → 직접 선택');}}
   for(k in D.text){if(D.text.hasOwnProperty(k)){el=d.getElementById(k);
    if(el){el.value=D.text[k];el.style.backgroundColor='#fff9c4';}else{warn.push(k+' 칸을 찾지 못함');}}}
   out='OK|'+warn.join('\n');
  }
 }
}catch(e){out='ERR|스크립트 오류: '+(e.message||e);}
document.documentElement.setAttribute('data-eqh',out);
})();"""

JS_CHECK = r"""(function(){
var out='';
""" + JS_COMMON + r"""
try{var w=findWin(window);
 if(!w){out='NOTFOUND';}
 else{var m=w.document.getElementById('authModal');
  out=(m.style.display==='none'||!m.offsetWidth)?'FOUND|닫힘':'FOUND|열림';}
}catch(e){out='ERR|'+(e.message||e);}
document.documentElement.setAttribute('data-eqh',out);
})();"""


def send_to_system(js):
    """시스템 화면을 찾아 js를 실행. (결과문자열, 설명) 반환"""
    docs = [(u, d) for u, d in find_ie_docs() if TARGET_HOST in u]
    if not docs:
        return None, ("장비관리 시스템 창(IE 모드)을 찾지 못했습니다.\n"
                      "Edge에서 시스템이 열려 있는지 확인하세요.")
    ran = False
    for _, doc in docs:
        res = run_js(doc, js)
        if res:
            ran = True
        if res and res != "NOTFOUND":
            return res, ""
    if not ran:
        return None, ("시스템 창은 찾았지만 스크립트 실행이 막혀 있습니다.\n"
                      "(보안 설정 문제일 수 있습니다. 화면을 캡처해 알려주세요.)")
    return None, "[장비/물품 > 장비코드등록] 메뉴 화면을 먼저 열어주세요."


# ------------------------------------------------------------------ 화면(GUI)
class App:
    def __init__(self, root):
        self.root = root
        self.recs, self.done = [], set()
        root.title("장비입력 도우미")
        root.geometry("560x640")
        root.attributes("-topmost", True)
        font = ("Malgun Gothic", 10)
        style = ttk.Style()
        style.configure("Treeview", font=font, rowheight=24)
        style.configure("Treeview.Heading", font=("Malgun Gothic", 10, "bold"))

        top = tk.Frame(root)
        top.pack(fill="x", padx=8, pady=6)
        tk.Button(top, text="엑셀 불러오기", font=font, command=self.open_file).pack(side="left")
        tk.Button(top, text="연결 확인", font=font, command=self.check).pack(side="left", padx=6)
        self.topmost = tk.BooleanVar(value=True)
        tk.Checkbutton(top, text="항상 위", font=font, variable=self.topmost,
                       command=lambda: root.attributes("-topmost", self.topmost.get())).pack(side="right")
        self.info = tk.Label(root, text="엑셀 파일을 불러오세요. (첫 행 = 머리글)", font=font, anchor="w", fg="#555")
        self.info.pack(fill="x", padx=8)

        mid = tk.Frame(root)
        mid.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("no", "name", "model", "mgmt", "done")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", selectmode="browse")
        for c, t, w in zip(cols, ("No", "품명", "모델명", "관리번호", "입력"), (40, 170, 140, 110, 45)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="center" if c in ("no", "done") else "w")
        sb = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.tag_configure("done", background="#e8f5e9")
        self.tree.bind("<Double-1>", lambda e: self.fill())

        tk.Button(root, text="선택 행 입력  (행 더블클릭도 가능)", font=("Malgun Gothic", 11, "bold"),
                  bg="#2e7d32", fg="white", command=self.fill).pack(fill="x", padx=8, pady=4)
        tk.Label(root, text="순서: 시스템 [추가] → 행 선택 → 입력 → 확인 후 시스템 [저장] → 창 닫고 다시 [추가]",
                 font=("Malgun Gothic", 9), fg="#777").pack(fill="x", padx=8)
        self.msg = tk.Text(root, height=7, font=font, bg="#f5f5f5", relief="flat", wrap="word")
        self.msg.pack(fill="x", padx=8, pady=6)
        self.say("준비됨.")
        if not HAS_WIN32:
            self.say("pywin32가 설치되어 있지 않습니다.\n명령창에서: pip install pywin32", err=True)

    def say(self, text, err=False):
        self.msg.configure(state="normal", fg="#c62828" if err else "#1b5e20")
        self.msg.delete("1.0", "end")
        self.msg.insert("1.0", text)
        self.msg.configure(state="disabled")

    def open_file(self):
        path = filedialog.askopenfilename(title="엑셀 파일 선택",
                                          filetypes=[("엑셀/CSV", "*.xlsx *.xlsm *.csv"), ("모든 파일", "*.*")])
        if not path:
            return
        try:
            recs, unknown, cols = load_records(path)
        except Exception as e:
            self.say("불러오기 실패: %s" % e, err=True)
            return
        self.recs, self.done = recs, set()
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(recs):
            self.tree.insert("", "end", iid=str(i),
                             values=(i + 1, r.get("품명", ""), r.get("모델명", ""), r.get("관리번호", ""), ""))
        if recs:
            self.tree.selection_set("0")
        self.info.configure(text="%s  |  %d건" % (os.path.basename(path), len(recs)))
        notes = ["불러오기 완료. 인식된 항목: " + ", ".join(cols)]
        if unknown:
            notes.append("무시된 열: " + ", ".join(unknown))
        if any(c in AUTO_FIELDS for c in cols):
            notes.append("※ 전화·주소는 도입처를 고르면 시스템이 자동으로 채우므로 엑셀 값은 쓰지 않습니다.")
        self.say("\n".join(notes))

    def build_data(self, r):
        text, warn = {}, []
        for f, fid in TEXT_ID.items():
            v = r.get(f, "")
            if f == "도입일" and v:
                v = fmt_date(v)
            if f == "도입가" and v:
                v = fmt_amt(v)
            if v:
                text[fid] = v
                if fid in MAXLEN and len(v) > MAXLEN[fid]:
                    warn.append("%s: %d자 (최대 %d자) → 저장 시 오류 가능" % (f, len(v), MAXLEN[fid]))
        return {"text": text, "stat": r.get("상태구분", ""), "entp": r.get("도입처", "")}, warn

    def check(self):
        if not HAS_WIN32:
            self.say("pywin32가 필요합니다: pip install pywin32", err=True)
            return
        res, why = send_to_system(JS_CHECK)
        if res is None:
            self.say(why, err=True)
        elif res.startswith("FOUND"):
            self.say("시스템 연결 성공. 등록 창 상태: " + res.split("|", 1)[1])
        else:
            self.say(res, err=True)

    def fill(self):
        if not HAS_WIN32:
            self.say("pywin32가 필요합니다: pip install pywin32", err=True)
            return
        sel = self.tree.selection()
        if not self.recs or not sel:
            self.say("먼저 엑셀을 불러오고 입력할 행을 선택하세요.", err=True)
            return
        i = int(sel[0])
        data, warn = self.build_data(self.recs[i])
        js = JS_FILL.replace("__DATA__", json.dumps(data, ensure_ascii=True))
        try:
            res, why = send_to_system(js)
        except Exception as e:
            self.say("연결 오류: %s" % e, err=True)
            return
        if res is None:
            self.say(why, err=True)
            return
        kind, _, detail = res.partition("|")
        if kind != "OK":
            self.say(detail or res, err=True)
            return
        self.done.add(i)
        self.tree.set(str(i), "done", "✔")
        self.tree.item(str(i), tags=("done",))
        nxt = next((j for j in range(i + 1, len(self.recs)) if j not in self.done), None)
        if nxt is not None:
            self.tree.selection_set(str(nxt))
            self.tree.see(str(nxt))
        warn += [w for w in detail.split("\n") if w]
        text = "%d번 [%s] 입력 완료 → 내용 확인 후 시스템에서 [저장]" % (i + 1, self.recs[i].get("품명", ""))
        if warn:
            text += "\n\n※ 확인 필요\n- " + "\n- ".join(warn)
        self.say(text, err=bool(warn))


if __name__ == "__main__":
    if HAS_WIN32:
        pythoncom.CoInitialize()
    root = tk.Tk()
    App(root)
    root.mainloop()
