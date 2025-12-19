# 📦 포토카드 자동 크롭 - 배포 가이드

## 🔨 1. 앱 빌드하기

### 기본 빌드 명령어

```bash
# 가상환경 활성화
source venv/bin/activate

# 앱 빌드 (단일 .app 파일)
pyinstaller --windowed --onefile --name "PhotoCardCrop" main.py
```

### 권장 빌드 명령어 (spec 파일 사용)

```bash
source venv/bin/activate
pyinstaller PhotoCardCrop.spec
```

### 아이콘 적용하기 (.icns)

1. **아이콘 파일 준비**: macOS용 아이콘은 `.icns` 형식이어야 합니다.
   
   PNG 파일을 ICNS로 변환하는 방법:
   ```bash
   # 1024x1024 PNG 파일 준비 후
   mkdir icon.iconset
   sips -z 16 16     icon.png --out icon.iconset/icon_16x16.png
   sips -z 32 32     icon.png --out icon.iconset/icon_16x16@2x.png
   sips -z 32 32     icon.png --out icon.iconset/icon_32x32.png
   sips -z 64 64     icon.png --out icon.iconset/icon_32x32@2x.png
   sips -z 128 128   icon.png --out icon.iconset/icon_128x128.png
   sips -z 256 256   icon.png --out icon.iconset/icon_128x128@2x.png
   sips -z 256 256   icon.png --out icon.iconset/icon_256x256.png
   sips -z 512 512   icon.png --out icon.iconset/icon_256x256@2x.png
   sips -z 512 512   icon.png --out icon.iconset/icon_512x512.png
   sips -z 1024 1024 icon.png --out icon.iconset/icon_512x512@2x.png
   iconutil -c icns icon.iconset
   ```

2. **빌드 명령어에 아이콘 추가**:
   ```bash
   pyinstaller --windowed --onefile --name "PhotoCardCrop" --icon=icon.icns main.py
   ```
   
   또는 `PhotoCardCrop.spec` 파일에서 `icon=None`을 `icon='icon.icns'`로 변경

### 빌드 결과물

```
dist/
└── PhotoCardCrop.app    ← 이 파일을 배포합니다
```

---

## 🍎 2. Apple Silicon (M1/M2) vs Intel 호환성

### 현재 상황

| 빌드 환경 | 결과물 | 호환성 |
|----------|--------|--------|
| Intel Mac에서 빌드 | x86_64 바이너리 | Intel Mac ✅, Apple Silicon Mac ✅ (Rosetta 2) |
| Apple Silicon에서 빌드 | arm64 바이너리 | Apple Silicon Mac ✅, Intel Mac ❌ |

### 권장 해결책

**방법 1: 각 아키텍처별로 따로 빌드** (권장)
```bash
# Apple Silicon Mac에서 빌드 → M1/M2 용
pyinstaller PhotoCardCrop.spec

# Intel Mac에서 빌드 → Intel 용
pyinstaller PhotoCardCrop.spec
```

**방법 2: Universal Binary 빌드** (고급)
```bash
# 두 아키텍처를 합친 유니버설 앱
pyinstaller --target-arch universal2 PhotoCardCrop.spec
```
> ⚠️ Universal Binary는 모든 의존성도 universal2를 지원해야 합니다.

### 현실적인 배포 전략

동료들의 맥북 종류에 따라:
- **모두 Apple Silicon (M1/M2/M3)**: M1 맥에서 빌드한 앱 배포
- **Intel과 Apple Silicon 혼합**: Intel 맥에서 빌드 (Rosetta 2로 M1에서도 실행 가능)
- **최적 성능 필요**: 두 버전을 각각 빌드하여 배포

---

## 🔐 3. "확인되지 않은 개발자" 경고 해결하기

### 동료들에게 전달할 안내문

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📷 포토카드 자동 크롭 앱 - 첫 실행 안내
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

이 앱은 회사 내부용으로 개발되어 Apple 공식 인증을 받지 않았습니다.
처음 실행할 때 보안 경고가 나타나면, 아래 방법으로 해결해주세요.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚨 "Apple에서 악성 소프트웨어가 있는지 확인할 수 없습니다" 라는
   경고가 뜬다면:

