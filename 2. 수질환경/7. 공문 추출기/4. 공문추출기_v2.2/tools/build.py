# -*- coding: utf-8 -*-
"""공문추출기 빌드 — 소스 폴더의 부품을 빌드목록.txt 순서대로 이어 붙여 공문추출기.html 한 파일을 만든다.

실행:  python tools/build.py            (보통은 빌드_windows.bat / 빌드_mac.command 를 더블클릭)
옵션:  --check   파일을 만들지 않고 검사만
       --watch   부품을 고칠 때마다 자동으로 다시 빌드 (멈추려면 Ctrl+C)

하는 일
  1. 빌드목록.txt 읽기 → 빠진 파일·목록에 없는 부품 확인
  2. 이어 붙이기 (.js·.css 앞에는 /* ===== 경로 ===== */ 표시를 넣어 오류 위치를 찾기 쉽게)
  3. 검사: </script 금지 · 같은 묶음 안 이름 중복 · (Node가 있으면) 스크립트 문법 · 버전 표기
  4. 이전 결과를 빌드결과/이전/ 에 보관(최근 5개) → 공문추출기.html 저장
  5. 시험용 엔진 묶음(시험/_엔진_묶음.js), 부품지도(문서/부품지도.md) 갱신
표준 라이브러리만 사용 (Python 3.8 이상).
"""
import os, re, sys, shutil, subprocess, tempfile, time, datetime

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, '소스')
LIST = os.path.join(SRC, '빌드목록.txt')
OUT = os.path.join(ROOT, '공문추출기.html')
BACKUP_DIR = os.path.join(ROOT, '빌드결과', '이전')
ENGINE_BUNDLE = os.path.join(ROOT, '시험', '_엔진_묶음.js')
PART_MAP = os.path.join(ROOT, '문서', '부품지도.md')
KEEP_BACKUPS = 5
SCRIPT_GROUPS = ('엔진', '화면')          # 한 함수 안에 이어 붙는 묶음 → 이름 중복 검사
SKIP_MAP_DIRS = ('10_외부라이브러리',)


def read(path):
    # newline='' : 줄바꿈(LF/CRLF)을 바꾸지 않음 → build_simple.sh·ps1 과 같은 결과
    with open(path, 'r', encoding='utf-8-sig', newline='') as f:
        return f.read()


def read_list():
    """빌드목록.txt → [(묶음, 경로)]"""
    items, group = [], ''
    for raw in read(LIST).splitlines():  # 줄 끝 \r 도 함께 제거됨
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('[') and line.endswith(']'):
            group = line[1:-1]
            continue
        items.append((group, line.replace('\\', '/')))
    return items


def piece(rel, text):
    """한 부품의 출력 조각 (build_simple.sh / build_simple.ps1 과 같은 규칙)"""
    if not text.endswith('\n'):
        text += '\n'
    if rel.endswith('.js') or rel.endswith('.css'):
        return '/* ===== ' + rel + ' ===== */\n' + text
    return text


DECL = re.compile(r'^(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)|^(?:const|let|var|class)\s+([A-Za-z_$][\w$]*)', re.M)


def top_names(text):
    return [a or b for a, b in DECL.findall(text)]


def find_node():
    for name in ('node', 'node.exe'):
        p = shutil.which(name)
        if p:
            return p
    return None


def syntax_check(html, node):
    """<script> 묶음마다 node --check"""
    errors = []
    blocks = re.findall(r'<script>\n(.*?)</script>', html, re.S)
    for i, js in enumerate(blocks, 1):
        fd, tmp = tempfile.mkstemp(suffix='.js')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(js)
        try:
            r = subprocess.run([node, '--check', tmp], capture_output=True, text=True, encoding='utf-8', errors='replace')
            if r.returncode != 0:
                msg = r.stderr.strip()
                m = re.search(r':(\d+)\n', msg)
                where = ''
                if m:  # 몇 번째 줄 → 어느 부품인지
                    ln = int(m.group(1)); cur = '?'
                    for k, l in enumerate(js.split('\n'), 1):
                        mm = re.match(r'/\* ===== (.+?) ===== \*/', l)
                        if mm:
                            cur, start = mm.group(1), k
                        if k == ln:
                            where = f' → 부품 {cur} 의 {ln - start}번째 줄 근처'
                            break
                errors.append(f'스크립트 {i}번 묶음 문법 오류{where}\n{msg[:600]}')
        finally:
            os.remove(tmp)
    return errors


