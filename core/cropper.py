"""
포토카드 자동 크롭 핵심 로직

OpenCV + Pillow를 사용하여 아이돌 사진을  
사용자 지정 규격에 맞게 자동 크롭합니다.
원본 해상도와 DPI를 유지합니다.
"""

import cv2
import numpy as np
from PIL import Image
from typing import Optional, Tuple, List, Dict, Any
import logging
import sys
import os
from pathlib import Path

# 로거 설정
logger = logging.getLogger(__name__)


def get_resource_path(relative_path: str) -> str:
    """
    PyInstaller 빌드 환경에서도 리소스 파일 경로를 올바르게 반환합니다.
    
    Args:
        relative_path: 리소스 파일의 상대 경로
        
    Returns:
        실제 파일 경로
    """
    # PyInstaller로 빌드된 경우 _MEIPASS 속성이 있음
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(base_path, relative_path)


# 프리셋 규격 (가로mm x 세로mm)
PRESET_SIZES = {
    '포토카드': (55, 85),
    '여권사진': (35, 45),
    '증명사진 3x4': (30, 40),
    '증명사진 4x5': (40, 50),
    'ID카드': (54, 86),
    '인스탁스 미니': (54, 86),
    '인스탁스 와이드': (99, 62),
    '인스탁스 스퀘어': (62, 62),
    '폴라로이드': (79, 79),
    '명함': (90, 50),
    '사용자 정의': (55, 85),  # 기본값
}


