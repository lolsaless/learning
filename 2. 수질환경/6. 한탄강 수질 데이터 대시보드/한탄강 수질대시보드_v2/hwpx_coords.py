"""hwpx(한글) 측정망 좌표표 → 리스트. 사용: python parse_hwpx.py 파일.hwpx"""
import re, sys, zipfile, xml.etree.ElementTree as ET
HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'
def dms(s):
    n = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', s)]
    return round(n[0] + n[1]/60 + n[2]/3600, 6) if len(n) >= 3 else None
def read(path):
    with zipfile.ZipFile(path) as z:
        secs = sorted(n for n in z.namelist() if re.match(r'Contents/section\d+\.xml', n))
        out = []
        for s in secs:
            root = ET.fromstring(z.read(s))
            for tbl in root.iter(HP+'tbl'):
                grid, carry = {}, {}
                for tc in tbl.iter(HP+'tc'):
                    a = tc.find(HP+'cellAddr'); sp = tc.find(HP+'cellSpan')
                    c, r, rs = int(a.get('colAddr')), int(a.get('rowAddr')), int(sp.get('rowSpan'))
                    txt = ''.join(t.text or '' for t in tc.iter(HP+'t')).strip()
                    for k in range(rs): grid[(r+k, c)] = txt
                rows = sorted({r for r, _ in grid})
                for r in rows:
                    lat, lon = dms(grid.get((r,5),'')), dms(grid.get((r,6),''))
                    if lat and lon and 33 < lat < 39 and 124 < lon < 132:
                        out.append({'수계': grid.get((r,0),''), '중권역': grid.get((r,1),''), '지점명': grid.get((r,2),''),
                                    '주소': grid.get((r,3),''), '채수지점': grid.get((r,4),''), '위도': lat, '경도': lon,
                                    '분류번호': grid.get((r,7),'')})
    return out
if __name__ == '__main__':
    for x in read(sys.argv[1]): print(x)
