# 绘本网页用图优化工具（本地 Pillow，不依赖豆包等第三方压缩）

## 作用

- 把高清源图缩小为适合 **手机 / 网页** 的 JPEG
- 自动生成列表用 **封面** `cover.jpg`
- 源图备份到 `assets/src/`，避免只剩压缩图无法重做

豆包等工具只负责「画原图」；**缩小与压缩在本仓库完成**。

## 目录约定

```
某绘本/
└── assets/
    ├── src/           # 高清源图（备份，建议不进 Git）
    │   ├── page-01.jpg
    │   └── ...
    ├── page-01.jpg    # 网页内页（脚本输出）
    ├── page-02.jpg
    ├── cover.jpg      # 首页列表封面（脚本输出，更小）
    └── ...
```

## 环境

在仓库根目录执行：

```powershell
pip install pillow
# 或
pip install -r tools/requirements.txt
```

## 常用命令

```powershell
cd D:\workspace\story-collection

# 预览将要做什么（不写文件）
python tools/optimize_images.py --all --dry-run

# 处理全部 series/ 与 oneshots/ 绘本
python tools/optimize_images.py --all

# 只处理某一册
python tools/optimize_images.py series/rose-princess/ep03-haircut

# 自定义尺寸与质量
python tools/optimize_images.py --all --page-max 1400 --cover-max 800 --quality 82
```

### 参数说明

| 参数 | 默认 | 含义 |
|------|------|------|
| `--page-max` | 1400 | 内页最长边像素 |
| `--cover-max` | 800 | `cover.jpg` 最长边像素 |
| `--quality` | 82 | JPEG 质量 |
| `--no-cover` | 关 | 不生成封面 |
| `--dry-run` | 关 | 只打印计划 |
| `--all` | 关 | 处理仓库内全部绘本 |

## 新故事标准流程

1. 用画图工具生成高清图（如 2304×1728）
2. 放入该册 `assets/src/page-01.jpg` …（若直接放进 `assets/`，首次跑脚本会自动备份到 `src/`）
3. 运行：

   ```powershell
   python tools/optimize_images.py series/rose-princess/ep04-你的主题
   ```

4. 确认生成了 `assets/page-XX.jpg` 与 `assets/cover.jpg`
5. 在根目录 `stories.json` 里登记，**封面路径用** `.../assets/cover.jpg`
6. 部署后强制刷新首页

## 从 Notion 同步新故事

首页的「同步新故事」会调用本机助手：查找 Notion 系列页里还没收录的 `EP##` 分册，下载插画，生成 `index.html` / `prompts.md`，并写入 `stories.json`。

```powershell
cd D:\workspace\story-collection
copy tools\.env.example tools\.env
# 编辑 tools/.env，填入 Notion 内部集成令牌
python tools/sync_server.py
```

浏览器打开 http://127.0.0.1:8765/ ，点「同步新故事」。

也可以直接跑命令行：

```powershell
python tools/sync_from_notion.py --preview --series rose-princess
python tools/sync_from_notion.py --series rose-princess
```

### 令牌怎么拿

1. 打开 [Notion Integrations](https://www.notion.so/my-integrations) 新建内部集成，复制 Secret  
2. 在 Notion 把 `story` 页面（以及系列子页面）Share 给这个集成  
3. 把令牌写入 `tools/.env` 的 `NOTION_TOKEN=`

系列要在 `stories.json` 的 `seriesCatalog` 里填写 `notionPage`（Notion 系列目录页链接）。

## 同步到 Gitee

镜像仓库：<https://gitee.com/aaaafei/story-collection.git>

代码进入 GitHub 后，`.github/workflows/sync-to-gitee.yml` 会把同一提交推到 Gitee（需在 GitHub 仓库 Secrets 里放同名 `GITEE_TOKEN`）。本地 / Cursor 提交后可用钩子或手动脚本，读取 Cursor Secrets 或 `tools/.env`。

令牌用网页上已配置的 **GITEE_TOKEN**（Cursor Cloud Agents → Secrets；GitHub Action 则读仓库 Actions secret 同名），不要把令牌写进仓库。本地也可写在 `tools/.env`（已在 `.gitignore` 中）。

```powershell
# 手动同步当前分支
bash tools/sync_to_gitee.sh

# 本机启用 post-commit 钩子（每次 git commit 后自动推 Gitee）
bash tools/sync_to_gitee.sh --install-hook
```

## 与首页的关系

`stories.json` 示例：

```json
{
  "cover": "series/rose-princess/ep01-seed-flower/assets/cover.jpg",
  "link": "series/rose-princess/ep01-seed-flower/index.html"
}
```

内页 HTML 仍引用 `assets/page-XX.jpg`（网页优化版），无需改路径。

## 注意

- **打印**请用 `assets/src/` 或外部原图，不要用网页压缩版去印大图。
- `assets/src/` 默认在 `.gitignore` 中，避免仓库过大；换电脑时请自行备份源图。
- 可重复执行：始终以 `src/` 为准重新生成网页图。
- 旧版单册脚本 `convert_images.py`（PNG→JPG 导入）可保留；网页优化统一用本工具。
