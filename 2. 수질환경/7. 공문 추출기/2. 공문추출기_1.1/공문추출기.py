# -*- coding: utf-8 -*-
"""
검사의뢰 공문 추출기 (파이썬 판) v1.1
================================================================
수질검사 의뢰 공문(ODT)을 공문 폴더에서 모두 읽어 시료 1개당 1행으로 보여 주고,
엑셀 저장 · 공문 단위 완료 체크 · 성적처리완료 폴더 이동 · 되돌리기 · 기준표 적용 · 원본 보기를 한다.

v1.1 (2026-10-22)
  - '시료명' 등 열 제목이 달라도 값이 시료번호 모양이면 시료 표로 인식 (동두천시 공문)
  - 항목 안 기준 표기 일반화: BOD(20이하), SS(20 ㎎/L 이하), T-P(0.5미만), BOD 20이하, pH(5.8~8.6) 등
  - 접수일 최근 순 정렬, 열 순서(접수일·의뢰기관·의뢰자·발신명의·시행·시료번호·검사항목·시료채취일)
  - 원본 보기: 원본 파일 열기(한글 등) + 서식 그대로 미리보기(브라우저)

- 표준 라이브러리만 사용 (pip 설치 불필요, 내부망 사용 가능): tkinter, zipfile, xml, json
- HTML 판(공문추출기.html)과 추출 규칙이 같고, _처리상태.json · 기준표.xlsx 를 함께 쓸 수 있다.

실행
  python 공문추출기.py                              # 화면(창)으로 실행
  python 공문추출기.py --folder D:\\공문 --excel 결과.xlsx   # 창 없이 엑셀만 만들기
  python 공문추출기.py --folder D:\\공문 --json 결과.json    # 창 없이 JSON 만들기
  python 공문추출기.py --preview 공문.odt                     # 원본 미리보기(브라우저)
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

VERSION = '1.1'
STATUS_FILE = '_처리상태.json'
DONE_DIR = '성적처리완료'
STD_RE = re.compile(r'^기준표\.(xlsx|csv)$', re.I)
HISTORY_MAX = 1000


# ════════════════════════════════════════════════════════════════
# 1. ODT 읽기 → 단순 트리 {n: 이름, a: 속성, c: [문자열 | 노드]}
# ════════════════════════════════════════════════════════════════
def _local(q: str) -> str:
    if q.startswith('{'):
        q = q.split('}', 1)[1]
    return q.split(':', 1)[1] if ':' in q else q


def _conv(el) -> dict:
    node = {'n': _local(el.tag), 'a': {_local(k): v for k, v in el.attrib.items()}, 'c': []}
    if el.text:
        node['c'].append(el.text)
    for ch in el:
        if not isinstance(ch.tag, str):  # 주석·처리명령
            if ch.tail:
                node['c'].append(ch.tail)
            continue
        node['c'].append(_conv(ch))
        if ch.tail:
            node['c'].append(ch.tail)
    return node


def unzip_entry(data: bytes, name: str, optional: bool = False):
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ValueError('ZIP 구조가 아님(손상되었거나 ODT 파일이 아님)')
    try:
        return zf.read(name)
    except KeyError:
        if optional:
            return None
        raise ValueError(name + ' 없음(ODT 파일이 아님)')


def parse_xml(raw: bytes) -> dict:
    return {'n': '#root', 'a': {}, 'c': [_conv(ET.fromstring(raw))]}


def kids(e, n=None):
    return [x for x in e['c'] if not isinstance(x, str) and (n is None or x['n'] == n)]


def walk(e, fn):
    for x in e['c']:
        if isinstance(x, str):
            continue
        if fn(x) is False:
            continue
        walk(x, fn)


def find_all(e, n):
    out = []
    walk(e, lambda x: out.append(x) if x['n'] == n else None)
    return out


def has(e, n) -> bool:
    found = []
    walk(e, lambda x: found.append(1) if x['n'] == n else None)
    return bool(found)


def text_all(e) -> str:
    return ''.join(x if isinstance(x, str) else text_all(x) for x in e['c'])


_WS = re.compile(r'[\t\r\n ]+')


def inline_text(e) -> str:
    out = []
    for x in e['c']:
        if isinstance(x, str):
            out.append(_WS.sub(' ', x))
            continue
        n = x['n']
        if n == 's':
            try:
                cnt = int(x['a'].get('c') or 1)
            except ValueError:
                cnt = 1
            out.append(' ' * (cnt or 1))
        elif n == 'tab':
            out.append('\t')
        elif n == 'line-break':
            out.append('\n')
        elif n in ('frame', 'note', 'annotation', 'table'):
            pass
        else:
            out.append(inline_text(x))
    return ''.join(out)


def block_lines(e) -> list:
    lines = []
    for x in kids(e):
        if x['n'] in ('p', 'h'):
            lines.extend(inline_text(x).split('\n'))
        elif x['n'] in ('list', 'list-item', 'section'):
            lines.extend(block_lines(x))
    return [t.strip() for t in lines if t.strip()]


def squash(t) -> str:
    return re.sub(r'\s+', '', t or '')


def spaced_name(t) -> str:
    toks = (t or '').split()
    if not toks:
        return ''
    return ''.join(toks) if all(len(x) == 1 for x in toks) else ' '.join(toks)


def _int(v, d=1):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


# ════════════════════════════════════════════════════════════════
# 2. 표 → 격자 (병합 처리)
# ════════════════════════════════════════════════════════════════
def table_rows(tbl) -> list:
    rows = []

    def collect(e):
        for x in kids(e):
            if x['n'] == 'table-row':
                rows.extend([x] * min(_int(x['a'].get('number-rows-repeated')), 3))
            elif x['n'] in ('table-header-rows', 'table-rows', 'table-row-group'):
                collect(x)
    collect(tbl)
    return rows


class Cell:
    __slots__ = ('r', 'c', 'rs', 'cs', 'lines', 'nested', 'text')


def build_grid(tbl) -> dict:
    rows = table_rows(tbl)
    G = {}
    for r, row in enumerate(rows):
        G.setdefault(r, {})
        c = 0
        for cell in kids(row):
            if cell['n'] not in ('table-cell', 'covered-table-cell'):
                continue
            rep = min(_int(cell['a'].get('number-columns-repeated')), 64)
            for _ in range(rep):
                if cell['n'] == 'table-cell' and c not in G[r]:
                    o = Cell()
                    o.r, o.c = r, c
                    o.rs = _int(cell['a'].get('number-rows-spanned'))
                    o.cs = _int(cell['a'].get('number-columns-spanned'))
                    o.lines = block_lines(cell)
                    o.nested = has(cell, 'table')
                    o.text = '\n'.join(o.lines)
                    for dr in range(o.rs):
                        for dc in range(o.cs):
                            G.setdefault(r + dr, {}).setdefault(c + dc, o)
                c += 1
    return {'G': G, 'nrows': len(rows)}


def row_origins(g, r) -> list:
    out, seen = [], set()
    row = g['G'].get(r, {})
    for c in sorted(row):
        o = row[c]
        if id(o) not in seen:
            seen.add(id(o))
            out.append(o)
    return out


def grid_text(g) -> str:
    return '\n'.join('|'.join(o.text for o in row_origins(g, r)) for r in sorted(g['G']))


# ════════════════════════════════════════════════════════════════
# 3. 날짜
# ════════════════════════════════════════════════════════════════
DATE_RE = re.compile(r"(?:(\d{4})|'(\d{2}))\s*(?:[.\-/]|년)\s*(\d{1,2})\s*(?:[.\-/]|월)\s*(\d{1,2})(?!\d)\s*(?:\.|일)?")


def parse_date(s):
    if not s:
        return None
    m = DATE_RE.search(s)
    if not m:
        return None
    y = m.group(1) or ('20' + m.group(2))
    mo, d = int(m.group(3)), int(m.group(4))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    t = re.search(r'(\d{1,2})\s*:\s*(\d{2})', s[m.end():])
    return {'date': f'{y}-{mo:02d}-{d:02d}', 'time': f'{int(t.group(1)):02d}:{t.group(2)}' if t else ''}


def all_dates(s) -> list:
    out = []
    for m in DATE_RE.finditer(s):
        p = parse_date(m.group(0))
        if p:
            p.update(index=m.start(), end=m.end())
            out.append(p)
    return out


# ════════════════════════════════════════════════════════════════
# 4. 사전 (설정) — 새 표기가 나오면 여기에 한 줄 추가
# ════════════════════════════════════════════════════════════════
ITEM_DICT = {
    'bod': 'BOD', 'toc': 'TOC', 'ss': 'SS', 'cod': 'COD',
    't-n': 'T-N', 'tn': 'T-N', '총질소': 'T-N',
    't-p': 'T-P', 'tp': 'T-P', '총인': 'T-P',
    'n-h(광)': 'n-H(광)', 'n-h(광유류)': 'n-H(광)', '노르말헥산(광유류)': 'n-H(광)', '노르말헥산(광)': 'n-H(광)',
    'n-h(동식)': 'n-H(동식)', 'n-h(동식물유류)': 'n-H(동식)', '노르말헥산(동식물유류)': 'n-H(동식)',
    'abs': 'ABS', '음이온계면활성제': 'ABS',
    '생태독성': '생태독성', '색도': '색도', '철': '철', 'ph': 'pH', '수소이온농도': 'pH',
    '대장균군': '대장균군', '총대장균군': '총대장균군', '페놀류': '페놀류', '시안': '시안', '구리': '구리', '아연': '아연',
    '납': '납', '카드뮴': '카드뮴', '크롬': '크롬', '6가크롬': '6가크롬', '비소': '비소', '수은': '수은', '망간': '망간', '불소': '불소',
}
SIDO_TITLE = {'시': '시장', '군': '군수', '도': '도지사'}
ORG_EXCEPTIONS = {}  # 예: {'○○사업소': {'의뢰기관': '○○시', '의뢰자': '○○시장'}}
REGION_CODE = re.compile(r'^(가|나|다|라|청정|특례|특정)(지역)?$')


def norm_item(tok):
    return ITEM_DICT.get(re.sub(r'\s+', '', str(tok or '').lower()))


# ════════════════════════════════════════════════════════════════
# 5. 머리글 분류
# ════════════════════════════════════════════════════════════════
def classify(h):
    t = squash(h)
    if not t:
        return None
    if re.match(r'^(연번|순번|번호|no\.?)$', t, re.I):
        return 'seq'
    if re.search(r'(시료|검체|지시|의뢰)번호', t):
        return 'sampleNo'
    if re.match(r'^(시료|검체)(명|코드|no\.?|명칭)$', t, re.I):
        return 'sampleName'  # v1.1: '시료명' 등 — 값이 번호 형태면 시료번호로 사용
    if '항목' in t:
        return 'itemsStd' if '기준' in t else 'items'
    if re.search(r'(채취|채수)(일|일자|일시|날짜)', t):
        return 'date'
    if '지역' in t:
        return 'region'
    if '기준' in t:
        return 'std'
    if re.search(r'(시료량|채취량|채수량|수량)', t) or t == '시료':
        return 'qty'
    if re.search(r'(업종|배출시설|성상|건물용도)', t):
        return 'industry'
    if '지점' in t:
        return 'point'
    if '비고' in t:
        return 'note'
    return 'other'


# ════════════════════════════════════════════════════════════════
# 6. 상단·하단
# ════════════════════════════════════════════════════════════════
def parse_header(tables):
    for t in tables:
        g = build_grid(t)
        r_recv, title, org = -1, '', ''
        for r in range(g['nrows']):
            os_ = row_origins(g, r)
            for k, o in enumerate(os_):
                if squash(o.text) == '수신' and r_recv < 0:
                    r_recv = r
                if squash(o.text) == '제목' and k + 1 < len(os_):
                    title = ' '.join(os_[k + 1].lines)
        if r_recv < 0 or not title:
            continue
        for r in range(r_recv):
            for o in row_origins(g, r):
                s = squash(o.text)
                if s and re.fullmatch(r'[가-힣]+', s) and len(s) <= 15:
                    org = s
        return {'org': org, 'title': title.strip()}
    return None


def parse_footer(tables):
    for t in tables:
        g = build_grid(t)
        r_si = r_coop = -1
        for r in range(g['nrows']):
            for o in row_origins(g, r):
                s = squash(o.text)
                if s == '시행' and r_si < 0:
                    r_si = r
                if s == '협조자' and r_coop < 0:
                    r_coop = r
        if r_si < 0:
            continue
        f = {}

        def next_vals(r, label):
            os_ = [o for o in row_origins(g, r) if o.text]
            for k, o in enumerate(os_):
                if squash(o.text) == label:
                    return [x.text.strip() for x in os_[k + 1:]]
            return []
        v = next_vals(r_si, '시행')
        f['siNo'] = v[0] if v else ''
        f['siDate'] = v[1] if len(v) > 1 else ''
        v = next_vals(r_si, '접수')
        f['rcNo'] = v[0] if v else ''
        f['rcDate'] = v[1] if len(v) > 1 else ''
        if r_coop > 1:
            names = [o for o in row_origins(g, r_coop - 1) if o.r == r_coop - 1 and o.text and not re.search(r'결|\d', o.text)]
            pos = [o for o in row_origins(g, r_coop - 2) if o.r == r_coop - 2 and o.text]
            f['drafter'] = names[0].text.strip() if names else ''
            f['drafterPos'] = pos[0].text.strip() if pos else ''
            for r in range(r_coop - 2):
                for o in row_origins(g, r):
                    if o.text and not o.nested:
                        f['sender'] = spaced_name(o.text)
        for r in range(g['nrows']):
            os_ = [o.text.strip() for o in row_origins(g, r) if o.text]
            if os_ and os_[0] == '우':
                f['zip'] = os_[1] if len(os_) > 1 else ''
                f['addr'] = os_[2] if len(os_) > 2 else ''
            if '전화번호' in os_:
                k = os_.index('전화번호')
                f['tel'] = os_[k + 1] if k + 1 < len(os_) else ''
            if '팩스번호' in os_:
                k = os_.index('팩스번호')
                f['fax'] = os_[k + 1] if k + 1 < len(os_) else ''
            em = next((x for x in os_ if '@' in x), None)
            if em:
                f['email'] = em
        return f
    return None


def sender_fallback(body, pos_first):
    cells = []

    def fn(x):
        if x['n'] == 'table-cell' and not has(x, 'table'):
            t = ' '.join(block_lines(x))
            if t:
                cells.append(t)
            return False
        return None
    walk(body, fn)
    for k, t in enumerate(cells):
        if squash(t) == squash(pos_first):
            return spaced_name(cells[k - 1]) if k > 0 else ''
    return ''


def derive_org(org_top, addr):
    if org_top in ORG_EXCEPTIONS:
        return ORG_EXCEPTIONS[org_top]
    org = ''
    if re.fullmatch(r'[가-힣]{1,4}(시|군)', org_top or '') or re.fullmatch(r'[가-힣]{1,3}도', org_top or ''):
        org = org_top
    else:
        m = re.search(r'(?:^|\s)([가-힣]{1,4}(?:시|군))(?=\s)', addr or '')
        if m:
            org = m.group(1)
    if not org:
        return {'의뢰기관': org_top, '의뢰자': ''}
    return {'의뢰기관': org, '의뢰자': org[:-1] + SIDO_TITLE[org[-1]]}


# ════════════════════════════════════════════════════════════════
# 7. 시료 표
# ════════════════════════════════════════════════════════════════
def looks_like_sample_no(v):
    """v1.1: 시료번호처럼 생긴 값인지 (예: 동두천-10-1, 2-10-401~402, TMS 2-10-3 (A~D))"""
    s = re.sub(r'\s*\n\s*', '', str(v or '')).strip()
    if not s or len(s) > 40 or DATE_RE.search(s):
        return False
    return bool(re.search(r'\d+\s*-\s*\d+', s))


def _data_column_values(g, hr, o):
    vals = []
    for r in range(hr + 1, g['nrows']):
        c = g['G'].get(r, {}).get(o.c)
        if c is not None and c.r == r and c.text:
            vals.append(c.text)
    return vals


def _code_ratio(vals):
    return sum(1 for v in vals if looks_like_sample_no(v)) / len(vals) if vals else 0


def pick_sample_col(g, hr):
    """시료번호 열: ① 제목에 '번호' ② '시료명' 등이면서 값이 번호 형태 ③ 항목 열이 있는 표에서 값이 번호 형태인 열"""
    os_ = row_origins(g, hr)
    for o in os_:
        if classify(o.text) == 'sampleNo':
            return o, 'header'
    for o in os_:
        if classify(o.text) == 'sampleName' and _code_ratio(_data_column_values(g, hr, o)) >= 0.6:
            return o, 'name'
    if not any((classify(o.text) or '').startswith('items') for o in os_):
        return None
    best, best_r = None, 0
    for o in os_:
        f = classify(o.text) or ''
        if f.startswith('items') or f in ('date', 'seq'):
            continue
        r = _code_ratio(_data_column_values(g, hr, o))
        if r > best_r:
            best, best_r = o, r
    return (best, 'content') if best is not None and best_r >= 0.6 else None


def find_sample_tables(tables):
    out, sigs = [], set()
    for t in tables:
        g = build_grid(t)
        for r in range(min(3, g['nrows'])):
            pick = pick_sample_col(g, r)
            if not pick:
                continue
            sig = grid_text(g)
            if sig in sigs:
                break
            sigs.add(sig)
            out.append((g, r, pick[0]))
            break
    return out


def join_no(lines):
    s = ''
    for line in lines:
        s += (' ' if s and not re.search(r'[-~]$', s) and not re.match(r'^[-~]', line) else '') + line
    return s.strip()


def read_sample_table(g, hr, sample_col=None):
    heads = []
    for o in row_origins(g, hr):
        f = classify(o.text)
        if sample_col is not None:
            f = 'sampleNo' if o is sample_col else ('other' if f == 'sampleNo' else f)
        if f == 'sampleName':
            f = 'industry'  # 시료번호로 쓰지 않은 '시료명'은 성상 정보로 보관
        heads.append({'o': o, 'f': f, 'name': spaced_name(o.text.replace('\n', ' '))})
    G = g['G']

    def cells_at(r, h, skip_header):
        out = []
        for c in range(h['o'].c, h['o'].c + h['o'].cs):
            o = G.get(r, {}).get(c)
            if o is not None and not (skip_header and o.r == hr) and all(o is not x for x in out):
                out.append(o)
        return out
    raw = [[' / '.join(' '.join(o.lines) for o in cells_at(r, h, False)) for h in heads] for r in range(hr, g['nrows'])]
    samples = []
    for r in range(hr + 1, g['nrows']):
        rec, no_cell, any_ = {}, None, False
        for h in heads:
            if not h['f'] or h['f'] == 'seq':
                continue
            cells = cells_at(r, h, True)
            text = '\n'.join(o.text for o in cells if o.text)
            if h['f'] == 'sampleNo':
                no_cell = cells[0] if cells else None
                rec['_noLines'] = no_cell.lines if no_cell else []
            if text:
                any_ = True
            if h['f'] == 'other':
                if text:
                    rec.setdefault('other', []).append(h['name'] + ': ' + text.replace('\n', ' '))
            else:
                rec[h['f']] = rec[h['f']] + '\n' + text if rec.get(h['f']) else text
        if not any_:
            continue
        cont = no_cell is None or not no_cell.text or no_cell.r < r
        if re.fullmatch(r'[-–—]', (rec.get('note') or '').strip()):
            rec['note'] = ''
        if not rec.get('region') and REGION_CODE.match(squash(rec.get('note'))):
            rec['region'] = rec['note'].strip()
            rec['note'] = ''
        group = {'items': rec.get('items') or rec.get('itemsStd') or '', 'std': rec.get('std') or '', 'region': rec.get('region') or ''}
        if cont:
            if samples:
                samples[-1]['groups'].append(group)
            continue
        samples.append({'rawNo': join_no(rec.get('_noLines') or []), 'groups': [group], 'date': rec.get('date') or '',
                        'qty': rec.get('qty') or '', 'industry': rec.get('industry') or '', 'point': rec.get('point') or '',
                        'note': rec.get('note') or '', 'other': ' / '.join(rec.get('other') or [])})
    return {'headers': [h['name'] for h in heads], 'raw': raw, 'samples': samples}


def expand_no(raw):
    s = re.sub(r'\s*\n\s*', '', raw).strip()
    subs = None
    sm = re.search(r'\(\s*([A-Za-z])\s*~\s*([A-Za-z])\s*\)\s*$', s)
    if sm:
        s = s[:sm.start()].strip()
        subs = [chr(c) for c in range(ord(sm.group(1).upper()), ord(sm.group(2).upper()) + 1)]
    bases = [s]
    rm = re.match(r'^(.*?)(\d+)\s*~\s*(?:[0-9A-Za-z가-힣\-]*-)?(\d+)$', s)
    if rm:
        a, b = int(rm.group(2)), int(rm.group(3))
        if b > a and b - a < 200:
            bases = [rm.group(1) + str(k) for k in range(a, b + 1)]
    out = []
    for b in bases:
        out.extend([f'{b}({x})' for x in subs] if subs else [b])
    return {'list': out, 'baseCount': len(bases)}


def parse_items(text):
    region = ''
    s = re.sub(r'[·•▪◦]', ',', text or '')
    ar = re.search(r'(?:→|->|⇒)\s*([^,\n]+)', s)
    if ar:
        region = ar.group(1).strip()
        s = s[:ar.start()] + s[ar.end():]
    s = s.replace('\n', ',')
    toks, depth, cur = [], 0, ''
    for ch in s:
        if ch in '(（':
            depth += 1
        elif ch in ')）':
            depth = max(0, depth - 1)
        if ch in ',，、' and depth == 0:
            toks.append(cur)
            cur = ''
        else:
            cur += ch
    toks.append(cur)
    items = []
    for t in toks:
        t = re.sub(r'^[\s\-–]+', '', t).strip()
        if not t:
            continue
        t, std = split_item_std(t)
        name = norm_item(t)
        items.append({'raw': t, 'name': name or t, 'known': bool(name), 'std': std})
    return {'items': items, 'region': region}


# v1.1: 항목 안의 기준 표기 — BOD(20), BOD(20이하), BOD(20 ㎎/L 이하), BOD(기준 20), BOD(≤20), T-P(0.5미만),
#       pH(5.8~8.6), 대장균군(3,000개/mL), BOD 20이하, SS: 20  → 이름과 기준값 분리
_STD_UNIT = r'(?:mg\s*/\s*[lLℓ]|㎎\s*/\s*[lLℓ]|㎎/ℓ|mg/ℓ|ppm|ppb|도|TU|개\s*/\s*(?:100\s*)?m[lL]|%)'
_STD_NUM = r'(\d[\d.,]*(?:\s*[~∼-]\s*\d[\d.,]*)?)'
STD_PAREN = re.compile(r'^(.*?\S)\s*[(（]\s*(?:기준\s*[:：]?\s*)?(≤|<=|<|이하|미만)?\s*' + _STD_NUM + r'\s*' + _STD_UNIT + r'?\s*(이하|미만)?\s*[)）]$')
STD_PLAIN = re.compile(r'^(.*?\S)\s*([:：])?\s*(≤|<=|<)?\s*' + _STD_NUM + r'\s*' + _STD_UNIT + r'?\s*(이하|미만)?$')


def _fmt_std(num, q):
    return re.sub(r'\s+', '', num).replace('∼', '~') + (' 미만' if q in ('미만', '<') else '')


def split_item_std(t):
    m = STD_PAREN.match(t)
    if m and not re.fullmatch(r'[\d.,]+', m.group(1)):
        return m.group(1).strip(), _fmt_std(m.group(3), m.group(2) or m.group(4))
    m = STD_PLAIN.match(t)
    if m and norm_item(m.group(1).strip()) and (m.group(2) or m.group(3) or m.group(5) or t[len(m.group(1)):len(m.group(1)) + 1].isspace()):
        return m.group(1).strip(), _fmt_std(m.group(4), m.group(3) or m.group(5))
    return t, ''


def apply_std_column(items, std):
    if not std:
        return
    v = std.replace('\n', ' ')
    each = re.search(r'각\s*([\d.]+)', v)
    if each:
        for i in items:
            if not i['std']:
                i['std'] = each.group(1)
        return
    hit = False
    for i in items:
        for key in dict.fromkeys([i['raw'], i['name']]):
            m = re.search(re.escape(key) + r'\s*[:：]?\s*([\d.]+)', v, re.I)
            if m:
                if not i['std']:
                    i['std'] = m.group(1)
                hit = True
                break
    if hit:
        return
    nums = re.findall(r'\d+(?:\.\d+)?', v)
    if len(nums) == len(items):
        for i, n in zip(items, nums):
            if not i['std']:
                i['std'] = n


# ════════════════════════════════════════════════════════════════
# 8. 본문 채취일 · 제목 대조
# ════════════════════════════════════════════════════════════════
def body_paragraphs(body):
    out = []
    for x in kids(body):
        if x['n'] in ('p', 'h'):
            t = re.sub(r'\s+', ' ', inline_text(x)).strip()
            if t:
                out.append(t)
        elif x['n'] in ('list', 'list-item', 'section'):
            out.extend(body_paragraphs(x))
    return out


def date_from_body(paras):
    found = []
    for p in paras:
        for d in all_dates(p):
            before, after = p[max(0, d['index'] - 25):d['index']], p[d['end']:d['end'] + 45]
            if re.search(r'의뢰\s*(일|일자)', before):
                continue
            if re.search(r'(채수|채취|채집)', after) or re.search(r'(채수|채취)[^.。]{0,15}$', before):
                found.append(d)
    return found


def title_check(title, samples, base_total):
    m = re.search(r'[(\[]([^()\[\]]*\d[^()\[\]]*)[)\]]\s*$', title or '')
    if not m or not samples:
        return ''
    code = m.group(1)
    n = re.search(r'등\s*(\d+)\s*건', code)
    if n:
        exp = int(n.group(1))
    else:
        r = re.search(r'(\d+)\s*~\s*(?:[0-9A-Za-z가-힣\-]*-)?(\d+)', code)
        if r:
            exp = int(r.group(2)) - int(r.group(1)) + 1
        else:
            S = re.sub(r'\([A-Z]~[A-Z]\)', '', squash(samples[0]['rawNo']), count=1, flags=re.I)
            C = squash(code)
            x = re.match('^' + re.escape(S) + r'-(\d+)$', C)
            if x:
                last = re.search(r'(\d+)$', S)
                exp = int(x.group(1)) - (int(last.group(1)) if last else 0) + 1
            elif S.replace('-', '') in C.replace('-', ''):
                exp = 1
            else:
                return f'제목 시료번호({code})와 표 시료번호 다름'
    return f'제목 시료 수({exp})와 표({base_total}) 다름' if exp != base_total else ''


# ════════════════════════════════════════════════════════════════
# 9. 메인 추출
# ════════════════════════════════════════════════════════════════
# v1.1: 엑셀·화면 기본 순서 — 접수일, 의뢰기관, 의뢰자, 발신명의, 시행, 시료번호, 검사항목, 시료채취일 먼저
COLUMNS = ['접수일', '의뢰기관', '의뢰자', '발신명의', '시행', '시료번호', '검사항목', '시료채취일', '기준', '기준출처', '지역구분',
           '채취시각', '채취일출처', '시료채취자', '접수', '시행일', '제목', '업종/성상', '시료량', '채취지점', '비고', '기타', '우편번호', '주소', '전화번호', '이메일', '확인필요', '파일명']


def extract_odt(data: bytes, file_name: str = '') -> dict:
    root = parse_xml(unzip_entry(data, 'content.xml'))
    ob = find_all(root, 'body')
    body = (kids(ob[0], 'text') or [root])[0] if ob else root
    tables = [t for t in find_all(body, 'table') if not find_all(t, 'table')]
    hdr = parse_header(tables) or {'org': '', 'title': ''}
    ftr = parse_footer(tables) or {}
    if not ftr.get('sender') and ftr.get('drafterPos'):
        ftr['sender'] = sender_fallback(body, ftr['drafterPos'])
    org = derive_org(hdr['org'], ftr.get('addr'))
    paras = body_paragraphs(body)
    doc_warn = []
    pdate = lambda s: (parse_date(s) or {}).get('date', '')
    doc = {
        '파일명': unicodedata.normalize('NFC', file_name or ''), '제목': hdr['title'], '상단기관명': hdr['org'],
        '의뢰기관': org['의뢰기관'], '의뢰자': org['의뢰자'], '발신명의': ftr.get('sender', ''),
        '시행': ftr.get('siNo', ''), '시행일': pdate(ftr.get('siDate')),
        '접수': ftr.get('rcNo', ''), '접수일': pdate(ftr.get('rcDate')),
        '시료채취자': ftr.get('drafter', ''), '기안자직위': ftr.get('drafterPos', ''),
        '우편번호': ftr.get('zip', ''), '주소': ftr.get('addr', ''), '전화번호': ftr.get('tel', ''), '이메일': ftr.get('email', ''),
    }
    if not doc['접수']:
        doc_warn.append('접수번호 없음')
    if not doc['의뢰자']:
        doc_warn.append('의뢰자 판정 불가')
    sts = find_sample_tables(tables)
    if not sts:
        doc_warn.append('시료표 미인식')
    body_dates = date_from_body(paras)
    body_date = body_dates[0] if body_dates else None
    bset = list(dict.fromkeys(d['date'] for d in body_dates))
    if len(bset) > 1:
        doc_warn.append('본문 채취일 여러 개: ' + ', '.join(bset))
    rows, all_samples, table_info, base_total = [], [], [], 0
    for g, hr, scol in sts:
        st = read_sample_table(g, hr, scol)
        table_info.append({'headers': st['headers'], 'raw': st['raw']})
        for s in st['samples']:
            ex = expand_no(s['rawNo'])
            base_total += ex['baseCount']
            all_samples.append(s)
            warn = []
            groups = []
            for gp in s['groups']:
                p = parse_items(gp['items'])
                std, region = gp['std'], gp['region']
                if std and not re.search(r'\d', std):  # '수질기준' 열에 지역코드가 들어간 경우
                    region, std = region or std, ''
                apply_std_column(p['items'], std)
                rg = re.sub(r'\s*\n\s*', ' ', region or p['region'] or '').strip()
                for i in p['items']:
                    i['region'] = rg
                groups.append({'items': p['items'], 'region': rg})
            items = []
            for gp in groups:
                for i in gp['items']:
                    if not any(x['name'] == i['name'] for x in items):
                        items.append(i)
            if '기준' in s['note']:
                apply_std_column(items, s['note'])
            unknown = [i['raw'] for i in items if not i['known']]
            if unknown:
                warn.append('미등록 항목: ' + ', '.join(unknown))
            if not items:
                warn.append('검사항목 없음')
            regs = [gp['region'] for gp in groups if gp['region']]
            if len(set(regs)) > 1:
                region_text = ' / '.join(f"{gp['region']}({', '.join(i['name'] for i in gp['items'])})" for gp in groups if gp['region'])
            else:
                region_text = regs[0] if regs else ''
            pd = parse_date(s['date'])
            if pd:
                date, time, src = pd['date'], pd['time'], '표'
            elif body_date:
                date, time, src = body_date['date'], body_date['time'], '본문'
            else:
                date, time, src = '채취일자 확인 필요', '', '확인필요'
                warn.append('채취일자 확인 필요')
            if pd and doc['접수일'] and pd['date'] > doc['접수일']:
                warn.append('채취일이 접수일보다 늦음')
            for no in ex['list']:
                row = dict(doc)
                row.update({
                    '시료번호': no, '시료번호원문': s['rawNo'], '검사항목': ', '.join(i['name'] for i in items),
                    '기준': '', '기준출처': '', '지역구분': region_text, '시료채취일': date, '채취시각': time, '채취일출처': src,
                    '업종/성상': spaced_name(s['industry'].replace('\n', ' ')), '시료량': s['qty'].replace('\n', ', '),
                    '채취지점': s['point'].replace('\n', ' '), '비고': s['note'].replace('\n', ' '), '기타': s['other'],
                    '_items': [{'name': i['name'], 'region': i.get('region') or region_text, 'stdDoc': i['std'] or '',
                                'std': i['std'] or '', 'src': '공문' if i['std'] else ''} for i in items],
                    '_warn': warn,
                })
                refresh_std_text(row)
                rows.append(row)
    tc = title_check(hdr['title'], all_samples, base_total)
    if tc:
        doc_warn.append(tc)
    if doc['시행일'] and doc['접수일'] and doc['접수일'] < doc['시행일']:
        doc_warn.append('접수일이 시행일보다 빠름')
    if not rows:
        row = dict(doc)
        row.update({'시료번호': '', '_items': [], '_warn': []})
        rows.append(row)
    for r in rows:
        r['_baseWarn'] = doc_warn + r.pop('_warn')
        r['확인필요'] = ' / '.join(r['_baseWarn'])
    d = dict(doc)
    d['본문'] = paras
    return {'doc': d, 'rows': rows, 'warnings': doc_warn, 'tables': table_info, 'duplicate': False, 'dupWarn': ''}


def mark_duplicates(results):
    by = {}
    for r in results:
        r['duplicate'], r['dupWarn'] = False, ''
        if r['doc'].get('접수'):
            by.setdefault(r['doc']['접수'], []).append(r)
    for lst in by.values():
        if len(lst) > 1:
            for i, r in enumerate(lst):
                others = ', '.join(x['doc']['파일명'] for x in lst if x is not r)
                r['duplicate'] = i > 0
                r['dupWarn'] = ('중복 공문(집계 제외)' if i > 0 else '중복 공문 있음') + ': ' + others
    for r in results:
        for x in r['rows']:
            x['확인필요'] = ' / '.join(x.get('_baseWarn', []) + ([r['dupWarn']] if r['dupWarn'] else []))
    return results


# ════════════════════════════════════════════════════════════════
# 10. 기준표 (지역구분 × 항목 → 기준값)
# ════════════════════════════════════════════════════════════════
def refresh_std_text(row):
    its = row.get('_items') or []
    with_std = [i for i in its if i['std']]
    row['기준'] = ', '.join(f"{i['name']} {i['std']}" for i in with_std)
    srcs = list(dict.fromkeys(i['src'] for i in with_std))
    if not with_std:
        row['기준출처'] = ''
    else:
        row['기준출처'] = ('공문+기준표' if len(srcs) > 1 else srcs[0]) + ('(일부)' if len(with_std) < len(its) else '')


def _norm_region_tok(t):
    return re.sub(r'지역$', '', squash(t))


def region_tokens(region):
    return [x for x in (_norm_region_tok(t) for t in re.split(r'[,/()（）·]+', str(region or ''))) if x]


def parse_std_table(rows2d):
    if not rows2d:
        return []
    hr = next((k for k, r in enumerate(rows2d) if any(squash(c) == '항목' for c in r)), -1)
    if hr < 0:
        return []
    H = [squash(h) for h in rows2d[hr]]
    ci = lambda key: next((k for k, h in enumerate(H) if key in h), -1)
    iR = ci('지역')
    iI = next((k for k, h in enumerate(H) if h == '항목' or '항목' in h), -1)
    iV, iU = ci('기준'), ci('단위')
    get = lambda r, k: (str(r[k]) if 0 <= k < len(r) and r[k] is not None else '').strip()
    out = []
    for r in rows2d[hr + 1:]:
        item, val = get(r, iI), get(r, iV)
        if not item or not val:
            continue
        region = get(r, iR) if iR >= 0 else ''
        out.append({'region': region, 'key': _norm_region_tok(region), 'item': norm_item(item) or item, 'value': val,
                    'unit': get(r, iU) if iU >= 0 else ''})
    return out


def lookup_std(table, item_name, region):
    toks, whole = region_tokens(region), squash(region).replace('지역', '')
    best, best_score = None, -1
    for e in table:
        if e['item'] != item_name:
            continue
        score = -1
        if not e['key'] or e['key'] in ('*', '전체'):
            score = 0
        elif e['key'] in toks:
            score = 10 + len(e['key'])
        elif len(e['key']) > 2 and e['key'].replace('지역', '') in whole:
            score = 5 + len(e['key'])
        if score > best_score:
            best, best_score = e, score
    return best


def apply_std_table(results, table):
    filled = 0
    for r in results:
        for row in r['rows']:
            for it in row.get('_items') or []:
                it['std'] = it['stdDoc']
                it['src'] = '공문' if it['stdDoc'] else ''
                if not it['stdDoc'] and table:
                    e = lookup_std(table, it['name'], it.get('region') or row.get('지역구분'))
                    if e:
                        it['std'], it['src'] = e['value'], '기준표'
                        filled += 1
            refresh_std_text(row)
    return filled


def missing_std_pairs(results):
    m = {}
    for r in results:
        if r.get('duplicate'):
            continue
        for row in r['rows']:
            for it in row.get('_items') or []:
                if it['std']:
                    continue
                region = it.get('region') or row.get('지역구분') or ''
                k = (region, it['name'])
                if k not in m:
                    m[k] = {'지역구분': region, '항목': it['name'], '예시': row['시료번호'], '건수': 0}
                m[k]['건수'] += 1
    return sorted(m.values(), key=lambda x: x['지역구분'] + x['항목'])


def read_xlsx_rows(data: bytes):
    ss = unzip_entry(data, 'xl/sharedStrings.xml', True)
    shared = [''.join(text_all(t) for t in find_all(si, 't')) for si in find_all(parse_xml(ss), 'si')] if ss else []
    sheet = unzip_entry(data, 'xl/worksheets/sheet1.xml', True)
    if not sheet:
        raise ValueError('첫 번째 시트를 찾을 수 없음')
    rows = []
    for row in find_all(parse_xml(sheet), 'row'):
        arr = {}
        for c in kids(row, 'c'):
            letters = (re.match(r'^[A-Z]+', c['a'].get('r', '')) or [None])[0] or 'A'
            ci = 0
            for ch in letters:
                ci = ci * 26 + (ord(ch) - 64)
            t = c['a'].get('t')
            if t == 'inlineStr':
                v = ''.join(text_all(x) for x in find_all(c, 't'))
            else:
                ve = kids(c, 'v')
                v = text_all(ve[0]) if ve else ''
                if t == 's':
                    v = shared[int(v)] if v.isdigit() and int(v) < len(shared) else ''
            arr[ci - 1] = v
        rows.append([arr.get(k, '') for k in range(max(arr) + 1)] if arr else [])
    return rows


def decode_text(data: bytes) -> str:
    try:
        return data.decode('utf-8').lstrip('\ufeff')
    except UnicodeDecodeError:
        return data.decode('cp949', errors='replace')  # 엑셀 기본 CSV(한글 Windows)


def read_std_file(path):
    with open(path, 'rb') as f:
        data = f.read()
    if path.lower().endswith('.csv'):
        rows = list(csv.reader(io.StringIO(decode_text(data))))
    else:
        rows = read_xlsx_rows(data)
    return parse_std_table(rows)


# ════════════════════════════════════════════════════════════════
# 10-1. 원본 미리보기 (ODT → HTML, v1.1) — HTML 판 renderOdtHtml 과 같은 규칙
# ════════════════════════════════════════════════════════════════
ODT_PREVIEW_CSS = """
.odt-page{font-family:"Malgun Gothic","맑은 고딕","Apple SD Gothic Neo","Noto Sans KR",sans-serif;font-size:10pt;line-height:1.3;color:#000;background:#fff;margin:0 auto;padding:1cm 0;box-sizing:content-box}
.odt-p{margin:0;min-height:1.2em;white-space:pre-wrap;word-break:keep-all;overflow-wrap:anywhere}
.odt-table{border-collapse:collapse;table-layout:fixed;margin:0}
.odt-table td{vertical-align:top;padding:1px 3px;overflow:hidden;overflow-wrap:anywhere}
.odt-frame{display:inline-block;vertical-align:top;max-width:100%}
.odt-img{display:inline-block;vertical-align:middle;object-fit:contain}
.odt-list{margin:0;padding-left:1.2em}"""
_IMG_MIME = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif', 'bmp': 'image/bmp', 'svg': 'image/svg+xml', 'webp': 'image/webp'}
_CSS_LEN = re.compile(r'^-?[\d.]+(cm|mm|in|pt|pc|px|%)$')
_ALIGN = {'start': 'left', 'left': 'left', 'end': 'right', 'right': 'right', 'center': 'center', 'justify': 'justify'}


def _hesc(v):
    return str('' if v is None else v).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _is_len(v):
    return bool(v) and bool(_CSS_LEN.match(str(v).strip()))


def render_odt_html(data: bytes) -> dict:
    import base64
    content = parse_xml(unzip_entry(data, 'content.xml'))
    sx = unzip_entry(data, 'styles.xml', True)
    styles_doc = parse_xml(sx) if sx else {'n': '#root', 'a': {}, 'c': []}
    S, D = {}, {}
    for root in (styles_doc, content):
        for box in find_all(root, 'styles') + find_all(root, 'automatic-styles'):
            for st in kids(box, 'style'):
                if st['a'].get('name'):
                    S[(st['a'].get('family') or '') + ':' + st['a']['name']] = st
            for st in kids(box, 'default-style'):
                if st['a'].get('family'):
                    D[st['a']['family']] = st
    cache = {}

    def props(family, name):
        key = family + ':' + (name or '')
        if key in cache:
            return cache[key]
        chain, cur, guard = [], S.get(family + ':' + name) if name else None, 0
        while cur is not None and guard < 20:
            chain.insert(0, cur)
            par = cur['a'].get('parent-style-name')
            cur = S.get(family + ':' + par) if par else None
            guard += 1
        if family in D:
            chain.insert(0, D[family])
        out = {}
        for st in chain:
            for pe in kids(st):
                out.setdefault(re.sub(r'-properties$', '', pe['n']), {}).update(pe['a'])
        cache[key] = out
        return out

    def text_css(t):
        if not t:
            return ''
        o = []
        size = t.get('font-size-asian') or t.get('font-size')
        w = t.get('font-weight-asian') or t.get('font-weight')
        if _is_len(size) and not size.endswith('%'):
            o.append('font-size:' + size)
        if w and (w == 'bold' or (w.isdigit() and int(w) >= 600)):
            o.append('font-weight:bold')
        if (t.get('font-style-asian') or t.get('font-style')) == 'italic':
            o.append('font-style:italic')
        if re.fullmatch(r'#[0-9a-fA-F]{6}', t.get('color') or ''):
            o.append('color:' + t['color'])
        if t.get('text-underline-style') and t['text-underline-style'] != 'none':
            o.append('text-decoration:underline')
        if t.get('background-color') and t['background-color'] != 'transparent':
            o.append('background-color:' + t['background-color'])
        return ';'.join(o)

    def para_css(p):
        if not p:
            return ''
        o = []
        if p.get('text-align'):
            o.append('text-align:' + _ALIGN.get(p['text-align'], 'left'))
        for k in ('margin-left', 'margin-right', 'margin-top', 'margin-bottom', 'text-indent'):
            if _is_len(p.get(k)):
                o.append(f'{k}:{p[k]}')
        lh = p.get('line-height')
        if lh and lh.endswith('%'):
            try:
                o.append(f'line-height:{float(lh[:-1]) / 100 * 1.2:.2f}')
            except ValueError:
                pass
        elif _is_len(lh):
            o.append('line-height:' + lh)
        return ';'.join(o)

    def cell_css(c):
        if not c:
            return ''
        o = [f'{k}:{c[k]}' for k in ('border', 'border-top', 'border-bottom', 'border-left', 'border-right') if c.get(k)]
        o += [f'{k}:{c[k]}' for k in ('padding', 'padding-top', 'padding-bottom', 'padding-left', 'padding-right') if _is_len(c.get(k))]
        if c.get('background-color') and c['background-color'] != 'transparent':
            o.append('background-color:' + c['background-color'])
        if c.get('vertical-align'):
            o.append('vertical-align:' + {'middle': 'middle', 'top': 'top', 'bottom': 'bottom'}.get(c['vertical-align'], 'top'))
        return ';'.join(o)

    imgs = {}
    for im in find_all(content, 'image'):
        href = im['a'].get('href')
        if not href or href in imgs or href.startswith('http'):
            continue
        try:
            b = unzip_entry(data, re.sub(r'^\./', '', href), True)
            mime = _IMG_MIME.get(href.rsplit('.', 1)[-1].lower())
            imgs[href] = f'data:{mime};base64,{base64.b64encode(b).decode()}' if b and mime else None
        except Exception:  # noqa: BLE001
            imgs[href] = None

    def r_inline(e):
        out = []
        for x in e['c']:
            if isinstance(x, str):
                out.append(_hesc(_WS.sub(' ', x)))
                continue
            n = x['n']
            if n == 's':
                out.append(' ' * (_int(x['a'].get('c')) or 1))
            elif n == 'tab':
                out.append('\t')
            elif n == 'line-break':
                out.append('<br>')
            elif n == 'frame':
                out.append(r_frame(x))
            elif n == 'span':
                css = text_css(props('text', x['a'].get('style-name')).get('text'))
                inner = r_inline(x)
                out.append(f'<span style="{css}">{inner}</span>' if css else inner)
            elif n in ('note', 'annotation', 'bookmark', 'bookmark-start', 'bookmark-end', 'soft-page-break'):
                pass
            else:
                out.append(r_inline(x))
        return ''.join(out)

    def r_frame(f):
        w = f['a'].get('width') if _is_len(f['a'].get('width')) else ''
        h = f['a'].get('height') if _is_len(f['a'].get('height')) else ''
        im, tb = kids(f, 'image'), kids(f, 'text-box')
        if tb:
            style = ' style="width:%s"' % w if w else ''
            return '<div class="odt-frame"%s>%s</div>' % (style, r_blocks(tb[0]))
        if im:
            src = imgs.get(im[0]['a'].get('href'))
            if src:
                return f'<img class="odt-img" src="{src}" style="{"width:" + w + ";" if w else ""}{"height:" + h if h else ""}" alt="">'
        return ''

    def r_table(t):
        tp = props('table', t['a'].get('style-name')).get('table') or {}
        cols = []

        def cols_of(e):
            for x in kids(e):
                if x['n'] == 'table-column':
                    rep = min(_int(x['a'].get('number-columns-repeated')), 64)
                    cw = (props('table-column', x['a'].get('style-name')).get('table-column') or {}).get('column-width')
                    cols.extend([cw if _is_len(cw) else ''] * rep)
                elif x['n'] in ('table-columns', 'table-header-columns', 'table-column-group'):
                    cols_of(x)
        cols_of(t)
        tw = tp.get('width') if _is_len(tp.get('width')) else ''
        h = ['<table class="odt-table"%s>' % (' style="width:%s"' % tw if tw else '')]
        if cols and all(cols):
            h.append('<colgroup>' + ''.join(f'<col style="width:{c}">' for c in cols) + '</colgroup>')
        for row in table_rows(t):
            rp = props('table-row', row['a'].get('style-name')).get('table-row') or {}
            rh = rp.get('row-height') or rp.get('min-row-height')
            h.append(f'<tr style="height:{rh}">' if _is_len(rh) else '<tr>')
            for cell in kids(row):
                if cell['n'] != 'table-cell':
                    continue
                rep = min(_int(cell['a'].get('number-columns-repeated')), 64)
                cs, rs = _int(cell['a'].get('number-columns-spanned')), _int(cell['a'].get('number-rows-spanned'))
                css = cell_css(props('table-cell', cell['a'].get('style-name')).get('table-cell'))
                inner = r_blocks(cell)
                attrs = (f' colspan="{cs}"' if cs > 1 else '') + (f' rowspan="{rs}"' if rs > 1 else '') + (f' style="{css}"' if css else '')
                h.append(f'<td{attrs}>{inner}</td>' * rep)
            h.append('</tr>')
        h.append('</table>')
        return ''.join(h)

    def r_blocks(e):
        out = []
        for x in kids(e):
            n = x['n']
            if n in ('p', 'h'):
                pr = props('paragraph', x['a'].get('style-name'))
                css = ';'.join(c for c in (para_css(pr.get('paragraph')), text_css(pr.get('text'))) if c)
                out.append('<div class="odt-p"%s>%s</div>' % (' style="%s"' % css if css else '', r_inline(x) or '&#8203;'))
            elif n == 'table':
                out.append(r_table(x))
            elif n == 'list':
                out.append('<div class="odt-list">' + ''.join(r_blocks(li) for li in kids(x, 'list-item')) + '</div>')
            elif n in ('section', 'list-item'):
                out.append(r_blocks(x))
            elif n == 'frame':
                out.append(r_frame(x))
        return ''.join(out)

    page_w = '17cm'
    pl = find_all(styles_doc, 'page-layout-properties')
    if pl and (pl[0]['a'].get('page-width') or '').endswith('cm'):
        try:
            w = float(pl[0]['a']['page-width'][:-2]) - float((pl[0]['a'].get('margin-left') or '0cm')[:-2] or 0) - float((pl[0]['a'].get('margin-right') or '0cm')[:-2] or 0)
            if w > 5:
                page_w = f'{w:.2f}cm'
        except ValueError:
            pass
    base = text_css(props('paragraph', '').get('text') or {})
    ob = find_all(content, 'body')
    body = (kids(ob[0], 'text') or [content])[0] if ob else content
    return {'html': f'<div class="odt-page" style="width:{page_w}{";" + base if base else ""}">{r_blocks(body)}</div>', 'css': ODT_PREVIEW_CSS, 'pageWidth': page_w}


def preview_html_document(data: bytes, title: str) -> str:
    r = render_odt_html(data)
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{_hesc(title)}</title><style>'
            'body{margin:0;background:#80868f;padding:24px}' + r['css']
            + '.odt-page{box-shadow:0 2px 12px rgba(0,0,0,.35);padding:1cm 1.5cm}@media print{body{background:#fff;padding:0}.odt-page{box-shadow:none;padding:0}}'
            f'</style></head><body>{r["html"]}</body></html>')


# ════════════════════════════════════════════════════════════════
# 11. 엑셀 작성 (모든 칸 텍스트 → 시료번호가 날짜로 바뀌지 않음)
#     스타일: 0 기본, 1 머리글, 2 노랑(확인필요), 3 회색(중복), 4 연녹색(완료)
# ════════════════════════════════════════════════════════════════
def _x(s):
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', '' if s is None else str(s))
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _col(n):
    s, n = '', n + 1
    while n:
        m = (n - 1) % 26
        s = chr(65 + m) + s
        n = (n - 1) // 26
    return s


def build_xlsx(sheets) -> bytes:
    """sheets: [{'name', 'columns': [{'header','width'}], 'rows': [[...]], 'style_of': f(ri, ci, v, row) -> int}]"""
    fill = lambda rgb: f'<fill><patternFill patternType="solid"><fgColor rgb="{rgb}"/></patternFill></fill>'
    xf = lambda font, fl, extra='<alignment vertical="center"/>': (
        f'<xf numFmtId="49" fontId="{font}" fillId="{fl}" borderId="1" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1">{extra}</xf>')
    files = {
        '[Content_Types].xml': '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        + ''.join(f'<Override PartName="/xl/worksheets/sheet{i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(len(sheets))) + '</Types>',
        '_rels/.rels': '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml': '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
        + ''.join(f'<sheet name="{_x(s["name"])[:31]}" sheetId="{i + 1}" r:id="rId{i + 1}"/>' for i, s in enumerate(sheets)) + '</sheets></workbook>',
        'xl/_rels/workbook.xml.rels': '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + ''.join(f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i + 1}.xml"/>' for i in range(len(sheets)))
        + f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        'xl/styles.xml': '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="10"/><name val="맑은 고딕"/><family val="3"/></font><font><b/><sz val="10"/><name val="맑은 고딕"/><family val="3"/></font></fonts>'
        + '<fills count="6"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>' + fill('FFDCE6F1') + fill('FFFFF2CC') + fill('FFE7E6E6') + fill('FFE2EFDA') + '</fills>'
        + '<borders count="2"><border/><border><left style="thin"><color rgb="FFBFBFBF"/></left><right style="thin"><color rgb="FFBFBFBF"/></right><top style="thin"><color rgb="FFBFBFBF"/></top><bottom style="thin"><color rgb="FFBFBFBF"/></bottom></border></borders>'
        + '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="5">'
        + xf(0, 0) + xf(1, 2, '<alignment horizontal="center" vertical="center" wrapText="1"/>') + xf(0, 3) + xf(0, 4) + xf(0, 5)
        + '</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
    }
    for i, s in enumerate(sheets):
        nc, nr = len(s['columns']), len(s['rows']) + 1
        cell = lambda r, c, v, st: f'<c r="{_col(c)}{r}" t="inlineStr" s="{st}"><is><t xml:space="preserve">{_x(v)}</t></is></c>'
        parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>']
        parts += [f'<col min="{k + 1}" max="{k + 1}" width="{c.get("width") or 12}" customWidth="1"/>' for k, c in enumerate(s['columns'])]
        parts.append('</cols><sheetData><row r="1" ht="22" customHeight="1">' + ''.join(cell(1, k, c['header'], 1) for k, c in enumerate(s['columns'])) + '</row>')
        sf = s.get('style_of')
        for ri, row in enumerate(s['rows']):
            parts.append(f'<row r="{ri + 2}">' + ''.join(cell(ri + 2, k, v, sf(ri, k, v, row) if sf else 0) for k, v in enumerate(row)) + '</row>')
        parts.append('</sheetData>' + (f'<autoFilter ref="A1:{_col(nc - 1)}{nr}"/>' if s['rows'] else '') + '</worksheet>')
        files[f'xl/worksheets/sheet{i + 1}.xml'] = ''.join(parts)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data.encode('utf-8'))
    return buf.getvalue()


XLSX_W = {'상태': 9, '접수': 30, '접수일': 11, '의뢰기관': 10, '의뢰자': 12, '발신명의': 18, '시행': 22, '시행일': 11, '제목': 40, '시료번호': 18,
          '검사항목': 34, '기준': 30, '기준출처': 10, '지역구분': 28, '시료채취일': 16, '채취시각': 8, '채취일출처': 9, '시료채취자': 9, '업종/성상': 22,
          '시료량': 22, '채취지점': 10, '비고': 18, '기타': 24, '우편번호': 8, '주소': 36, '전화번호': 14, '이메일': 22, '확인필요': 40, '파일명': 44}


def export_rows_xlsx(docs, status_of) -> bytes:
    """docs: Doc 목록, status_of(doc) -> '처리대기' | '완료체크' | '처리완료'"""
    header = ['상태'] + COLUMNS
    rows, meta = [], []
    for d in docs:
        st = status_of(d)
        for r in d.rows():
            rows.append([st] + ['' if r.get(c) is None else r.get(c) for c in COLUMNS])
            meta.append((d.duplicate, st))
    i_warn, i_date = header.index('확인필요'), header.index('시료채취일')

    def style_of(ri, k, v, row):
        dup, st = meta[ri]
        if dup:
            return 3
        if (k == i_warn and v) or (k == i_date and v == '채취일자 확인 필요'):
            return 2
        if k == 0 and st != '처리대기':
            return 4
        return 0
    return build_xlsx([{'name': '공문추출', 'columns': [{'header': h, 'width': XLSX_W.get(h, 12)} for h in header], 'rows': rows, 'style_of': style_of}])


# ════════════════════════════════════════════════════════════════
# 12. 공문 폴더 관리 (화면·명령줄 공용)
# ════════════════════════════════════════════════════════════════
def nfc(s):
    return unicodedata.normalize('NFC', s)


def short_no(v):
    m = re.search(r'-(\d+)$', v or '')
    return m.group(1) if m else (v or '')


class Doc:
    def __init__(self, path, loc):
        self.path, self.loc = path, loc          # loc: 'root' | 'done'
        self.name = os.path.basename(path)
        self.nm = nfc(self.name)
        self.result, self.error = None, None
        self.key = ''

    @property
    def duplicate(self):
        return bool(self.result and self.result.get('duplicate'))

    def rows(self):
        if self.result:
            return self.result['rows']
        return [{'파일명': self.nm, '확인필요': '읽기 실패: ' + str(self.error)}]

    def has_warn(self):
        return bool(self.error) or any(r.get('확인필요') for r in self.rows())


class Folder:
    def __init__(self, path):
        self.path = path
        self.cache = {}
        self.docs, self.done_docs, self.excluded = [], [], []
        self.done_count = 0
        self.std_table, self.std_file, self.std_filled, self.std_error = [], '', 0, ''
        self.status = {'version': 1, 'checked': {}, 'history': []}
        self.read_status()

    # ── 처리상태 파일 (HTML 판과 같은 형식) ──
    def read_status(self):
        self.status = {'version': 1, 'checked': {}, 'history': []}
        p = os.path.join(self.path, STATUS_FILE)
        try:
            with open(p, encoding='utf-8') as f:
                j = json.load(f)
            if isinstance(j, dict):
                self.status = {'version': 1, 'checked': j.get('checked') or {}, 'history': j.get('history') or []}
        except (OSError, ValueError):
            pass

    def write_status(self):
        self.status['updated'] = datetime.now().astimezone().isoformat(timespec='seconds')
        self.status['history'] = self.status['history'][:HISTORY_MAX]
        p = os.path.join(self.path, STATUS_FILE)
        tmp = p + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self.status, f, ensure_ascii=False, indent=1)
        os.replace(tmp, p)

    def is_checked(self, d):
        return d.loc == 'root' and d.key in self.status['checked']

    def set_checked(self, d, on):
        if d.loc != 'root':
            return
        if on:
            self.status['checked'][d.key] = {'at': datetime.now().astimezone().isoformat(timespec='seconds'), 'file': d.nm}
        else:
            self.status['checked'].pop(d.key, None)
        self.write_status()

    # ── 읽기 ──
    def _list(self, folder):
        odt, other, std = [], [], None
        try:
            names = os.listdir(folder)
        except OSError:
            return odt, other, std
        for name in names:
            p = os.path.join(folder, name)
            if not os.path.isfile(p):
                continue
            nm = nfc(name)
            if nm.startswith('~$') or nm.startswith('.'):
                continue
            if nm.lower().endswith('.odt'):
                odt.append(p)
            elif STD_RE.match(nm):
                std = p
            elif nm not in (STATUS_FILE, STATUS_FILE + '.tmp'):
                other.append(nm)
        odt.sort(key=lambda p: nfc(os.path.basename(p)))
        return odt, other, std

    def _parse(self, path, loc):
        st = os.stat(path)
        ck = (loc, nfc(os.path.basename(path)), st.st_size, st.st_mtime_ns)
        if ck in self.cache:
            return self.cache[ck]
        d = Doc(path, loc)
        try:
            if not st.st_size:
                raise ValueError('빈 파일 (다운로드 중이거나 손상된 파일)')
            with open(path, 'rb') as f:
                d.result = extract_odt(f.read(), d.nm)
        except Exception as e:  # noqa: BLE001  공문 하나가 실패해도 나머지는 계속
            d.error = str(e) or e.__class__.__name__
        d.key = d.result['doc']['접수'] if d.result and d.result['doc'].get('접수') else 'file:' + d.nm
        self.cache[ck] = d
        return d

    def scan(self, include_done=False, progress=None):
        odt, other, std = self._list(self.path)
        docs = []
        for i, p in enumerate(odt):
            docs.append(self._parse(p, 'root'))
            if progress:
                progress(i + 1, len(odt))
        self.docs, self.excluded = docs, other
        done_dir = os.path.join(self.path, DONE_DIR)
        dodt = self._list(done_dir)[0] if os.path.isdir(done_dir) else []
        self.done_count = len(dodt)
        self.done_docs = [self._parse(p, 'done') for p in dodt] if include_done else []
        self.load_std(std)
        mark_duplicates([d.result for d in self.docs if d.result])
        mark_duplicates([d.result for d in self.done_docs if d.result])
        self.std_filled = apply_std_table([d.result for d in self.docs + self.done_docs if d.result], self.std_table)

    def load_std(self, path):
        self.std_table, self.std_file, self.std_error = [], '', ''
        if not path:
            return
        try:
            self.std_table = read_std_file(path)
            self.std_file = nfc(os.path.basename(path))
        except Exception as e:  # noqa: BLE001
            self.std_error = f'기준표({nfc(os.path.basename(path))})를 읽지 못했습니다. 엑셀에서 열려 있다면 닫고 새로고침 하세요. ({e})'

    def checked_groups(self):
        groups = {}
        for d in self.docs:
            if self.is_checked(d):
                groups.setdefault(d.key, []).append(d)
        return list(groups.items())

    # ── 이동 ──
    @staticmethod
    def unique_path(folder, name):
        p = os.path.join(folder, name)
        if not os.path.exists(p):
            return p
        base, ext = os.path.splitext(name)
        for k in range(2, 1000):
            p = os.path.join(folder, f'{base} ({k}){ext}')
            if not os.path.exists(p):
                return p
        raise OSError('같은 이름의 파일이 너무 많습니다.')

    @staticmethod
    def explain(e):
        if isinstance(e, FileNotFoundError):
            return '파일이 이미 옮겨졌거나 없습니다. 새로고침 후 다시 확인하세요.'
        if isinstance(e, PermissionError):
            return '파일이 다른 프로그램(한글·엑셀 등)에서 열려 있거나 쓰기 권한이 없습니다. 파일을 닫고 다시 시도하세요.'
        return str(e)

    def move(self, src, dst_dir):
        """같은 드라이브 안의 이름 변경으로 옮김 → 실패하면 아무것도 바뀌지 않음"""
        if not os.path.exists(src):
            raise FileNotFoundError(src)
        os.makedirs(dst_dir, exist_ok=True)
        dst = self.unique_path(dst_dir, nfc(os.path.basename(src)))
        os.rename(src, dst)
        return dst

    def process_checked(self):
        ok, fail = [], []
        done_dir = os.path.join(self.path, DONE_DIR)
        for key, docs in self.checked_groups():
            moved, failed = [], False
            for d in docs:
                try:
                    to = self.move(d.path, done_dir)
                    moved.append({'from': d.nm, 'to': os.path.basename(to)})
                    ok.append((d.nm, os.path.basename(to)))
                except OSError as e:
                    failed = True
                    fail.append((d.nm, self.explain(e)))
            if moved:
                self.status['history'].insert(0, {'at': datetime.now().astimezone().isoformat(timespec='seconds'), 'action': '처리완료', 'key': key, 'files': moved})
            if not failed:
                self.status['checked'].pop(key, None)
        self.write_status()
        return ok, fail

    def restore(self, d):
        to = self.move(d.path, self.path)
        self.status['checked'].pop(d.key, None)
        self.status['history'].insert(0, {'at': datetime.now().astimezone().isoformat(timespec='seconds'), 'action': '되돌리기', 'key': d.key,
                                          'files': [{'from': d.nm, 'to': os.path.basename(to)}]})
        self.write_status()
        return os.path.basename(to)

    def status_of(self, d):
        return '처리완료' if d.loc == 'done' else ('완료체크' if self.is_checked(d) else '처리대기')

    def make_std_template(self):
        results = [d.result for d in self.docs + self.done_docs if d.result]
        miss = missing_std_pairs(results)
        if not miss:
            return None, 0
        fname = '기준표_추가필요.xlsx' if self.std_file else '기준표.xlsx'
        unit = lambda it: {'생태독성': 'TU', '색도': '도', 'pH': ''}.get(it, 'mg/L')
        rows = [[m['지역구분'], m['항목'], '', unit(m['항목']), f"{m['건수']}건 (예: {m['예시']})"] for m in miss]
        guide = [['기준표 작성 방법'], ['1. [기준표] 시트의 기준값 칸을 채우고 저장합니다. (파일 이름은 반드시 기준표.xlsx)'],
                 ['2. 지역구분은 공문에 적힌 값(가, 나, 청정, 특례, 기타, 하수처리구역내 등)을 그대로 씁니다.'],
                 ['3. 지역구분을 비우거나 * 로 쓰면 모든 지역에 적용합니다. 같은 항목에 지역별 기준이 있으면 지역이 맞는 쪽이 우선입니다.'],
                 ['4. 공문에 기준이 적혀 있으면 공문 값을 우선하고, 기준표는 빈 항목만 채웁니다.'],
                 ['5. 항목 이름은 BOD, TOC, SS, T-N, T-P, n-H(광), ABS, 생태독성, 색도 등 프로그램 표준명을 씁니다. (총인·총질소 등도 인식)']]
        data = build_xlsx([
            {'name': '기준표', 'columns': [{'header': '지역구분', 'width': 30}, {'header': '항목', 'width': 14}, {'header': '기준값', 'width': 10},
                                         {'header': '단위', 'width': 8}, {'header': '참고(해당 시료)', 'width': 26}], 'rows': rows,
             'style_of': lambda ri, k, v, row: 2 if k == 2 else 0},
            {'name': '작성 안내', 'columns': [{'header': '안내', 'width': 110}], 'rows': guide}])
        p = os.path.join(self.path, fname)
        with open(p, 'wb') as f:
            f.write(data)
        return fname, len(miss)

    def stats(self):
        live = [d for d in self.docs if not d.duplicate]
        return {'공문': len(live), '시료': sum(len([r for r in d.result['rows'] if r.get('시료번호')]) for d in live if d.result),
                '확인필요': sum(1 for d in self.docs if d.has_warn()), '완료체크': len(self.checked_groups()),
                '중복': len(self.docs) - len(live), '읽기실패': sum(1 for d in self.docs if d.error), 'ODT아님': len(self.excluded)}


# ════════════════════════════════════════════════════════════════
# 13. 화면 (tkinter)
# ════════════════════════════════════════════════════════════════
VIEW_COLS = [  # (키, 표시 이름, 폭, 공문단위 여부, 기본 표시) — v1.1 기본 순서
    ('접수일', '접수일', 100, True, True), ('의뢰기관', '의뢰기관', 80, True, True), ('의뢰자', '의뢰자', 90, True, True),
    ('발신명의', '발신명의', 160, True, True), ('시행', '시행', 170, True, True), ('시료번호', '시료번호', 140, False, True),
    ('검사항목', '검사항목', 260, False, True), ('시료채취일', '시료채취일', 150, False, True),
    ('기준', '기준', 200, False, False), ('지역구분', '지역구분', 170, False, False), ('시료채취자', '채취자', 64, True, False),
    ('접수', '접수번호', 70, True, False), ('시행일', '시행일', 100, True, False), ('제목', '제목', 280, True, False),
    ('기준출처', '기준출처', 80, False, False), ('채취시각', '채취시각', 60, False, False), ('채취일출처', '채취일출처', 70, False, False),
    ('업종/성상', '업종/성상', 160, False, False), ('시료량', '시료량', 160, False, False), ('채취지점', '채취지점', 90, False, False),
    ('비고', '비고', 120, False, False), ('기타', '기타', 160, False, False), ('우편번호', '우편번호', 60, True, False),
    ('주소', '주소', 240, True, False), ('전화번호', '전화번호', 100, True, False), ('이메일', '이메일', 150, True, False),
    ('파일명', '파일명', 280, True, False), ('확인필요', '확인필요', 320, False, True),
]
VIEW_STATES = [('pending', '처리 대기 공문 전체'), ('unchecked', '완료 체크 안 한 공문'), ('checked', '완료 체크한 공문'), ('done', '성적처리완료 폴더')]


def config_path():
    base = os.environ.get('APPDATA') or os.path.expanduser('~')
    return os.path.join(base, '공문추출기_설정.json')


def load_config():
    try:
        with open(config_path(), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    try:
        with open(config_path(), 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def open_with_default_app(path):
    """원본 파일을 기본 프로그램(한글·LibreOffice 등)으로 연다"""
    import subprocess
    if sys.platform == 'win32':
        os.startfile(path)  # noqa: S606
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', path])
    else:
        subprocess.Popen(['xdg-open', path])


def open_preview_in_browser(path, title):
    """원본 ODT를 서식 그대로 HTML로 그려 기본 브라우저에서 연다 (임시 폴더에 저장)"""
    import tempfile
    import webbrowser
    from pathlib import Path
    with open(path, 'rb') as f:
        html = preview_html_document(f.read(), title)
    folder = Path(tempfile.gettempdir()) / '공문추출기_미리보기'
    folder.mkdir(exist_ok=True)
    out = folder / (re.sub(r'[\\/:*?"<>|]', '_', os.path.splitext(title)[0])[:80] + '.html')
    out.write_text(html, encoding='utf-8')
    webbrowser.open(out.as_uri())
    return str(out)


def run_gui(initial_folder=None):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    cfg = load_config()
    if sys.platform == 'win32':  # 고해상도 화면에서 글자가 흐려지지 않게
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass
    root = tk.Tk()
    root.title(f'검사의뢰 공문 추출기 v{VERSION} (파이썬 판)')
    root.geometry(cfg.get('geometry') or '1500x820')
    font = ('Malgun Gothic', 10)
    style = ttk.Style(root)
    try:
        style.theme_use('clam')
    except tk.TclError:
        pass
    style.configure('.', font=font)
    style.configure('Treeview', rowheight=24, font=font)
    style.configure('Treeview.Heading', font=(font[0], 10, 'bold'), background='#eef2f7')
    style.configure('Accent.TButton', foreground='#ffffff', background='#1f5fae')
    style.map('Accent.TButton', background=[('disabled', '#9fb6d6'), ('active', '#194f92')])

    S = {'folder': None, 'sort': ('접수일', -1), 'view': 'pending', 'last_scan': 0.0, 'busy': False,
         'cols': cfg.get('cols_v11') or [k for k, _, _, _, d in VIEW_COLS if d], 'row_doc': {}}

    # ── 상단 ──
    top = tk.Frame(root, bg='#1f2b3a', padx=12, pady=8)
    top.pack(fill='x')
    tk.Label(top, text='검사의뢰 공문 추출기', bg='#1f2b3a', fg='#f2f5f9', font=(font[0], 12, 'bold')).pack(side='left')
    tk.Label(top, text='  공문 폴더', bg='#1f2b3a', fg='#9aa6b5').pack(side='left')
    folder_var = tk.StringVar(value='연결 안 됨')
    tk.Label(top, textvariable=folder_var, bg='#2c3a4c', fg='#ffffff', padx=8, pady=2).pack(side='left', padx=6)
    btn_help = ttk.Button(top, text='도움말')
    btn_help.pack(side='right', padx=2)
    btn_refresh = ttk.Button(top, text='새로고침', state='disabled')
    btn_refresh.pack(side='right', padx=2)
    btn_pick = ttk.Button(top, text='공문 폴더 선택')
    btn_pick.pack(side='right', padx=2)

    # ── 도구줄 ──
    bar = ttk.Frame(root, padding=(12, 6))
    bar.pack(fill='x')
    ttk.Label(bar, text='검색').pack(side='left')
    q_var = tk.StringVar()
    ttk.Entry(bar, textvariable=q_var, width=34).pack(side='left', padx=(4, 10))
    org_var = tk.StringVar(value='기관 전체')
    org_box = ttk.Combobox(bar, textvariable=org_var, state='readonly', width=12, values=['기관 전체'])
    org_box.pack(side='left', padx=4)
    view_var = tk.StringVar(value=VIEW_STATES[0][1])
    view_box = ttk.Combobox(bar, textvariable=view_var, state='readonly', width=22, values=[v for _, v in VIEW_STATES])
    view_box.pack(side='left', padx=4)
    warn_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(bar, text='확인필요만', variable=warn_var).pack(side='left', padx=8)
    col_btn = ttk.Menubutton(bar, text='열 선택')
    col_btn.pack(side='right')
    col_menu = tk.Menu(col_btn, tearoff=False)
    col_btn['menu'] = col_menu
    col_vars = {}

    # ── 표 ──
    mid = ttk.Frame(root)
    mid.pack(fill='both', expand=True)
    cols_all = ['chk'] + [k for k, *_ in VIEW_COLS]
    tree = ttk.Treeview(mid, columns=cols_all, show='headings', selectmode='browse')
    vs = ttk.Scrollbar(mid, orient='vertical', command=tree.yview)
    hs = ttk.Scrollbar(mid, orient='horizontal', command=tree.xview)
    tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
    tree.grid(row=0, column=0, sticky='nsew')
    vs.grid(row=0, column=1, sticky='ns')
    hs.grid(row=1, column=0, sticky='ew')
    mid.rowconfigure(0, weight=1)
    mid.columnconfigure(0, weight=1)
    tree.heading('chk', text='완료')
    tree.column('chk', width=64, anchor='center', stretch=False)
    for k, label, w, _, _ in VIEW_COLS:
        tree.heading(k, text=label, command=lambda k=k: sort_by(k))
        tree.column(k, width=w, stretch=False)
    tree.tag_configure('odd', background='#f7f9fc')
    tree.tag_configure('checked', background='#e7f4ec')
    tree.tag_configure('warn', foreground='#8a5a00')
    tree.tag_configure('dup', background='#f0f1f3', foreground='#8a94a6')
    tree.tag_configure('err', background='#fdecea', foreground='#b42318')

    # ── 하단 ──
    bottom = ttk.Frame(root, padding=(12, 6))
    bottom.pack(fill='x')
    btn_done = ttk.Button(bottom, text='완료 체크한 공문 처리 완료 (0)', style='Accent.TButton', state='disabled')
    btn_done.pack(side='left', padx=2)
    btn_excel = ttk.Button(bottom, text='엑셀 저장', state='disabled')
    btn_excel.pack(side='left', padx=2)
    btn_std = ttk.Button(bottom, text='기준표 양식 만들기', state='disabled')
    btn_std.pack(side='left', padx=2)
    ttk.Separator(bottom, orient='vertical').pack(side='left', fill='y', padx=8)
    btn_preview = ttk.Button(bottom, text='원본 미리보기', state='disabled')
    btn_preview.pack(side='left', padx=2)
    btn_open = ttk.Button(bottom, text='원본 파일 열기', state='disabled')
    btn_open.pack(side='left', padx=2)
    stat_var = tk.StringVar(value='공문 폴더를 선택하세요.')
    ttk.Label(bottom, textvariable=stat_var, foreground='#667085').pack(side='right')

    # ── 동작 ──
    def rebuild_col_menu():
        col_menu.delete(0, 'end')
        for k, label, *_ in VIEW_COLS:
            v = col_vars.setdefault(k, tk.BooleanVar())
            v.set(k in S['cols'])
            col_menu.add_checkbutton(label=label, variable=v, command=lambda k=k: toggle_col(k))
        col_menu.add_separator()
        col_menu.add_command(label='기본값', command=lambda: set_cols([k for k, _, _, _, d in VIEW_COLS if d]))
        col_menu.add_command(label='전체 표시', command=lambda: set_cols([k for k, *_ in VIEW_COLS]))

    def set_cols(cols):
        S['cols'] = cols
        cfg['cols_v11'] = cols
        save_config(cfg)
        rebuild_col_menu()
        render()

    def toggle_col(k):
        cols = [c for c, *_ in VIEW_COLS if (c in S['cols']) != (c == k)]
        set_cols(cols)

    def view_key():
        cur = view_var.get()
        return next((k for k, v in VIEW_STATES if cur.startswith(v)), 'pending')

    def visible_docs():
        F = S['folder']
        if not F:
            return []
        vk = view_key()
        src = F.done_docs if vk == 'done' else F.docs
        q = q_var.get().strip().lower()
        org = org_var.get()
        out = []
        for d in src:
            if vk == 'checked' and not F.is_checked(d):
                continue
            if vk == 'unchecked' and F.is_checked(d):
                continue
            rows = d.rows()
            if org != '기관 전체' and (rows[0].get('의뢰기관') or '') != org:
                continue
            if warn_var.get() and not d.has_warn():
                continue
            if q and q not in d.nm.lower() and not any(q in str(r.get(c) or '').lower() for r in rows for c in COLUMNS):
                continue
            out.append(d)
        key, direction = S['sort']

        def sv(d):
            r = d.rows()[0]
            n = short_no(r.get('접수'))
            rno = n.zfill(10) if n.isdigit() else ''
            if key == '접수':
                return rno or ('~' if direction > 0 else '') + (r.get('접수') or d.nm)
            if key == '접수일':
                return (r.get('접수일') or ('9999' if direction > 0 else '0000')) + '|' + rno
            return str(r.get(key) or '')
        out.sort(key=lambda d: d.nm)
        out.sort(key=sv, reverse=direction < 0)
        return out

    def render(*_):
        F = S['folder']
        tree.delete(*tree.get_children())
        S['row_doc'] = {}
        tree['displaycolumns'] = ['chk'] + [k for k, *_ in VIEW_COLS if k in S['cols']]
        key, direction = S['sort']
        for k, label, *_ in VIEW_COLS:
            tree.heading(k, text=label + ((' ▲' if direction > 0 else ' ▼') if k == key else ''))
        if not F:
            return
        vk = view_key()
        tree.heading('chk', text='되돌리기' if vk == 'done' else '완료')
        orgs = sorted({(d.rows()[0].get('의뢰기관') or '') for d in F.docs + F.done_docs} - {''})
        org_box['values'] = ['기관 전체'] + orgs
        view_box['values'] = [v if k != 'done' else f'{v} ({F.done_count})' for k, v in VIEW_STATES]
        if view_var.get().startswith('성적처리완료'):
            view_var.set(f'성적처리완료 폴더 ({F.done_count})')
        docs = visible_docs()
        for gi, d in enumerate(docs):
            rows = d.rows()
            chk = F.is_checked(d)
            for i, r in enumerate(rows):
                tags = []
                if d.error:
                    tags.append('err')
                elif d.duplicate:
                    tags.append('dup')
                elif chk:
                    tags.append('checked')
                elif gi % 2:
                    tags.append('odd')
                if r.get('확인필요') and not d.error:
                    tags.append('warn')
                vals = []
                for k, _, _, is_doc, _ in VIEW_COLS:
                    v = '' if (is_doc and i > 0) else (r.get(k) or '')
                    if k == '접수' and v:
                        v = short_no(v)
                    if k == '시료채취일' and r.get('채취일출처') == '본문' and v:
                        v += ' (본문)'
                    if k == '기준' and '기준표' in (r.get('기준출처') or '') and v:
                        v += ' [기준표]'
                    if k == '확인필요' and v:
                        v = '⚠ ' + v
                    if d.error and k == '시료번호':
                        v = '읽기 실패 — ' + d.nm
                    if d.error and k == '검사항목':
                        v = str(d.error)
                    vals.append(str(v).replace('\n', ' '))
                first = '' if i > 0 else ('[되돌리기]' if d.loc == 'done' else ('☑' if chk else '☐'))
                iid = tree.insert('', 'end', values=[first] + vals, tags=tags)
                S['row_doc'][iid] = d
        st = F.stats()
        bits = [f"공문 {st['공문']}건", f"시료 {st['시료']}개", f"확인필요 {st['확인필요']}", f"완료체크 {st['완료체크']}"]
        if st['중복']:
            bits.append(f"중복 {st['중복']}")
        if st['읽기실패']:
            bits.append(f"읽기실패 {st['읽기실패']}")
        if st['ODT아님']:
            bits.append(f"ODT 아님 {st['ODT아님']}")
        bits.append(f'기준표 {len(F.std_table)}행 · {F.std_filled}항목 적용' if F.std_file else '기준표 없음')
        total = len(F.done_docs if vk == 'done' else F.docs)
        if len(docs) != total:
            bits.append(f'표시 {len(docs)}건')
        stat_var.set(' · '.join(bits))
        n = st['완료체크']
        btn_done.configure(text=f'완료 체크한 공문 처리 완료 ({n})', state='normal' if n and vk != 'done' else 'disabled')

    def sort_by(k):
        key, direction = S['sort']
        S['sort'] = (k, -direction) if key == k else (k, -1 if k == '접수일' else 1)
        render()

    def scan(quiet=False):
        F = S['folder']
        if not F or S['busy']:
            return
        S['busy'] = True
        try:
            if not quiet:
                root.config(cursor='watch')

                def prog(i, n):
                    stat_var.set(f'공문 읽는 중… {i} / {n}')
                    root.update_idletasks()
            else:
                prog = None
            F.read_status()
            F.scan(include_done=view_key() == 'done', progress=prog)
            if F.std_error and not quiet:
                messagebox.showwarning('기준표', F.std_error)
        except OSError as e:
            messagebox.showerror('폴더 읽기 실패', str(e))
        finally:
            S['busy'] = False
            S['last_scan'] = datetime.now().timestamp()
            root.config(cursor='')
        render()

    def connect(path):
        if not path or not os.path.isdir(path):
            return
        S['folder'] = Folder(path)
        folder_var.set(path)
        cfg['folder'] = path
        save_config(cfg)
        for b in (btn_refresh, btn_excel, btn_std):
            b.configure(state='normal')
        scan()

    def pick():
        p = filedialog.askdirectory(title='공문 폴더 선택', initialdir=cfg.get('folder') or os.path.expanduser('~'))
        if p:
            connect(p)

    def on_click(event):
        if tree.identify_region(event.x, event.y) != 'cell' or tree.identify_column(event.x) != '#1':
            return
        iid = tree.identify_row(event.y)
        d = S['row_doc'].get(iid)
        if not d or tree.set(iid, 'chk') == '':
            return
        F = S['folder']
        if d.loc == 'done':
            restore(d)
        else:
            try:
                F.set_checked(d, not F.is_checked(d))
            except OSError as e:
                messagebox.showerror('처리상태 저장 실패', Folder.explain(e))
            render()
        return 'break'

    def restore(d):
        F = S['folder']
        if not messagebox.askyesno('되돌리기', f'{d.nm}\n\n이 공문을 공문 폴더로 되돌립니다. 완료 체크는 해제됩니다.'):
            return
        try:
            to = F.restore(d)
            messagebox.showinfo('되돌리기', f'되돌렸습니다: {to}')
        except OSError as e:
            messagebox.showerror('되돌리기 실패', Folder.explain(e))
        scan(quiet=True)

    def process():
        F = S['folder']
        groups = F.checked_groups()
        if not groups:
            return
        files = [d.nm for _, ds in groups for d in ds]
        msg = f'완료 체크한 공문 {len(groups)}건(파일 {len(files)}개)을 {DONE_DIR} 폴더로 옮깁니다.\n\n' + '\n'.join('· ' + f for f in files[:25])
        if len(files) > 25:
            msg += f'\n… 외 {len(files) - 25}개'
        if not messagebox.askyesno('처리 완료', msg):
            return
        ok, fail = F.process_checked()
        text = f'옮긴 파일 {len(ok)}개'
        if any(a != b for a, b in ok):
            text += '\n(같은 이름이 있어 번호를 붙인 파일이 있습니다)'
        if fail:
            text += f'\n\n옮기지 못한 파일 {len(fail)}개\n' + '\n'.join(f'· {a}\n   {b}' for a, b in fail) + '\n\n실패한 공문은 완료 체크가 그대로 남아 있습니다.'
            messagebox.showwarning('처리 완료 결과', text)
        else:
            messagebox.showinfo('처리 완료 결과', text)
        scan(quiet=True)

    def export():
        F = S['folder']
        docs = visible_docs()
        if not docs:
            messagebox.showinfo('엑셀 저장', '저장할 공문이 없습니다.')
            return
        p = filedialog.asksaveasfilename(title='엑셀 저장', defaultextension='.xlsx', initialdir=cfg.get('excel_dir') or F.path,
                                         initialfile=f'공문추출_{datetime.now():%Y-%m-%d}.xlsx', filetypes=[('엑셀 파일', '*.xlsx')])
        if not p:
            return
        try:
            with open(p, 'wb') as f:
                f.write(export_rows_xlsx(docs, F.status_of))
            cfg['excel_dir'] = os.path.dirname(p)
            save_config(cfg)
            messagebox.showinfo('엑셀 저장', f'저장했습니다.\n{p}')
        except PermissionError:
            messagebox.showerror('엑셀 저장', '같은 이름의 엑셀 파일이 열려 있어 저장할 수 없습니다. 엑셀을 닫거나 다른 이름으로 저장하세요.')

    def std_template():
        F = S['folder']
        fname = '기준표_추가필요.xlsx' if F.std_file else '기준표.xlsx'
        if not messagebox.askyesno('기준표 양식 만들기', f'기준이 비어 있는 지역구분 × 항목을 모아 공문 폴더에 {fname} 파일을 만듭니다.\n\n'
                                   '1. 엑셀로 열어 기준값 칸을 채우고 저장합니다.\n'
                                   + ('2. 채운 행을 기존 기준표.xlsx에 옮겨 붙입니다.\n' if F.std_file else '')
                                   + '3. 엑셀을 닫고 [새로고침]을 누르면 기준이 채워집니다.'):
            return
        try:
            name, n = F.make_std_template()
            if not name:
                messagebox.showinfo('기준표', '기준이 비어 있는 항목이 없습니다.')
            else:
                messagebox.showinfo('기준표', f'{name} 파일을 만들었습니다. ({n}개 항목)')
        except OSError as e:
            messagebox.showerror('기준표', Folder.explain(e))

    def selected_doc():
        sel = tree.selection()
        return S['row_doc'].get(sel[0]) if sel else None

    def open_original(d=None):
        d = d or selected_doc()
        if not d:
            messagebox.showinfo('원본 파일 열기', '표에서 공문 행을 먼저 선택하세요.')
            return
        try:
            open_with_default_app(d.path)
        except OSError as e:
            messagebox.showerror('원본 파일 열기', f'파일을 열지 못했습니다. ODT를 열 수 있는 프로그램(한글 등)이 있는지 확인하세요.\n\n{Folder.explain(e)}')

    def preview_original(d=None):
        d = d or selected_doc()
        if not d:
            messagebox.showinfo('원본 미리보기', '표에서 공문 행을 먼저 선택하세요.')
            return
        try:
            open_preview_in_browser(d.path, d.nm)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror('원본 미리보기', f'원본을 표시할 수 없습니다.\n\n{e}')

    def on_select(event=None):
        st = 'normal' if selected_doc() else 'disabled'
        btn_preview.configure(state=st)
        btn_open.configure(state=st)

    def detail(event=None):
        sel = tree.selection()
        if not sel:
            return
        d = S['row_doc'].get(sel[0])
        if not d:
            return
        w = tk.Toplevel(root)
        w.title(d.nm)
        w.geometry('760x720')
        bar2 = ttk.Frame(w, padding=(10, 6))
        bar2.pack(fill='x')
        ttk.Button(bar2, text='원본 미리보기 (서식 그대로)', command=lambda: preview_original(d)).pack(side='left', padx=2)
        ttk.Button(bar2, text='원본 파일 열기 (한글 등)', command=lambda: open_original(d)).pack(side='left', padx=2)
        ttk.Label(bar2, text=d.nm, foreground='#667085').pack(side='left', padx=10)
        txt = tk.Text(w, wrap='word', font=font, padx=10, pady=10, tabs=('100p',))
        sb = ttk.Scrollbar(w, command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        txt.pack(fill='both', expand=True)
        txt.tag_configure('h', font=(font[0], 11, 'bold'), spacing1=10, spacing3=4)
        txt.tag_configure('w', foreground='#8a5a00', background='#fff4cc')
        txt.tag_configure('m', background='#ffe58a')
        if d.error:
            txt.insert('end', f'읽기 실패: {d.error}\n', 'w')
        if d.result:
            dd, res = d.result['doc'], d.result
            txt.insert('end', dd['제목'] + '\n', 'h')
            warns = list(dict.fromkeys(x for r in res['rows'] for x in (r.get('확인필요') or '').split(' / ') if x))
            for x in warns:
                txt.insert('end', '⚠ ' + x + '\n', 'w')
            for k, v in [('파일', d.nm), ('의뢰기관', f"{dd['의뢰기관']} / {dd['의뢰자']}"), ('발신명의', dd['발신명의']),
                         ('시행', f"{dd['시행']} ({dd['시행일']})"), ('접수', f"{dd['접수']} ({dd['접수일']})"),
                         ('시료채취자', f"{dd['시료채취자']} ({dd['기안자직위']})"), ('주소', f"{dd['우편번호']} {dd['주소']}"),
                         ('연락처', f"{dd['전화번호']} {dd['이메일']}")]:
                txt.insert('end', f'{k}\t{v}\n')
            txt.insert('end', '\n추출된 시료\n', 'h')
            for r in res['rows']:
                if r.get('시료번호'):
                    txt.insert('end', f"· {r['시료번호']} | {r['검사항목']} | 기준: {r['기준'] or '-'} | 지역: {r['지역구분'] or '-'} | 채취일: {r['시료채취일']}"
                                      f"{' (본문)' if r.get('채취일출처') == '본문' else ''}\n")
            for t in res['tables']:
                txt.insert('end', '\n공문 시료 표 원문\n', 'h')
                for row in t['raw']:
                    txt.insert('end', ' | '.join(row) + '\n')
            if dd.get('본문'):
                txt.insert('end', '\n본문\n', 'h')
                for p in dd['본문']:
                    pos = 0
                    for m in DATE_RE.finditer(p):
                        txt.insert('end', p[pos:m.start()])
                        txt.insert('end', m.group(0), 'm')
                        pos = m.end()
                    txt.insert('end', p[pos:] + '\n')
        txt.configure(state='disabled')

    def help_():
        messagebox.showinfo('사용 방법', '1. 공문(ODT)을 공문 폴더에 저장합니다. 창으로 돌아오면 자동으로 다시 읽습니다.\n\n'
                            '2. 시료 1개당 1행으로, 최근 접수한 공문이 위에 보입니다. 확인필요 열(⚠)은 직접 확인이 필요한 값입니다. 행을 두 번 누르면 추출 결과 창이 열리고, [원본 미리보기]는 서식 그대로 브라우저에, [원본 파일 열기]는 한글 등으로 원본을 엽니다.\n\n'
                            f'3. 성적 작성이 끝난 공문은 맨 앞 [완료] 칸을 눌러 체크합니다(공문 단위). 체크는 {STATUS_FILE}에 저장되어 HTML 판과 함께 쓸 수 있습니다.\n\n'
                            f'4. [처리 완료]를 누르면 체크한 공문이 {DONE_DIR} 폴더로 옮겨집니다. 보기에서 [성적처리완료 폴더]를 고르면 [되돌리기]를 할 수 있습니다.\n\n'
                            '5. [엑셀 저장]은 현재 보이는 공문을 저장합니다. 모든 칸은 텍스트입니다.\n\n'
                            '6. [기준표 양식 만들기]로 기준이 빈 항목 목록을 만들고, 기준값을 채워 기준표.xlsx로 두면 자동으로 채워집니다.')

    def on_focus(event):
        if event.widget is root and S['folder'] and not S['busy'] and datetime.now().timestamp() - S['last_scan'] > 2:
            scan(quiet=True)

    def on_close():
        cfg['geometry'] = root.geometry()
        save_config(cfg)
        root.destroy()

    btn_pick.configure(command=pick)
    btn_refresh.configure(command=scan)
    btn_help.configure(command=help_)
    btn_done.configure(command=process)
    btn_excel.configure(command=export)
    btn_std.configure(command=std_template)
    btn_preview.configure(command=preview_original)
    btn_open.configure(command=open_original)
    tree.bind('<<TreeviewSelect>>', on_select)
    tree.bind('<Button-1>', on_click)
    tree.bind('<Double-1>', detail)
    tree.bind('<Return>', detail)
    q_var.trace_add('write', render)
    org_box.bind('<<ComboboxSelected>>', render)
    view_box.bind('<<ComboboxSelected>>', lambda e: scan() if view_key() == 'done' else render())
    warn_var.trace_add('write', render)
    root.bind('<FocusIn>', on_focus)
    root.protocol('WM_DELETE_WINDOW', on_close)
    rebuild_col_menu()
    render()
    start = initial_folder or cfg.get('folder')
    if start and os.path.isdir(start):
        root.after(100, lambda: connect(start))
    root.mainloop()


# ════════════════════════════════════════════════════════════════
# 14. 명령줄
# ════════════════════════════════════════════════════════════════
def run_cli(args):
    F = Folder(args.folder)
    F.scan(include_done=args.include_done)
    if F.std_error:
        print('[경고]', F.std_error, file=sys.stderr)
    docs = F.docs + (F.done_docs if args.include_done else [])
    st = F.stats()
    print(f"공문 {st['공문']}건 · 시료 {st['시료']}개 · 확인필요 {st['확인필요']} · 중복 {st['중복']} · 읽기실패 {st['읽기실패']}"
          + (f' · 기준표 {len(F.std_table)}행 {F.std_filled}항목 적용' if F.std_file else ''))
    if args.excel:
        with open(args.excel, 'wb') as f:
            f.write(export_rows_xlsx(docs, F.status_of))
        print('엑셀 저장:', args.excel)
    if args.json:
        out = [{'파일명': d.nm, '위치': d.loc, '상태': F.status_of(d), '오류': d.error,
                'rows': [{c: r.get(c, '') for c in COLUMNS} for r in d.rows()]} for d in docs]
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('JSON 저장:', args.json)
    if not args.excel and not args.json:
        for d in docs:
            for r in d.rows():
                print(' | '.join(str(r.get(c, '')) for c in ('접수', '의뢰기관', '시료번호', '검사항목', '기준', '시료채취일', '확인필요')))


def main(argv=None):
    ap = argparse.ArgumentParser(description='검사의뢰 공문(ODT) 추출기')
    ap.add_argument('--folder', help='공문 폴더 (지정하지 않으면 창으로 실행)')
    ap.add_argument('--excel', help='엑셀로 저장할 경로 (창 없이 실행)')
    ap.add_argument('--json', help='JSON으로 저장할 경로 (창 없이 실행)')
    ap.add_argument('--include-done', action='store_true', help='성적처리완료 폴더의 공문도 포함')
    ap.add_argument('--gui', action='store_true', help='--folder를 지정해도 창으로 실행')
    ap.add_argument('--preview', metavar='ODT', help='원본 ODT를 서식 그대로 HTML로 만들어 브라우저에서 열기')
    ap.add_argument('--preview-out', metavar='HTML', help='--preview 결과를 이 경로에 저장만 함 (브라우저 열지 않음)')
    args = ap.parse_args(argv)
    if args.preview:
        if args.preview_out:
            with open(args.preview, 'rb') as f:
                html = preview_html_document(f.read(), nfc(os.path.basename(args.preview)))
            with open(args.preview_out, 'w', encoding='utf-8') as f:
                f.write(html)
            print('미리보기 저장:', args.preview_out)
        else:
            print('미리보기:', open_preview_in_browser(args.preview, nfc(os.path.basename(args.preview))))
        return
    if args.folder and not args.gui:
        if not os.path.isdir(args.folder):
            ap.error('폴더를 찾을 수 없습니다: ' + args.folder)
        run_cli(args)
    else:
        run_gui(args.folder)


if __name__ == '__main__':
    main()
