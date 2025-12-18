# 📷 포토카드 자동 크롭 프로그램

아이돌 고화질 사진을 포토카드 규격(55x85mm, 550x850px)에 맞춰 자동으로 크롭하는 프로그램입니다.

## ✨ 주요 기능

- **얼굴 자동 감지**: Google MediaPipe를 사용한 정확한 얼굴 인식
- **스마트 크롭**: 눈 위치를 기준으로 자연스러운 포토카드 구도
- **조절 가능한 파라미터**: 
  - `zoom_factor`: 얼굴 크기 대비 프레임 비율
  - `eye_position`: 눈의 세로 위치 비율
- **지능형 패딩**: 이미지 경계 초과 시 흰색/평균색/미러 패딩 적용
- **대량 처리**: 수천 장의 이미지를 폴더 단위로 일괄 처리

## 🛠️ 설치

### 1. Python 환경 준비 (3.8 이상 권장)

```bash
# 가상환경 생성 (선택)
python -m venv venv
source venv/bin/activate  # macOS/Linux
# 또는
venv\Scripts\activate  # Windows
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

## 📖 사용법

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

# 파라미터 조정하여 처리
python main.py -d ./input_folder -o ./output_folder --zoom 2.5 --eye-position 0.4
```

## ⚙️ 주요 파라미터

| 파라미터 | 설명 | 기본값 | 권장 범위 |
|---------|------|--------|----------|
| `--zoom`, `-z` | 얼굴 크기 대비 프레임 비율<br>값이 클수록 얼굴이 작게 보임 | 2.8 | 2.5 ~ 3.5 |
| `--eye-position`, `-e` | 눈의 세로 위치 (위에서부터)<br>0.4 = 위에서 40% 지점 | 0.4 | 0.3 ~ 0.5 |
| `--padding`, `-p` | 패딩 색상 모드 | white | white, average, mirror |
| `--format`, `-f` | 출력 이미지 포맷 | jpg | jpg, png, webp |
| `--quality`, `-q` | 출력 품질 (1-100) | 95 | 85 ~ 100 |

### 파라미터 조정 가이드

#### zoom_factor 조절 예시

```
zoom=2.5  →  얼굴이 크게 (클로즈업)
zoom=2.8  →  기본값 (적당한 여백)
zoom=3.5  →  얼굴이 작게 (넓은 여백)
```

#### eye_position 조절 예시

```
eye_position=0.30  →  눈이 위쪽 (이마 여백 적음)
eye_position=0.40  →  기본값 (균형잡힌 구도)
eye_position=0.50  →  눈이 아래쪽 (이마 여백 많음)
```

## 📁 프로젝트 구조

```
image_crop/
├── main.py              # 프로그램 실행 진입점 (CLI)
├── requirements.txt     # 필요한 라이브러리
├── README.md           # 사용 설명서
├── core/
│   ├── __init__.py
│   └── cropper.py      # 이미지 처리 핵심 로직
└── utils/
    ├── __init__.py
    └── file_handler.py # 파일 입출력 관리
```

## 💡 Python 코드로 직접 사용

```python
from core.cropper import PhotoCardCropper
from utils.file_handler import FileHandler, BatchProcessor

# 크로퍼 초기화
cropper = PhotoCardCropper(
    zoom_factor=2.8,       # 얼굴 크기 비율
    eye_position=0.4,      # 눈 위치 (위에서 40%)
    padding_mode='white',  # 패딩 색상
    fallback_on_no_face=True  # 얼굴 미감지 시 중앙 크롭
)

# 단일 이미지 처리
result = cropper.process_image('input.jpg')

# 저장
import cv2
cv2.imwrite('output.jpg', result)
```

### 대량 처리

```python
from core.cropper import PhotoCardCropper
from utils.file_handler import FileHandler, BatchProcessor

# 초기화
cropper = PhotoCardCropper(zoom_factor=2.8)
file_handler = FileHandler(
    input_dir='./input_folder',
    output_dir='./output_folder',
    output_format='jpg',
    output_quality=95
)

# 배치 프로세서로 일괄 처리
batch_processor = BatchProcessor(file_handler, cropper)
stats = batch_processor.process_batch()

print(f"성공: {stats['success']}, 실패: {stats['failed']}")
```

## ⚠️ 주의사항

- 입력 이미지는 고화질(1000px 이상)을 권장합니다
- 얼굴이 명확하게 보이는 사진에서 최적의 결과를 얻을 수 있습니다
- 단체 사진의 경우 가장 큰 얼굴을 기준으로 크롭됩니다

## 🔧 문제 해결

### 얼굴을 찾지 못하는 경우

1. 이미지 해상도가 너무 낮지 않은지 확인
2. 얼굴이 너무 작거나 측면이 아닌지 확인
3. `--skip-no-face` 옵션으로 건너뛰기 또는 기본값인 중앙 크롭 적용

### 메모리 부족

- 대량의 고해상도 이미지 처리 시 발생 가능
- 폴더를 나눠서 처리하거나 이미지 해상도를 낮춰주세요

## 📝 라이선스

MIT License
