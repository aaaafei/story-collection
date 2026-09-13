# 蔷薇公主系列 · 共用设定

本目录是「蔷薇公主系列」的**唯一真相来源**：角色外形、画风、参考图、Prompt 模板都放这里。

各分册（`epNN-*/`）只负责本册剧情与逐页可变 Prompt，**不要在各册里另写一套角色描述**。

仓库总结构见 [`../README.md`](../README.md)。

## 目录结构

```
series/rose-princess/
├── README.md                 # 本说明
├── character-bible.md        # 角色圣经
├── style-guide.md            # 画风 + 生成参数
├── prompt-template.md        # Prompt 拼装模板
├── workflow.md               # 操作流程
├── refs/                     # 角色标准参考图
├── ep01-seed-flower/         # 第 1 册
└── ep02-sisters/             # 第 2 册
```

## 系列书目

| 序号 | 目录 | 书名 |
|------|------|------|
| 1 | [`ep01-seed-flower/`](ep01-seed-flower/) | 蔷薇公主的玫瑰公主花 |
| 2 | [`ep02-sisters/`](ep02-sisters/) | 蔷薇公主和玫瑰公主 |
| 3 | [`ep03-haircut/`](ep03-haircut/) | 超长头发大捣乱 |
| … | `ep04-.../` | 后续新故事（序号连续） |

## 快速开始（生成一张新图）

1. 打开 [`character-bible.md`](character-bible.md)，复制本页出场角色的「Prompt 固定段」
2. 打开 [`prompt-template.md`](prompt-template.md)，按模板拼完整 Prompt
3. 挂上 [`refs/`](refs/) 里对应角色的标准照作为参考图
4. 用 [`style-guide.md`](style-guide.md) 规定的模型与尺寸生成
5. 对照验收清单检查 → 放入该册 `assets/page-XX.jpg`
6. 把最终 Prompt 记入该册 `prompts.md`
