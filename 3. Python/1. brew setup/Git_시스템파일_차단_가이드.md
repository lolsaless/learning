# Git 시스템 파일 차단 가이드 (Mac mini · Intel MacBook · Windows)

`.DS_Store`는 macOS Finder가 폴더를 열 때마다 자동으로 만드는 파일입니다.
Mac 내장 디스크에서는 생성 자체를 끌 수 없으므로, **git이 무시하도록** 설정하는 것이 해결책입니다.

- 이 저장소: 루트의 `.gitignore`에 이미 등록되어 있어 추가 작업이 필요 없습니다.
- 다른 저장소까지 막기: 아래 **전역 설정**을 PC마다 한 번씩 실행합니다.

## 1. Mac (Mac mini, Intel MacBook 각각 한 번씩)

터미널에서 실행합니다.

```bash
printf '%s\n' .DS_Store '._*' .AppleDouble .Spotlight-V100 .Trashes Thumbs.db desktop.ini '~$*' > ~/.gitignore_global
git config --global core.excludesfile ~/.gitignore_global
```

USB·외장 디스크·네트워크 드라이브에 `.DS_Store`가 생기지 않게 하려면 다음도 실행합니다. (내장 디스크에는 적용되지 않습니다.)

```bash
defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool true
defaults write com.apple.desktopservices DSDontWriteUSBStores -bool true
killall Finder
```

## 2. Windows

Windows는 `.DS_Store`를 만들지 않지만, Mac에서 만든 파일이 USB·클라우드로 넘어올 수 있으므로 같이 막아 둡니다.
PowerShell에서 실행합니다.

```powershell
".DS_Store`n._*`n.AppleDouble`nThumbs.db`ndesktop.ini`n~`$*" | Out-File -Encoding utf8 "$HOME\.gitignore_global"
git config --global core.excludesfile "$HOME\.gitignore_global"
```

## 3. 이미 올라간 파일 지우기

`.gitignore`는 **아직 추적하지 않는 파일**에만 적용됩니다.
예전에 커밋된 `.DS_Store`가 다시 보이면 저장소 폴더에서 아래를 실행한 뒤 커밋합니다.

```bash
git rm -r --cached --ignore-unmatch '*.DS_Store'
git commit -m ".DS_Store 추적 제거"
```

## 4. 설정 확인

```bash
git config --global core.excludesfile
git check-ignore -v .DS_Store
```

두 번째 명령에서 `.gitignore` 경로가 출력되면 정상입니다.
