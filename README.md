# 鮭Viewer

フォルダまたは ZIP 内の画像・PDF を一覧表示し、カードクリックで詳細ビューアーを開くアプリです。

## 必要環境

- Python 3.10 以上
- Windows 推奨（PySide6 GUI を利用）

## セットアップ

```bash
python -m pip install -r requirements.txt
```

## 実行

```bash
python main.py
```

- 「フォルダを開く」または「ZIPを開く」で対象を選択
- 一覧カードをクリックすると詳細表示へ遷移
- PDF も表示対象として扱います

## 依存ライブラリ

- PySide6
- OpenCV
- NumPy
- PyMuPDF
- Pillow
- natsort
