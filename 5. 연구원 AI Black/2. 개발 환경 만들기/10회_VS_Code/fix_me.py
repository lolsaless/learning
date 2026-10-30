"""10회 실습 — 오류 찾기

이 파일에는 일부러 넣은 오류가 3개 있습니다.
VS Code에서 열면 오류가 있는 곳에 빨간 물결 밑줄이 생깁니다.
밑줄에 마우스를 올려 설명을 읽고, 하나씩 고친 뒤 실행해 보세요.
"""

place = "3층 사무실
values = [512, 548, 601, 577, 630]

limit = 1000
average = sum(values) / len(values)

print("측정 지점 :", place)
print("평균      :", round(averge, 1), "ppm")

if average >= limit:
print("판정      : 부적합")
else:
    print("판정      : 적합")