def part_header(text):
    """부품 머리말에서 제목·하는 일·주요 이름·고칠 때"""
    h = {}
    m = re.search(r'\[(.+?)\]\s*(.*)', text[:800])
    if m:
        h['title'] = m.group(2).strip()
    for key, lab in (('does', '하는 일'), ('names', '주요 이름'), ('edit', '이럴 때 고침')):
        mm = re.search(lab + r'\s*:\s*(.+)', text[:1500])
        if mm:
            h[key] = mm.group(1).strip()
    if 'title' in h:
        h['title'] = re.sub(r'\s*\*/\s*$', '', h['title'])
    return h


# 머리말을 넣을 수 없는 HTML 틀 부품 설명
FIXED_NOTES = {
    '00_틀/01_문서머리.html': ('문서 시작, 브라우저 탭 제목(title)', 'title', '브라우저 탭 제목'),
    '00_틀/02_화면구성.html': ('화면 배치: 상단 버튼, 도구줄(검색·필터), 알림줄, 표·상세 패널 자리, 하단 버튼, 확인 창·달력 자리, 버전 표시', 'btnPick, fState, fWm, banner, grid, detail, btnDone, datePop, class="ver"', '버튼·필터를 새로 넣거나 이름을 바꿀 때, 버전 표시'),
    '00_틀/03_스크립트경계.html': ('스크립트 묶음 사이 경계', '-', '고치지 않음'),
    '00_틀/09_문서끝.html': ('문서 끝', '-', '고치지 않음'),
}
QUICK = [
    ('새 항목 표기(예: "노르말헥산")가 미등록 항목으로 나옴', '20_엔진/01_설정_사전.js', 'ITEM_DICT'),
    ('시료 표를 못 찾음("시료표 미인식"), 새 열 이름', '20_엔진/12_접수공문_시료표.js', 'classify, pickSampleCol'),
    ('항목 안 기준 표기(BOD(20이하) 등)가 잘못 나뉨', '20_엔진/13_접수공문_항목_기준.js', 'STD_PAREN, splitItemStd'),
    ('의뢰기관·의뢰자·발신명의·시행번호가 틀림', '20_엔진/11_접수공문_머리꼬리.js', 'parseFooter, deriveOrg'),
    ('첨부 HWPX 시료 목록을 못 읽음', '20_엔진/22_첨부_시료목록.js', 'samplesFromAttachments'),
    ('시행공문이 의뢰공문과 안 이어짐', '20_엔진/31_시행공문.js', 'REL_RE, parseReply'),
    ('성적서 양식이 바뀌어 값이 비거나 틀림', '20_엔진/41_시험성적서.js', 'parseReportPage'),
    ('짝짓기(일치/일부) 조건', '20_엔진/42_대조.js', 'matchReport'),
    ('항목별 처리기간 기본값, 계산 규칙', '20_엔진/51_처리기한.js', 'STD_DAYS, deadline'),
    ('다음 해 공휴일 내장', '20_엔진/52_공휴일.js', 'HOLIDAYS_BUILTIN'),
    ('공문별 폴더 이름 규칙', '20_엔진/71_폴더이름.js', 'caseFolderName'),
    ('표 기본 열·순서, 설정 기본값(임박 일수 등)', '40_화면/02_설정_열_기본값_상태.js', 'COLS, DEFAULT_SETTINGS'),
    ('보기 필터 추가', '40_화면/07_필터_정렬.js (+ 00_틀/02_화면구성.html 의 fState)', 'visibleDocs'),
    ('표 칸에 보이는 글자·색', '40_화면/08_목록표_그리기.js', 'cellOf'),
    ('상세 패널 구역 내용', '40_화면/09_상세_추출결과.js', 'dueSection 등'),
    ('워터마크 모양·위치', '40_화면/10_원본보기_워터마크.js', 'WM_CSS, wmHtml'),
    ('처리 완료 때 옮기는 규칙', '40_화면/12_처리완료_되돌리기.js', 'processChecked'),
    ('이력 문서에 넣는 내용·순서', '40_화면/15_이력문서.js', 'historyBlocks'),
    ('이력 문서 글꼴·여백·쪽 배치', '30_문서생성/02_Word_PDF_그림.js', 'buildDocx, layoutPages'),
    ('엑셀 열·색', '40_화면/16_엑셀_기준표양식_열선택.js', 'exportExcel'),
    ('색·글꼴·간격(디자인)', '01_디자인/*.css', '01_색상_기본글꼴.css 의 --accent 등'),
    ('새 버튼 만들기', '00_틀/02_화면구성.html → 기능 부품 → 40_화면/18_이벤트_연결.js', 'bindUi'),
]