【방법 1】 우클릭으로 열기 (가장 간단!)
   1. PhotoCardCrop.app 파일을 우클릭 (또는 Control+클릭)
   2. 메뉴에서 "열기" 선택
   3. 경고창에서 "열기" 버튼 클릭
   4. 이후로는 더블클릭으로 정상 실행됩니다!

【방법 2】 시스템 설정에서 허용
   1. 앱을 더블클릭하여 경고 메시지 확인
   2. 시스템 설정 > 개인 정보 보호 및 보안 이동
   3. "보안" 섹션에서 "확인 없이 열기" 버튼 클릭
   4. 앱을 다시 더블클릭

【방법 3】 터미널 명령어 (고급)
   터미널에서 아래 명령어 입력:
   
   xattr -cr /Applications/PhotoCardCrop.app
   
   (앱 경로는 실제 위치에 맞게 수정)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 한 번 허용하면 이후로는 경고 없이 실행됩니다!

문의: [박상우 / 010-2287-6849]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 배포 전 격리 속성 제거 (선택사항)

앱을 배포하기 전에 직접 격리 속성을 제거할 수 있습니다:

```bash
# 빌드된 앱의 격리 속성 제거
xattr -cr dist/PhotoCardCrop.app
```

이렇게 하면 일부 경우 경고가 줄어들 수 있습니다.

---

## 📋 4. 빠른 빌드 체크리스트

```
□ 가상환경 활성화됨 (source venv/bin/activate)
□ pyinstaller 설치됨 (pip install pyinstaller)
□ 아이콘 파일 준비됨 (선택사항)
□ 빌드 실행
□ dist/PhotoCardCrop.app 생성 확인
□ 테스트 실행
□ 배포 (압축파일 또는 공유 드라이브)
□ 동료들에게 첫 실행 안내문 전달
```

---

## 🗜️ 5. 배포 방법

### 방법 1: ZIP 압축 (권장)
```bash
cd dist
zip -r PhotoCardCrop.zip PhotoCardCrop.app
```

### 방법 2: DMG 이미지 생성
```bash
# create-dmg 설치 (Homebrew)
brew install create-dmg

# DMG 생성
create-dmg \
  --volname "포토카드 자동 크롭" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 100 \
  --icon "PhotoCardCrop.app" 150 185 \
  --app-drop-link 450 185 \
  "PhotoCardCrop.dmg" \
  "dist/PhotoCardCrop.app"
```

### 방법 3: 공유 드라이브
- Google Drive, Dropbox, 회사 NAS 등에 업로드
- 링크를 동료들에게 공유

---

## ❓ FAQ

**Q: 앱이 실행되지 않고 바로 종료됩니다**
> A: 터미널에서 실행하여 오류 메시지를 확인하세요:
> ```bash
> /Applications/PhotoCardCrop.app/Contents/MacOS/PhotoCardCrop
> ```

**Q: "손상되어 열 수 없습니다" 메시지가 나옵니다**
> A: 터미널에서 격리 속성을 제거하세요:
> ```bash
> xattr -cr /Applications/PhotoCardCrop.app
> ```

**Q: M1 맥에서 실행이 느립니다**
> A: Intel Mac에서 빌드된 앱을 Rosetta 2로 실행 중일 수 있습니다.
> M1 Mac에서 다시 빌드하면 네이티브 성능으로 실행됩니다.

**Q: 특정 이미지에서 얼굴을 인식하지 못합니다**
> A: Haar Cascade는 정면 얼굴에 최적화되어 있습니다.
> 옆모습이나 가려진 얼굴은 인식이 어려울 수 있습니다.

---

## 📞 기술 지원

빌드나 배포 중 문제가 발생하면 아래 정보와 함께 문의해주세요:
- macOS 버전 (예: macOS 15.2)
- 칩 종류 (Intel / M1 / M2 / M3)
- 오류 메시지 스크린샷



