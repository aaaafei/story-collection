# -*- coding: utf-8 -*-
"""将绘本源 PNG 转为 JPG，保存到绘本 assets 目录。"""
import os
from PIL import Image

SRC_DIR = r"C:\Users\Administrator\Doubao\chats\2026-09-09\new-chat\绘本素材"
DST_DIR = r"D:\workspace\story-collection\rose-princess-picturebook\assets"

os.makedirs(DST_DIR, exist_ok=True)

for i in range(1, 11):
    src = os.path.join(SRC_DIR, "page%d.png" % i)
    dst = os.path.join(DST_DIR, "page-%02d.jpg" % i)
    im = Image.open(src)
    im = im.convert("RGB")
    im.save(dst, "JPEG", quality=85, optimize=True)
    print(dst, os.path.getsize(dst))