def write_part_map(items, texts):
    lines = ['# 부품지도 (자동 생성 — tools/build.py 가 빌드할 때마다 고쳐 씀, 직접 고치지 말 것)', '',
             '고칠 내용이 생기면 **이 표에서 부품을 찾아 그 파일만** 고친 뒤 빌드한다. 자세한 방법은 `문서/수정방법.md`.',
             '부품 설명은 각 파일 맨 위 머리말(하는 일·주요 이름·이럴 때 고침)에서 가져온다. 머리말을 고치면 이 표도 바뀐다.', '',
             '## 자주 하는 수정 → 고칠 부품', '', '| 이런 수정 | 고칠 부품 (소스/…) | 찾을 이름 |', '|---|---|---|']
    lines += [f'| {a} | `{b}` | {c} |' for a, b, c in [q for q in QUICK if isinstance(q, tuple)]]
    lines.append('')
    groups = {}
    for g, rel in items:
        if rel in groups.get(g, []):
            continue
        groups.setdefault(g, []).append(rel)
    names = {'틀': '화면 틀(HTML)', '디자인': '디자인(CSS)', '엔진': '엔진 — 파일 읽기·해석·계산 (화면과 무관, 시험 가능)',
             '문서생성': '문서 생성(엑셀·Word·PDF)', '화면': '화면 — 버튼·표·패널·폴더 작업', '외부라이브러리': '외부 라이브러리 (고치지 않음)'}
    for g in ('틀', '디자인', '엔진', '문서생성', '화면'):
        if g not in groups:
            continue
        lines += [f'## {names.get(g, g)}', '', '| 파일 | 줄 | 하는 일 | 주요 이름 | 이럴 때 고침 |', '|---|---|---|---|---|']
        for rel in groups[g]:
            t = texts[rel]
            h = part_header(t)
            if rel in FIXED_NOTES:
                h = dict(zip(('does', 'names', 'edit'), FIXED_NOTES[rel]))
            does = h.get('does') or h.get('title', '')
            lines.append(f"| `{rel}` | {t.count(chr(10))} | {does} | {h.get('names', '')} | {h.get('edit', '')} |")
        lines.append('')
    os.makedirs(os.path.dirname(PART_MAP), exist_ok=True)
    with open(PART_MAP, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines))


def backup():
    if not os.path.exists(OUT):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    dst = os.path.join(BACKUP_DIR, f'공문추출기_{stamp}.html')
    shutil.copy2(OUT, dst)
    olds = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith('공문추출기_') and f.endswith('.html'))
    for f in olds[:-KEEP_BACKUPS]:
        try:
            os.remove(os.path.join(BACKUP_DIR, f))
        except OSError:
            pass
    return dst


