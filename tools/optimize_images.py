# -*- coding: utf-8 -*-
"""
将绘本图片生成为适合手机/网页阅读的尺寸（本地处理，不依赖豆包等第三方压缩）。

默认约定：
  - 源图：<册>/assets/src/page-XX.jpg（若无 src，会先从 assets/ 备份）
  - 网页内页：<册>/assets/page-XX.jpg（默认最长边 1400px）
  - 列表封面：<册>/assets/cover.jpg（默认最长边 800px，通常来自 page-01）

用法见 tools/README.md
"""
from __future__ import print_function

import argparse
import os
import shutil
import sys

try:
    from PIL import Image
except ImportError:
    print("缺少 Pillow，请先执行: pip install pillow", file=sys.stderr)
    sys.exit(1)

# 默认参数（网页用；打印请保留 assets/src 或外部高清原图）
DEFAULT_PAGE_MAX = 1400
DEFAULT_COVER_MAX = 800
DEFAULT_QUALITY = 82
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def list_book_dirs(root):
    books = []
    for base in (
        os.path.join(root, "series"),
        os.path.join(root, "oneshots"),
    ):
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            # 跳过 src 目录本身被当成册
            if os.path.basename(dirpath) == "assets" and any(
                f.lower().endswith(IMAGE_EXTS) or f.lower().endswith(".jpg")
                for f in filenames
            ):
                book = os.path.dirname(dirpath)
                books.append(book)
            # 也接受仅有 src 的
            if os.path.basename(dirpath) == "src" and os.path.basename(os.path.dirname(dirpath)) == "assets":
                book = os.path.dirname(os.path.dirname(dirpath))
                if book not in books:
                    books.append(book)
    # 去重并排序
    return sorted(set(books))


def ensure_src_backup(assets_dir, dry_run=False):
    """若 assets/src 不存在，把当前 assets 下的图片复制进去作为源图备份。"""
    src_dir = os.path.join(assets_dir, "src")
    web_files = [
        f for f in os.listdir(assets_dir)
        if os.path.isfile(os.path.join(assets_dir, f))
        and f.lower().endswith(IMAGE_EXTS)
        and f.lower() != "cover.jpg"
    ]
    if not web_files:
        return src_dir, False

    existing_src = []
    if os.path.isdir(src_dir):
        existing_src = [
            f for f in os.listdir(src_dir)
            if os.path.isfile(os.path.join(src_dir, f)) and f.lower().endswith(IMAGE_EXTS)
        ]

    if existing_src:
        return src_dir, False

    if dry_run:
        print("  [dry-run] 将备份 %d 张图到 assets/src/" % len(web_files))
        return src_dir, True

    os.makedirs(src_dir, exist_ok=True)
    for name in web_files:
        shutil.copy2(os.path.join(assets_dir, name), os.path.join(src_dir, name))
        print("  备份源图 -> src/%s" % name)
    return src_dir, True


def collect_sources(assets_dir):
    src_dir = os.path.join(assets_dir, "src")
    if os.path.isdir(src_dir):
        names = [
            f for f in os.listdir(src_dir)
            if os.path.isfile(os.path.join(src_dir, f)) and f.lower().endswith(IMAGE_EXTS)
        ]
        if names:
            return src_dir, sorted(names)

    names = [
        f for f in os.listdir(assets_dir)
        if os.path.isfile(os.path.join(assets_dir, f))
        and f.lower().endswith(IMAGE_EXTS)
        and f.lower() != "cover.jpg"
    ]
    return assets_dir, sorted(names)


def resize_image(im, max_side):
    im = im.convert("RGB")
    w, h = im.size
    longest = max(w, h)
    if longest <= max_side:
        return im
    scale = float(max_side) / float(longest)
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    return im.resize((nw, nh), getattr(Image, "Resampling", Image).LANCZOS)


def save_jpeg(im, path, quality, dry_run=False):
    if dry_run:
        print("  [dry-run] 写入 %s (%dx%d)" % (path, im.size[0], im.size[1]))
        return 0
    im.save(path, "JPEG", quality=quality, optimize=True, progressive=True)
    return os.path.getsize(path)


