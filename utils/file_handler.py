"""
파일 입출력 관리 모듈

이미지 파일 탐색, 로드, 저장 등을 담당합니다.
Pillow를 사용하여 DPI/메타데이터를 보존합니다.
"""

import os
import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from typing import List, Optional, Generator, Tuple, Dict, Any
from datetime import datetime
import logging
import shutil

# 로거 설정
logger = logging.getLogger(__name__)

# 지원하는 이미지 확장자
SUPPORTED_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'
}


class FileHandler:
    """
    파일 입출력 관리 클래스
    
    이미지 파일 탐색, 로드, 저장 및 배치 처리를 담당합니다.
    DPI와 메타데이터를 보존합니다.
    """
    
    def __init__(
        self,
        input_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        output_format: str = 'jpg',
        output_quality: int = 95,
        preserve_structure: bool = True,
        preserve_dpi: bool = True  # DPI 보존 옵션
    ):
        """
        FileHandler 초기화
        
        Args:
            input_dir: 입력 이미지 디렉토리 경로
            output_dir: 출력 이미지 디렉토리 경로
            output_format: 출력 이미지 포맷 ('jpg', 'png', 'webp')
            output_quality: JPEG/WebP 품질 (1-100)
            preserve_structure: 하위 폴더 구조 유지 여부
            preserve_dpi: 원본 DPI 정보 보존 여부
        """
        self.input_dir = Path(input_dir) if input_dir else None
        self.output_dir = Path(output_dir) if output_dir else None
        self.output_format = output_format.lower().lstrip('.')
        self.output_quality = output_quality
        self.preserve_structure = preserve_structure
        self.preserve_dpi = preserve_dpi
        
        # 출력 디렉토리 생성
        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"출력 디렉토리 설정: {self.output_dir}")
    
    @staticmethod
    def is_supported_image(file_path: str) -> bool:
        ext = Path(file_path).suffix.lower()
        return ext in SUPPORTED_EXTENSIONS
    
    def find_images(
        self,
        directory: Optional[str] = None,
        recursive: bool = True
    ) -> List[Path]:
        search_dir = Path(directory) if directory else self.input_dir
        
        if not search_dir or not search_dir.exists():
            logger.error(f"디렉토리가 존재하지 않음: {search_dir}")
            return []
        
        images = []
        
        if recursive:
            for ext in SUPPORTED_EXTENSIONS:
                images.extend(search_dir.rglob(f'*{ext}'))
                images.extend(search_dir.rglob(f'*{ext.upper()}'))
        else:
            for ext in SUPPORTED_EXTENSIONS:
                images.extend(search_dir.glob(f'*{ext}'))
                images.extend(search_dir.glob(f'*{ext.upper()}'))
        
        images = sorted(set(images))
        logger.info(f"탐색 완료: {len(images)}개 이미지 발견 ({search_dir})")
        
        return images
    
    def iter_images(
        self,
        directory: Optional[str] = None,
        recursive: bool = True
    ) -> Generator[Tuple[Path, np.ndarray], None, None]:
        for image_path in self.find_images(directory, recursive):
            image = self.load_image(str(image_path))
            if image is not None:
                yield image_path, image
    
    @staticmethod
    def load_image(file_path: str) -> Optional[np.ndarray]:
        try:
            img_array = np.fromfile(file_path, dtype=np.uint8)
            image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            if image is None:
                logger.error(f"이미지 디코딩 실패: {file_path}")
                return None
            
            return image
            
        except Exception as e:
            logger.error(f"이미지 로드 실패 ({file_path}): {str(e)}")
            return None
    
    def save_image(
        self,
        image: np.ndarray,
        output_path: Optional[str] = None,
        original_path: Optional[str] = None,
        suffix: str = '_cropped',
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        이미지 저장 (DPI 및 메타데이터 보존)
        
        Args:
            image: 저장할 이미지 (BGR numpy 배열)
            output_path: 저장 경로
            original_path: 원본 파일 경로
            suffix: 파일명에 추가할 접미사
            metadata: DPI, EXIF 등 메타데이터 딕셔너리
            
        Returns:
            저장된 파일 경로 또는 실패 시 None
        """
        try:
            if output_path:
                save_path = Path(output_path)
            elif original_path and self.output_dir:
                original = Path(original_path)
                
                if self.preserve_structure and self.input_dir:
                    try:
                        rel_path = original.relative_to(self.input_dir)
                        save_dir = self.output_dir / rel_path.parent
                    except ValueError:
                        save_dir = self.output_dir
                else:
                    save_dir = self.output_dir
                
                save_dir.mkdir(parents=True, exist_ok=True)
                new_name = f"{original.stem}{suffix}.{self.output_format}"
                save_path = save_dir / new_name
            else:
                logger.error("저장 경로를 결정할 수 없습니다.")
                return None
            
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 확장자 결정
            if self.output_format in ('jpg', 'jpeg'):
                ext = '.jpg'
            elif self.output_format == 'png':
                ext = '.png'
            elif self.output_format == 'webp':
                ext = '.webp'
            elif self.output_format == 'tiff':
                ext = '.tiff'
            else:
                ext = f'.{self.output_format}'
            
            if save_path.suffix.lower() != ext:
                save_path = save_path.with_suffix(ext)
            
            # BGR -> RGB 변환 후 Pillow Image로 변환
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(image_rgb)
            
            # 저장 파라미터 설정
            save_kwargs = {}
            
            # DPI 설정
            if self.preserve_dpi and metadata and 'dpi' in metadata:
                dpi = metadata['dpi']
                # DPI가 튜플이 아닌 경우 처리
                if isinstance(dpi, (int, float)):
                    dpi = (dpi, dpi)
                save_kwargs['dpi'] = dpi
                logger.info(f"DPI 보존: {dpi}")
            
            # 포맷별 품질 설정
            if self.output_format in ('jpg', 'jpeg'):
                save_kwargs['quality'] = self.output_quality
                save_kwargs['subsampling'] = 0  # 최고 품질 서브샘플링
                
                # EXIF 데이터 보존 (JPEG만)
                if metadata and 'exif' in metadata and metadata['exif']:
                    save_kwargs['exif'] = metadata['exif']
                    
            elif self.output_format == 'png':
                # PNG는 무손실이므로 compress_level만 설정
                compress_level = max(0, min(9, (100 - self.output_quality) // 10))
                save_kwargs['compress_level'] = compress_level
                
            elif self.output_format == 'webp':
                save_kwargs['quality'] = self.output_quality
                save_kwargs['method'] = 6  # 최고 품질 압축
                
            elif self.output_format in ('tiff', 'tif'):
                save_kwargs['compression'] = 'tiff_lzw'
            
            # ICC 프로파일 보존
            if metadata and 'icc_profile' in metadata and metadata['icc_profile']:
                save_kwargs['icc_profile'] = metadata['icc_profile']
            
            # 저장
            pil_image.save(str(save_path), **save_kwargs)
            
            logger.debug(f"이미지 저장 완료: {save_path}")
            return str(save_path)
                
        except Exception as e:
            logger.error(f"이미지 저장 실패: {str(e)}")
            return None
    
    def get_output_path(
        self,
        original_path: str,
        suffix: str = '_cropped'
    ) -> str:
        original = Path(original_path)
        
        if self.output_dir:
            if self.preserve_structure and self.input_dir:
                try:
                    rel_path = original.relative_to(self.input_dir)
                    save_dir = self.output_dir / rel_path.parent
                except ValueError:
                    save_dir = self.output_dir
            else:
                save_dir = self.output_dir
        else:
            save_dir = original.parent
        
        new_name = f"{original.stem}{suffix}.{self.output_format}"
        return str(save_dir / new_name)
    
    def create_backup(self, file_path: str) -> Optional[str]:
        try:
            original = Path(file_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{original.stem}_backup_{timestamp}{original.suffix}"
            backup_path = original.parent / backup_name
            
            shutil.copy2(file_path, backup_path)
            logger.info(f"백업 생성: {backup_path}")
            
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"백업 생성 실패 ({file_path}): {str(e)}")
            return None
    
    @staticmethod
    def get_image_info(file_path: str) -> Optional[dict]:
        try:
            path = Path(file_path)
            
            if not path.exists():
                return None
            
            file_size = path.stat().st_size
            
            # Pillow로 상세 정보 읽기
            pil_image = Image.open(str(path))
            width, height = pil_image.size
            
            # DPI 정보
            dpi = pil_image.info.get('dpi', (72, 72))
            
            return {
                'path': str(path.absolute()),
                'name': path.name,
                'extension': path.suffix.lower(),
                'width': width,
                'height': height,
                'dpi': dpi,
                'file_size': file_size,
                'file_size_mb': round(file_size / (1024 * 1024), 2)
            }
            
        except Exception as e:
            logger.error(f"이미지 정보 조회 실패 ({file_path}): {str(e)}")
            return None


class BatchProcessor:
    """대량 이미지 배치 처리 클래스"""
    
    def __init__(
        self,
        file_handler: FileHandler,
        cropper,
        skip_existing: bool = True
    ):
        self.file_handler = file_handler
        self.cropper = cropper
        self.skip_existing = skip_existing
        
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0
        }
    
    def reset_stats(self):
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0
        }
    
    def process_batch(
        self,
        input_dir: Optional[str] = None,
        recursive: bool = True,
        progress_callback=None
    ) -> dict:
        self.reset_stats()
        
        images = self.file_handler.find_images(input_dir, recursive)
        self.stats['total'] = len(images)
        
        if not images:
            logger.warning("처리할 이미지가 없습니다.")
            return self.stats
        
        logger.info(f"배치 처리 시작: 총 {len(images)}개 이미지")
        
        for idx, image_path in enumerate(images, 1):
            try:
                if progress_callback:
                    progress_callback(idx, len(images), str(image_path))
                
                output_path = self.file_handler.get_output_path(str(image_path))
                
                if self.skip_existing and Path(output_path).exists():
                    logger.debug(f"건너뛰기 (이미 존재): {image_path.name}")
                    self.stats['skipped'] += 1
                    continue
                
                # 이미지 처리 (메타데이터 포함)
                result = self.cropper.process_image(str(image_path))
                
                if result is not None:
                    image_data, metadata = result
                    
                    # 메타데이터와 함께 저장
                    saved_path = self.file_handler.save_image(
                        image_data,
                        original_path=str(image_path),
                        metadata=metadata
                    )
                    
                    if saved_path:
                        self.stats['success'] += 1
                        logger.info(f"[{idx}/{len(images)}] 완료: {image_path.name}")
                    else:
                        self.stats['failed'] += 1
                        logger.error(f"[{idx}/{len(images)}] 저장 실패: {image_path.name}")
                else:
                    self.stats['failed'] += 1
                    logger.error(f"[{idx}/{len(images)}] 처리 실패: {image_path.name}")
                    
            except Exception as e:
                self.stats['failed'] += 1
                logger.error(f"[{idx}/{len(images)}] 예외 발생 ({image_path.name}): {str(e)}")
        
        logger.info(
            f"배치 처리 완료 - "
            f"성공: {self.stats['success']}, "
            f"실패: {self.stats['failed']}, "
            f"건너뜀: {self.stats['skipped']}"
        )
        
        return self.stats