def build(check_only=False):
    t0 = time.time()
    errors, warns = [], []
    if not os.path.exists(LIST):
        print('[오류] 소스/빌드목록.txt 가 없습니다.'); return 1
    items = read_list()
    texts = {}
    for g, rel in items:
        p = os.path.join(SRC, rel)
        if not os.path.isfile(p):
            errors.append(f'목록에 있지만 파일이 없음: 소스/{rel}')
            continue
        if rel not in texts:
            texts[rel] = read(p)
    # 목록에 없는 부품 (만들어 놓고 목록에 안 넣은 경우)
    listed = {rel for _, rel in items}
    for d, _, fs in os.walk(SRC):
        for f in fs:
            rel = os.path.relpath(os.path.join(d, f), SRC).replace('\\', '/')
            if rel.endswith(('.js', '.css', '.html')) and rel not in listed:
                warns.append(f'목록에 없는 부품(빌드에 안 들어감): 소스/{rel}')
    if errors:
        return report(errors, warns, t0)
    # </script 금지 (스크립트가 중간에 끊김)
    for g, rel in items:
        if rel.endswith('.js') and re.search(r'</script', texts[rel], re.I):
            errors.append(f'소스/{rel}: 글자 "</script" 가 있으면 화면이 깨집니다. "<\\/script" 로 쓰세요.')
    # 같은 묶음 안 이름 중복
    for grp in SCRIPT_GROUPS:
        seen = {}
        for g, rel in items:
            if g != grp or not rel.endswith('.js'):
                continue
            for n in top_names(texts[rel]):
                if n in seen and seen[n] != rel:
                    errors.append(f'[{grp}] 이름 "{n}" 이(가) 두 부품에 있음: {seen[n]} / {rel}')
                elif n in seen:
                    errors.append(f'[{grp}] 이름 "{n}" 이(가) {rel} 안에 두 번 있음')
                seen.setdefault(n, rel)
    html = ''.join(piece(rel, texts[rel]) for _, rel in items)
    engine = ''.join(piece(rel, texts[rel]) for g, rel in items if g == '엔진')
    # 문법 검사
    node = find_node()
    if node:
        errors += syntax_check(html, node)
    else:
        warns.append('Node.js 가 없어 스크립트 문법 검사를 건너뜀 (다른 검사는 함). 고친 뒤 화면을 열어 오류가 없는지 확인하세요.')
    # 버전 표기 일치
    ev = re.search(r"ENGINE_VERSION = '([\d.]+)'", engine)
    hv = re.search(r'<span class="ver">v([\d.]+)</span>', html)
    if ev and hv and ev.group(1) != hv.group(1):
        warns.append(f'버전 표기가 다름: 화면 v{hv.group(1)} / 엔진 {ev.group(1)} (00_틀/02_화면구성.html, 20_엔진/99_엔진_끝.js)')
    if errors or check_only:
        return report(errors, warns, t0, check_only=check_only)
    bk = backup()
    with open(OUT, 'w', encoding='utf-8', newline='') as f:
        f.write(html)
    os.makedirs(os.path.dirname(ENGINE_BUNDLE), exist_ok=True)
    with open(ENGINE_BUNDLE, 'w', encoding='utf-8', newline='') as f:
        f.write(engine)
    write_part_map(items, texts)
    print(f'[완료] 공문추출기.html  ({len(html.encode("utf-8")) / 1024:.1f} KB, 부품 {len(texts)}개, {time.time() - t0:.1f}초)')
    if bk:
        print(f'       이전 파일 보관: {os.path.relpath(bk, ROOT)}')
    print('       시험용 엔진: 시험/_엔진_묶음.js · 부품지도: 문서/부품지도.md')
    return report([], warns, t0, done=True)


def report(errors, warns, t0, check_only=False, done=False):
    for w in warns:
        print('[주의] ' + w)
    for e in errors:
        print('[오류] ' + e)
    if errors:
        print(f'\n빌드하지 않았습니다 (오류 {len(errors)}개). 기존 공문추출기.html 은 그대로입니다.')
        return 1
    if check_only:
        print('[검사 통과] 파일은 만들지 않았습니다 (--check).')
    return 0


def watch():
    print('부품을 고칠 때마다 자동으로 빌드합니다. 멈추려면 Ctrl+C')
    def stamp():
        s = 0.0
        for d, _, fs in os.walk(SRC):
            for f in fs:
                s = max(s, os.path.getmtime(os.path.join(d, f)))
        return s
    last = None
    try:
        while True:
            st = stamp()
            if st != last:
                last = st
                print('\n' + datetime.datetime.now().strftime('%H:%M:%S'), '빌드')
                build()
            time.sleep(1)
    except KeyboardInterrupt:
        print('\n멈춤')
    return 0


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--watch' in args:
        sys.exit(watch())
    sys.exit(build(check_only='--check' in args))
