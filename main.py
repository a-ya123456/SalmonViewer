import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from natsort import natsorted
from shiboken6 import isValid

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

# 分割したファイルのインポート
from thumbnail_engine import LoaderThread
from viewer import DetailViewer
from components import ThumbnailCard

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("画像フォルダ ビューアー")
        self.resize(1240, 800)
        self.setStyleSheet("QMainWindow { background-color: white; }")
        self.viewer = None
        self.cards = []
        self.temp_dirs = []
        self.zip_to_dir = {}

        self.toolbar = QToolBar(); self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        btn_style = "QPushButton { padding: 6px 12px; border: 1px solid #ccc; border-radius: 4px; background-color: white; }"
        self.btn_open = QPushButton(" 📁 フォルダを開く "); self.btn_open.setStyleSheet(btn_style); self.btn_open.clicked.connect(self.select_folder); self.toolbar.addWidget(self.btn_open)
        
        self.btn_open_zip = QPushButton(" 📦 ZIPを開く "); self.btn_open_zip.setStyleSheet(btn_style); self.btn_open_zip.clicked.connect(self.select_zip); self.toolbar.addWidget(self.btn_open_zip)
        
        self.btn_depth = QPushButton(" 表示階層 ▿ "); self.btn_depth.setStyleSheet(btn_style)
        self.depth_menu = QMenu(self); self.depth_group = QActionGroup(self)
        for i in range(1, 6):
            a = QAction(f"{i} 階層まで表示", self, checkable=True); a.setData(i); a.triggered.connect(self.apply_settings); self.depth_menu.addAction(a); self.depth_group.addAction(a)
            if i == 3: a.setChecked(True)
        self.btn_depth.setMenu(self.depth_menu); self.toolbar.addWidget(self.btn_depth)

        self.hide_toggle = QPushButton(" 階層外を隠す: OFF "); self.hide_toggle.setCheckable(True); self.hide_toggle.setStyleSheet(btn_style); self.hide_toggle.toggled.connect(self.on_toggle_changed); self.toolbar.addWidget(self.hide_toggle)

        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.setCentralWidget(self.scroll)
        self.container = QWidget(); self.scroll.setWidget(self.container)
        self.main_vbox = QVBoxLayout(self.container)
        self.grid = QGridLayout(); self.grid.setSpacing(15); self.main_vbox.addLayout(self.grid)

        self.init_msg_widget = QWidget()
        msg_layout = QVBoxLayout(self.init_msg_widget)
        self.msg_icon = QLabel("📁")
        self.msg_icon.setStyleSheet("font-size: 64px; margin-bottom: 10px;")
        self.msg_label = QLabel("フォルダを選択してください")
        self.msg_label.setStyleSheet("color: #555; font-size: 22px; font-weight: bold;")
        self.sub_msg = QLabel("上のボタンからフォルダまたはZIPファイルを選択すると一覧が表示されます\nサブフォルダ内の画像・PDFも階層ごとに整理されます")
        self.sub_msg.setStyleSheet("color: #999; font-size: 13px;")
        
        for w in [self.msg_icon, self.msg_label, self.sub_msg]:
            w.setAlignment(Qt.AlignCenter)
            msg_layout.addWidget(w)
        
        msg_layout.insertStretch(0, 1)
        msg_layout.addStretch(1)
        
        # メインレイアウトに追加（gridと同じ階層に置く）
        self.main_vbox.addWidget(self.init_msg_widget)

        self.loader = LoaderThread(); self.loader.worker.finished.connect(self.on_thumb_done); self.loader.start()
        self.resize_timer = QTimer(); self.resize_timer.setSingleShot(True); self.resize_timer.timeout.connect(self.rearrange_grid)

    def select_folder(self):
        path = QFileDialog.getExistingDirectory(self, "フォルダを選択")
        if path: 
            self.load_folders(path)

    def on_toggle_changed(self, checked):
        self.hide_toggle.setText(f" 階層外を隠す: {'ON' if checked else 'OFF'} ")
        self.apply_settings()

    def select_zip(self):
        path, _ = QFileDialog.getOpenFileName(self, "ZIPファイルを選択", "", "ZIP Files (*.zip)")
        if path:
            self.load_zip(path)

    def load_zip(self, zip_path):
        try:
            temp_dir = tempfile.mkdtemp()
            self.temp_dirs.append(temp_dir)
            
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(temp_dir)
            
            self.load_folders(temp_dir)
        except Exception as e:
            self.init_msg_widget.show()
            self.msg_icon.setText("❌")
            self.msg_label.setText("ZIP読み込み失敗")
            self.sub_msg.setText(f"エラー: {str(e)}")

    def load_folders(self, root_path):
        root = Path(root_path)
        self.container.setUpdatesEnabled(False)
        self.loader.clear_jobs()
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.cards.clear()
        
        valid_img_ext = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        
        def scan(current_dir, depth):
            if depth > 10: return
            try:
                files = list(current_dir.iterdir())
                
                imgs = natsorted([str(f) for f in files if f.suffix.lower() in valid_img_ext])
                if imgs:
                    rel = current_dir.relative_to(root)
                    card = ThumbnailCard(f"📁 {rel if rel != Path('.') else current_dir.name}", imgs, depth, self.container)
                    card.clicked.connect(self.open_viewer)
                    self.cards.append(card)
                
                zips = natsorted([f for f in files if f.suffix.lower() == ".zip"])
                for z in zips:
                    try:
                        with zipfile.ZipFile(str(z), 'r') as zf:
                            zip_imgs = []
                            for file_info in zf.filelist:
                                if Path(file_info.filename).suffix.lower() in valid_img_ext:
                                    zip_imgs.append(file_info.filename)
                            zip_imgs = natsorted(zip_imgs)
                            
                            if zip_imgs:
                                first_img = zip_imgs[0]
                                zf.extract(first_img, tempfile.gettempdir())
                                
                                zip_path = str(z).replace('\\', '/')
                                extracted_imgs = [f"{zip_path}#{img}" for img in zip_imgs]
                                card = ThumbnailCard(f"📦 {z.name}", extracted_imgs, depth, self.container)
                                card.clicked.connect(self.open_viewer)
                                self.cards.append(card)
                    except:
                        pass
                
                pdfs = natsorted([f for f in files if f.suffix.lower() == ".pdf"])
                for p in pdfs:
                    card = ThumbnailCard(f"📄 {p.name}", [str(p)], depth, self.container)
                    card.clicked.connect(self.open_viewer)
                    self.cards.append(card)

                for d in natsorted([x for x in files if x.is_dir()]): 
                    scan(d, depth + 1)
            except: 
                pass
        
        scan(root, 0)
        self.apply_settings()
        self.container.setUpdatesEnabled(True)

    def apply_settings(self):
        limit = self.depth_group.checkedAction().data()
        hide = self.hide_toggle.isChecked()
        
        has_any_cards = len(self.cards) > 0
        has_visible_cards = False

        for c in self.cards:
            c.update_appearance(limit)
            is_vis = c.is_enabled if hide else True
            c.setVisible(is_vis)
            if is_vis:
                has_visible_cards = True
            
            if c.is_enabled and not c.cached_pixmap and not c.loading_requested:
                c.loading_requested = True
                self.loader.add_job(c.images[0], c)
        
        # --- メッセージの出し分けロジック ---
        if not has_any_cards:
            # フォルダを読み込んだけれど、そもそも画像もPDFも一つもなかった場合
            self.init_msg_widget.show()
            self.msg_icon.setText("🔍")
            self.msg_label.setText("ファイルが見つかりませんでした")
            self.sub_msg.setText("選択したフォルダ内（サブフォルダ含む）に\n対応する画像やPDFが存在しません。")
        elif not has_visible_cards:
            # ファイルはあるけれど、設定（表示階層制限など）で全て隠れている場合
            self.init_msg_widget.show()
            self.msg_icon.setText("🚫")
            self.msg_label.setText("表示対象がありません")
            self.sub_msg.setText(f"現在の設定（{limit}階層まで）では表示できるフォルダがありません。\n「表示階層」を増やすか、「階層外を隠す」をOFFにしてください。")
        else:
            # カードがある場合はメッセージを隠す
            self.init_msg_widget.hide()
        
        self.rearrange_grid()

    def rearrange_grid(self):
        # 一旦すべての伸縮設定をリセット
        for i in range(self.grid.columnCount()):
            self.grid.setColumnStretch(i, 0)
        for i in range(self.grid.rowCount()):
            self.grid.setRowStretch(i, 0)

        visible = [c for c in self.cards if c.isVisible()]
        
        # カードがない（メッセージ表示中）なら、Stretchを設定せずに終了
        if not visible:
            return

        cols = max(1, (self.scroll.viewport().width() - 30) // 230) 
        
        for i, c in enumerate(visible):
            row = i // cols
            col = i % cols
            self.grid.addWidget(c, row, col)

        # カードがある時だけ、右側と下側に「重り」を置く
        self.grid.setColumnStretch(cols, 1)
        self.grid.setRowStretch((len(visible) // cols) + 1, 1)

    def on_thumb_done(self, q, c):
        if isValid(c):
            c.cached_pixmap = QPixmap.fromImage(q)
            if c.is_enabled: c.img_label.setPixmap(c.cached_pixmap.scaled(c.img_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def open_viewer(self, imgs):
        if self.viewer: self.viewer.close()
        self.viewer = DetailViewer(imgs); self.viewer.show()

    def resizeEvent(self, e): 
        self.resize_timer.start(50)
        super().resizeEvent(e)
    
    def closeEvent(self, e): 
        self.loader.is_running = False
        self.loader.quit()
        self.loader.wait()
        for temp_dir in self.temp_dirs:
            if Path(temp_dir).exists():
                shutil.rmtree(temp_dir)
        super().closeEvent(e)

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())