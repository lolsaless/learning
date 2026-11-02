# 2단계. 개발 환경 만들기 (4~6주, 07~12회)

> 내 PC(Mac·Windows)에 **Python 3.13 · VS Code · 가상환경 · Git/GitHub**를 갖추고,
> 여러 PC에서 같은 환경으로 작업하는 방법을 익힙니다.

## 회차 목록

| 회차 | 주 | 주제 | 폴더 | 실습 파일 |
|---|---|---|---|---|
| 07 | 4 | 컴퓨터와 친해지기 (파일·경로·터미널) | `07회_컴퓨터와_친해지기` | 터미널 미션 |
| 08 | 4 | 패키지 관리자 (Homebrew·winget) | `08회_패키지_관리자` | Git·tree 설치 |
| 09 | 5 | Python 설치와 첫 실행 | `09회_Python_설치` | `check_setup.py`, `first_program.py` |
| 10 | 5 | VS Code 설치와 첫 코드 | `10회_VS_Code` | `fix_me.py`, `first_notebook.ipynb` |
| 11 | 6 | 가상환경과 Colab | `11회_가상환경과_Colab` | `venv_first_data.ipynb`, 엑셀 실습 파일 |
| 12 | 6 | Git과 GitHub | `12회_Git과_GitHub` | `gitignore_예시.txt`, 2단계 정리 퀴즈 |

## 보충 실습

| 번호 | 주 | 주제 | 폴더 |
|---|---|---|---|
| S04 | 4 | Windows에서 Homebrew 쓰기 (WSL2) | `보충/S04_Windows에서_Homebrew` |
| S05 | 5 | VS Code 잘 쓰기 (단축키, 설정 동기화) | `보충/S05_VS_Code_잘_쓰기` |
| S06 | 6 | 여러 PC에서 GitHub 쓰기 (GitHub Desktop, 충돌 해결) | `보충/S06_여러_PC에서_GitHub_쓰기` |

## 이 단계의 약속

| 약속 | Mac | Windows |
|---|---|---|
| 파이썬 버전 | **3.13** | **3.13** |
| 파이썬 실행 (가상환경 밖) | `python3.13` | `py -3.13` |
| 파이썬 실행 (가상환경 안) | `python` | `python` |
| 작업 폴더 | `~/Documents/ai-black` | `~\Documents\ai-black` |
| 가상환경 | `ai-black/.venv` 하나 | 같음 |
| 라이브러리 목록 | `requirements.txt` (과정 폴더의 파일을 복사) | 같음 |
| GitHub 저장소 | `내아이디/ai-black` (Private) | 같음 |

## 수강생 작업 폴더 (2단계를 마치면)

```
Documents/ai-black/          ← GitHub 저장소 (Private)
├── .gitignore               ← .venv, .DS_Store 등 제외
├── .venv/                   ← 가상환경 (GitHub에 올리지 않음)
├── README.md
├── requirements.txt
├── 01_practice/             ← 수업 실습 (check_setup.py, first_notebook.ipynb …)
├── 02_homework/             ← 주차별 과제
└── 03_my_project/
```

## 함께 쓰는 공통자료
- `../공통자료/터미널_명령어_치트시트.md`
- `../공통자료/설치_점검표.md` — 2단계가 끝나면 모든 항목 ✅
- `../공통자료/자주_나는_오류_모음.md`
- `../requirements.txt` — 과정 전체 라이브러리 목록

## 기존 자료와의 관계
`3. Python/1. brew setup`의 가이드(Homebrew 설정, Apple 실리콘 가상환경, Intel Mac GitHub 설정, 시스템 파일 차단)를 각 회차에서 **심화 참고 자료**로 연결했습니다.
