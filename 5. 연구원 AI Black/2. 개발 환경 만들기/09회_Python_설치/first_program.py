"""나의 첫 파이썬 프로그램 — CO2 측정값 판정

측정값 목록의 평균을 구하고, 기준(1,000 ppm)과 비교해 판정합니다.
(측정값은 수업용 가상 데이터입니다)

실행 방법
    Mac     : python3.13 first_program.py
    Windows : py -3.13 first_program.py
"""

# 측정 지점 이름과 5분 간격 CO2 측정값(ppm)
place = "2층 교실"
values = [930, 1012, 1088, 1045, 1120, 998, 1061]

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
