# -*- coding: utf-8 -*-
"""파트 지도 만들기: 코드를 읽어 docs/파트지도.md 를 다시 쓴다.  실행: python tools/part_map.py"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.web.partmap import to_markdown, build      # noqa: E402

if __name__ == "__main__":
    m = build()
    out = os.path.join(ROOT, "docs", "파트지도.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(to_markdown(m))
    print(f"파트 지도 저장: {out}  (구성요소 {len(m['components'])}개, 파일 {m['total_files']}개, {m['total_lines']:,}줄)")
