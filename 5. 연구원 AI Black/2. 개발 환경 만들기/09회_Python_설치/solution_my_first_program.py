"""09회 과제 해답 — 측정값을 바꾸고 기준 초과 횟수를 추가한 버전 (가상 데이터)"""

# 측정 지점 이름과 5분 간격 CO2 측정값(ppm)
place = "1층 사무실"
values = [612, 645, 701, 688, 720, 695, 710, 702]

# 기준값
limit = 1000

# 평균 계산: 합계 ÷ 개수
average = sum(values) / len(values)

# 결과 출력
print("측정 지점 :", place)
print("측정 횟수 :", len(values), "회")
print("최댓값    :", max(values), "ppm")
print("최솟값    :", min(values), "ppm")
print("평균      :", round(average, 1), "ppm")

# 판정: 평균이 기준 이상이면 부적합
if average >= limit:
    print("판정      : 부적합 (기준", limit, "ppm 이상)")
else:
    print("판정      : 적합")

# 도전: 기준 이상인 측정값의 개수 세기
over_count = 0
for value in values:
    if value >= limit:
        over_count = over_count + 1
print("기준 초과 횟수 :", over_count, "회")
