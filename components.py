from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

class ThumbnailCard(QFrame):
    clicked = Signal(list)

    def __init__(self, name, images, depth, parent=None):
        super().__init__(parent)
        self.images = images
        self.depth = depth
        self.is_enabled = True
        self.cached_pixmap = None
        self.loading_requested = False

        self.setFixedSize(215, 270)
        l = QVBoxLayout(self)
        self.img_label = QLabel("Wait...")
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setFixedHeight(180)
        self.img_label.setStyleSheet("background-color: #f9f9f9; border-radius: 4px;")
        
        self.name_label = QLabel(name)
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet("font-size: 12px; color: #333; font-weight: 500;")
        
        l.addWidget(self.img_label)
        l.addWidget(self.name_label)
        self.setCursor(Qt.PointingHandCursor)

    def update_appearance(self, limit):
        self.is_enabled = (self.depth < limit)
        if self.is_enabled:
            self.setStyleSheet("ThumbnailCard { background-color: white; border: 1px solid #ddd; border-radius: 8px; } ThumbnailCard:hover { border: 2px solid #0078d4; }")
            if self.cached_pixmap:
                self.img_label.setPixmap(self.cached_pixmap.scaled(self.img_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.img_label.setText("Too Deep")
            self.setStyleSheet("ThumbnailCard { background-color: #f5f5f5; border: 1px solid #eee; border-radius: 8px; }")

    def mouseReleaseEvent(self, event):
        if self.is_enabled and event.button() == Qt.LeftButton:
            self.clicked.emit(self.images)