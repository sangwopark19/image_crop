# 📷 포토카드 자동 크롭 프로그램

아이돌 고화질 사진을 포토카드 규격(55x85mm)에 맞춰 자동으로 크롭하는 프로그램입니다.  
**원본 해상도와 DPI를 유지**하여 인쇄용 고품질 결과물을 생성합니다.

## ✨ 주요 기능

- **얼굴 자동 감지**: OpenCV Haar Cascade를 사용한 정확한 얼굴 인식
- **스마트 크롭**: 눈 위치를 기준으로 자연스러운 포토카드 구도
- **📍 이미지별 위치 조정**: 사진마다 개별적으로 좌우/상하 위치 미세 조정 가능 (v1.2)
- **다양한 출력 규격**: 포토카드, 여권사진, 증명사진, ID카드, 폴라로이드 등 프리셋 지원
- **사용자 정의 규격**: 원하는 가로/세로 mm 직접 입력 가능
- **원본 DPI 유지**: 고해상도 원본 품질 그대로 유지
- **지능형 패딩**: 이미지 경계 초과 시 흰색/평균색/미러 패딩 적용
- **대량 처리**: 수천 장의 이미지를 폴더 단위로 일괄 처리 (하위 폴더 포함)
- **실시간 미리보기**: 설정 변경 시 즉시 결과 확인 가능

## 🚀 빠른 시작 (ARM Mac)

ARM Mac (M1/M2/M3/M4) 사용자는 미리 빌드된 앱을 바로 사용할 수 있습니다.

1. `PhotoCardCrop_v1.2.dmg` 파일을 다운로드
2. DMG 파일을 열고 `PhotoCardCrop.app`을 Applications 폴더로 드래그
3. 앱 실행 후 바로 사용

> ⚠️ 처음 실행 시 "확인되지 않은 개발자" 경고가 나타날 수 있습니다.  
> 터미널에서 `xattr -cr /Applications/PhotoCardCrop.app` 실행 후 다시 시도하세요.

---

## 🖥️ GUI 사용법

### 기본 사용

1. **원본 폴더 선택**: 크롭할 사진들이 있는 폴더 선택
2. **저장 폴더 선택**: 결과물을 저장할 폴더 선택
3. **출력 규격 선택**: 프리셋 선택 또는 사용자 정의 크기 입력
4. **파라미터 조절**: 슬라이더로 줌, 눈 위치 조정
5. **미리보기 확인**: 오른쪽 미리보기 창에서 결과 확인
6. **변환 시작**: 버튼 클릭으로 일괄 처리

### 📍 이미지별 위치 조정 (v1.2 신기능)

머리카락이나 얼굴이 한쪽으로 치우친 사진을 개별 조정할 수 있습니다:

1. 미리보기에서 이전/다음 버튼으로 이미지 탐색
2. **좌우 이동** 슬라이더: 크롭 영역을 좌우로 이동
3. **상하 이동** 슬라이더: 크롭 영역을 상하로 이동
4. 각 이미지의 설정은 **자동 저장**됩니다
5. 다른 이미지로 이동해도 설정이 유지됩니다
6. **조정된 이미지 수**가 표시되어 쉽게 확인 가능
7. **초기화** 버튼으로 현재 이미지 설정 리셋

### 지원하는 출력 규격 프리셋

| 프리셋 | 크기 (mm) |
|--------|-----------|
| 포토카드 | 55 × 85 |
| 여권사진 | 35 × 45 |
| 증명사진 3×4 | 30 × 40 |
| 증명사진 4×5 | 40 × 50 |
| ID카드 | 54 × 86 |
| 인스탁스 미니 | 54 × 86 |
| 인스탁스 스퀘어 | 62 × 62 |
| 폴라로이드 | 79 × 79 |
| 명함 가로 | 90 × 50 |
| 명함 세로 | 50 × 90 |

---

## 🛠️ 설치 (소스에서 실행)

### 1. Python 환경 준비 (3.10 이상 권장)

```bash
# 가상환경 생성
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 실행

```bash
python main.py  # GUI 모드
```

---

## 💻 CLI 사용법

### 단일 이미지 처리

```bash
# 기본 사용
python main.py -i input.jpg -o output.jpg

# 파라미터 조정
python main.py -i input.jpg -o output.jpg --zoom 3.0 --eye-position 0.35
```

### 폴더 일괄 처리

```bash
# 기본 사용 (하위 폴더 포함)
python main.py -d ./input_folder -o ./output_folder

# 사용자 정의 규격 (여권사진 35×45mm)
python main.py -d ./photos -o ./output --width 35 --height 45

