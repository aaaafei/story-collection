# story-collection · 故事收藏屋

儿童绘本静态站。首页目录 + 多系列连载 + 独立单本。

## 目录结构

```
├── index.html              # 首页（读取 stories.json 渲染）
├── stories.json            # 书架目录（系列登记 + 故事列表）
├── manifest.webmanifest    # 轻量 PWA 清单（scope=/story/）
├── sw.js                   # 网络透传 SW（不缓存内容，仅便于安装）
├── icons/                  # PWA 图标
├── tools/                  # 本地工具（图片优化、Gitee 同步等）
│   ├── optimize_images.py
│   ├── sync_to_gitee.sh    # 提交/推送后同步到 Gitee
│   └── README.md
├── series/                 # 连载系列
│   ├── _template/          # 新系列脚手架
│   └── rose-princess/      # 蔷薇公主系列（设定 + ep01/ep02/...）
├── oneshots/               # 独立单本（拉不下公主、打喷嚏公主等）
└── deploy/                 # Nginx 配置示例
```

详细约定见 [`series/README.md`](series/README.md)。  
图片优化（手机网页用图）见 [`tools/README.md`](tools/README.md)。  
推送到 GitHub 后会由 Action 自动镜像到 Gitee；本地也可 `bash tools/sync_to_gitee.sh`。详见 [`tools/README.md`](tools/README.md#同步到-gitee)。

## 本地预览

需通过 **HTTPS**（或 localhost）的 HTTP 服务访问（Nginx 的 `/story/`）。  
不要直接双击 `index.html`，否则无法加载 `stories.json`，PWA 也无法注册。

## 轻量 PWA（方案 A）

- 可「安装到主屏幕 / 安装应用」，**不做离线缓存**，以免阻碍故事更新。
- `manifest` 的 `start_url` / `scope` 固定为 `/story/`（与 Nginx 挂载一致）。
- iOS 多为「添加到主屏幕」；微信内请用系统浏览器打开。

## 网页用图（本地优化）

高清原图放入各册 `assets/src/` 后，在仓库根目录执行：

```powershell
pip install -r tools/requirements.txt
python tools/optimize_images.py --all
```

会生成网页内页与 `cover.jpg`。首页封面请指向 `assets/cover.jpg`。详见 [`tools/README.md`](tools/README.md)。

## 新开系列 / 新分册

1. 复制 `series/_template/` → `series/<slug>/`，填写角色圣经与 refs  
2. 新建 `epNN-主题/` 放入绘本与高清图  
3. 运行 `python tools/optimize_images.py <该册路径>`  
4. 在根目录 `stories.json` 登记（`cover` 用 `assets/cover.jpg`）

也可以在本机运行 `python tools/sync_server.py`，用 `http://127.0.0.1:8765/` 打开首页，点「同步新故事」从 Notion 拉取尚未收录的系列分册。配置见 [`tools/README.md`](tools/README.md)。
