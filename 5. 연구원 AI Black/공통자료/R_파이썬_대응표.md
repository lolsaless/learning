# R ↔ 파이썬 대응표

> 이 저장소의 기존 R 코드(`4. R/`)를 읽고 파이썬으로 옮길 때 쓰는 표입니다.
> 어느 R 파일이 몇 회차 실습이 되는지는 `00_커리큘럼/03_R_파이썬_변환_대응표.md`를 보세요.
> **pandas** 열은 4단계부터 쓰는 방법입니다.

## 1. 기본 문법

| 하는 일 | R | 파이썬 |
|---|---|---|
| 값 담기 | `x <- 10` | `x = 10` |
| 출력 | `print(x)` | `print(x)` |
| 주석 | `# 설명` | `# 설명` |
| 문자열 붙이기 | `paste("CO2", "ppm")` / `paste0(...)` | `"CO2" + " ppm"`, `f"{a} {b}"` |
| 나머지 | `7 %% 2` | `7 % 2` |
| 몫 | `7 %/% 2` | `7 // 2` |
| 같다 / 다르다 | `==` / `!=` | `==` / `!=` |
| 그리고 / 또는 / 아님 | `&` `&&` / `|` `||` / `!` | `and` / `or` / `not` |
| 참·거짓 | `TRUE`, `FALSE` | `True`, `False` |
| 값 없음 | `NA`, `NULL` | `None` (pandas: `NaN`) |

## 2. 자료 구조

| 하는 일 | R | 파이썬 (기본) | pandas (4단계) |
|---|---|---|---|
| 값 여러 개 | `c(1, 2, 3)` | `[1, 2, 3]` | `pd.Series([1, 2, 3])` |
| 1부터 10 | `1:10` | `range(1, 11)` | |
| 길이 | `length(x)` | `len(x)` | `len(s)` |
| 첫 번째 값 | `x[1]` | `x[0]` ⚠️ | `s.iloc[0]` |
| 마지막 값 | `x[length(x)]` | `x[-1]` | `s.iloc[-1]` |
| 2~4번째 | `x[2:4]` | `x[1:4]` ⚠️ | `s.iloc[1:4]` |
| 이름 붙은 목록 | `list(a = 1, b = 2)` | `{"a": 1, "b": 2}` | |
| 표 | `data.frame(...)`, `tibble(...)` | 딕셔너리의 리스트 | `pd.DataFrame(...)` |
| 열 꺼내기 | `df$연비` | `[r["연비"] for r in rows]` | `df["연비"]` |
| 행·열 수 | `nrow(df)`, `ncol(df)`, `dim(df)` | `len(rows)`, `len(rows[0])` | `df.shape` |
| 열 이름 | `names(df)` | `list(rows[0].keys())` | `df.columns` |
| 앞부분 | `head(df, 5)` | `rows[:5]` | `df.head(5)` |

## 3. 계산

| 하는 일 | R | 파이썬 (기본) | pandas |
|---|---|---|---|
| 합계·평균 | `sum(x)`, `mean(x)` | `sum(x)`, `statistics.mean(x)` | `s.sum()`, `s.mean()` |
| 결측 제외 평균 | `mean(x, na.rm = TRUE)` | `mean([v for v in x if v is not None])` | `s.mean()` (자동 제외) |
| 표준편차 | `sd(x)` | `statistics.stdev(x)` | `s.std()` |
| 중앙값 | `median(x)` | `statistics.median(x)` | `s.median()` |
| 최대·최소 | `max(x)`, `min(x)` | `max(x)`, `min(x)` | `s.max()`, `s.min()` |
| 반올림 | `round(x, 1)` | `round(x, 1)` | `s.round(1)` |
| 로그 | `log(x)` (자연로그) | `math.log(x)` | `np.log(s)` |
| 위치끼리 더하기 | `a + b` | `[x + y for x, y in zip(a, b)]` ⚠️ | `df["a"] + df["b"]` |
| 결측 확인 | `is.na(x)` | `v is None` | `s.isna()` |

## 4. 제어문과 함수

| 하는 일 | R | 파이썬 |
|---|---|---|
| 조건 | `if (x >= 1000) { ... } else { ... }` | `if x >= 1000:` + 들여쓰기 / `else:` |
| 한 줄 조건 | `ifelse(x >= 1000, "부적합", "적합")` | `"부적합" if x >= 1000 else "적합"` (pandas: `np.where(...)`) |
| 반복 | `for (i in 1:20) { ... }` | `for i in range(1, 21):` |
| while | `while (i <= 10) { ... }` | `while i <= 10:` |
| 함수 | `f <- function(x, y = 2) { x + y }` | `def f(x, y=2):` + `return x + y` |
| 목록에 함수 적용 | `lapply(x, f)`, `sapply(x, f)` | `[f(v) for v in x]` |

