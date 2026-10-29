# Apple Silicon Mac에서 Python 가상환경 만들기

## 목적

Intel Mac과 Apple Silicon Mac 사이에서는 가상환경 폴더 자체를 공유하지 않는다. Python 코드와 `requirements.txt` 같은 프로젝트 파일만 공유하고, 가상환경은 각 Mac의 사용자 홈 폴더에 별도로 만든다.

이렇게 하면 iCloud 또는 GitHub 동기화 과정에서 서로 다른 CPU 아키텍처용 패키지가 충돌하는 것을 방지할 수 있다.

## 이번에 구성한 환경

- 프로젝트 작업 폴더: `/Users/lol/Documents/GitHub`
- 가상환경 폴더: `/Users/lol/.venvs/github`
- Python 버전: `3.14.3`
- CPU 아키텍처: `arm64` (Apple Silicon)
- VS Code 인터프리터: `/Users/lol/.venvs/github/bin/python`

## 다음번에 직접 실행할 명령

VS Code 터미널에서 프로젝트 폴더로 이동한 뒤 다음 명령을 순서대로 실행한다.

```bash
# 1. 현재 위치와 Python 환경 확인
pwd
python3 --version
uname -m

# 2. 홈 폴더에 가상환경 저장 폴더 생성
mkdir -p ~/.venvs

# 3. GitHub 작업용 가상환경 생성
# 이미 ~/.venvs/github가 존재한다면 이 명령은 생략한다.
python3 -m venv ~/.venvs/github

# 4. 가상환경 활성화
source ~/.venvs/github/bin/activate

# 5. 정상 활성화 확인
echo "$VIRTUAL_ENV"
which python
python --version
```

정상적으로 활성화되면 터미널 프롬프트 앞에 `(github)`가 표시된다.

```text
(github) lol@jouihoui-Macmini GitHub %
```

## 가상환경 종료

작업을 마친 후 다음 명령을 실행한다.

```bash
deactivate
```

## 다음 터미널에서 다시 활성화하기

가상환경은 한 번 만들면 매번 새로 생성할 필요가 없다. 새로운 터미널을 열었을 때 다음 명령만 실행하면 된다.

```bash
source ~/.venvs/github/bin/activate
```

## VS Code 인터프리터 선택

1. VS Code에서 `Command + Shift + P`를 누른다.
2. `Python: Select Interpreter`를 검색해 선택한다.
3. `Enter interpreter path`를 선택한다.
4. 다음 경로를 입력한다.

```text
/Users/lol/.venvs/github/bin/python
```

## 패키지 목록 공유하기

두 Mac에서 같은 패키지 구성을 사용하려면 가상환경 폴더가 아니라 패키지 목록을 공유한다.

현재 환경의 패키지 목록 저장:

```bash
pip freeze > requirements.txt
```

다른 Mac에서 해당 Mac 전용 가상환경을 만든 후 패키지 설치:

```bash
pip install -r requirements.txt
```

`requirements.txt`는 프로젝트와 함께 GitHub 또는 iCloud로 동기화해도 된다. 반면 `~/.venvs/github`는 각 Mac에 따로 존재하므로 동기화되지 않는다.
