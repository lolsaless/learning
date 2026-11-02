# 재제출 비교 파트 (`parts/compare`)

## 하는 일
팀이 원본을 고쳐 다시 보냈을 때 **무엇이 바뀌었고 문서의 어느 칸을 고쳐야 하는지** 알려 준다.
1. 보관: 원본을 등록하거나 내용이 바뀔 때마다 그 판을 작업 폴더 `원본보관/` 에 복사(원본 파일은 그대로)
2. 비교: 이전 판 ↔ 새 판 칸 단위 비교. 형식이 달라도 됨(xlsx·ods·csv·pdf·docx·hwpx …). 행이 끼워지면 행 이름으로 줄 맞춤
3. 영향: 바뀐 칸을 출처로 쓰던 문서 칸과, 새 값으로 바꾸면 문서에 적힐 값(배율·자릿수 반영)
4. 짝 찾기: 이름이 바뀐 새 파일(`…(수정).xlsx`)이 어느 원본의 새 판인지 이름·내용으로 추정

## 파일
- diff.py — flatten(형식 무관 칸 목록) · diff · similarity
- part.py — ComparePart(archive · archived · compare_paths · affected · match) / routes.py

## 입구
- archive(sid, 경로, 내용고유값) / compare_paths(이전, 이후) / affected(비교, 출처색인) / match(새 파일, 원본 목록, 읽은 원본)

## 출구
- 원본 변경 확인 결과에 diff·impact 를 붙임(조립부 check_sources)
- 재제출 확인 resubmit_check → 교체 resubmit_apply(조립부)

## 화면 주소
/api/resubmit/check · /api/resubmit/apply · /api/compare

## 한계
- 여러 칸의 평균·합으로 만든 문서 값(월평균 등)은 '영향'에 새 값을 계산해 넣지 않는다(다시 검증하면 빨강으로 보임).
- 인쇄 문서(pdf·docx) 원본은 표시 자릿수까지만 알 수 있어 끝자리 1 차이가 날 수 있다.

## 시험
tests/test_compare.py · app/evaluation.py score_resubmit(정답표 '재제출')
