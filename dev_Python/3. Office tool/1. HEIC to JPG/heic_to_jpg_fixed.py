"""HEIC/HEIF 사진을 JPG/PNG/WEBP로 변환한다. 실행하면 폴더 선택 창이 열린다.

설치: pip install pillow pillow-heif
사용:
    python heic_to_jpg.py                       # 폴더 선택 창
    python heic_to_jpg.py 입력폴더 [출력폴더]    # 경로 직접 지정
    python heic_to_jpg.py -f png -q 90 --max-mb 0
"""
import argparse
import io
import math
import sys
from pathlib import Path

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

SCALE_STEP = 0.85
FORMATS = {"jpg": ("JPEG", ".jpg"), "png": ("PNG", ".png"), "webp": ("WEBP", ".webp")}
SOURCE_EXTS = (".heic", ".heif")


def encode(img, fmt, quality):
    buf = io.BytesIO()
    if fmt == "png":
        img.save(buf, "PNG", optimize=True)
    else:
        img.save(buf, FORMATS[fmt][0], quality=quality, optimize=True)
    return buf.getvalue()


def compress(img, fmt, quality, max_bytes):
    """max_bytes가 0이면 그대로 저장, 아니면 품질 -> 해상도 순으로 줄여 용량을 맞춘다."""
    if max_bytes < 0:
        raise ValueError("최대 용량은 0 이상이어야 합니다.")
    qualities = [q for q in range(quality, 40, -10)] or [quality]
    while True:
        for q in qualities:
            data = encode(img, fmt, q)
            if not max_bytes or len(data) <= max_bytes:
                return data
            if fmt == "png":  # PNG는 품질 옵션이 없으므로 바로 축소
                break
        w, h = img.size
        if w == 1 and h == 1:
            raise ValueError("최소 이미지 크기에서도 용량 제한을 만족할 수 없습니다. 최대 용량을 늘리세요.")
        img = img.resize((max(1, int(w * SCALE_STEP)), max(1, int(h * SCALE_STEP))), Image.Resampling.LANCZOS)


def pick_folder():
    """폴더 선택 창을 띄운다. 취소하면 None."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    folder = filedialog.askdirectory(title="HEIC 이미지가 들어 있는 폴더를 선택하세요")
    root.destroy()
    return Path(folder) if folder else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", nargs="?", help="입력 폴더 (생략하면 선택 창)")
    ap.add_argument("dst", nargs="?", help="출력 폴더 (기본: 입력폴더/converted)")
    ap.add_argument("-f", "--format", choices=FORMATS, default="jpg", help="출력 형식 (기본 jpg)")
    ap.add_argument("-q", "--quality", type=int, default=85, help="품질 1~100 (기본 85)")
    ap.add_argument("--max-mb", type=float, default=1.0, help="파일당 최대 MB, 0이면 제한 없음 (기본 1)")
    args = ap.parse_args()
    if not math.isfinite(args.max_mb) or args.max_mb < 0:
        ap.error("--max-mb는 0 이상의 유한한 숫자여야 합니다.")
    if 0 < args.max_mb < 0.000001:
        ap.error("--max-mb는 0 또는 0.000001 MB(1바이트) 이상이어야 합니다.")

    src = Path(args.src).expanduser() if args.src else pick_folder()
    if src is None:
        sys.exit("폴더를 선택하지 않아 종료합니다.")
    if not src.is_dir():
        ap.error(f"입력 폴더가 존재하지 않거나 폴더가 아닙니다: {src}")
    dst = Path(args.dst).expanduser() if args.dst else src / "converted"

    quality = max(1, min(100, args.quality))
    max_bytes = int(args.max_mb * 1_000_000)
    ext = FORMATS[args.format][1]

    files = sorted(p for p in src.iterdir() if p.is_file() and p.suffix.lower() in SOURCE_EXTS)
    if not files:
        sys.exit(f"HEIC/HEIF 파일이 없습니다: {src}")
    dst.mkdir(parents=True, exist_ok=True)

    failed = 0
    for p in files:
        try:
            with Image.open(p) as im:
                img = ImageOps.exif_transpose(im)  # 회전 반영
                img = img.convert("RGB" if args.format == "jpg" else "RGBA")
            data = compress(img, args.format, quality, max_bytes)
            out = dst / (p.stem + ext)
            suffix = 1
            while out.exists():
                out = dst / f"{p.stem} ({suffix}){ext}"
                suffix += 1
            out.write_bytes(data)
            print(f"{p.name} -> {out.name} ({len(data) / 1024:.0f} KB)")
        except Exception as e:
            failed += 1
            print(f"실패: {p.name}: {e}", file=sys.stderr)
    print(f"완료: 성공 {len(files) - failed}개, 실패 {failed}개 -> {dst}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
