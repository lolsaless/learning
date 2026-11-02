# -*- coding: utf-8 -*-
"""[가상자료 ①] 가상 사전: 기관·시군·하천·측정소·사람 이름·주소·문구.

모두 지어낸 이름이다. 실제 기관·사람·주소를 쓰지 않는다(대회 규칙: 합성 모의데이터만).
공문 서식(수신·경유·제목·붙임·끝·결재 줄·시행 번호·공개 구분)은 실제 공문의 '틀'만 참고했다.
"""

PROVINCES = ["한빛도", "가람도", "누리도", "솔빛도", "마루도", "하늬도", "별무리도", "온새도"]
CITY_ROOTS = ["가온", "나래", "다솜", "라온", "마루", "바다", "사랑", "아라", "자람", "차오", "하람", "한결",
              "별빛", "늘봄", "새솔", "푸름", "여울", "도담", "미리", "온누리", "보람", "슬기", "해솔", "나린"]
RIVER_ROOTS = ["은하", "솔내", "가람", "누리", "별내", "맑은", "푸른", "해오름", "달빛", "구름", "물안개", "새벽",
               "버들", "반디", "모래", "갈대"]
DONG_ROOTS = ["가온", "나래", "다솜", "라온", "마루", "바다", "새봄", "하늘", "솔밭", "들꽃", "샘골", "윗말"]
SURNAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오", "서", "신", "권", "황", "안", "송"]
GIVEN = ["가람", "나래", "다온", "라희", "마루", "보람", "새봄", "솔이", "아름", "여울", "윤슬", "이든", "지우",
         "찬솔", "초롱", "하늘", "한결", "해든", "도담", "로운", "별하", "서린", "온유", "단비"]
RANKS = ["주무관", "주무관", "주무관", "환경연구사", "보건연구사", "행정주사", "환경주사"]
LEAD_RANKS = ["팀장", "팀장", "과장"]

TEAMS = {
    "수질": "수질분석팀", "대기": "대기환경팀", "토양": "토양폐기물팀", "먹는물": "먹는물검사팀",
    "운영": "운영지원팀", "기획": "연구기획팀", "생태": "생태하천팀", "정도": "정도관리팀",
}

# 공문 맨 아래 문구(가상) — 실제 기관 표어를 쓰지 않는다
FOOTERS = ["작은 실천, 맑은 물 — 종이 한 장 아끼기", "확인 또 확인, 정확한 행정의 시작",
           "개인정보는 꼭 필요한 만큼만", "출처를 남기면 다음 해가 쉬워집니다", "한 번 더 읽고, 한 번 덜 고치기"]
OPEN_KINDS = ["대국민 공개", "부분공개(6)", "비공개(5)"]

ITEMS_WATER = [("BOD", "생물화학적 산소요구량", "mg/L", 1), ("COD", "화학적 산소요구량", "mg/L", 1),
               ("TOC", "총유기탄소", "mg/L", 1), ("SS", "부유물질", "mg/L", 1),
               ("T-N", "총질소", "mg/L", 3), ("T-P", "총인", "mg/L", 4)]
DOC_NAME = {"BOD": "BOD", "COD": "COD", "TOC": "TOC", "SS": "SS", "T-N": "총질소", "T-P": "총인"}


def person(rng):
    return rng.choice(SURNAMES) + rng.choice(GIVEN)


def cities(rng, n):
    roots = rng.sample(CITY_ROOTS, n)
    return [r + rng.choice(["시", "시", "군"]) for r in roots]


def rivers(rng, n):
    return [r + rng.choice(["천", "천", "강"]) for r in rng.sample(RIVER_ROOTS, n)]


def stations(rng, n):
    return [r + rng.choice(["동", "읍", "면"]) for r in rng.sample(DONG_ROOTS, n)]


def org(rng):
    prov = rng.choice(PROVINCES)
    return {"province": prov, "name": f"{prov} 보건환경연구원", "short": prov.replace("도", "") + "보환연",
            "council": f"{prov}의회 환경농정위원회", "dept_code": f"{prov}보건환경연구원",
            "zip": f"{rng.randint(10, 63)}{rng.randint(100, 999)}",
            "addr": f"{prov} {rng.choice(CITY_ROOTS)}시 {rng.choice(DONG_ROOTS)}로 {rng.randint(1, 300)}",
            "tel": f"0{rng.randint(31, 64)}-{rng.randint(100, 999)}-{rng.randint(1000, 9999)}",
            "web": "www.example.go.kr"}
