# -*- coding: utf-8 -*-
"""원본 대조 엔진.

방법 요약(이름이 아니라 '숫자가 놓인 모양'으로 출처를 찾는다)
 ① 색인   : 모든 원본의 숫자 칸을 값 순서로 정렬해 둔다(배율별: 그대로·÷1,000·÷1,000,000·×1,000·×100).
 ② 후보   : 문서 숫자 하나마다 반올림 범위 안에 드는 원본 칸을 찾는다.
 ③ 열 맞추기: 문서 표의 한 열에 있는 숫자들이 원본의 어느 열(배율 포함)에 몰려 있는지 투표한다.
            표가 행·열이 뒤바뀌어 있을 수 있으므로 '그대로'와 '뒤집기' 두 방향을 모두 시험한다.
 ④ 행 맞추기: 맞춘 열 안에서 문서의 각 행이 원본의 어느 행인지 투표한다.
 ⑤ 보충    : 맞춘 행·열 정보로 아직 못 맞춘 열·행을 다시 맞춘다(작은 숫자처럼 흔한 값도 여기서 쓰임).
 ⑥ 판정    : 맞춘 위치의 원본 값과 문서 값을 비교한다(일치·반올림·단위환산·단위 다름·불일치).
 ⑦ 내부 점검: 합계 행·열, 비율(%) 열, 증감률 문장, 날짜 요일을 다시 계산한다.

파일 구성
  index.py      ① 원본 색인(SourceIndex)
  table_map.py  ②~⑤ 표를 원본 블록과 맞추기
  judge.py      ⑥ 칸별 판정
  calc.py       ⑦ 합계·비율 재계산
  clips.py      복사 기록 힌트
  verifier.py   위 조각을 합친 Verifier
"""
from app.parts.verify.engine.index import SourceIndex, AGREE, DISAGREE, scale_label   # noqa: F401
from app.parts.verify.engine.verifier import Verifier                               # noqa: F401
