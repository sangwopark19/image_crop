#!/usr/bin/env python3
"""
포토카드 자동 크롭 프로그램 - GUI 버전

아이돌 고화질 사진을 포토카드 규격(55x85mm, 550x850px)에 맞춰
자동으로 크롭하는 데스크탑 프로그램입니다.

GUI: tkinter + ttk 기반 (macOS 호환)
"""

import os
import sys
import threading
import queue
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, END
from PIL import Image, ImageTk
import cv2
import numpy as np


# ============================================================
# 로깅 설정
# ============================================================

class QueueHandler(logging.Handler):
    """로그를 큐로 전달하는 핸들러"""
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue
    
    def emit(self, record):
        self.log_queue.put(self.format(record))


def setup_logging(log_queue: queue.Queue):
    """로깅 설정"""
    formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S')
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    
    queue_handler = QueueHandler(log_queue)
    queue_handler.setLevel(logging.INFO)
    queue_handler.setFormatter(formatter)
    root_logger.addHandler(queue_handler)


# ============================================================
# GUI 애플리케이션
# ============================================================

class PhotoCardCropperApp:
    """포토카드 크롭 GUI 애플리케이션"""
    
    # 프리셋 규격 (가로mm x 세로mm)
    PRESET_SIZES = {
        '포토카드 (55×85)': (55, 85),
        '여권사진 (35×45)': (35, 45),
        '증명사진 3×4 (30×40)': (30, 40),
        '증명사진 4×5 (40×50)': (40, 50),
        'ID카드 (54×86)': (54, 86),
        '인스탁스 미니 (54×86)': (54, 86),
        '인스탁스 스퀘어 (62×62)': (62, 62),
        '폴라로이드 (79×79)': (79, 79),
        '명함 가로 (90×50)': (90, 50),
        '명함 세로 (50×90)': (50, 90),
        '사용자 정의': (55, 85),
    }
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("📷 사진 자동 크롭")
        self.root.geometry("950x900")
        self.root.minsize(900, 850)
        
        # 변수 초기화
        self.input_dir: Optional[str] = None
        self.output_dir: Optional[str] = None
        self.is_processing = False
        self.processing_thread: Optional[threading.Thread] = None
        
        # 크로퍼 (지연 로딩)
        self.cropper = None
        self.file_handler_module = None
        self.PhotoCardCropper = None
        self.FileHandler = None
        self.BatchProcessor = None
        
        # 미리보기 관련
        self.preview_image_path: Optional[str] = None
        self.preview_original_image: Optional[np.ndarray] = None
        self.preview_photo_image: Optional[ImageTk.PhotoImage] = None
        self.preview_update_job = None  # 디바운싱용
        self.preview_cropper = None
        
        # 이미지별 오프셋 저장 {이미지경로: (offset_x, offset_y)}
        self.image_offsets: dict = {}
        
        # tkinter 변수
        self.zoom_var = tk.DoubleVar(value=2.8)
        self.eye_var = tk.DoubleVar(value=0.42)
        self.offset_x_var = tk.DoubleVar(value=0.0)  # 좌우 오프셋 (-0.3 ~ 0.3)
        self.offset_y_var = tk.DoubleVar(value=0.0)  # 상하 오프셋 (-0.3 ~ 0.3)
        self.progress_var = tk.DoubleVar(value=0)
        self.width_var = tk.StringVar(value="55")
        self.height_var = tk.StringVar(value="85")
        self.preset_var = tk.StringVar(value="포토카드 (55×85)")
        self._updating_from_preset = False  # 프리셋에서 값 업데이트 중 플래그
        
        # 로그 큐
        self.log_queue = queue.Queue()
        setup_logging(self.log_queue)
        
        # 스타일 설정
        self._setup_styles()
        
        # UI 구성
        self._create_widgets()
        
        # 로그 업데이트 타이머
        self._poll_log_queue()
    
    def _setup_styles(self):
        """ttk 스타일 설정"""
        style = ttk.Style()
        
        # 테마 설정 (macOS는 aqua 사용)
        available_themes = style.theme_names()
        if 'aqua' in available_themes:
            style.theme_use('aqua')
        elif 'clam' in available_themes:
            style.theme_use('clam')
        
        # 커스텀 스타일
        style.configure('Title.TLabel', font=('SF Pro Display', 24, 'bold'))
        style.configure('Subtitle.TLabel', font=('SF Pro Display', 12), foreground='#666666')
        style.configure('Section.TLabel', font=('SF Pro Display', 14, 'bold'))
        style.configure('Value.TLabel', font=('SF Pro Display', 12, 'bold'), foreground='#007AFF')
        style.configure('Hint.TLabel', font=('SF Pro Display', 10), foreground='#888888')
        style.configure('Status.TLabel', font=('SF Pro Display', 11))
        
        # 버튼 스타일
        style.configure('Action.TButton', font=('SF Pro Display', 14, 'bold'), padding=(20, 12))
        style.configure('Folder.TButton', font=('SF Pro Display', 11), padding=(15, 8))
        
        # 프레임 스타일
        style.configure('Card.TFrame', relief='flat')
        style.configure('TLabelframe', font=('SF Pro Display', 12, 'bold'))
        style.configure('TLabelframe.Label', font=('SF Pro Display', 12, 'bold'))
    
    def _create_widgets(self):
        """UI 위젯 생성"""
        # 메인 컨테이너
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill='both', expand=True)
        
        # 헤더
        self._create_header(main_frame)
        
        # 좌우 분할 컨테이너
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill='both', expand=True)
        
        # 왼쪽: 설정 패널
        left_frame = ttk.Frame(content_frame)
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # 오른쪽: 미리보기 패널
        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side='right', fill='both')
        
        # 왼쪽 섹션들
        self._create_file_section(left_frame)
        self._create_options_section(left_frame)
        self._create_action_section(left_frame)
        self._create_progress_section(left_frame)
        self._create_log_section(left_frame)
        
        # 오른쪽: 미리보기
        self._create_preview_section(right_frame)
    
    def _create_header(self, parent):
        """헤더 생성"""
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill='x', pady=(0, 15))
        
        title_label = ttk.Label(
            header_frame,
            text="📷 포토카드 자동 크롭",
            style='Title.TLabel'
        )
        title_label.pack(anchor='w')
        
        subtitle_label = ttk.Label(
            header_frame,
            text="아이돌 사진을 포토카드 규격(55×85mm)에 맞춰 자동 크롭합니다",
            style='Subtitle.TLabel'
        )
        subtitle_label.pack(anchor='w', pady=(5, 0))
    
    def _create_file_section(self, parent):
        """파일 선택 섹션"""
        section_frame = ttk.LabelFrame(parent, text=" 📁 폴더 선택 ", padding=15)
        section_frame.pack(fill='x', pady=(0, 12))
        
        # 원본 폴더
        input_frame = ttk.Frame(section_frame)
        input_frame.pack(fill='x', pady=(0, 10))
        
        self.input_btn = ttk.Button(
            input_frame,
            text="원본 폴더 선택",
            style='Folder.TButton',
            command=self._select_input_folder,
            width=15
        )
        self.input_btn.pack(side='left')
        
        self.input_label = ttk.Label(
            input_frame,
            text="선택된 폴더 없음",
            style='Hint.TLabel'
        )
        self.input_label.pack(side='left', padx=(15, 0))
        
        # 저장 폴더
        output_frame = ttk.Frame(section_frame)
        output_frame.pack(fill='x')
        
        self.output_btn = ttk.Button(
            output_frame,
            text="저장 폴더 선택",
            style='Folder.TButton',
            command=self._select_output_folder,
            width=15
        )
        self.output_btn.pack(side='left')
        
        self.output_label = ttk.Label(
            output_frame,
            text="선택된 폴더 없음",
            style='Hint.TLabel'
        )
        self.output_label.pack(side='left', padx=(15, 0))
    
    def _create_options_section(self, parent):
        """옵션 조절 섹션"""
        section_frame = ttk.LabelFrame(parent, text=" ⚙️ 옵션 조절 ", padding=15)
        section_frame.pack(fill='x', pady=(0, 12))
        
        # ========== 출력 규격 선택 ==========
        size_frame = ttk.Frame(section_frame)
        size_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(
            size_frame,
            text="📐 출력 규격",
            font=('SF Pro Display', 12, 'bold')
        ).pack(anchor='w')
        
        # 프리셋 드롭다운
        preset_frame = ttk.Frame(size_frame)
        preset_frame.pack(fill='x', pady=(8, 0))
        
        ttk.Label(preset_frame, text="프리셋:").pack(side='left')
        
        self.preset_combo = ttk.Combobox(
            preset_frame,
            textvariable=self.preset_var,
            values=list(self.PRESET_SIZES.keys()),
            state='readonly',
            width=20
        )
        self.preset_combo.pack(side='left', padx=(10, 0))
        self.preset_combo.bind('<<ComboboxSelected>>', self._on_preset_change)
        
        # 가로/세로 입력
        size_input_frame = ttk.Frame(size_frame)
        size_input_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Label(size_input_frame, text="가로:").pack(side='left')
        self.width_entry = ttk.Entry(
            size_input_frame,
            textvariable=self.width_var,
            width=8
        )
        self.width_entry.pack(side='left', padx=(5, 0))
        ttk.Label(size_input_frame, text="mm").pack(side='left', padx=(2, 15))
        
        ttk.Label(size_input_frame, text="세로:").pack(side='left')
        self.height_entry = ttk.Entry(
            size_input_frame,
            textvariable=self.height_var,
            width=8
        )
        self.height_entry.pack(side='left', padx=(5, 0))
        ttk.Label(size_input_frame, text="mm").pack(side='left', padx=(2, 0))
        
        # 비율 표시
        self.ratio_label = ttk.Label(
            size_frame,
            text="비율: 55:85 (0.647)",
            style='Hint.TLabel'
        )
        self.ratio_label.pack(anchor='w', pady=(5, 0))
        
        # 입력값 변경 시 비율 업데이트
        self.width_var.trace_add('write', self._on_size_change)
        self.height_var.trace_add('write', self._on_size_change)
        
        # 구분선
        ttk.Separator(section_frame, orient='horizontal').pack(fill='x', pady=15)
        
        # ========== Zoom Factor 슬라이더 ==========
        zoom_frame = ttk.Frame(section_frame)
        zoom_frame.pack(fill='x', pady=(0, 15))
        
        zoom_label_frame = ttk.Frame(zoom_frame)
        zoom_label_frame.pack(fill='x')
        
        ttk.Label(
            zoom_label_frame,
            text="얼굴 확대 비율 (Zoom Factor)"
        ).pack(side='left')
        
        self.zoom_value_label = ttk.Label(
            zoom_label_frame,
            text="2.80",
            style='Value.TLabel'
        )
        self.zoom_value_label.pack(side='right')
        
        self.zoom_slider = ttk.Scale(
            zoom_frame,
            from_=1.5,
            to=5.0,
            variable=self.zoom_var,
            orient='horizontal',
            command=self._on_zoom_change
        )
        self.zoom_slider.pack(fill='x', pady=(8, 0))
        
        ttk.Label(
            zoom_frame,
            text="← 얼굴 크게 (클로즈업)  │  얼굴 작게 (여백 많음) →",
            style='Hint.TLabel'
        ).pack(fill='x', pady=(5, 0))
        
        # ========== Eye Position 슬라이더 ==========
        eye_frame = ttk.Frame(section_frame)
        eye_frame.pack(fill='x')
        
        eye_label_frame = ttk.Frame(eye_frame)
        eye_label_frame.pack(fill='x')
        
        ttk.Label(
            eye_label_frame,
            text="눈 높이 위치 (Eye Position)"
        ).pack(side='left')
        
        self.eye_value_label = ttk.Label(
            eye_label_frame,
            text="0.42",
            style='Value.TLabel'
        )
        self.eye_value_label.pack(side='right')
        
        self.eye_slider = ttk.Scale(
            eye_frame,
            from_=0.2,
            to=0.6,
            variable=self.eye_var,
            orient='horizontal',
            command=self._on_eye_change
        )
        self.eye_slider.pack(fill='x', pady=(8, 0))
        
        ttk.Label(
            eye_frame,
            text="← 눈이 위쪽 (이마 적음)  │  눈이 아래쪽 (이마 많음) →",
            style='Hint.TLabel'
        ).pack(fill='x', pady=(5, 0))
        
        # ========== 위치 조정 섹션 ==========
        ttk.Separator(section_frame, orient='horizontal').pack(fill='x', pady=15)
        
        offset_header_frame = ttk.Frame(section_frame)
        offset_header_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Label(
            offset_header_frame,
            text="📍 위치 미세 조정 (이미지별)",
            font=('SF Pro Display', 12, 'bold')
        ).pack(side='left')
        
        self.reset_offset_btn = ttk.Button(
            offset_header_frame,
            text="초기화",
            command=self._reset_current_image_offset,
            width=8
        )
        self.reset_offset_btn.pack(side='right')
        
        # 조정된 이미지 수 표시
        self.offset_count_label = ttk.Label(
            section_frame,
            text="조정된 이미지: 0개",
            style='Hint.TLabel'
        )
        self.offset_count_label.pack(anchor='w', pady=(0, 5))
        
        # 좌우 오프셋 슬라이더
        offset_x_frame = ttk.Frame(section_frame)
        offset_x_frame.pack(fill='x', pady=(0, 10))
        
        offset_x_label_frame = ttk.Frame(offset_x_frame)
        offset_x_label_frame.pack(fill='x')
        
        ttk.Label(
            offset_x_label_frame,
            text="좌우 이동"
        ).pack(side='left')
        
        self.offset_x_value_label = ttk.Label(
            offset_x_label_frame,
            text="0",
            style='Value.TLabel'
        )
        self.offset_x_value_label.pack(side='right')
        
        self.offset_x_slider = ttk.Scale(
            offset_x_frame,
            from_=-0.3,
            to=0.3,
            variable=self.offset_x_var,
            orient='horizontal',
            command=self._on_offset_x_change
        )
        self.offset_x_slider.pack(fill='x', pady=(5, 0))
        
        ttk.Label(
            offset_x_frame,
            text="← 왼쪽 이동  │  오른쪽 이동 →",
            style='Hint.TLabel'
        ).pack(fill='x', pady=(3, 0))
        
        # 상하 오프셋 슬라이더
        offset_y_frame = ttk.Frame(section_frame)
        offset_y_frame.pack(fill='x')
        
        offset_y_label_frame = ttk.Frame(offset_y_frame)
        offset_y_label_frame.pack(fill='x')
        
        ttk.Label(
            offset_y_label_frame,
            text="상하 이동"
        ).pack(side='left')
        
        self.offset_y_value_label = ttk.Label(
            offset_y_label_frame,
            text="0",
            style='Value.TLabel'
        )
        self.offset_y_value_label.pack(side='right')
        
        self.offset_y_slider = ttk.Scale(
            offset_y_frame,
            from_=-0.3,
            to=0.3,
            variable=self.offset_y_var,
            orient='horizontal',
            command=self._on_offset_y_change
        )
        self.offset_y_slider.pack(fill='x', pady=(5, 0))
        
        ttk.Label(
            offset_y_frame,
            text="← 위로 이동  │  아래로 이동 →",
            style='Hint.TLabel'
        ).pack(fill='x', pady=(3, 0))
    
    def _create_action_section(self, parent):
        """실행 버튼 섹션"""
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill='x', pady=(0, 12))
        
        self.start_btn = ttk.Button(
            action_frame,
            text="🚀 변환 시작",
            style='Action.TButton',
            command=self._start_processing
        )
        self.start_btn.pack(fill='x', ipady=5)
    
    def _create_progress_section(self, parent):
        """진행 상황 섹션"""
        section_frame = ttk.LabelFrame(parent, text=" 📊 진행 상황 ", padding=15)
        section_frame.pack(fill='x', pady=(0, 12))
        
        # 상태 라벨
        status_frame = ttk.Frame(section_frame)
        status_frame.pack(fill='x', pady=(0, 8))
        
        self.status_label = ttk.Label(
            status_frame,
            text="대기 중",
            style='Status.TLabel'
        )
        self.status_label.pack(side='right')
        
        # 프로그레스 바
        self.progress_bar = ttk.Progressbar(
            section_frame,
            variable=self.progress_var,
            maximum=100,
            mode='determinate'
        )
        self.progress_bar.pack(fill='x', pady=(0, 5))
        
        # 진행률 텍스트
        self.progress_label = ttk.Label(
            section_frame,
            text="0 / 0 (0%)",
            style='Hint.TLabel'
        )
        self.progress_label.pack()
    
    def _create_log_section(self, parent):
        """로그 섹션"""
        section_frame = ttk.LabelFrame(parent, text=" 📝 처리 로그 ", padding=10)
        section_frame.pack(fill='both', expand=True)
        
        # 버튼 프레임
        btn_frame = ttk.Frame(section_frame)
        btn_frame.pack(fill='x', pady=(0, 8))
        
        clear_btn = ttk.Button(
            btn_frame,
            text="로그 지우기",
            command=self._clear_log,
            width=12
        )
        clear_btn.pack(side='right')
        
        # 로그 텍스트 박스
        self.log_text = scrolledtext.ScrolledText(
            section_frame,
            height=8,
            font=('Menlo', 10),
            wrap=tk.WORD,
            bg='#1E1E1E',
            fg='#D4D4D4',
            insertbackground='white'
        )
        self.log_text.pack(fill='both', expand=True)
        
        # 초기 메시지
        self._append_log("프로그램이 준비되었습니다. 폴더를 선택하고 변환을 시작하세요.")
    
    def _create_preview_section(self, parent):
        """미리보기 섹션"""
        section_frame = ttk.LabelFrame(parent, text=" 👁️ 미리보기 ", padding=10)
        section_frame.pack(fill='both', expand=True)
        
        # 미리보기 정보
        self.preview_info_label = ttk.Label(
            section_frame,
            text="원본 폴더를 선택하면 첫 번째 이미지로 미리보기가 표시됩니다",
            style='Hint.TLabel',
            wraplength=280
        )
        self.preview_info_label.pack(pady=(0, 10))
        
        # 미리보기 캔버스 (고정 크기)
        self.preview_canvas = tk.Canvas(
            section_frame,
            width=280,
            height=430,
            bg='#2D2D2D',
            highlightthickness=1,
            highlightbackground='#555555'
        )
        self.preview_canvas.pack(pady=5)
        
        # 이미지 선택 버튼
        btn_frame = ttk.Frame(section_frame)
        btn_frame.pack(fill='x', pady=(10, 0))
        
        self.preview_prev_btn = ttk.Button(
            btn_frame,
            text="◀ 이전",
            command=self._prev_preview_image,
            width=8
        )
        self.preview_prev_btn.pack(side='left')
        
        self.preview_next_btn = ttk.Button(
            btn_frame,
            text="다음 ▶",
            command=self._next_preview_image,
            width=8
        )
        self.preview_next_btn.pack(side='right')
        
        # 현재 이미지 인덱스
        self.preview_index = 0
        self.preview_images = []
    
    # ============================================================
    # 이벤트 핸들러
    # ============================================================
    
    def _select_input_folder(self):
        """원본 폴더 선택"""
        folder = filedialog.askdirectory(title="원본 이미지 폴더 선택")
        if folder:
            self.input_dir = folder
            display_path = self._truncate_path(folder, 40)
            self.input_label.configure(text=display_path)
            self._append_log(f"원본 폴더 선택: {folder}")
            
            # 미리보기용 이미지 목록 로드
            self._load_preview_images(folder)
    
    def _select_output_folder(self):
        """저장 폴더 선택"""
        folder = filedialog.askdirectory(title="저장 폴더 선택")
        if folder:
            self.output_dir = folder
            display_path = self._truncate_path(folder, 40)
            self.output_label.configure(text=display_path)
            self._append_log(f"저장 폴더 선택: {folder}")
    
    def _on_preset_change(self, event):
        """프리셋 선택 변경"""
        preset_name = self.preset_var.get()
        if preset_name in self.PRESET_SIZES:
            width, height = self.PRESET_SIZES[preset_name]
            
            # 플래그 설정: _on_size_change에서 프리셋 변경 방지
            self._updating_from_preset = True
            self.width_var.set(str(width))
            self.height_var.set(str(height))
            self._updating_from_preset = False
            
            # 비율 라벨 업데이트
            ratio = width / height
            self.ratio_label.configure(text=f"비율: {width:.0f}:{height:.0f} ({ratio:.3f})")
            
            if preset_name != '사용자 정의':
                self._append_log(f"📐 규격 변경: {preset_name}")
            
            # 미리보기 업데이트
            self._schedule_preview_update()
    
    def _on_size_change(self, *args):
        """가로/세로 값 변경 시 비율 업데이트"""
        # 프리셋에서 업데이트 중이면 무시
        if getattr(self, '_updating_from_preset', False):
            return
            
        try:
            width = float(self.width_var.get())
            height = float(self.height_var.get())
            
            if width > 0 and height > 0:
                ratio = width / height
                self.ratio_label.configure(text=f"비율: {width:.0f}:{height:.0f} ({ratio:.3f})")
                
                # 사용자가 직접 값을 변경한 경우 프리셋을 '사용자 정의'로 변경
                current_preset = self.preset_var.get()
                if current_preset != '사용자 정의':
                    preset_size = self.PRESET_SIZES.get(current_preset)
                    if preset_size and (preset_size[0] != width or preset_size[1] != height):
                        self.preset_var.set('사용자 정의')
                
                # 미리보기 업데이트
                self._schedule_preview_update()
        except ValueError:
            pass
    
    def _on_zoom_change(self, value):
        """Zoom 슬라이더 변경"""
        val = float(value)
        self.zoom_value_label.configure(text=f"{val:.2f}")
        # 미리보기 업데이트 (디바운싱)
        self._schedule_preview_update()
    
    def _on_eye_change(self, value):
        """Eye Position 슬라이더 변경"""
        val = float(value)
        self.eye_value_label.configure(text=f"{val:.2f}")
        # 미리보기 업데이트 (디바운싱)
        self._schedule_preview_update()
    
    def _on_offset_x_change(self, value):
        """좌우 오프셋 슬라이더 변경"""
        val = float(value)
        # 퍼센트로 표시
        percent = int(val * 100)
        self.offset_x_value_label.configure(text=f"{percent:+d}%")
        # 현재 이미지에 오프셋 저장
        self._save_current_image_offset()
        # 미리보기 업데이트 (디바운싱)
        self._schedule_preview_update()
    
    def _on_offset_y_change(self, value):
        """상하 오프셋 슬라이더 변경"""
        val = float(value)
        # 퍼센트로 표시
        percent = int(val * 100)
        self.offset_y_value_label.configure(text=f"{percent:+d}%")
        # 현재 이미지에 오프셋 저장
        self._save_current_image_offset()
        # 미리보기 업데이트 (디바운싱)
        self._schedule_preview_update()
    
    def _save_current_image_offset(self):
        """현재 이미지의 오프셋 값 저장"""
        if self.preview_images and 0 <= self.preview_index < len(self.preview_images):
            image_path = self.preview_images[self.preview_index]
            offset_x = self.offset_x_var.get()
            offset_y = self.offset_y_var.get()
            self.image_offsets[image_path] = (offset_x, offset_y)
            # 조정된 이미지 수 업데이트
            self._update_offset_count()
    
    def _load_image_offset(self, image_path: str):
        """이미지의 저장된 오프셋 값 불러오기"""
        if image_path in self.image_offsets:
            offset_x, offset_y = self.image_offsets[image_path]
        else:
            # 저장된 값이 없으면 기본값 (0, 0) 사용
            offset_x, offset_y = 0.0, 0.0
        
        # 슬라이더 업데이트 (이벤트 방지를 위해 trace 없이)
        self.offset_x_var.set(offset_x)
        self.offset_y_var.set(offset_y)
        
        # 라벨 업데이트
        self.offset_x_value_label.configure(text=f"{int(offset_x * 100):+d}%")
        self.offset_y_value_label.configure(text=f"{int(offset_y * 100):+d}%")
    
    def _reset_current_image_offset(self):
        """현재 이미지의 오프셋 초기화"""
        self.offset_x_var.set(0.0)
        self.offset_y_var.set(0.0)
        self.offset_x_value_label.configure(text="+0%")
        self.offset_y_value_label.configure(text="+0%")
        self._save_current_image_offset()
        self._schedule_preview_update()
    
    def _update_offset_count(self):
        """조정된 이미지 수 업데이트"""
        # 0이 아닌 오프셋을 가진 이미지 수 계산
        adjusted_count = sum(
            1 for ox, oy in self.image_offsets.values() 
            if ox != 0 or oy != 0
        )
        self.offset_count_label.configure(text=f"조정된 이미지: {adjusted_count}개")
    
    def _clear_log(self):
        """로그 지우기"""
        self.log_text.delete('1.0', END)
    
    def _append_log(self, message: str):
        """로그 추가"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(END, f"[{timestamp}] {message}\n")
        self.log_text.see(END)
    
    def _truncate_path(self, path: str, max_length: int) -> str:
        """긴 경로 줄이기"""
        if len(path) <= max_length:
            return path
        return "..." + path[-(max_length - 3):]
    
    # ============================================================
    # 미리보기 관련 메서드
    # ============================================================
    
    def _load_preview_images(self, folder: str):
        """폴더에서 미리보기용 이미지 목록 로드 (하위 폴더 포함)"""
        supported_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
        
        # 성능 제한: 최대 탐색 깊이 및 최대 이미지 수
        MAX_DEPTH = 5
        MAX_IMAGES = 1000
        
        images = []
        
        def scan_folder(current_folder: str, current_depth: int):
            """재귀적으로 폴더 스캔 (깊이 제한 적용)"""
            if current_depth > MAX_DEPTH or len(images) >= MAX_IMAGES:
                return
            
            try:
                entries = sorted(os.listdir(current_folder))
            except PermissionError:
                return  # 권한 없는 폴더 스킵
            
            for entry in entries:
                if len(images) >= MAX_IMAGES:
                    break
                
                full_path = os.path.join(current_folder, entry)
                
                # 심볼릭 링크 무시 (무한 루프 방지)
                if os.path.islink(full_path):
                    continue
                
                if os.path.isfile(full_path):
                    ext = os.path.splitext(entry)[1].lower()
                    if ext in supported_extensions:
                        images.append(full_path)
                elif os.path.isdir(full_path):
                    # 숨김 폴더 스킵 (예: .git, .DS_Store 등)
                    if not entry.startswith('.'):
                        scan_folder(full_path, current_depth + 1)
        
        # 스캔 시작
        scan_folder(folder, 0)
        
        # 경로 기준으로 정렬
        images.sort()
        
        self.preview_images = images
        self.preview_index = 0
        
        if images:
            # 하위 폴더 수 계산
            unique_folders = set(os.path.dirname(img) for img in images)
            folder_count = len(unique_folders)
            
            if folder_count > 1:
                self._append_log(f"📷 미리보기: {len(images)}개 이미지 발견 ({folder_count}개 폴더)")
            else:
                self._append_log(f"📷 미리보기: {len(images)}개 이미지 발견")
            
            if len(images) >= MAX_IMAGES:
                self._append_log(f"⚠️ 최대 {MAX_IMAGES}개까지만 표시됩니다")
            
            self._load_current_preview_image()
        else:
            self._append_log("⚠️ 폴더에 이미지 파일이 없습니다")
            self.preview_info_label.configure(text="이미지 파일이 없습니다")
            self.preview_canvas.delete("all")
    
    def _load_current_preview_image(self):
        """현재 인덱스의 이미지를 로드"""
        if not self.preview_images:
            return
        
        image_path = self.preview_images[self.preview_index]
        filename = os.path.basename(image_path)
        
        # 해당 이미지의 저장된 오프셋 불러오기
        self._load_image_offset(image_path)
        
        # 상대 경로 계산 (원본 폴더 기준)
        if self.input_dir:
            rel_path = os.path.relpath(image_path, self.input_dir)
            rel_folder = os.path.dirname(rel_path)
        else:
            rel_folder = ""
        
        try:
            # 이미지 로드 (OpenCV)
            self.preview_original_image = cv2.imread(image_path)
            if self.preview_original_image is None:
                raise ValueError("이미지를 읽을 수 없습니다")
            
            # 정보 표시 (폴더 경로 포함 + 개별 오프셋 상태)
            h, w = self.preview_original_image.shape[:2]
            if rel_folder:
                display_name = f"📁 {rel_folder}/\n📄 {filename}"
            else:
                display_name = f"📄 {filename}"
            
            # 개별 오프셋 설정 여부 표시
            offset_indicator = ""
            if image_path in self.image_offsets:
                ox, oy = self.image_offsets[image_path]
                if ox != 0 or oy != 0:
                    offset_indicator = " 📍"
            
            self.preview_info_label.configure(
                text=f"{display_name}\n({w}×{h}px) - {self.preview_index + 1}/{len(self.preview_images)}{offset_indicator}"
            )
            
            # 미리보기 업데이트
            self._update_preview()
            
        except Exception as e:
            self._append_log(f"⚠️ 미리보기 로드 실패: {filename} - {e}")
            self.preview_info_label.configure(text=f"로드 실패: {filename}")
    
    def _prev_preview_image(self):
        """이전 이미지"""
        if self.preview_images and self.preview_index > 0:
            self.preview_index -= 1
            self._load_current_preview_image()
    
    def _next_preview_image(self):
        """다음 이미지"""
        if self.preview_images and self.preview_index < len(self.preview_images) - 1:
            self.preview_index += 1
            self._load_current_preview_image()
    
    def _schedule_preview_update(self):
        """미리보기 업데이트 스케줄 (디바운싱)"""
        # 기존 예약된 작업 취소
        if self.preview_update_job is not None:
            self.root.after_cancel(self.preview_update_job)
        
        # 150ms 후에 업데이트 (슬라이더 드래그 중 과도한 호출 방지)
        self.preview_update_job = self.root.after(150, self._update_preview)
    
    def _update_preview(self):
        """미리보기 이미지 업데이트"""
        self.preview_update_job = None
        
        if self.preview_original_image is None:
            return
        
        try:
            # 크로퍼 초기화 (필요시)
            if self.preview_cropper is None:
                from core.cropper import PhotoCardCropper
                self.preview_cropper = PhotoCardCropper(preserve_resolution=False)
            
            # 현재 설정 값 가져오기
            zoom = self.zoom_var.get()
            eye_pos = self.eye_var.get()
            
            try:
                width_mm = float(self.width_var.get())
                height_mm = float(self.height_var.get())
                aspect_ratio = width_mm / height_mm
            except ValueError:
                aspect_ratio = 55 / 85  # 기본 포토카드 비율
            
            # 미리보기용 출력 크기 설정 (캔버스에 맞춤)
            preview_height = 400
            preview_width = int(preview_height * aspect_ratio)
            
            # 크로퍼 설정 업데이트
            self.preview_cropper.default_output_width = preview_width
            self.preview_cropper.default_output_height = preview_height
            self.preview_cropper.aspect_ratio = aspect_ratio
            
            # 오프셋 값 가져오기
            offset_x = self.offset_x_var.get()
            offset_y = self.offset_y_var.get()
            
            # 크롭 실행
            result = self.preview_cropper.process_image_from_array(
                self.preview_original_image,
                zoom_factor=zoom,
                eye_position=eye_pos,
                offset_x=offset_x,
                offset_y=offset_y
            )
            
            if result is not None:
                cropped_image = result[0]  # (image, dpi, exif, icc) 중 image만
                
                # BGR -> RGB 변환
                cropped_rgb = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2RGB)
                
                # PIL Image로 변환
                pil_image = Image.fromarray(cropped_rgb)
                
                # 캔버스 크기에 맞게 리사이징
                canvas_width = self.preview_canvas.winfo_width()
                canvas_height = self.preview_canvas.winfo_height()
                
                if canvas_width < 10:  # 초기화 전이면 기본값 사용
                    canvas_width = 280
                    canvas_height = 430
                
                # 비율 유지하며 캔버스에 맞춤
                img_ratio = pil_image.width / pil_image.height
                canvas_ratio = canvas_width / canvas_height
                
                if img_ratio > canvas_ratio:
                    new_width = canvas_width - 10
                    new_height = int(new_width / img_ratio)
                else:
                    new_height = canvas_height - 10
                    new_width = int(new_height * img_ratio)
                
                pil_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # PhotoImage로 변환 (참조 유지 필수)
                self.preview_photo_image = ImageTk.PhotoImage(pil_image)
                
                # 캔버스에 표시
                self.preview_canvas.delete("all")
                x = canvas_width // 2
                y = canvas_height // 2
                self.preview_canvas.create_image(x, y, image=self.preview_photo_image, anchor='center')
            else:
                # 얼굴 감지 실패
                self.preview_canvas.delete("all")
                self.preview_canvas.create_text(
                    140, 215,
                    text="얼굴을 감지하지 못했습니다",
                    fill='#FF6B6B',
                    font=('SF Pro Display', 11)
                )
                
        except Exception as e:
            self._append_log(f"⚠️ 미리보기 오류: {e}")
    
    def _poll_log_queue(self):
        """로그 큐 폴링"""
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_text.insert(END, message + "\n")
                self.log_text.see(END)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._poll_log_queue)
    
    # ============================================================
    # 이미지 처리
    # ============================================================
    
    def _load_modules(self):
        """모듈 지연 로딩"""
        if self.cropper is None:
            self._append_log("🔄 AI 모델 로딩 중... (최초 1회)")
            self.root.update()
            
            # 지연 임포트
            from core.cropper import PhotoCardCropper
            from utils.file_handler import FileHandler, BatchProcessor
            
            self.PhotoCardCropper = PhotoCardCropper
            self.FileHandler = FileHandler
            self.BatchProcessor = BatchProcessor
            
            self._append_log("✅ 모델 로딩 완료")
    
    def _start_processing(self):
        """변환 시작"""
        # 유효성 검사
        if not self.input_dir:
            self._append_log("❌ 오류: 원본 폴더를 선택해주세요.")
            return
        
        if not self.output_dir:
            self._append_log("❌ 오류: 저장 폴더를 선택해주세요.")
            return
        
        if not Path(self.input_dir).exists():
            self._append_log("❌ 오류: 원본 폴더가 존재하지 않습니다.")
            return
        
        # 규격 유효성 검사
        try:
            width_mm = float(self.width_var.get())
            height_mm = float(self.height_var.get())
            if width_mm <= 0 or height_mm <= 0:
                raise ValueError()
        except ValueError:
            self._append_log("❌ 오류: 올바른 규격(가로/세로)을 입력해주세요.")
            return
        
        if self.is_processing:
            self._append_log("⚠️ 이미 처리 중입니다.")
            return
        
        # 모듈 로딩 (스레드 시작 전에 동기적으로 실행)
        self._load_modules()
        
        # 처리 시작
        self.is_processing = True
        self._set_ui_state(enabled=False)
        
        # 진행 상황 초기화
        self.progress_var.set(0)
        self.progress_label.configure(text="0 / 0 (0%)")
        self.status_label.configure(text="처리 중...")
        
        # 파라미터
        zoom_factor = self.zoom_var.get()
        eye_position = self.eye_var.get()
        offset_x = self.offset_x_var.get()
        offset_y = self.offset_y_var.get()
        
        offset_info = ""
        if offset_x != 0 or offset_y != 0:
            offset_info = f", 오프셋: ({int(offset_x*100):+d}%, {int(offset_y*100):+d}%)"
        
        self._append_log(f"🚀 변환 시작 - 규격: {width_mm}×{height_mm}mm, zoom: {zoom_factor:.2f}, eye: {eye_position:.2f}{offset_info}")
        
        # 이미지별 오프셋 복사 (스레드 안전)
        image_offsets_copy = dict(self.image_offsets)
        
        # 별도 스레드에서 처리
        self.processing_thread = threading.Thread(
            target=self._process_images,
            args=(zoom_factor, eye_position, width_mm, height_mm, offset_x, offset_y, image_offsets_copy),
            daemon=True
        )
        self.processing_thread.start()
    
    def _process_images(self, zoom_factor: float, eye_position: float, width_mm: float, height_mm: float, offset_x: float = 0.0, offset_y: float = 0.0, image_offsets: dict = None):
        """이미지 처리 (별도 스레드)"""
        if image_offsets is None:
            image_offsets = {}
        
        try:
            # 크로퍼 초기화 (사용자 정의 규격 + 원본 해상도/DPI 유지)
            cropper = self.PhotoCardCropper(
                zoom_factor=zoom_factor,
                eye_position=eye_position,
                width_mm=width_mm,
                height_mm=height_mm,
                padding_mode='white',
                fallback_on_no_face=True,
                preserve_resolution=True,  # 원본 해상도 유지
                offset_x=offset_x,
                offset_y=offset_y
            )
            
            # 파일 핸들러 초기화 (DPI 보존)
            file_handler = self.FileHandler(
                input_dir=self.input_dir,
                output_dir=self.output_dir,
                output_format='jpg',
                output_quality=100,  # 최고 품질
                preserve_structure=True,
                preserve_dpi=True  # DPI 보존
            )
            
            # 이미지 목록 조회
            images = file_handler.find_images(recursive=True)
            total = len(images)
            
            if total == 0:
                self.root.after(0, lambda: self._append_log("⚠️ 처리할 이미지가 없습니다."))
                self.root.after(0, self._processing_complete)
                return
            
            # 개별 오프셋이 설정된 이미지 수
            adjusted_count = sum(1 for img in images if str(img) in image_offsets and image_offsets[str(img)] != (0.0, 0.0))
            
            self.root.after(0, lambda: self._append_log(f"📷 총 {total}개 이미지 발견"))
            self.root.after(0, lambda w=width_mm, h=height_mm: self._append_log(f"📐 출력 규격: {w}×{h}mm (원본 DPI 유지)"))
            if adjusted_count > 0:
                self.root.after(0, lambda c=adjusted_count: self._append_log(f"📍 개별 위치 조정: {c}개 이미지"))
            
            # 처리 루프
            success_count = 0
            fail_count = 0
            
            for idx, image_path in enumerate(images, 1):
                try:
                    # 이미지별 오프셋 확인
                    img_path_str = str(image_path)
                    if img_path_str in image_offsets:
                        img_offset_x, img_offset_y = image_offsets[img_path_str]
                    else:
                        img_offset_x, img_offset_y = offset_x, offset_y
                    
                    # 이미지 처리 (메타데이터 포함, 개별 오프셋 적용)
                    result = cropper.process_image(
                        str(image_path),
                        offset_x=img_offset_x,
                        offset_y=img_offset_y
                    )
                    
                    if result is not None:
                        image_data, metadata = result
                        
                        # 메타데이터와 함께 저장
                        saved_path = file_handler.save_image(
                            image_data,
                            original_path=str(image_path),
                            metadata=metadata
                        )
                        
                        if saved_path:
                            success_count += 1
                            # DPI 정보 표시
                            dpi_info = f" (DPI: {metadata.get('dpi', (72,72))[0]})" if metadata else ""
                            log_msg = f"✅ {image_path.name}{dpi_info}"
                        else:
                            fail_count += 1
                            log_msg = f"❌ {image_path.name} - 저장 실패"
                    else:
                        fail_count += 1
                        log_msg = f"⚠️ {image_path.name} - 얼굴 미감지"
                    
                except Exception as e:
                    fail_count += 1
                    log_msg = f"❌ {image_path.name} - {str(e)}"
                
                # UI 업데이트 (메인 스레드에서)
                progress = (idx / total) * 100
                self.root.after(0, lambda p=progress, i=idx, t=total, m=log_msg: 
                               self._update_progress(p, i, t, m))
            
            # 완료 메시지
            self.root.after(0, lambda: self._append_log(
                f"\n🎉 변환 완료! 성공: {success_count}, 실패: {fail_count}"
            ))
            
        except Exception as e:
            self.root.after(0, lambda: self._append_log(f"❌ 오류 발생: {str(e)}"))
        
        finally:
            self.root.after(0, self._processing_complete)
    
    def _update_progress(self, progress: float, current: int, total: int, log_msg: str):
        """진행 상황 업데이트 (메인 스레드)"""
        self.progress_var.set(progress)
        percentage = int(progress)
        self.progress_label.configure(text=f"{current} / {total} ({percentage}%)")
        self._append_log(log_msg)
    
    def _processing_complete(self):
        """처리 완료"""
        self.is_processing = False
        self._set_ui_state(enabled=True)
        self.status_label.configure(text="완료!")
    
    def _set_ui_state(self, enabled: bool):
        """UI 상태 설정"""
        state = 'normal' if enabled else 'disabled'
        self.input_btn.configure(state=state)
        self.output_btn.configure(state=state)
        self.zoom_slider.configure(state=state)
        self.eye_slider.configure(state=state)
        self.offset_x_slider.configure(state=state)
        self.offset_y_slider.configure(state=state)
        self.start_btn.configure(state=state)
        
        if enabled:
            self.start_btn.configure(text="🚀 변환 시작")
        else:
            self.start_btn.configure(text="⏳ 처리 중...")


# ============================================================
# CLI 지원 (하위 호환성)
# ============================================================

def run_cli():
    """CLI 모드 실행"""
    import argparse
    
    from core.cropper import PhotoCardCropper
    from utils.file_handler import FileHandler, BatchProcessor
    
    parser = argparse.ArgumentParser(
        description='사진 자동 크롭 프로그램 - CLI 모드',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 포토카드 규격 (기본값 55x85mm)
  python main.py -i photo.jpg -o output.jpg
  
  # 여권사진 규격 (35x45mm)
  python main.py -d ./photos -o ./output --width 35 --height 45
  
  # 정사각형 (62x62mm)
  python main.py -d ./photos -o ./output --width 62 --height 62
"""
    )
    
    parser.add_argument('-i', '--input', type=str, help='단일 이미지 파일 경로')
    parser.add_argument('-d', '--directory', type=str, help='이미지 폴더 경로')
    parser.add_argument('-o', '--output', type=str, help='출력 경로')
    parser.add_argument('--width', '-W', type=float, default=55, help='출력 규격 가로 mm (기본값: 55)')
    parser.add_argument('--height', '-H', type=float, default=85, help='출력 규격 세로 mm (기본값: 85)')
    parser.add_argument('--zoom', '-z', type=float, default=2.8, help='Zoom factor (기본값: 2.8)')
    parser.add_argument('--eye-position', '-e', type=float, default=0.42, help='Eye position (기본값: 0.42)')
    parser.add_argument('--offset-x', type=float, default=0.0, help='좌우 오프셋 -0.3~0.3 (기본값: 0.0)')
    parser.add_argument('--offset-y', type=float, default=0.0, help='상하 오프셋 -0.3~0.3 (기본값: 0.0)')
    parser.add_argument('--format', '-f', type=str, choices=['jpg', 'png', 'webp', 'tiff'], default='jpg')
    parser.add_argument('--quality', '-q', type=int, default=100, help='출력 품질 (기본값: 100)')
    
    args = parser.parse_args()
    
    if not args.input and not args.directory:
        parser.print_help()
        return
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    
    print(f"📐 출력 규격: {args.width}×{args.height}mm")
    
    # 크로퍼 초기화 (사용자 정의 규격 + 원본 해상도/DPI 유지)
    cropper = PhotoCardCropper(
        zoom_factor=args.zoom,
        eye_position=args.eye_position,
        width_mm=args.width,
        height_mm=args.height,
        preserve_resolution=True,  # 원본 해상도 유지
        offset_x=args.offset_x,
        offset_y=args.offset_y
    )
    
    if args.input:
        # 단일 이미지 처리
        result = cropper.process_image(args.input)
        if result is not None:
            image_data, metadata = result
            
            # FileHandler로 DPI 보존하며 저장
            file_handler = FileHandler(
                output_format=args.format,
                output_quality=args.quality,
                preserve_dpi=True
            )
            output_path = args.output or f"{Path(args.input).stem}_cropped.{args.format}"
            saved = file_handler.save_image(image_data, output_path=output_path, metadata=metadata)
            if saved:
                print(f"저장 완료: {saved} (DPI: {metadata.get('dpi', (72,72))})")
    else:
        # 폴더 처리
        file_handler = FileHandler(
            input_dir=args.directory,
            output_dir=args.output or str(Path(args.directory) / 'cropped'),
            output_format=args.format,
            output_quality=args.quality,
            preserve_dpi=True  # DPI 보존
        )
        
        batch_processor = BatchProcessor(file_handler, cropper)
        stats = batch_processor.process_batch()
        
        print(f"\n완료! 성공: {stats['success']}, 실패: {stats['failed']}")


# ============================================================
# 메인 실행
# ============================================================

def main():
    """메인 함수"""
    # CLI 인자가 있으면 CLI 모드
    if len(sys.argv) > 1 and sys.argv[1] in ['-i', '-d', '--input', '--directory', '-h', '--help']:
        run_cli()
    else:
        # GUI 모드
        root = tk.Tk()
        app = PhotoCardCropperApp(root)
        root.mainloop()


if __name__ == '__main__':
    main()
