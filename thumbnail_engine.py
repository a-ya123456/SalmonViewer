import cv2
import numpy as np
import fitz
import zipfile
import io
from pathlib import Path
from PIL import Image
from PySide6.QtGui import QImage
from PySide6.QtCore import QObject, QThread, Signal
from shiboken6 import isValid

Image.MAX_IMAGE_PIXELS = None

class ThumbnailWorker(QObject):
    finished = Signal(QImage, object)

    def process(self, image_path, card_obj):
        try:
            qimg = None
            
            if '#' in image_path:
                parts = image_path.split('#', 1)
                zip_path = parts[0]
                img_path = parts[1]
                try:
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        img_data = zf.read(img_path)
                        img_array = np.frombuffer(img_data, np.uint8)
                        img = cv2.imdecode(img_array, cv2.IMREAD_UNCHANGED)
                        if img is not None:
                            h, w = img.shape[:2]
                            ratio = 210 / max(h, w)
                            resized = cv2.resize(img, (int(w * ratio), int(h * ratio)), interpolation=cv2.INTER_AREA)
                            
                            if len(resized.shape) == 2:
                                resized = cv2.cvtColor(resized, cv2.COLOR_GRAY_RGBA)
                            elif resized.shape[2] == 3:
                                resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGBA)
                            elif resized.shape[2] == 4:
                                resized = cv2.cvtColor(resized, cv2.COLOR_BGRA2RGBA)
                            
                            h, w, ch = resized.shape
                            qimg = QImage(resized.data, w, h, ch * w, QImage.Format_RGBA8888).copy()
                except:
                    pass
            
            if qimg is None:
                path_obj = Path(image_path)
                ext = path_obj.suffix.lower()
                
                if ext == ".pdf":
                    doc = fitz.open(image_path)
                    page = doc[0]
                    pix = page.get_pixmap(matrix=fitz.Matrix(0.6, 0.6))
                    qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
                    doc.close()
                else:
                    try:
                        img_array = np.fromfile(image_path, np.uint8)
                        img = cv2.imdecode(img_array, cv2.IMREAD_UNCHANGED)
                        if img is not None:
                            h, w = img.shape[:2]
                            ratio = 210 / max(h, w)
                            resized = cv2.resize(img, (int(w * ratio), int(h * ratio)), interpolation=cv2.INTER_AREA)
                            
                            if len(resized.shape) == 2:
                                resized = cv2.cvtColor(resized, cv2.COLOR_GRAY_RGBA)
                            elif resized.shape[2] == 3:
                                resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGBA)
                            elif resized.shape[2] == 4:
                                resized = cv2.cvtColor(resized, cv2.COLOR_BGRA2RGBA)
                            
                            h, w, ch = resized.shape
                            qimg = QImage(resized.data, w, h, ch * w, QImage.Format_RGBA8888).copy()
                    except:
                        qimg = None

                    if qimg is None:
                        with Image.open(image_path) as pil_img:
                            pil_img.thumbnail((210, 210))
                            pil_img = pil_img.convert("RGBA")
                            qimg = QImage(pil_img.tobytes("raw", "RGBA"), pil_img.size[0], pil_img.size[1], QImage.Format_RGBA8888).copy()

            if qimg and isValid(card_obj):
                self.finished.emit(qimg, card_obj)
        except:
            pass

class LoaderThread(QThread):
    def __init__(self):
        super().__init__()
        self.worker = ThumbnailWorker()
        self.queue = []
        self.is_running = True

    def add_job(self, path, card):
        self.queue.append((path, card))

    def clear_jobs(self):
        self.queue = []

    def run(self):
        while self.is_running:
            if self.queue:
                path, card = self.queue.pop(0)
                self.worker.process(path, card)
            else:
                self.msleep(5)