class FaceDetector:
    """OpenCV 기반 얼굴 감지 클래스"""
    
    # Haar Cascade 파일명
    FACE_CASCADE_FILE = "haarcascade_frontalface_default.xml"
    EYE_CASCADE_FILE = "haarcascade_eye.xml"
    
    def __init__(self):
        # Haar Cascade 파일 경로 결정
        face_cascade_path = self._find_cascade_file(self.FACE_CASCADE_FILE)
        eye_cascade_path = self._find_cascade_file(self.EYE_CASCADE_FILE)
        
        logger.info(f"Haar Cascade 경로: {face_cascade_path}")
        
        self.face_cascade = cv2.CascadeClassifier(face_cascade_path)
        self.eye_cascade = cv2.CascadeClassifier(eye_cascade_path)
        
        if self.face_cascade.empty():
            raise RuntimeError(f"얼굴 감지 모델 로드 실패: {face_cascade_path}")
        
        logger.info("FaceDetector 초기화 완료 (Haar Cascade)")
    
    def _find_cascade_file(self, filename: str) -> str:
        """
        Haar Cascade 파일을 찾습니다.
        PyInstaller 빌드 환경과 개발 환경 모두 지원합니다.
        """
        # 1. PyInstaller 번들 내부 (data 폴더)
        if hasattr(sys, '_MEIPASS'):
            bundled_path = os.path.join(sys._MEIPASS, 'data', filename)
            if os.path.exists(bundled_path):
                return bundled_path
            # data 폴더 없이 직접 있는 경우
            bundled_path2 = os.path.join(sys._MEIPASS, filename)
            if os.path.exists(bundled_path2):
                return bundled_path2
        
        # 2. OpenCV 기본 경로 (개발 환경)
        cv2_path = cv2.data.haarcascades + filename
        if os.path.exists(cv2_path):
            return cv2_path
        
        # 3. 현재 디렉토리의 data 폴더
        local_path = os.path.join(os.path.dirname(__file__), '..', 'data', filename)
        if os.path.exists(local_path):
            return local_path
        
        # 찾지 못한 경우 기본 OpenCV 경로 반환 (오류 메시지용)
        return cv2_path
    
    def detect_faces(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5,
            minSize=(50, 50), flags=cv2.CASCADE_SCALE_IMAGE
        )
        return [(x, y, w, h) for (x, y, w, h) in faces]
    
    def detect_eyes_in_face(self, image: np.ndarray, face_bbox: Tuple[int, int, int, int]) -> List[Tuple[int, int, int, int]]:
        x, y, w, h = face_bbox
        face_upper = image[y:y + h // 2, x:x + w]
        gray_upper = cv2.cvtColor(face_upper, cv2.COLOR_BGR2GRAY)
        eyes = self.eye_cascade.detectMultiScale(
            gray_upper, scaleFactor=1.1, minNeighbors=5, minSize=(20, 20)
        )
        return [(ex + x, ey + y, ew, eh) for (ex, ey, ew, eh) in eyes]
    
    def get_eye_center(self, image: np.ndarray, face_bbox: Tuple[int, int, int, int]) -> Tuple[int, int]:
        x, y, w, h = face_bbox
        eyes = self.detect_eyes_in_face(image, face_bbox)
        
        if len(eyes) >= 2:
            eye_centers = [(ex + ew // 2, ey + eh // 2) for (ex, ey, ew, eh) in eyes[:2]]
            center_x = (eye_centers[0][0] + eye_centers[1][0]) // 2
            center_y = (eye_centers[0][1] + eye_centers[1][1]) // 2
            return (center_x, center_y)
        elif len(eyes) == 1:
            ex, ey, ew, eh = eyes[0]
            return (ex + ew // 2, ey + eh // 2)
        else:
            center_x = x + w // 2
            center_y = y + int(h * 0.35)
            return (center_x, center_y)


class PhotoCardCropper:
    """
    사진 자동 크롭 클래스
    
    원본 해상도와 DPI를 유지하면서 사용자 지정 비율로 크롭합니다.
    """
    
    # 기본 규격: 포토카드 55x85mm
    DEFAULT_WIDTH_MM = 55
    DEFAULT_HEIGHT_MM = 85
    
    def __init__(
        self,
        zoom_factor: float = 2.8,
        eye_position: float = 0.4,
        width_mm: float = DEFAULT_WIDTH_MM,
        height_mm: float = DEFAULT_HEIGHT_MM,
        padding_mode: str = 'white',
        fallback_on_no_face: bool = True,
        preserve_resolution: bool = True,
        min_output_height: int = 850,
        offset_x: float = 0.0,
        offset_y: float = 0.0
    ):
        """
        PhotoCardCropper 초기화
        
        Args:
            zoom_factor: 얼굴 크기 대비 프레임 비율 (권장: 2.5 ~ 3.5)
            eye_position: 눈 위치 비율 (0.0 ~ 1.0, 기본값: 0.4)
            width_mm: 출력 규격 가로 (mm)
            height_mm: 출력 규격 세로 (mm)
            padding_mode: 패딩 모드 ('white', 'average', 'mirror')
            fallback_on_no_face: 얼굴 미감지 시 원본 중앙 크롭 사용 여부
            preserve_resolution: True면 원본 해상도 유지
            min_output_height: 최소 출력 높이 (픽셀)
            offset_x: 좌우 오프셋 비율 (-0.5 ~ 0.5, 음수: 왼쪽, 양수: 오른쪽)
            offset_y: 상하 오프셋 비율 (-0.5 ~ 0.5, 음수: 위, 양수: 아래)
        """
        self.zoom_factor = zoom_factor
        self.eye_position = eye_position
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.padding_mode = padding_mode
        self.fallback_on_no_face = fallback_on_no_face
        self.preserve_resolution = preserve_resolution
        self.min_output_height = min_output_height
        self.offset_x = offset_x
        self.offset_y = offset_y
        
        # 비율 계산
        self.aspect_ratio = width_mm / height_mm
        
        # 기본 출력 크기 (10px/mm 기준)
        self.default_output_width = int(width_mm * 10)
        self.default_output_height = int(height_mm * 10)
        
        self.face_detector = FaceDetector()
        
        logger.info(
            f"PhotoCardCropper 초기화 완료 - "
            f"규격: {width_mm}x{height_mm}mm (비율: {self.aspect_ratio:.3f}), "
            f"zoom: {zoom_factor}, eye: {eye_position}"
        )
    
    def set_size(self, width_mm: float, height_mm: float):
        """출력 규격 변경"""
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.aspect_ratio = width_mm / height_mm
        self.default_output_width = int(width_mm * 10)
        self.default_output_height = int(height_mm * 10)
        logger.info(f"규격 변경: {width_mm}x{height_mm}mm (비율: {self.aspect_ratio:.3f})")
    
    def _detect_largest_face(self, image: np.ndarray) -> Optional[Tuple[int, int, int, int, Tuple[int, int]]]:
        faces = self.face_detector.detect_faces(image)
        if not faces:
            return None
        
        largest_face = max(faces, key=lambda f: f[2] * f[3])
        x, y, w, h = largest_face
        eye_center = self.face_detector.get_eye_center(image, largest_face)
        return (x, y, w, h, eye_center)
    
    def _calculate_crop_region(
        self,
        image: np.ndarray,
        face_bbox: Tuple[int, int, int, int],
        eye_center: Tuple[int, int],
        offset_x: Optional[float] = None,
        offset_y: Optional[float] = None
    ) -> Tuple[int, int, int, int]:
        face_x, face_y, face_w, face_h = face_bbox
        eye_center_x, eye_center_y = eye_center
        
        # 오프셋 값 결정
        off_x = offset_x if offset_x is not None else self.offset_x
        off_y = offset_y if offset_y is not None else self.offset_y
        
        # 얼굴 크기를 기준으로 크롭 영역 크기 계산
        crop_height = int(face_h * self.zoom_factor)
        crop_width = int(crop_height * self.aspect_ratio)
        
        # 눈의 위치가 eye_position 비율에 오도록 y 좌표 계산
        crop_y = eye_center_y - int(crop_height * self.eye_position)
        crop_x = eye_center_x - crop_width // 2
        
        # 사용자 오프셋 적용 (비율 기반)
        # offset_x: 양수면 오른쪽으로 이동 (이미지가 왼쪽으로 이동하는 효과)
        # offset_y: 양수면 아래로 이동 (이미지가 위로 이동하는 효과)
        crop_x += int(crop_width * off_x)
        crop_y += int(crop_height * off_y)
        
        return crop_x, crop_y, crop_width, crop_height
    
    def _get_padding_color(self, image: np.ndarray) -> Tuple[int, int, int]:
        if self.padding_mode == 'white':
            return (255, 255, 255)
        elif self.padding_mode == 'average':
            avg_color = cv2.mean(image)[:3]
            return tuple(int(c) for c in avg_color)
        return (255, 255, 255)
    
    def _crop_with_padding(
        self,
        image: np.ndarray,
        crop_x: int,
        crop_y: int,
        crop_width: int,
        crop_height: int
    ) -> np.ndarray:
        img_height, img_width = image.shape[:2]
        padding_color = self._get_padding_color(image)
        
        if self.padding_mode == 'mirror':
            pad_left = max(0, -crop_x)
            pad_top = max(0, -crop_y)
            pad_right = max(0, (crop_x + crop_width) - img_width)
            pad_bottom = max(0, (crop_y + crop_height) - img_height)
            
            if pad_left > 0 or pad_top > 0 or pad_right > 0 or pad_bottom > 0:
                image = cv2.copyMakeBorder(
                    image, pad_top, pad_bottom, pad_left, pad_right,
                    cv2.BORDER_REFLECT_101
                )
                crop_x += pad_left
                crop_y += pad_top
            
            cropped = image[crop_y:crop_y + crop_height, crop_x:crop_x + crop_width]
        else:
            cropped = np.full((crop_height, crop_width, 3), padding_color, dtype=np.uint8)
            
            src_x1 = max(0, crop_x)
            src_y1 = max(0, crop_y)
            src_x2 = min(img_width, crop_x + crop_width)
            src_y2 = min(img_height, crop_y + crop_height)
            
            dst_x1 = src_x1 - crop_x
            dst_y1 = src_y1 - crop_y
            dst_x2 = dst_x1 + (src_x2 - src_x1)
            dst_y2 = dst_y1 + (src_y2 - src_y1)
            
            if src_x2 > src_x1 and src_y2 > src_y1:
                cropped[dst_y1:dst_y2, dst_x1:dst_x2] = image[src_y1:src_y2, src_x1:src_x2]
        
        return cropped
    
    def _center_crop_fallback(self, image: np.ndarray) -> np.ndarray:
        img_height, img_width = image.shape[:2]
        
        target_ratio = self.aspect_ratio
        current_ratio = img_width / img_height
        
        if current_ratio > target_ratio:
            crop_width = int(img_height * target_ratio)
            crop_height = img_height
        else:
            crop_width = img_width
            crop_height = int(img_width / target_ratio)
        
        crop_x = (img_width - crop_width) // 2
        crop_y = (img_height - crop_height) // 2
        
        return self._crop_with_padding(image, crop_x, crop_y, crop_width, crop_height)
    
    def _load_image_with_metadata(self, image_path: str) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
        """이미지와 메타데이터(DPI 등)를 함께 로드"""
        metadata = {
            'dpi': (72, 72),
            'exif': None,
            'icc_profile': None
        }
        
        try:
            pil_image = Image.open(image_path)
            
            if 'dpi' in pil_image.info:
                metadata['dpi'] = pil_image.info['dpi']
            elif hasattr(pil_image, '_getexif') and pil_image._getexif():
                exif = pil_image._getexif()
                if exif and 282 in exif and 283 in exif:
                    metadata['dpi'] = (exif[282], exif[283])
            
            if hasattr(pil_image, 'info') and 'exif' in pil_image.info:
                metadata['exif'] = pil_image.info['exif']
            
            if 'icc_profile' in pil_image.info:
                metadata['icc_profile'] = pil_image.info['icc_profile']
            
            if pil_image.mode == 'RGBA':
                pil_image = pil_image.convert('RGB')
            
            image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            
            logger.info(f"DPI 정보: {metadata['dpi']}")
            
            return image, metadata
            
        except Exception as e:
            logger.error(f"이미지 로드 실패: {e}")
            return None, metadata
    
    def process_image(
        self,
        image_path: str,
        zoom_factor: Optional[float] = None,
        eye_position: Optional[float] = None,
        width_mm: Optional[float] = None,
        height_mm: Optional[float] = None,
        offset_x: Optional[float] = None,
        offset_y: Optional[float] = None
    ) -> Optional[Tuple[np.ndarray, Dict[str, Any]]]:
        """
        이미지 처리 메인 함수
        
        Args:
            image_path: 이미지 파일 경로
            zoom_factor: 얼굴 크기 대비 프레임 비율
            eye_position: 눈 위치 비율
            width_mm: 출력 규격 가로 (mm)
            height_mm: 출력 규격 세로 (mm)
            offset_x: 좌우 오프셋 비율 (-0.5 ~ 0.5)
            offset_y: 상하 오프셋 비율 (-0.5 ~ 0.5)
            
        Returns:
            (처리된 이미지, 메타데이터) 튜플 또는 실패 시 None
        """
        # 파라미터 오버라이드
        zoom = zoom_factor if zoom_factor is not None else self.zoom_factor
        eye_pos = eye_position if eye_position is not None else self.eye_position
        off_x = offset_x if offset_x is not None else self.offset_x
        off_y = offset_y if offset_y is not None else self.offset_y
        
        # 규격 오버라이드
        if width_mm is not None and height_mm is not None:
            original_aspect = self.aspect_ratio
            self.aspect_ratio = width_mm / height_mm
        else:
            original_aspect = None
        
        original_zoom = self.zoom_factor
        original_eye_pos = self.eye_position
        original_offset_x = self.offset_x
        original_offset_y = self.offset_y
        self.zoom_factor = zoom
        self.eye_position = eye_pos
        self.offset_x = off_x
        self.offset_y = off_y
        
        try:
            image, metadata = self._load_image_with_metadata(image_path)
            
            if image is None:
                logger.error(f"이미지 로드 실패: {image_path}")
                return None
            
            img_height, img_width = image.shape[:2]
            logger.info(f"이미지 로드 완료: {image_path} ({img_width}x{img_height}, DPI: {metadata['dpi']})")
            logger.info(f"출력 규격: {self.width_mm}x{self.height_mm}mm (비율: {self.aspect_ratio:.3f})")
            
            face_result = self._detect_largest_face(image)
            
            if face_result is None:
                logger.warning(f"얼굴 미감지: {image_path}")
                
                if self.fallback_on_no_face:
                    logger.info("폴백 모드: 중앙 크롭 적용")
                    cropped = self._center_crop_fallback(image)
                else:
                    logger.info("스킵 모드: 처리 건너뜀")
                    return None
            else:
                face_x, face_y, face_w, face_h, eye_center = face_result
                logger.info(f"얼굴 감지 완료 - 위치: ({face_x}, {face_y}), 크기: {face_w}x{face_h}")
                
                crop_x, crop_y, crop_w, crop_h = self._calculate_crop_region(
                    image, (face_x, face_y, face_w, face_h), eye_center
                )
                
                logger.info(f"크롭 영역 - 시작: ({crop_x}, {crop_y}), 크기: {crop_w}x{crop_h}")
                
                cropped = self._crop_with_padding(image, crop_x, crop_y, crop_w, crop_h)
            
            if self.preserve_resolution:
                crop_h, crop_w = cropped.shape[:2]
                
                if crop_h < self.min_output_height:
                    scale = self.min_output_height / crop_h
                    new_w = int(crop_w * scale)
                    new_h = self.min_output_height
                    result = cv2.resize(cropped, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
                else:
                    result = cropped
            else:
                result = cv2.resize(
                    cropped,
                    (self.default_output_width, self.default_output_height),
                    interpolation=cv2.INTER_LANCZOS4
                )
            
            result_h, result_w = result.shape[:2]
            logger.info(f"처리 완료: {image_path} -> {result_w}x{result_h}")
            
            return result, metadata
            
        except Exception as e:
            logger.error(f"이미지 처리 중 오류 발생 ({image_path}): {str(e)}")
            return None
            
        finally:
            self.zoom_factor = original_zoom
            self.eye_position = original_eye_pos
            self.offset_x = original_offset_x
            self.offset_y = original_offset_y
            if original_aspect is not None:
                self.aspect_ratio = original_aspect
    
    def process_image_from_array(
        self,
        image: np.ndarray,
        zoom_factor: Optional[float] = None,
        eye_position: Optional[float] = None,
        offset_x: Optional[float] = None,
        offset_y: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Tuple[np.ndarray, Dict[str, Any]]]:
        """numpy 배열로부터 직접 이미지 처리"""
        zoom = zoom_factor if zoom_factor is not None else self.zoom_factor
        eye_pos = eye_position if eye_position is not None else self.eye_position
        off_x = offset_x if offset_x is not None else self.offset_x
        off_y = offset_y if offset_y is not None else self.offset_y
        
        if metadata is None:
            metadata = {'dpi': (72, 72), 'exif': None, 'icc_profile': None}
        
        original_zoom = self.zoom_factor
        original_eye_pos = self.eye_position
        original_offset_x = self.offset_x
        original_offset_y = self.offset_y
        self.zoom_factor = zoom
        self.eye_position = eye_pos
        self.offset_x = off_x
        self.offset_y = off_y
        
        try:
            if image is None or image.size == 0:
                logger.error("유효하지 않은 이미지 배열")
                return None
            
            face_result = self._detect_largest_face(image)
            
            if face_result is None:
                if self.fallback_on_no_face:
                    cropped = self._center_crop_fallback(image)
                else:
                    return None
            else:
                face_x, face_y, face_w, face_h, eye_center = face_result
                crop_x, crop_y, crop_w, crop_h = self._calculate_crop_region(
                    image, (face_x, face_y, face_w, face_h), eye_center
                )
                cropped = self._crop_with_padding(image, crop_x, crop_y, crop_w, crop_h)
            
            if self.preserve_resolution:
                crop_h, crop_w = cropped.shape[:2]
                if crop_h < self.min_output_height:
                    scale = self.min_output_height / crop_h
                    new_w = int(crop_w * scale)
                    new_h = self.min_output_height
                    result = cv2.resize(cropped, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
                else:
                    result = cropped
            else:
                result = cv2.resize(
                    cropped,
                    (self.default_output_width, self.default_output_height),
                    interpolation=cv2.INTER_LANCZOS4
                )
            
            return result, metadata
            
        except Exception as e:
            logger.error(f"이미지 처리 중 오류: {str(e)}")
            return None
            
        finally:
            self.zoom_factor = original_zoom
            self.eye_position = original_eye_pos
            self.offset_x = original_offset_x
            self.offset_y = original_offset_y
