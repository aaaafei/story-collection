# -*- coding: utf-8 -*-
"""
从 Notion 系列页查找尚未收录的分册，下载插画并生成绘本目录文件。

用法：
  python tools/sync_from_notion.py --preview --series rose-princess
  python tools/sync_from_notion.py --series rose-princess

需要 Notion 内部集成令牌：环境变量 NOTION_TOKEN，或 tools/.env。
"""
from __future__ import print_function

import argparse
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from io import BytesIO

try:
    from PIL import Image
except ImportError:
    Image = None


NOTION_VERSION = "2022-06-28"
NOTION_API = "https://api.notion.com/v1"
TZ_SHANGHAI = timezone(timedelta(hours=8))

EP_TITLE_RE = re.compile(r"EP\s*(\d+)\s*[-–—]\s*(.+)", re.I)
COVER_HEAD_RE = re.compile(r"^封面")
PAGE_HEAD_RE = re.compile(r"^第\s*(\d+)\s*页")
CHAR_HEAD_RE = re.compile(r"角色参考|认识角色")
EXTRA_HEAD_RE = re.compile(r"儿歌|尾页|成长")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

SLUG_PHRASES = (
    ("人鱼宝宝的泡泡冠军", "bubble-champion"),
    ("奇怪的电梯山", "elevator-mountain"),
    ("人鱼妈妈去宝藏照相馆", "treasure-studio"),
    ("开心检察官的最后一枚印章", "happy-inspector"),
    ("金尾巴美人鱼的窗外世界", "golden-tail"),
    ("穿过荆棘墙去看电影", "thorn-cinema"),
    ("螃蟹节的小人鱼宝宝", "crab-festival"),
    ("奇奇怪怪的骰子", "dice"),
    ("噩梦妖怪和美梦仙子", "nightmare-fairy"),
    ("鹿角灯下的勇气宝石", "courage-gem"),
)

WORD_MAP = (
    ("泡泡冠军", "bubble-champion"),
    ("电梯山", "elevator-mountain"),
    ("照相馆", "photo-studio"),
    ("人鱼宝宝", "mermaid-baby"),
    ("人鱼妈妈", "mermaid-mom"),
    ("金尾巴", "golden-tail"),
    ("美人鱼", "mermaid"),
    ("宝藏", "treasure"),
    ("奇怪的", "strange"),
    ("开心", "happy"),
)

KNOWN_CHARS = (
    ("蔷薇公主", "姐姐 · 主角", "粉色长发的姐姐，温柔又勇敢，常常带着妹妹一起出门。"),
    ("玫瑰公主", "妹妹 · 主角", "蓝色头发的妹妹，调皮热心，遇到事会大声说出来。"),
    ("小人鱼宝宝", "小朋友", "还很小的人鱼宝宝，常常跟着姐姐们一起玩。"),
    ("小人鱼姐姐", "好朋友", "人鱼家的姐姐，喜欢和蔷薇、玫瑰一起冒险。"),
    ("人鱼妈妈", "大人", "温柔的人鱼妈妈，有时也会累，需要安静休息。"),
    ("开心检察官", "新朋友", "戴着小礼帽，拿着笑容放大镜，认真检查大家的心情。"),
    ("金尾巴美人鱼", "新朋友", "有金色鱼尾的美人鱼，一开始有点害羞。"),
    ("小风妖怪", "调皮朋友", "呼呼吹来的小风妖怪，捣蛋之后也会道歉。"),
    ("美梦仙子", "守护者", "把噩梦泡泡变成甜甜梦的仙子。"),
    ("噩梦妖怪", "新朋友", "抱着泡泡的小妖怪，其实也怕黑。"),
    ("地下公主", "好朋友", "住在地下城堡的小公主。"),
    ("国王", "爸爸", "彩虹城堡的国王，会及时赶来帮忙。"),
    ("王后", "妈妈", "彩虹城堡的王后，温柔又有办法。"),
)

CN_DIGITS = "零一二三四五六七八九"


def repo_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def log_print(message):
    print(message, flush=True)


