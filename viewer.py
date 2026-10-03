import cv2
import numpy as np
import fitz
import zipfile
import io
from pathlib import Path
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QPushButton
from PySide6.QtGui import QPixmap, QImage, QWheelEvent
from PySide6.QtCore import Qt, QTimer

class DetailViewer(QMainWindow):
    last_geometry = None

    def __init__(self, image_paths, parent=None):
        super().__init__(parent)
        self.setWindowTitle("詳細ビューアー")
        self.image_paths = image_paths
        self.current_index = 0
        self.current_pdf_doc = None
        self.pdf_page_index = 0
        self.zip_cache = {}

        self.is_zoomed = False
        self.zoom_factor = 1.0
        self.drag_start_pos = None
        self.full_pixmap = None

        if DetailViewer.last_geometry:
            self.restoreGeometry(DetailViewer.last_geometry)
        else:
            self.resize(1200, 900)

        self.setStyleSheet("QMainWindow { background-color: white; }")

        cw = QWidget()
        self.setCentralWidget(cw)
        self.main_layout = QVBoxLayout(cw)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setStyleSheet("background-color: white; border: none;")
        
        # 矢印キーのスクロール機能を排除
        self.scroll_area.keyPressEvent = lambda e: e.ignore()
        self.scroll_area.horizontalScrollBar().setFocusPolicy(Qt.NoFocus)
        self.scroll_area.verticalScrollBar().setFocusPolicy(Qt.NoFocus)

        self.image_label = QLabel("読み込み中...")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.scroll_area.setWidget(self.image_label)
        self.main_layout.addWidget(self.scroll_area)

        nav_container = QWidget()
        nav_layout = QHBoxLayout(nav_container)
        self.btn_prev = QPushButton("◀ 前へ")
        self.btn_next = QPushButton("次へ ▶")
        self.info = QLabel("")
        
        self.btn_prev.setFocusPolicy(Qt.NoFocus)
        self.btn_next.setFocusPolicy(Qt.NoFocus)
        
        btn_style = "QPushButton { background: white; color: #333; border: 1px solid #ccc; border-radius: 4px; padding: 6px 25px; }"
        self.btn_prev.setStyleSheet(btn_style); self.btn_next.setStyleSheet(btn_style)
        self.btn_prev.clicked.connect(self.prev_item); self.btn_next.clicked.connect(self.next_item)

        nav_layout.addStretch(1); nav_layout.addWidget(self.btn_prev); nav_layout.addWidget(self.info); nav_layout.addWidget(self.btn_next); nav_layout.addStretch(1)
        self.main_layout.addWidget(nav_container)

        self.image_label.mousePressEvent = self.image_mouse_press
        self.image_label.mouseMoveEvent = self.image_mouse_move
        self.image_label.mouseReleaseEvent = self.image_mouse_release
        self.scroll_area.wheelEvent = self.handle_wheel

        self.load_current_resource()

    def load_current_resource(self):
        if not self.image_paths: return
        path = self.image_paths[self.current_index]
        path_obj = Path(path)
        ext = path_obj.suffix.lower()

        if self.current_pdf_doc:
            self.current_pdf_doc.close()
            self.current_pdf_doc = None

        if ext == ".pdf":
            try:
                self.current_pdf_doc = fitz.open(path)
                self.update_pdf_display()
            except: self.image_label.setText("PDF読み込み失敗")
        else:
            img_loaded = False
            
            if '#' in path:
                parts = path.split('#', 1)
                zip_path = parts[0]
                img_path = parts[1]
                try:
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        img_data = zf.read(img_path)
                        img_array = np.frombuffer(img_data, np.uint8)
                        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                        if img is not None:
                            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                            h, w, ch = img.shape
                            qimg = QImage(img.data, w, h, ch * w, QImage.Format_RGB888).copy()
                            self.full_pixmap = QPixmap.fromImage(qimg)
                            self.update_display()
                            self.info.setText(f"{self.current_index + 1} / {len(self.image_paths)}")
                            img_loaded = True
                except:
                    pass
            
            if not img_loaded:
                try:
                    img_array = np.fromfile(path, np.uint8)
                    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                    if img is not None:
                        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        h, w, ch = img.shape
                        qimg = QImage(img.data, w, h, ch * w, QImage.Format_RGB888).copy()
                        self.full_pixmap = QPixmap.fromImage(qimg)
                        self.update_display()
                        self.info.setText(f"{self.current_index + 1} / {len(self.image_paths)}")
                        img_loaded = True
                except: pass
            
            if not img_loaded:
                self.image_label.setText("画像読み込み失敗")
        
        self.setFocus()

    def update_pdf_display(self):
        if not self.current_pdf_doc: return
        page = self.current_pdf_doc[self.pdf_page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(3.0, 3.0)) # 解像度3.0
        qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
        self.full_pixmap = QPixmap.fromImage(qimg)
        self.update_display()
        self.info.setText(f"PDF {self.pdf_page_index + 1}/{len(self.current_pdf_doc)} | {self.current_index + 1}/{len(self.image_paths)}")

    def update_display(self):
        if self.full_pixmap is None: return
        if not self.is_zoomed:
            pix = self.full_pixmap.scaled(self.scroll_area.viewport().size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(pix)
            self.image_label.setCursor(Qt.PointingHandCursor)
        else:
            w, h = int(self.full_pixmap.width() * self.zoom_factor), int(self.full_pixmap.height() * self.zoom_factor)
            self.image_label.setPixmap(self.full_pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.image_label.setCursor(Qt.OpenHandCursor)

    def handle_wheel(self, event: QWheelEvent):
        if not self.is_zoomed: return
        old_factor = self.zoom_factor
        if event.angleDelta().y() > 0: self.zoom_factor *= 1.15
        else: self.zoom_factor /= 1.15
        self.zoom_factor = max(0.1, min(self.zoom_factor, 10.0))
        self._adjust_scrollbars(event.position(), self.zoom_factor / old_factor)
        self.update_display()
        self.setFocus()

    def image_mouse_press(self, event):
        if event.button() == Qt.LeftButton:
            if not self.is_zoomed:
                view_size = self.image_label.size()
                click_pos = event.position()
                fit_factor = min(self.scroll_area.viewport().width() / self.full_pixmap.width(), self.scroll_area.viewport().height() / self.full_pixmap.height())
                self.zoom_factor = fit_factor * 1.8 
                self.is_zoomed = True
                self.update_display()
                rel_x = click_pos.x() / view_size.width()
                rel_y = click_pos.y() / view_size.height()
                QTimer.singleShot(1, lambda: self._center_on_rel_pos(rel_x, rel_y))
            else:
                self.is_zoomed = False
                self.update_display()
            self.setFocus()
        elif event.button() == Qt.RightButton and self.is_zoomed:
            self.drag_start_pos = event.globalPosition().toPoint()
            self.image_label.setCursor(Qt.ClosedHandCursor)

    def _center_on_rel_pos(self, rel_x, rel_y):
        h_bar = self.scroll_area.horizontalScrollBar()
        v_bar = self.scroll_area.verticalScrollBar()
        new_x = (self.image_label.width() * rel_x) - (self.scroll_area.viewport().width() / 2)
        new_y = (self.image_label.height() * rel_y) - (self.scroll_area.viewport().height() / 2)
        h_bar.setValue(int(new_x)); v_bar.setValue(int(new_y))

    def _adjust_scrollbars(self, pos, relative_factor):
        h_bar = self.scroll_area.horizontalScrollBar(); v_bar = self.scroll_area.verticalScrollBar()
        h_bar.setValue(int((h_bar.value() + pos.x()) * relative_factor - pos.x()))
        v_bar.setValue(int((v_bar.value() + pos.y()) * relative_factor - pos.y()))

    def image_mouse_move(self, event):
        if self.is_zoomed and self.drag_start_pos:
            curr = event.globalPosition().toPoint()
            delta = curr - self.drag_start_pos
            self.scroll_area.horizontalScrollBar().setValue(self.scroll_area.horizontalScrollBar().value() - delta.x())
            self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().value() - delta.y())
            self.drag_start_pos = curr

    def image_mouse_release(self, event):
        if event.button() == Qt.RightButton:
            self.drag_start_pos = None
            if self.is_zoomed: self.image_label.setCursor(Qt.OpenHandCursor)

    def prev_item(self):
        if self.current_pdf_doc and self.pdf_page_index > 0:
            self.pdf_page_index -= 1; self.is_zoomed = False; self.update_pdf_display()
        elif self.current_index > 0:
            self.current_index -= 1; self.pdf_page_index = 0; self.is_zoomed = False; self.load_current_resource()

    def next_item(self):
        if self.current_pdf_doc and self.pdf_page_index < len(self.current_pdf_doc) - 1:
            self.pdf_page_index += 1; self.is_zoomed = False; self.update_pdf_display()
        elif self.current_index < len(self.image_paths) - 1:
            self.current_index += 1; self.pdf_page_index = 0; self.is_zoomed = False; self.load_current_resource()

    def keyPressEvent(self, e):
        # 矢印キー（左）または Aキー
        if e.key() == Qt.Key_Left or e.key() == Qt.Key_A:
            self.prev_item()
        
        # 矢印キー（右）または Dキー
        elif e.key() == Qt.Key_Right or e.key() == Qt.Key_D:
            self.next_item()
            
        # ESCキーで閉じる
        elif e.key() == Qt.Key_Escape:
            self.close()
        
        # その他のキー（もしあれば）は標準の処理へ渡す
        else:
            super().keyPressEvent(e)

    def resizeEvent(self, event):
        DetailViewer.last_geometry = self.saveGeometry()
        QTimer.singleShot(50, self.update_display)
        super().resizeEvent(event)

    def closeEvent(self, event):
        if self.current_pdf_doc: self.current_pdf_doc.close()
        super().closeEvent(event)