# 위치 오프셋 적용
python main.py -d ./photos -o ./output --offset-x 0.1 --offset-y -0.05
```

## ⚙️ 주요 파라미터

| 파라미터 | 설명 | 기본값 | 권장 범위 |
|---------|------|--------|----------|
| `--zoom`, `-z` | 얼굴 크기 대비 프레임 비율<br>값이 클수록 얼굴이 작게 보임 | 2.8 | 1.5 ~ 5.0 |
| `--eye-position`, `-e` | 눈의 세로 위치 (위에서부터)<br>0.4 = 위에서 40% 지점 | 0.42 | 0.2 ~ 0.6 |
| `--width`, `-W` | 출력 규격 가로 (mm) | 55 | - |
| `--height`, `-H` | 출력 규격 세로 (mm) | 85 | - |
| `--offset-x` | 좌우 오프셋 (음수: 왼쪽, 양수: 오른쪽) | 0.0 | -0.3 ~ 0.3 |
| `--offset-y` | 상하 오프셋 (음수: 위, 양수: 아래) | 0.0 | -0.3 ~ 0.3 |
| `--format`, `-f` | 출력 이미지 포맷 | jpg | jpg, png, webp, tiff |
| `--quality`, `-q` | 출력 품질 (1-100) | 100 | 85 ~ 100 |

### 파라미터 조정 가이드

#### zoom_factor 조절

```
zoom=1.5  →  얼굴이 매우 크게 (극단적 클로즈업)
zoom=2.8  →  기본값 (적당한 여백)
zoom=5.0  →  얼굴이 작게 (넓은 여백)
```

#### eye_position 조절

```
eye_position=0.20  →  눈이 위쪽 (이마 여백 적음)
eye_position=0.42  →  기본값 (균형잡힌 구도)
eye_position=0.60  →  눈이 아래쪽 (이마 여백 많음)
```

---

## 📁 프로젝트 구조

```
image_crop/
├── main.py              # 프로그램 진입점 (GUI + CLI)
├── requirements.txt     # 필요한 라이브러리
├── README.md            # 사용 설명서
├── DISTRIBUTION_GUIDE.md # 배포 가이드
├── PhotoCardCrop.spec   # PyInstaller 빌드 설정
├── data/                # Haar Cascade 모델 파일
│   ├── haarcascade_frontalface_default.xml
│   └── haarcascade_eye.xml
├── core/
│   ├── __init__.py
│   └── cropper.py       # 이미지 처리 핵심 로직
└── utils/
    ├── __init__.py
    └── file_handler.py  # 파일 입출력 관리
```

---

## 💡 Python 코드로 직접 사용

```python
from core.cropper import PhotoCardCropper
from utils.file_handler import FileHandler, BatchProcessor

# 크로퍼 초기화 (사용자 정의 규격 + 원본 해상도 유지)
cropper = PhotoCardCropper(
    zoom_factor=2.8,
    eye_position=0.42,
    width_mm=55,           # 출력 가로 (mm)
    height_mm=85,          # 출력 세로 (mm)
    padding_mode='white',
    fallback_on_no_face=True,
    preserve_resolution=True,  # 원본 해상도 유지
    offset_x=0.0,          # 좌우 오프셋
    offset_y=0.0           # 상하 오프셋
)

# 단일 이미지 처리
result = cropper.process_image('input.jpg')
if result:
    image_data, metadata = result
    # metadata에 DPI, EXIF, ICC 프로파일 정보 포함
```

### 대량 처리

```python
from core.cropper import PhotoCardCropper
from utils.file_handler import FileHandler, BatchProcessor

# 초기화
cropper = PhotoCardCropper(
    zoom_factor=2.8,
    preserve_resolution=True
)

file_handler = FileHandler(
    input_dir='./input_folder',
    output_dir='./output_folder',
    output_format='jpg',
    output_quality=100,
    preserve_dpi=True  # DPI 보존
)

# 배치 프로세서로 일괄 처리
batch_processor = BatchProcessor(file_handler, cropper)
stats = batch_processor.process_batch()

print(f"성공: {stats['success']}, 실패: {stats['failed']}")
```

---

## ⚠️ 주의사항

- 입력 이미지는 고화질(1000px 이상)을 권장합니다
- 얼굴이 명확하게 보이는 사진에서 최적의 결과를 얻을 수 있습니다
- 단체 사진의 경우 가장 큰 얼굴을 기준으로 크롭됩니다
- 원본 DPI가 유지되므로 인쇄용으로 적합합니다

## 🔧 문제 해결

### 얼굴을 찾지 못하는 경우

1. 이미지 해상도가 너무 낮지 않은지 확인
2. 얼굴이 너무 작거나 측면이 아닌지 확인
3. 기본적으로 얼굴 미감지 시 중앙 크롭이 적용됩니다

### macOS에서 앱이 열리지 않는 경우

```bash
xattr -cr /Applications/PhotoCardCrop.app
```

### 메모리 부족

- 대량의 고해상도 이미지 처리 시 발생 가능
- 폴더를 나눠서 처리하거나 이미지 해상도를 낮춰주세요

---

## 📋 버전 히스토리

### v1.2 (2025-12-19)
- ✨ **이미지별 위치 조정** 기능 추가
- 📍 각 사진마다 개별 좌우/상하 오프셋 설정 가능
- 🔄 이미지 전환 시 설정 자동 저장/복원
- 📊 조정된 이미지 수 표시
- 🔘 오프셋 초기화 버튼 추가

### v1.1 (2025-12-18)
- 사용자 정의 출력 규격 지원
- 원본 DPI/해상도 유지 기능
- 실시간 미리보기
- 하위 폴더 탐색 지원

### v1.0 (2025-12-16)
- 초기 버전 출시
- 얼굴 인식 기반 자동 크롭
- GUI 데스크탑 앱

---

## 📝 라이선스

MIT License