def load_env(root):
    for path in (
        os.path.join(root, "tools", ".env"),
        os.path.join(root, ".env"),
    ):
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def notion_token():
    return (
        os.environ.get("NOTION_TOKEN")
        or os.environ.get("NOTION_API_KEY")
        or os.environ.get("NOTION_SECRET")
        or ""
    ).strip()


def load_catalog(root):
    path = os.path.join(root, "stories.json")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_catalog(root, data):
    path = os.path.join(root, "stories.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def page_id_from_url(value):
    if not value:
        return ""
    text = value.strip()
    match = re.search(
        r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        text,
        re.I,
    )
    if match:
        return match.group(1).lower()
    match = re.search(r"([0-9a-f]{32})", text, re.I)
    if not match:
        return ""
    raw = match.group(1).lower()
    return "%s-%s-%s-%s-%s" % (raw[0:8], raw[8:12], raw[12:16], raw[16:20], raw[20:32])


class NotionError(RuntimeError):
    def __init__(self, message, status=None):
        super(NotionError, self).__init__(message)
        self.status = status


class NotionClient(object):
    def __init__(self, token):
        self.token = token

    def request(self, path, method="GET"):
        url = NOTION_API + path
        req = urllib.request.Request(
            url,
            method=method,
            headers={
                "Authorization": "Bearer " + self.token,
                "Notion-Version": NOTION_VERSION,
                "User-Agent": "story-collection-sync/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8", errors="replace")
            if err.code == 401:
                raise NotionError("Notion 令牌无效，请检查 NOTION_TOKEN。", 401)
            if err.code == 404:
                raise NotionError(
                    "找不到 Notion 页面。请把「story」和对应系列页分享给这个集成。",
                    404,
                )
            raise NotionError("Notion API 错误 %s：%s" % (err.code, body[:300]), err.code)

    def children(self, block_id):
        results = []
        cursor = None
        while True:
            path = "/blocks/%s/children?page_size=100" % block_id
            if cursor:
                path += "&start_cursor=" + urllib.parse.quote(cursor)
            data = self.request(path)
            results.extend(data.get("results") or [])
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
            time.sleep(0.12)
        return results

    def page(self, page_id):
        return self.request("/pages/" + page_id)


def rich_text(items):
    if not items:
        return ""
    return "".join(item.get("plain_text") or "" for item in items).strip()


def block_plain(block):
    kind = block.get("type") or ""
    payload = block.get(kind) or {}
    if not isinstance(payload, dict):
        return ""
    return rich_text(payload.get("rich_text") or payload.get("text") or [])


def file_from_payload(payload):
    if not isinstance(payload, dict):
        return None
    kind = payload.get("type")
    info = payload.get(kind) or {}
    url = info.get("url") or ""
    name = payload.get("name") or info.get("name") or ""
    if not url:
        return None
    caption = rich_text(payload.get("caption") or [])
    return {"url": url, "name": name, "caption": caption}


def iter_content_blocks(client, block_id):
    for block in client.children(block_id):
        yield block
        kind = block.get("type")
        if block.get("has_children") and kind in (
            "column_list",
            "column",
            "toggle",
            "synced_block",
            "table",
        ):
            for child in iter_content_blocks(client, block.get("id")):
                yield child


def cn_num(n):
    n = int(n)
    if n <= 10:
        return "零一二三四五六七八九十"[n]
    if n < 20:
        return "十" + (CN_DIGITS[n - 10] if n > 10 else "")
    if n < 100:
        tens, ones = divmod(n, 10)
        return CN_DIGITS[tens] + "十" + (CN_DIGITS[ones] if ones else "")
    return str(n)


def slugify(episode, title):
    text = (title or "").strip()
    for src, dst in SLUG_PHRASES:
        if src in text:
            return "ep%02d-%s" % (episode, dst)
    slug = text
    for src, dst in WORD_MAP:
        slug = slug.replace(src, dst if dst else "-")
    slug = re.sub(r"[的了着过和与及]", "-", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"[^a-zA-Z0-9\-]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-").lower()
    if not slug or CJK_RE.search(slug):
        return "ep%02d" % episode
    return "ep%02d-%s" % (episode, slug[:40].strip("-"))


def parse_episode_title(title):
    clean = re.sub(r"^[\W_]+", "", title or "", flags=re.U).strip()
    match = EP_TITLE_RE.search(clean) or EP_TITLE_RE.search(title or "")
    if not match:
        return None
    name = re.sub(r"\s+", " ", match.group(2)).strip()
    name = re.sub(r"[（(].*?[）)]$", "", name).strip()
    return int(match.group(1)), name


def heading_kind(text):
    raw = (text or "").strip()
    if COVER_HEAD_RE.search(raw):
        return "cover", None, "封面"
    page = PAGE_HEAD_RE.search(raw)
    if page:
        title = raw.split("｜", 1)[-1].split("|", 1)[-1].strip()
        title = PAGE_HEAD_RE.sub("", title).strip("｜| :：")
        if not title or title.startswith("第"):
            title = raw
        return "page", int(page.group(1)), title
    if CHAR_HEAD_RE.search(raw):
        return "chars", None, raw
    if EXTRA_HEAD_RE.search(raw):
        return "extra", None, raw
    return "other", None, raw


def new_section(kind="lead", page_no=None, title=""):
    return {
        "kind": kind,
        "page_no": page_no,
        "title": title,
        "texts": [],
        "images": [],
        "files": [],
    }


def parse_page_blocks(blocks):
    current = new_section()
    sections = [current]
    status = ""

    for block in blocks:
        kind = block.get("type")
        if kind in ("heading_1", "heading_2", "heading_3"):
            current = new_section(*heading_kind(block_plain(block)))
            sections.append(current)
            continue
        if kind == "callout":
            text = block_plain(block)
            if text:
                if current["kind"] == "lead" and not status:
                    status = text
                else:
                    current["texts"].append(text)
            continue
        if kind == "image":
            info = file_from_payload(block.get("image") or {})
            if info:
                current["images"].append(info)
            continue
        if kind == "file":
            payload = block.get("file") or {}
            info = file_from_payload(payload)
            if not info:
                continue
            name = (info.get("name") or payload.get("name") or "").lower()
            info["name"] = payload.get("name") or info.get("name") or ""
            if name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                current["images"].append(info)
            else:
                current["files"].append(info)
            continue
        if kind in (
            "paragraph",
            "quote",
            "bulleted_list_item",
            "numbered_list_item",
        ):
            text = block_plain(block)
            if not text or text == current.get("title"):
                continue
            if PAGE_HEAD_RE.match(text) and current.get("title") and current["title"] in text:
                continue
            current["texts"].append(text)
    return sections, status


def pick_first_image(section):
    images = (section or {}).get("images") or []
    return images[0] if images else None


def text_join(lines, sep="\n"):
    return sep.join(line.strip() for line in (lines or []) if line and line.strip())


def is_ready(status, cover, pages):
    if cover or pages:
        image_count = (1 if cover and pick_first_image(cover) else 0) + sum(
            1 for page in pages if pick_first_image(page)
        )
        if image_count >= 3:
            return True
        if image_count >= 1 and status and "已完成" in status:
            return True
    if status and re.search(r"未完成|进行中|草稿|待.*图", status):
        return False
    return False


def build_book_model(title, episode, sections, status):
    cover = None
    pages = []
    extras = []
    char_sec = None
    for section in sections:
        kind = section["kind"]
        if kind == "cover" and not cover:
            cover = section
        elif kind == "page":
            pages.append(section)
        elif kind == "chars":
            char_sec = section
        elif kind in ("extra", "other"):
            if section["texts"] or section["images"]:
                extras.append(section)

    pages.sort(key=lambda item: item.get("page_no") or 0)
    if not cover and pages and pages[0].get("page_no") == 1:
        # EP16 风格：第 1 页就是封面
        cover = pages.pop(0)
        cover["kind"] = "cover"
        if not cover.get("title") or cover["title"].startswith("第"):
            cover["title"] = title

    quote_lines = []
    if cover:
        quote_lines.extend(cover.get("texts") or [])
    subtitle = ""
    cover_line = ""
    if quote_lines:
        first = quote_lines[0]
        if "·" in first:
            left, right = first.split("·", 1)
            if title in left or "系列" in right:
                subtitle = right.strip()
                cover_line = text_join(quote_lines[1:]) if len(quote_lines) > 1 else ""
            else:
                cover_line = text_join(quote_lines)
        else:
            cover_line = text_join(quote_lines)
    if not cover_line and pages:
        cover_line = text_join(pages[0].get("texts") or [])
    ending = ""
    for extra in extras:
        blob = text_join(extra.get("texts") or [])
        if blob:
            ending = blob
            break
    if not ending:
        for page in reversed(pages):
            blob = text_join(page.get("texts") or [])
            if blob:
                ending = blob.split("\n")[-1].strip()
                break

    return {
        "title": title,
        "episode": episode,
        "status": status,
        "subtitle": subtitle or "蔷薇公主系列 · 新故事",
        "cover": cover,
        "pages": pages,
        "cover_line": cover_line,
        "ending": ending,
        "char_sec": char_sec,
        "ready": is_ready(status, cover, pages),
    }


def discover_episodes(client, series_page_id):
    found = []
    seen = set()
    for block in client.children(series_page_id):
        if block.get("type") != "child_page":
            continue
        page_id = block.get("id")
        title = ((block.get("child_page") or {}).get("title")) or ""
        parsed = parse_episode_title(title)
        if not parsed or page_id in seen:
            continue
        seen.add(page_id)
        episode, name = parsed
        found.append(
            {
                "id": page_id,
                "title": name,
                "episode": episode,
                "notionTitle": title,
            }
        )
    found.sort(key=lambda item: item["episode"])
    return found


def list_series_status(root, data=None):
    data = data or load_catalog(root)
    catalog = data.get("seriesCatalog") or []
    stories = data.get("stories") or []
    rows = []
    for meta in catalog:
        name = meta.get("name")
        episodes = [s for s in stories if s.get("series") == name]
        max_ep = max((s.get("episode") or 0) for s in episodes) if episodes else 0
        rows.append(
            {
                "id": meta.get("id"),
                "name": name,
                "badge": meta.get("badge"),
                "desc": meta.get("desc"),
                "accent": meta.get("accent"),
                "notionPage": meta.get("notionPage") or "",
                "episodeCount": len(episodes),
                "latestEpisode": max_ep,
            }
        )
    return rows


def existing_episodes(data, series_name):
    return {
        int(item["episode"])
        for item in data.get("stories") or []
        if item.get("series") == series_name and item.get("episode")
    }


def unique_slug(root, series_id, episode, title):
    base = slugify(episode, title)
    folder = os.path.join(root, "series", series_id, base)
    if not os.path.isdir(folder):
        return base
    for suffix in range(2, 20):
        candidate = "%s-%d" % (base, suffix)
        folder = os.path.join(root, "series", series_id, candidate)
        if not os.path.isdir(folder):
            return candidate
    return "%s-%d" % (base, int(time.time()) % 10000)


def download_image(url, dest_path):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "story-collection-sync/1.0"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        payload = resp.read()
    if Image is None:
        with open(dest_path, "wb") as fh:
            fh.write(payload)
        return dest_path
    image = Image.open(BytesIO(payload))
    if image.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", image.size, (255, 255, 255))
        bg.paste(image, mask=image.split()[-1])
        image = bg
    else:
        image = image.convert("RGB")
    image.save(dest_path, "JPEG", quality=92, optimize=True)
    return dest_path


def html_br(text):
    escaped = html.escape(text or "").strip()
    escaped = re.sub(r"(?:\r\n|\r|\n)+", "<br>", escaped)
    return escaped


def pick_characters(model):
    blob = " ".join(
        [
            model.get("cover_line") or "",
            text_join((model.get("cover") or {}).get("texts") or []),
            " ".join(text_join(page.get("texts") or []) for page in model.get("pages") or []),
            text_join(((model.get("char_sec") or {}).get("texts") or [])),
        ]
    )
    picked = []
    for name, badge, desc in KNOWN_CHARS:
        if name in blob:
            picked.append({"name": name, "badge": badge, "desc": desc})
        if len(picked) >= 4:
            break
    if model.get("char_sec"):
        extra_name = None
        for line in model["char_sec"].get("texts") or []:
            match = re.search(r"[\u4e00-\u9fff]{2,12}", line)
            if match:
                extra_name = match.group(0)
                break
        caption = ""
        images = model["char_sec"].get("images") or []
        if images:
            caption = images[0].get("caption") or ""
            if "｜" in caption:
                extra_name = extra_name or caption.split("｜", 1)[-1].strip()
        if extra_name and extra_name not in [item["name"] for item in picked]:
            desc = text_join((model["char_sec"].get("texts") or [])[:2]) or "本册新出场的朋友。"
            picked = (picked + [{"name": extra_name, "badge": "本册登场", "desc": desc}])[:4]
    if not picked:
        picked = [
            {"name": "蔷薇公主", "badge": "姐姐 · 主角", "desc": KNOWN_CHARS[0][2]},
            {"name": "玫瑰公主", "badge": "妹妹 · 主角", "desc": KNOWN_CHARS[1][2]},
        ]
    return picked


def tags_from_model(model):
    tags = []
    subtitle = model.get("subtitle") or ""
    for piece in re.split(r"[·•、，,]", subtitle):
        piece = piece.strip()
        if piece and "系列" not in piece and "绘本" not in piece and len(piece) <= 12:
            tags.append(piece)
    if not tags:
        tags = ["温馨日常", "系列连载"]
    return tags[:3]


def story_desc(series_name, model):
    episode = model["episode"]
    line = re.sub(r"\s+", "", model.get("cover_line") or "")
    if not line:
        pages = model.get("pages") or []
        line = re.sub(r"\s+", "", text_join((pages[0].get("texts") or []) if pages else []))
    if len(line) > 120:
        line = line[:118].rstrip("，,。；; ") + "……"
    return "系列第%s篇：%s" % (cn_num(episode), line or model["title"])


def donor_html(root):
    preferred = os.path.join(
        root, "series", "rose-princess", "ep16-happy-inspector", "index.html"
    )
    if os.path.isfile(preferred):
        return preferred
    series_root = os.path.join(root, "series")
    for dirpath, dirnames, filenames in os.walk(series_root):
        if "index.html" in filenames and os.path.basename(dirpath).startswith("ep"):
            return os.path.join(dirpath, "index.html")
    raise RuntimeError("找不到可用的绘本 HTML 模板。")


def split_donor(root):
    path = donor_html(root)
    text = open(path, "r", encoding="utf-8").read()
    head, rest = text.split("</head>", 1)
    _, lightbox = rest.split('<div class="lightbox"', 1)
    return head, '<div class="lightbox"' + lightbox


def render_episode_html(root, model, series_name):
    head, lightbox = split_donor(root)
    title = model["title"]
    head = re.sub(
        r"<title>.*?</title>",
        "<title>%s · 儿童绘本</title>" % html.escape(title),
        head,
        count=1,
    )
    tags = tags_from_model(model)
    meta = ['<span>适读年龄 3-6 岁</span>']
    meta.extend("<span>%s</span>" % html.escape(tag) for tag in tags[:3])
    if "水彩画风" not in tags:
        meta.append("<span>水彩画风</span>")
    chars = pick_characters(model)
    char_html = []
    for idx, char in enumerate(chars, start=1):
        char_html.append(
            '      <div class="char-card c%d">\n'
            '        <span class="badge">%s</span>\n'
            "        <h3>%s</h3>\n"
            "        <p>%s</p>\n"
            "      </div>"
            % (
                ((idx - 1) % 4) + 1,
                html.escape(char["badge"]),
                html.escape(char["name"]),
                html.escape(char["desc"]),
            )
        )
    cover_title = ((model.get("cover") or {}).get("title") or "封面").strip() or "封面"
    articles = []
    for idx, page in enumerate(model.get("pages") or [], start=2):
        number = page.get("page_no") or (idx if model.get("cover") else idx)
        page_title = page.get("title") or ("第%s页" % cn_num(number))
        body = html_br(text_join(page.get("texts") or []))
        src_index = idx
        articles.append(
            "    <article class=\"page\">\n"
            '      <div class="img-box"><img src="assets/page-%02d.jpg" alt="%s"></div>\n'
            '      <div class="text-box">\n'
            '        <span class="p-no">第 %d 页</span>\n'
            "        <h2>%s</h2>\n"
            '        <p class="quote">%s</p>\n'
            "      </div>\n"
            "    </article>"
            % (
                src_index,
                html.escape(page_title),
                number,
                html.escape(page_title),
                body or html.escape(page_title),
            )
        )
    intro = model.get("subtitle") or "翻开故事，跟着图画一页一页看"
    if "·" in intro:
        intro = "翻开故事，" + intro.split("·", 1)[-1].strip()
    body = """
<body>

<a class="back-home" href="../../../index.html">← 返回故事目录</a>

<header class="hero">
  <div class="wrap">
    <span class="page-tag">系列故事 · 第%s篇</span>
    <h1>%s</h1>
    <p class="subtitle">%s</p>
    <div class="meta-line">
      %s
    </div>
    <div class="cover-frame">
      <img src="assets/page-01.jpg" alt="封面：%s">
    </div>
    <p class="cover-line">%s</p>
  </div>
</header>

<section class="characters">
  <div class="wrap">
    <h2 class="section-title">认识角色</h2>
    <p class="section-note">%s</p>
    <div class="char-grid">
%s
    </div>
  </div>
</section>

<section class="story">
  <div class="wrap">
    <p class="intro">%s</p>

%s

  </div>
</section>

<section class="ending">
  <div class="wrap">
    <p class="the-end">完</p>
    <p>%s</p>
  </div>
</section>

<footer>《%s》· 系列第%s篇 · %s</footer>

""" % (
        cn_num(model["episode"]),
        html.escape(title),
        html.escape(model.get("subtitle") or ""),
        "\n      ".join(meta),
        html.escape(cover_title),
        html_br(model.get("cover_line") or ""),
        html.escape(intro),
        "\n".join(char_html),
        html.escape(intro),
        "\n".join(articles),
        html_br(model.get("ending") or model.get("cover_line") or title),
        html.escape(title),
        cn_num(model["episode"]),
        html.escape(series_name),
    )
    return head + "</head>\n" + body + lightbox


def render_prompts(model, series_name, notion_title):
    lines = [
        "# 《%s》绘本制作记录" % model["title"],
        "",
        "> 来源：Notion「%s」。配图已下载到 `assets/src/`，网页图由 `tools/optimize_images.py` 生成。"
        % notion_title,
        "> 角色外形以系列 [`../character-bible.md`](../character-bible.md) 为准。",
        "> 最后更新：%s" % datetime.now(TZ_SHANGHAI).strftime("%Y-%m-%d"),
        "",
        "## 一、项目概览",
        "",
        "| 项 | 内容 |",
        "|---|---|",
        "| 书名 | %s |" % model["title"],
        "| 适配年龄 | 3-6 岁 |",
        "| 系列归属 | %s第%s篇 |" % (series_name, cn_num(model["episode"])),
        "| 主题 | %s |" % (model.get("subtitle") or model["title"]),
        "| 交付物 | `index.html` + `assets/` |",
        "",
    ]
    if model.get("status"):
        lines.extend(["Notion 标注：%s" % model["status"], ""])
    lines.extend(["## 二、逐页文字", ""])
    cover = model.get("cover") or {}
    cover_title = cover.get("title") or "封面"
    lines.extend(
        [
            "### 第 1 页 %s" % cover_title,
            "",
            text_join(cover.get("texts") or []) or (model.get("cover_line") or ""),
            "",
        ]
    )
    for page in model.get("pages") or []:
        number = page.get("page_no") or 0
        lines.extend(
            [
                "### 第 %d 页 %s" % (number, page.get("title") or ""),
                "",
                text_join(page.get("texts") or []),
                "",
            ]
        )
    if model.get("ending"):
        lines.extend(["## 三、结尾", "", model["ending"], ""])
    return "\n".join(lines).rstrip() + "\n"


def insert_story(data, story):
    stories = data.setdefault("stories", [])
    last = None
    for idx, item in enumerate(stories):
        if item.get("series") == story.get("series"):
            last = idx
    if last is None:
        stories.append(story)
    else:
        stories.insert(last + 1, story)


def update_series_readme(root, series_id, episode, slug, title):
    path = os.path.join(root, "series", series_id, "README.md")
    if not os.path.isfile(path):
        return
    text = open(path, "r", encoding="utf-8").read()
    marker = "| … | `epNN-.../` | 后续新故事（序号连续） |"
    row = "| %d | [`%s/`](%s/) | %s |" % (episode, slug, slug, title)
    if ("| %d |" % episode) in text:
        return
    if marker in text:
        text = text.replace(marker, row + "\n" + marker)
    else:
        text = text.rstrip() + "\n" + row + "\n"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def save_ref_image(root, series_id, model, log):
    section = model.get("char_sec") or {}
    image = pick_first_image(section)
    if not image:
        return
    refs = os.path.join(root, "series", series_id, "refs")
    os.makedirs(refs, exist_ok=True)
    caption = image.get("caption") or "character-ref"
    slug = re.sub(r"[^a-zA-Z0-9\-]+", "-", caption.lower()).strip("-") or "new-character"
    dest = os.path.join(refs, slug[:40] + ".jpg")
    if os.path.isfile(dest):
        return
    try:
        download_image(image["url"], dest)
        log("  新角色参考图 -> refs/%s" % os.path.basename(dest))
    except Exception as err:
        log("  角色参考图下载失败：%s" % err)


def write_book(root, series_meta, item, model, log):
    series_id = series_meta["id"]
    series_name = series_meta["name"]
    slug = unique_slug(root, series_id, model["episode"], model["title"])
    book_dir = os.path.join(root, "series", series_id, slug)
    src_dir = os.path.join(book_dir, "assets", "src")
    os.makedirs(src_dir, exist_ok=True)

    assets = []
    cover_img = pick_first_image(model.get("cover"))
    if cover_img:
        assets.append((cover_img, model["title"]))
    for page in model.get("pages") or []:
        image = pick_first_image(page)
        if image:
            assets.append((image, page.get("title") or ""))
    if not assets:
        raise RuntimeError("这一册还没有可下载的插画。")

    for index, (image, _label) in enumerate(assets, start=1):
        dest = os.path.join(src_dir, "page-%02d.jpg" % index)
        log("  下载插画 %d/%d" % (index, len(assets)))
        download_image(image["url"], dest)
        time.sleep(0.08)

    html_text = render_episode_html(root, model, series_name)
    with open(os.path.join(book_dir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(html_text)
    with open(os.path.join(book_dir, "prompts.md"), "w", encoding="utf-8") as fh:
        fh.write(render_prompts(model, series_name, item.get("notionTitle") or model["title"]))

    save_ref_image(root, series_id, model, log)

    rel = os.path.join("series", series_id, slug).replace("\\", "/")
    subprocess.check_call(
        [sys.executable, os.path.join("tools", "optimize_images.py"), rel],
        cwd=root,
    )
    return slug, rel, len(assets)


def preview_series(root, series_ids, log=log_print):
    load_env(root)
    token = notion_token()
    if not token:
        raise NotionError("还没有配置 NOTION_TOKEN。请在 tools/.env 写入集成令牌。", 503)
    data = load_catalog(root)
    client = NotionClient(token)
    wanted = set(series_ids or [])
    result = []
    for meta in data.get("seriesCatalog") or []:
        if wanted and meta.get("id") not in wanted:
            continue
        page = page_id_from_url(meta.get("notionPage") or "")
        if not page:
            result.append(
                {
                    "id": meta.get("id"),
                    "name": meta.get("name"),
                    "error": "这个系列还没有填写 notionPage。",
                    "newEpisodes": [],
                    "existing": sorted(existing_episodes(data, meta.get("name"))),
                }
            )
            continue
        log("正在查看 Notion「%s」…" % (meta.get("name") or meta.get("id")))
        episodes = discover_episodes(client, page)
        have = existing_episodes(data, meta.get("name"))
        fresh = [item for item in episodes if item["episode"] not in have]
        result.append(
            {
                "id": meta.get("id"),
                "name": meta.get("name"),
                "notionPage": meta.get("notionPage"),
                "existing": sorted(have),
                "latestInNotion": max((item["episode"] for item in episodes), default=0),
                "newEpisodes": fresh,
            }
        )
    return result


def fetch_model(client, item):
    blocks = list(iter_content_blocks(client, item["id"]))
    sections, status = parse_page_blocks(blocks)
    return build_book_model(item["title"], item["episode"], sections, status)


def sync_series(root, series_ids, episode_keys=None, log=log_print):
    load_env(root)
    token = notion_token()
    if not token:
        raise NotionError("还没有配置 NOTION_TOKEN。请在 tools/.env 写入集成令牌。", 503)
    if Image is None:
        raise RuntimeError("缺少 Pillow，请先执行: pip install -r tools/requirements.txt")

    data = load_catalog(root)
    client = NotionClient(token)
    wanted = set(series_ids or [])
    allow = set(episode_keys or [])
    imported = []
    skipped = []
    errors = []

    for meta in data.get("seriesCatalog") or []:
        if wanted and meta.get("id") not in wanted:
            continue
        page = page_id_from_url(meta.get("notionPage") or "")
        if not page:
            skipped.append({"series": meta.get("name"), "reason": "未配置 notionPage"})
            continue
        log("查找系列：%s" % meta.get("name"))
        have = existing_episodes(data, meta.get("name"))
        for item in discover_episodes(client, page):
            key = "%s:%d" % (meta.get("id"), item["episode"])
            if item["episode"] in have:
                continue
            if allow and key not in allow and str(item["episode"]) not in allow:
                continue
            log("发现新故事 EP%02d %s" % (item["episode"], item["title"]))
            try:
                model = fetch_model(client, item)
            except Exception as err:
                errors.append({"title": item["title"], "reason": str(err)})
                log("  读取失败：%s" % err)
                continue
            if not model.get("ready"):
                reason = model.get("status") or "插画还不够，先跳过"
                skipped.append(
                    {
                        "series": meta.get("name"),
                        "episode": item["episode"],
                        "title": item["title"],
                        "reason": reason,
                    }
                )
                log("  尚未完成：%s" % reason)
                continue
            try:
                slug, rel, n_img = write_book(root, meta, item, model, log)
            except Exception as err:
                errors.append({"title": item["title"], "reason": str(err)})
                log("  制作失败：%s" % err)
                continue
            created = datetime.now(TZ_SHANGHAI).strftime("%Y-%m-%dT%H:%M:%S+08:00")
            story = {
                "series": meta.get("name"),
                "episode": item["episode"],
                "createdAt": created,
                "cover": "%s/assets/cover.jpg" % rel,
                "title": model["title"],
                "desc": story_desc(meta.get("name"), model),
                "tags": tags_from_model(model),
                "link": "%s/index.html" % rel,
            }
            insert_story(data, story)
            update_series_readme(root, meta["id"], item["episode"], slug, model["title"])
            imported.append(
                {
                    "series": meta.get("name"),
                    "episode": item["episode"],
                    "title": model["title"],
                    "slug": slug,
                    "path": rel,
                    "images": n_img,
                }
            )
            log("  已写入 %s（%d 张图）" % (rel, n_img))
            have.add(item["episode"])

    if imported:
        save_catalog(root, data)
        log("已更新 stories.json")
    elif not skipped and not errors:
        log("没有发现需要同步的新故事。")
    return {"imported": imported, "skipped": skipped, "errors": errors}


def main(argv=None):
    parser = argparse.ArgumentParser(description="从 Notion 同步新的系列故事")
    parser.add_argument("--series", action="append", dest="series", help="系列 id，可重复")
    parser.add_argument("--preview", action="store_true", help="只查找，不写文件")
    parser.add_argument("--all", action="store_true", help="同步 stories.json 中全部已配置系列")
    args = parser.parse_args(argv)
    root = repo_root()
    load_env(root)
    data = load_catalog(root)
    series_ids = list(args.series or [])
    if args.all or not series_ids:
        series_ids = [
            item.get("id")
            for item in data.get("seriesCatalog") or []
            if item.get("id")
        ]
    if args.preview:
        rows = preview_series(root, series_ids)
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    result = sync_series(root, series_ids)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result.get("errors") else 1


if __name__ == "__main__":
    sys.exit(main())