## 5. 문자열

| 하는 일 | R (stringr 포함) | 파이썬 |
|---|---|---|
| 자르기 | `substr(s, 1, 10)` | `s[:10]` |
| 나누기 | `str_split(s, "/")[[1]][3]` | `s.split("/")[2]` ⚠️ |
| 포함 여부 | `str_detect(s, "실내공기질")` | `"실내공기질" in s` |
| 바꾸기 | `gsub(")", "", s)` | `s.replace(")", "")` |
| 공백 제거 | `trimws(s)` | `s.strip()` |
| 열 나누기 | `separate(df, 열, into = c(...), sep = " ~ ")` | `s.split(" ~ ")` (pandas: `df["열"].str.split(" ~ ", expand=True)`) |

## 6. 파일과 데이터

| 하는 일 | R | 파이썬 (기본) | pandas |
|---|---|---|---|
| 작업 폴더 | `setwd("D:/...")` ⚠️ 고정 경로 | `Path.cwd()`, `Path(__file__).parent` | |
| CSV 읽기 | `read.csv("a.csv")` | `csv.DictReader` | `pd.read_csv("a.csv")` |
| 엑셀 읽기 | `readxl::read_excel("a.xlsx")` | `openpyxl` | `pd.read_excel("a.xlsx")` |
| CSV 쓰기 | `write.csv(df, "a.csv", row.names = FALSE)` | `csv.DictWriter` | `df.to_csv("a.csv", index=False, encoding="utf-8-sig")` |
| 엑셀 쓰기 | `writexl::write_xlsx(df, "a.xlsx")` | | `df.to_excel("a.xlsx", index=False)` |
| 패키지 불러오기 | `library(tidyverse)` | `import pandas as pd` | |
| 패키지 설치 | `install.packages("x")` | `pip install x` (가상환경 안) | |

## 7. dplyr ↔ pandas (4단계 미리 보기)

| dplyr | pandas |
|---|---|
| `filter(df, 항목 == "CO2")` | `df[df["항목"] == "CO2"]` 또는 `df.query('항목 == "CO2"')` |
| `select(df, 시설명, 측정값)` | `df[["시설명", "측정값"]]` |
| `mutate(df, 판정 = ifelse(...))` | `df["판정"] = np.where(...)` |
| `arrange(df, desc(측정값))` | `df.sort_values("측정값", ascending=False)` |
| `group_by(df, 시설군) %>% summarize(평균 = mean(측정값))` | `df.groupby("시설군")["측정값"].mean()` |
| `inner_join(a, b, by = "접수번호")` | `a.merge(b, on="접수번호")` |
| `pivot_longer(...)` / `pivot_wider(...)` | `df.melt(...)` / `df.pivot(...)` |
| `%>%` (파이프) | 메서드 이어 쓰기 `df.query(...).groupby(...).mean()` |

## 8. ggplot2 ↔ matplotlib/seaborn (5단계 미리 보기)

| ggplot2 | 파이썬 |
|---|---|
| `geom_point()` | `plt.scatter(x, y)` / `sns.scatterplot(...)` |
| `geom_line()` | `plt.plot(x, y)` |
| `geom_bar()`, `geom_col()` | `plt.bar(x, y)` |
| `geom_boxplot()` | `sns.boxplot(...)` |
| `geom_histogram()` | `plt.hist(x, bins=20)` |
| `geom_hline(yintercept = 1000)` | `plt.axhline(1000)` |
| `geom_smooth(method = "lm")` | `sns.regplot(...)` |
| `geom_text_repel()` | `adjustText` 라이브러리 |
| `facet_wrap(~ 항목)` | `sns.FacetGrid` / `plt.subplots` |

---

### ⚠️ 표시는 옮길 때 가장 자주 틀리는 곳입니다
1. **번호는 0부터** — R `x[1]` = 파이썬 `x[0]`, R `[2:4]` = 파이썬 `[1:4]`
2. **리스트 `+`** — R의 벡터 `a + b`는 위치끼리 더하기, 파이썬 리스트 `a + b`는 이어 붙이기
3. **고정 경로** — R 코드의 `setwd("D:/github/...")`는 다른 PC에서 동작하지 않음 → 상대 경로로
