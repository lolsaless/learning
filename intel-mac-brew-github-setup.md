# Intel Mac: Homebrew + GitHub 연동 세팅 가이드

macOS Intel(x86_64) 환경에서 Homebrew를 설치하고 git / GitHub CLI(`gh`)를 연동하는 전체 절차입니다.
(테스트 환경: macOS 14.8.9, Intel x86_64)

## 0. 사전 확인: Xcode Command Line Tools

```bash
xcode-select -p || xcode-select --install
```

`/Library/Developer/CommandLineTools`가 출력되면 이미 설치된 것이므로 다음 단계로 진행합니다.

## 1. Homebrew 설치

> ⚠️ **주의**: 공식 Homebrew 설치 스크립트(`install.sh`)는 최근 버전부터 macOS에서 **Apple Silicon(arm64)만 지원**하도록 막혀 있습니다. Intel Mac에서 공식 스크립트를 실행하면 다음과 같은 에러가 납니다.
>
> ```
> Homebrew on macOS is only supported on Apple Silicon processors!
> ```
>
> 따라서 Intel Mac에서는 **수동 설치(git clone) 방식**을 사용해야 합니다.

### 1-1. 저장소 직접 clone

```bash
sudo mkdir -p /usr/local/homebrew
sudo chown -R "$(whoami)" /usr/local/homebrew
git clone https://github.com/Homebrew/brew /usr/local/homebrew
```

### 1-2. PATH 등록 (zsh 기준)

```bash
echo 'eval "$(/usr/local/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/usr/local/homebrew/bin/brew shellenv)"
```

### 1-3. 업데이트 및 확인

```bash
brew update --force --quiet
brew doctor
brew --version
```

> 참고: Homebrew가 Intel Mac용 사전 컴파일 바이너리(bottle) 제공을 점차 줄이는 추세라, 일부 패키지(git 설치 시 `json-c` 등 의존성)는 소스에서 직접 빌드되며 시간이 걸릴 수 있습니다.

## 2. git 설치 (brew로 최신 버전 사용)

```bash
brew install git
```

설치 후 PATH가 제대로 갱신됐는지 확인합니다. 같은 셸 세션에서 바로 확인하면 이전 경로가 캐시(hash)되어 옛 버전이 나올 수 있으니, `hash -r`로 셸 캐시를 초기화합니다.

```bash
hash -r
which git      # /usr/local/homebrew/bin/git 이어야 함
git --version  # brew 버전(예: 2.55.0)이어야 함, "Apple Git-xxx"가 아니어야 정상
```

## 3. GitHub CLI(`gh`) 설치 및 인증

### 3-1. 설치

```bash
brew install gh
```

### 3-2. git 사용자 정보 설정

```bash
git config --global user.name "이름"
git config --global user.email "GitHub 가입 이메일"
```

### 3-3. 로그인

```bash
gh auth login
```

대화형 프롬프트 선택:
1. `What account do you want to log into?` → **GitHub.com**
2. `What is your preferred protocol for Git operations?` → **HTTPS** (또는 SSH, 아래 참고)
3. `Authenticate Git with your GitHub credentials?` → **Yes**
4. `How would you like to authenticate GitHub CLI?` → **Login with a web browser**

터미널에 뜨는 one-time code를 복사하고, 브라우저가 열리면(`https://github.com/login/device`) 입력해 인증합니다.

> ⚠️ 터미널에 출력되는 안내 문구(`Press Enter to open ...`, `One-time code ...` 등)를 실수로 복사해서 다시 셸에 붙여넣으면 `command not found` 같은 에러가 납니다. 이건 인증 실패가 아니라 단순 오타이니, `gh auth status`로 실제 로그인 여부를 확인하면 됩니다.

### 3-4. 인증 상태 확인

```bash
gh auth status
```

`gh`가 HTTPS 프로토콜용 git credential helper를 자동으로 등록해주므로, 이후 `git clone https://...`, `git push`, `git pull` 시 비밀번호 입력 없이 동작합니다.

### 3-5. (선택) SSH로 전환하고 싶은 경우

```bash
gh config set -h github.com git_protocol ssh
gh ssh-key list
# 키가 없으면 새로 생성 + 등록
ssh-keygen -t ed25519 -C "이메일" -f ~/.ssh/id_ed25519
gh ssh-key add ~/.ssh/id_ed25519.pub --title "$(hostname)"
```

## 4. 동작 확인

```bash
git clone https://github.com/octocat/Hello-World.git /tmp/gh-test && echo "CLONE OK"
cd /tmp/gh-test && git log -1 --oneline
rm -rf /tmp/gh-test
```

정상적으로 clone되고 로그가 출력되면 설정 완료입니다.

## 5. VSCode 소스 제어 연동 시 주의사항

VSCode가 brew git(`/usr/local/homebrew/bin/git`)을 자동으로 인식하며, `gh auth login`에서 등록한 credential helper를 그대로 사용하므로 별도 설정 없이 동작합니다.

기존에 로컬/원격 브랜치가 갈라져 있는(diverged) 저장소를 열면 pull 시 다음과 같은 에러가 날 수 있습니다.

```
hint: You have divergent branches and need to specify how to reconcile them.
fatal: Need to specify how to reconcile divergent branches.
```

이 경우 pull 전략을 전역으로 지정해주면 해결됩니다.

```bash
# 병합 커밋 방식 (기본, 안전)
git config --global pull.rebase false

# 또는 rebase 방식 (히스토리를 깔끔하게 유지)
git config --global pull.rebase true
```

설정 후 다시 pull/fetch 하면 정상 동작합니다.

## 요약 체크리스트

- [ ] Xcode Command Line Tools 설치 확인
- [ ] Homebrew 수동 설치 (`/usr/local/homebrew`) — Intel Mac은 공식 설치 스크립트 사용 불가
- [ ] `~/.zprofile`에 brew PATH 등록
- [ ] `brew install git`
- [ ] `brew install gh`
- [ ] `git config --global user.name/user.email` 설정
- [ ] `gh auth login`으로 GitHub 인증
- [ ] `git config --global pull.rebase [true|false]`로 병합 전략 지정
- [ ] 테스트 clone으로 동작 확인