def optimize_book(book_dir, page_max, cover_max, quality, make_cover=True, dry_run=False):
    assets_dir = os.path.join(book_dir, "assets")
    if not os.path.isdir(assets_dir):
        print("跳过（无 assets/）: %s" % book_dir)
        return

    rel = os.path.relpath(book_dir, repo_root())
    print("\n==> %s" % rel)

    ensure_src_backup(assets_dir, dry_run=dry_run)
    source_dir, names = collect_sources(assets_dir)
    if not names:
        print("  无图片可处理")
        return

    # 只用 page-* 作为内页；其它零散图也处理但 cover 优先 page-01
    page_names = [n for n in names if n.lower().startswith("page-")]
    if not page_names:
        page_names = list(names)

    total_in = 0
    total_out = 0
    for name in page_names:
        src_path = os.path.join(source_dir, name)
        # 输出统一为 .jpg
        base, _ = os.path.splitext(name)
        out_name = base + ".jpg"
        out_path = os.path.join(assets_dir, out_name)

        with Image.open(src_path) as im:
            total_in += os.path.getsize(src_path)
            out_im = resize_image(im, page_max)
            size = save_jpeg(out_im, out_path, quality, dry_run=dry_run)
            total_out += size
            if not dry_run:
                print("  内页 %s -> %s (%dx%d, %.0f KB)" % (
                    name, out_name, out_im.size[0], out_im.size[1], size / 1024.0
                ))

    if make_cover:
        cover_src_name = None
        for candidate in ("page-01.jpg", "page-01.jpeg", "page-01.png", "page-1.jpg"):
            if candidate in names or candidate.lower() in [n.lower() for n in names]:
                # 大小写匹配
                for n in names:
                    if n.lower() == candidate.lower():
                        cover_src_name = n
                        break
            if cover_src_name:
                break
        if not cover_src_name and page_names:
            cover_src_name = page_names[0]

        if cover_src_name:
            cover_path = os.path.join(assets_dir, "cover.jpg")
            with Image.open(os.path.join(source_dir, cover_src_name)) as im:
                out_im = resize_image(im, cover_max)
                size = save_jpeg(out_im, cover_path, quality, dry_run=dry_run)
                if not dry_run:
                    print("  封面 cover.jpg (%dx%d, %.0f KB)" % (
                        out_im.size[0], out_im.size[1], size / 1024.0
                    ))

    if not dry_run and total_in and total_out:
        print("  合计源图约 %.1f MB -> 网页内页约 %.1f MB" % (
            total_in / 1024.0 / 1024.0, total_out / 1024.0 / 1024.0
        ))


def resolve_targets(root, paths, all_books):
    if all_books:
        return list_book_dirs(root)
    if not paths:
        print("请指定绘本目录，或使用 --all", file=sys.stderr)
        sys.exit(2)
    targets = []
    for p in paths:
        abs_p = os.path.abspath(p)
        if os.path.basename(abs_p) == "assets":
            abs_p = os.path.dirname(abs_p)
        if not os.path.isdir(abs_p):
            print("目录不存在: %s" % p, file=sys.stderr)
            sys.exit(2)
        targets.append(abs_p)
    return targets


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="本地优化绘本图片，生成适合手机浏览的 JPEG（不依赖第三方在线工具）。"
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="绘本目录（含 assets/），例如 series/rose-princess/ep01-seed-flower",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="处理仓库内 series/ 与 oneshots/ 下全部绘本",
    )
    parser.add_argument(
        "--page-max",
        type=int,
        default=DEFAULT_PAGE_MAX,
        help="内页最长边像素（默认 %d）" % DEFAULT_PAGE_MAX,
    )
    parser.add_argument(
        "--cover-max",
        type=int,
        default=DEFAULT_COVER_MAX,
        help="封面 cover.jpg 最长边像素（默认 %d）" % DEFAULT_COVER_MAX,
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=DEFAULT_QUALITY,
        help="JPEG quality 1-95（默认 %d）" % DEFAULT_QUALITY,
    )
    parser.add_argument(
        "--no-cover",
        action="store_true",
        help="不生成 cover.jpg",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印将要执行的操作，不写文件",
    )
    args = parser.parse_args(argv)

    root = repo_root()
    targets = resolve_targets(root, args.paths, args.all)
    if not targets:
        print("未找到可处理的绘本目录", file=sys.stderr)
        sys.exit(1)

    print("仓库: %s" % root)
    print("将处理 %d 个绘本目录 | 内页最长边=%d | 封面最长边=%d | quality=%d" % (
        len(targets), args.page_max, args.cover_max, args.quality
    ))

    for book in targets:
        optimize_book(
            book,
            page_max=args.page_max,
            cover_max=args.cover_max,
            quality=args.quality,
            make_cover=not args.no_cover,
            dry_run=args.dry_run,
        )

    print("\n完成。请把 stories.json 中的 cover 改为各册 assets/cover.jpg（若尚未改）。")
    print("源图在各册 assets/src/（默认不提交 Git，见 .gitignore）。")


if __name__ == "__main__":
    main()
