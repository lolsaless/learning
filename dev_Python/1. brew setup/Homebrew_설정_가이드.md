# Homebrew 설정 및 관리 가이드

이 문서는 **Apple Silicon Mac(M1·M2·M3·M4 계열)**과 macOS 기본 셸인 **zsh**를 기준으로 작성했습니다.

현재 PC의 Homebrew 설치 경로는 다음과 같습니다.

```text
/opt/homebrew
```

## 1. Homebrew란?

Homebrew는 macOS에서 프로그램과 개발 도구를 설치하고 업데이트하는 패키지 관리자입니다. Python, Git, Node.js 같은 명령줄 프로그램뿐 아니라 일부 macOS 앱도 관리할 수 있습니다.

Homebrew에서 자주 사용하는 용어는 다음과 같습니다.

| 용어 | 의미 | 예시 |
|---|---|---|
| Formula | 명령줄 프로그램 또는 라이브러리 | Python, Git, wget |
| Cask | 일반 macOS 애플리케이션 | Visual Studio Code, Chrome |
| Tap | Homebrew 패키지 저장소 | `homebrew/core` |
| Keg | 특정 버전의 실제 설치 폴더 | `/opt/homebrew/Cellar/...` |

## 2. Homebrew 설치

Homebrew가 설치되어 있지 않은 경우에만 다음 명령을 터미널에서 실행합니다.

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

설치 여부는 다음과 같이 확인합니다.

```bash
brew --version
brew --prefix
```

Apple Silicon Mac에서는 `brew --prefix` 결과가 일반적으로 다음과 같아야 합니다.

```text
/opt/homebrew
```

> 이미 Homebrew가 설치되어 있다면 설치 명령을 다시 실행할 필요가 없습니다.

## 3. zsh에서 Homebrew 경로 설정

터미널에서 `brew` 명령을 인식하게 하려면 `~/.zprofile`에 Homebrew 환경 설정을 추가합니다.

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

첫 번째 명령은 새 터미널을 열 때 Homebrew를 자동으로 불러오도록 설정하고, 두 번째 명령은 현재 터미널에 바로 적용합니다.

설정 결과를 확인합니다.

```bash
which brew
brew --prefix
echo "$PATH"
```

정상적인 결과에는 다음 경로가 포함됩니다.

```text
/opt/homebrew/bin/brew
/opt/homebrew
```

### 중복 설정 확인

같은 설정을 여러 번 추가하지 않도록 다음 명령으로 확인할 수 있습니다.

```bash
grep -n 'brew shellenv' ~/.zprofile ~/.zshrc 2>/dev/null
```

`brew shellenv` 설정은 보통 `~/.zprofile`에 한 번만 있으면 충분합니다.

## 4. 패키지 설치 및 확인

### 명령줄 프로그램 설치

```bash
brew install 패키지명
```

예시:

```bash
brew install git
brew install python
```

### macOS 앱 설치

```bash
brew install --cask 앱이름
```

예시:

```bash
brew install --cask visual-studio-code
```

### 패키지 검색

```bash
brew search 검색어
```

### 설치된 항목 확인

```bash
# 명령줄 프로그램
brew list --formula

# macOS 앱
brew list --cask

# 버전까지 함께 표시
brew list --versions
```

### 패키지 정보 확인

```bash
brew info 패키지명
```

예시:

```bash
brew info python
```

## 5. Homebrew와 패키지 업데이트

Homebrew에서는 `update`와 `upgrade`의 역할이 다릅니다.

- `brew update`: Homebrew 자체와 패키지 목록을 최신 상태로 갱신
- `brew upgrade`: 실제로 설치된 프로그램을 새 버전으로 교체

권장 순서는 다음과 같습니다.

```bash
# 1. Homebrew와 패키지 정보 갱신
brew update

# 2. 업데이트 가능한 항목 확인
brew outdated

# 3. 설치된 패키지 전체 업데이트
brew upgrade

# 4. 불필요한 이전 버전과 다운로드 파일 정리
brew cleanup

# 5. 설정 상태 점검
brew doctor
```

