"""문서 데이터 모델 — 파서가 만들고 비교기가 읽는 공통 형식.

Document
 ├ layout: [노드]       (v1.1) 문서 모양 재현용 배치 트리 — 문단·표·셀의 순서와 모양 정보.
 │                       노드의 "b" 는 blocks 의 순번(글자가 없는 빈 문단·빈 셀은 None).
 │     문단 {"t":"p","b":순번,"ps":문단모양ID,"pg":쪽,"items":[하위 노드],"sec":구역,"sp":[시작,끝]}
 │     표   {"t":"tbl","w":너비,"align":정렬,"rows":[[셀]]}
 │       셀 {"b","cs":열합침,"rs":행합침,"w","h","bf":테두리ID,"ps","va":세로정렬,"items",
 │            "r","c":행·열(1부터),"sec","sp":칸 안 문단들 범위}   (v2.0 sec·sp·r·c — 병합 위치)
 │     기타 {"t":"sub","kind":"header|footer|note|shape","label":이름,"paras":[문단 노드]}
 └ blocks: [Block]      문서 순서대로 펼친 '비교 단위'
     · 본문 문단 1개 = Block 1개 (kind='para')
     · 표 셀 1개    = Block 1개 (kind='cell', 셀 안 여러 문단은 줄바꿈으로 이어 붙임)
     · 머리말/꼬리말/각주/글상자 = kind='header'|'footer'|'note'|'shape'
     └ runs: [Run]      같은 서식으로 이어진 글자 묶음 (서식 비교용)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Run:
    text: str
    style: str              # 서식 키 (Document.styles 의 키). 해석된 속성값으로 만든 문자열이라
                            # 서로 다른 파일 사이에서도 같은 서식이면 같은 키가 된다.


@dataclass
class Block:
    index: int              # 문서 안 순번 (0부터)
    kind: str               # para | cell | header | footer | note | shape
    path: str               # 기계용 위치 (예: s0/p12/t3/r1c2)
    location: str           # 사람용 위치 (예: "표 3 · 2행 3열")
    context: str            # 가까운 제목 문단 (예: "□ 조사 결과")
    page: int               # 추정 쪽 번호 (줄 배치 정보 기반, 참고용)
    text: str
    runs: List[Run] = field(default_factory=list)
    table: Optional[int] = None   # 표 번호 (1부터)
    row: Optional[int] = None     # 행 (1부터)
    col: Optional[int] = None     # 열 (1부터)
    span: Optional[List[int]] = None   # (v2.0) [구역 번호, 시작, 끝] 원문 바이트 위치 — 문단은 hp:p 요소 전체,
                                       #        표 칸은 칸 안 첫 문단 시작 ~ 마지막 문단 끝

    def char_styles(self) -> List[str]:
        """글자 하나하나의 서식 키 목록 (text 와 길이가 같음)."""
        out: List[str] = []
        for r in self.runs:
            out.extend([r.style] * len(r.text))
        return out


@dataclass
class Document:
    id: str
    name: str
    size: int
    sha1: str
    meta: Dict[str, str]                 # 작성자, 수정일 등 (content.hpf)
    blocks: List[Block]
    styles: Dict[str, Dict[str, Any]]    # 서식 키 → 속성 {font,size,color,...}
    stats: Dict[str, int]
    warnings: List[str] = field(default_factory=list)
    source_path: str = ""                # 폴더에서 읽었으면 원래 경로
    # ── v1.1 문서 모양 재현용 ──
    layout: List[Dict[str, Any]] = field(default_factory=list)
    para_styles: Dict[str, Dict[str, Any]] = field(default_factory=dict)    # paraPr id → 속성
    border_fills: Dict[str, Dict[str, Any]] = field(default_factory=dict)   # borderFill id → 속성
    page_setup: Dict[str, int] = field(default_factory=dict)                # 용지 크기·여백 (HWPUNIT)
    # ── v2.0 병합·고치기용: 원본 파일 그대로 (JSON 으로 내보내지 않음) ──
    raw: bytes = field(default=b"", repr=False)
    section_names: List[str] = field(default_factory=list)

    @property
    def modified(self) -> str:
        return self.meta.get("ModifiedDate", "")

    def summary(self) -> Dict[str, Any]:
        """목록 표시에 쓰는 가벼운 정보 (블록 내용 제외)."""
        return {
            "id": self.id, "name": self.name, "size": self.size, "sha1": self.sha1,
            "meta": self.meta, "stats": self.stats, "warnings": self.warnings,
            "source_path": self.source_path,
        }

    def to_dict(self) -> Dict[str, Any]:
        d = self.summary()
        d["blocks"] = [asdict(b) for b in self.blocks]
        d["layout"] = self.layout
        return d
