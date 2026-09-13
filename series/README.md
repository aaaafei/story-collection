# 故事系列总览

本仓库按「系列连载 / 独立单本」分目录：

```
story-collection/
├── index.html                 # 首页目录（支持多系列分组）
├── series/                    # 所有连载系列
│   ├── _template/             # 新系列脚手架（复制后改名）
│   └── rose-princess/         # 蔷薇公主系列
│       ├── character-bible.md
│       ├── refs/
│       ├── ep01-.../
│       └── ep02-.../
└── oneshots/                  # 暂不连载的单本
    ├── labu-princess/
    └── sneeze-princess/
```

## 规则

| 类型 | 放哪里 | 首页字段 |
|------|--------|----------|
| 连载系列 | `series/<系列英文slug>/` | `series: "中文系列名"`，并在 `seriesCatalog` 登记 |
| 系列分册 | `series/<slug>/epNN-主题/` | 路径写入 stories 的 cover/link |
| 独立单本 | `oneshots/<书名slug>/` | 不写 `series` 字段 |
| 单本升级成系列 | 整本挪进 `series/<slug>/ep01-.../`，补设定层 | 补 catalog + series 字段 |

## 新开一个系列

1. 复制 `series/_template/` → `series/<新slug>/`
2. 填写该系列的 `character-bible.md` 等
3. 创建 `ep01-.../` 放入首册
4. 在根目录 `stories.json` 的 `seriesCatalog` 与 `stories` 中登记