특정 프로그램만 업데이트하려면 이름을 지정합니다.

```bash
brew upgrade 패키지명
```

예시:

```bash
brew upgrade python
brew upgrade git
```

실제 업데이트를 실행하지 않고 예정된 작업만 보고 싶다면 다음 명령을 사용합니다.

```bash
brew upgrade --dry-run
```

## 6. 패키지 삭제

일반 패키지는 다음과 같이 삭제합니다.

```bash
brew uninstall 패키지명
```

예시:

```bash
brew uninstall wget
```

Homebrew로 설치한 macOS 앱도 같은 방식으로 삭제할 수 있습니다.

```bash
brew uninstall --cask 앱이름
```

더 이상 필요하지 않은 의존 패키지를 확인하고 정리하려면 다음 명령을 사용합니다.

```bash
# 다른 패키지가 사용하지 않는 의존 패키지 확인
brew autoremove --dry-run

# 확인 후 실제 정리
brew autoremove

# 이전 버전과 캐시 정리
brew cleanup
```

> `brew autoremove`를 실행하기 전에는 반드시 `--dry-run` 결과를 확인하는 것이 안전합니다.

## 7. Homebrew Python 설정

### Python 설치

Homebrew가 현재 기본으로 제공하는 Python을 설치합니다.

```bash
brew install python
```

이미 설치되어 있다면 다음 명령으로 업데이트합니다.

```bash
brew update
brew upgrade python
```

설치 결과를 확인합니다.

```bash
python3 --version
pip3 --version
which python3
```

Apple Silicon Mac에서 Homebrew Python은 일반적으로 다음 경로로 연결됩니다.

```text
/opt/homebrew/bin/python3
```

### 시스템 Python과 구분

macOS가 제공하는 시스템 Python은 다음 위치에 있을 수 있습니다.

```text
/usr/bin/python3
```

이 Python은 macOS 또는 시스템 도구가 사용할 수 있으므로 직접 삭제하거나 변경하지 않습니다. 일반적인 개발 작업에는 `/opt/homebrew/bin/python3`를 사용합니다.

현재 터미널에서 어떤 Python이 선택되는지 확인하려면 다음 명령을 실행합니다.

```bash
which -a python3
python3 --version
```

### Python 패키지는 가상환경에 설치

Homebrew Python의 기본 환경에 패키지를 직접 설치하지 않고, 프로젝트마다 가상환경을 만드는 것이 안전합니다.

```bash
# 프로젝트 폴더로 이동
cd 프로젝트경로

# 가상환경 생성
python3 -m venv .venv

# 가상환경 활성화
source .venv/bin/activate

# 패키지 설치
python -m pip install 패키지명
```

가상환경이 활성화되면 터미널 프롬프트 앞에 보통 `(.venv)`가 표시됩니다.

가상환경을 종료하려면 다음 명령을 실행합니다.

```bash
deactivate
```

가상환경을 더 이상 사용하지 않는다면 활성화를 종료한 뒤 프로젝트의 `.venv` 폴더를 삭제하면 됩니다. 프로젝트 소스 파일은 삭제되지 않습니다.

### pip 사용 원칙

실행 중인 Python과 정확히 연결된 pip를 사용하려면 다음 형태를 권장합니다.

```bash
python -m pip install 패키지명
python -m pip list
python -m pip list --outdated
```

Homebrew의 기본 Python은 외부 관리 환경으로 설정될 수 있으므로 다음 명령을 기본 환경에서 무리하게 실행하지 않는 것이 좋습니다.

```bash
pip3 install --break-system-packages 패키지명
sudo pip3 install 패키지명
```

`sudo pip` 또는 `--break-system-packages` 대신 가상환경을 사용합니다.

## 8. 여러 Python 환경이 보일 때 확인 방법

VS Code에서 Python 인터프리터가 여러 개 표시되면 먼저 실제 경로를 확인합니다.

```bash
which -a python3
which -a pip3
brew list --formula | grep '^python'
```

