# story-collection · 故事收藏屋

儿童绘本静态站。首页目录 + 多系列连载 + 独立单本。

## 目录结构

```
├── index.html              # 首页（多系列分组 + 独立故事）
├── series/                 # 连载系列
│   ├── _template/          # 新系列脚手架
│   └── rose-princess/      # 蔷薇公主系列（设定 + ep01/ep02/...）
├── oneshots/               # 独立单本（拉不下公主、打喷嚏公主等）
└── deploy/                 # Nginx 配置示例
```

详细约定见 [`series/README.md`](series/README.md)。

## 本地预览

用浏览器打开根目录 `index.html`，或挂到 Nginx 的 `/story/`（见 `deploy/nginx-story-collection.conf`）。

## 新开系列 / 新分册

1. 复制 `series/_template/` → `series/<slug>/`，填写角色圣经与 refs  
2. 新建 `epNN-主题/` 放入绘本  
3. 在根 `index.html` 登记 `seriesCatalog` 与 `stories`
