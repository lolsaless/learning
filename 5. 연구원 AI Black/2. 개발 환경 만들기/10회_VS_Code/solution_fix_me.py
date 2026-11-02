"""10회 실습 해답 — 오류 3개를 고친 버전"""

place = "3층 사무실"                     # 오류 1: 닫는 따옴표 추가
values = [512, 548, 601, 577, 630]

limit = 1000
average = sum(values) / len(values)

print("측정 지점 :", place)
print("평균      :", round(average, 1), "ppm")   # 오류 2: averge → average

if average >= limit:
    print("판정      : 부적합")            # 오류 3: if 아래 줄 들여쓰기(공백 4칸)
else:
    print("판정      : 적합")
