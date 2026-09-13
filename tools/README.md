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