홈 폴더에 생성된 가상환경을 찾으려면 다음 명령을 사용할 수 있습니다.

```bash
find ~ -type f -name pyvenv.cfg 2>/dev/null
```

다만 다음 항목은 함부로 삭제하지 않습니다.

- `/usr/bin/python3`: macOS 시스템 Python
- `~/.codex` 아래 환경: Codex 앱이 관리할 수 있는 내부 환경
- 사용 중인 프로젝트의 `.venv`: 프로젝트 패키지가 들어 있는 환경
- 경로와 용도를 모르는 환경

가상환경을 삭제한 뒤 VS Code 목록에 이전 경로가 계속 표시되면 명령 팔레트에서 다음 명령을 실행합니다.

```text
Developer: Reload Window
```

그다음 `Python: Select Interpreter`에서 `/opt/homebrew/bin/python3` 또는 현재 프로젝트의 `.venv/bin/python`을 선택합니다.

## 9. 프로그램 업데이트를 잠시 막는 방법

특정 Formula를 자동 업데이트 대상에서 제외하려면 고정합니다.

```bash
brew pin 패키지명
```

다시 업데이트할 수 있게 하려면 고정을 해제합니다.

```bash
brew unpin 패키지명
```

고정된 항목을 확인합니다.

```bash
brew list --pinned
```

버전 고정은 보안 업데이트를 놓칠 수 있으므로 특별한 이유가 있을 때만 사용합니다.

## 10. 문제 해결

### `brew: command not found`

현재 터미널에 Homebrew 환경 설정을 적용합니다.

```bash
eval "$(/opt/homebrew/bin/brew shellenv)"
```

새 터미널에서도 자동 적용되도록 `~/.zprofile`을 확인합니다.

```bash
grep -n 'brew shellenv' ~/.zprofile
```

### Homebrew 상태 점검

```bash
brew doctor
brew config
```

`brew doctor`의 모든 경고가 반드시 오류를 뜻하는 것은 아닙니다. 경고 내용을 확인한 뒤 관련된 문제만 수정합니다.

### 패키지가 업데이트되지 않을 때

```bash
brew update
brew outdated
brew list --pinned
brew info 패키지명
```

고정된 패키지라면 다음과 같이 해제한 뒤 업데이트합니다.

```bash
brew unpin 패키지명
brew upgrade 패키지명
```

### Homebrew Python이 선택되지 않을 때

```bash
which -a python3
echo "$PATH"
eval "$(/opt/homebrew/bin/brew shellenv)"
hash -r
```

이후 다시 확인합니다.

```bash
which python3
python3 --version
```

## 11. 권장 정기 관리 순서

한 달에 한 번 정도 다음 순서로 점검하면 충분합니다.

```bash
brew update
brew outdated
brew upgrade
brew cleanup
brew doctor
```

업데이트 전에 변경 내용을 먼저 확인하고 싶다면 다음처럼 실행합니다.

```bash
brew update
brew outdated
brew upgrade --dry-run
```

## 12. 현재 PC 권장 구성

현재 PC에서는 다음과 같이 단순하게 유지하는 것을 권장합니다.

```text
Homebrew: /opt/homebrew
개발용 Python: /opt/homebrew/bin/python3
시스템 Python: /usr/bin/python3 — 삭제하지 않음
프로젝트 패키지: 각 프로젝트의 .venv에 설치
```

Python 관리 도구를 여러 개 동시에 사용할 필요가 없다면 Homebrew Python 하나와 프로젝트별 `.venv`만 유지하는 구성이 가장 이해하기 쉽습니다.

## 공식 문서

- [Homebrew 설치 안내](https://docs.brew.sh/Installation)
- [Homebrew 명령어 설명서](https://docs.brew.sh/Manpage)
- [Homebrew 자주 묻는 질문](https://docs.brew.sh/FAQ)
- [Homebrew의 Python 관리 안내](https://docs.brew.sh/Language-Runtimes-and-Packages#python)

