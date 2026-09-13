# story-collection · 故事收藏屋

儿童绘本静态站。首页目录 + 多系列连载 + 独立单本。

## 目录结构

```
├── index.html              # 首页（读取 stories.json 渲染）
├── stories.json            # 书架目录（系列登记 + 故事列表）
├── manifest.webmanifest    # 轻量 PWA 清单（scope=/story/）
├── sw.js                   # 网络透传 SW（不缓存内容，仅便于安装）
├── icons/                  # PWA 图标
├── series/                 # 连载系列
│   ├── _template/          # 新系列脚手架
│   └── rose-princess/      # 蔷薇公主系列（设定 + ep01/ep02/...）
├── oneshots/               # 独立单本（拉不下公主、打喷嚏公主等）
└── deploy/                 # Nginx 配置示例
```

详细约定见 [`series/README.md`](series/README.md)。

## 本地预览

需通过 **HTTPS**（或 localhost）的 HTTP 服务访问（Nginx 的 `/story/`）。  
不要直接双击 `index.html`，否则无法加载 `stories.json`，PWA 也无法注册。

## 轻量 PWA（方案 A）

- 可「安装到主屏幕 / 安装应用」，**不做离线缓存**，以免阻碍故事更新。
- `manifest` 的 `start_url` / `scope` 固定为 `/story/`（与 Nginx 挂载一致）。
- iOS 多为「添加到主屏幕」；微信内请用系统浏览器打开。

## 新开系列 / 新分册

1. 复制 `series/_template/` → `series/<slug>/`，填写角色圣经与 refs  
2. 新建 `epNN-主题/` 放入绘本  
3. 在根目录 `stories.json` 登记 `seriesCatalog` 与 `stories`
