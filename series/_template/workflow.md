# ＜系列中文名＞ · 工作流程

## A. 新增一本分册

1. 在本系列目录下新建 `epNN-主题/`（序号连续）
2. 放入 `index.html`、`assets/`、`prompts.md`
3. `prompts.md` 写明：角色与画风见本系列根目录（`../character-bible.md` 等）
4. 根目录 `stories.json`：`stories` 增加一条，`series` 填本系列中文名；路径指向新分册；必要时同步 `seriesCatalog`
5. 长期新角色：先写入 `character-bible.md`，再补 `refs/` 标准照
6. 「返回故事目录」链接使用 `../../../index.html`

## B. 替换一页配图

1. 复制角色固定段 → 按模板拼 Prompt → 挂 refs → 生成  
2. 验收 → 替换 `assets/page-XX.jpg` → 写入该册 `prompts.md`  
3. 首页点「强制刷新」确认

## C. 验收清单

- [ ] 发色发型 / 裙色 / 发饰一致
- [ ] Q 版比例与脸型感一致
- [ ] 无恐怖造型

## D. 修改角色外形

1. 改 `character-bible.md` → 重渲 `refs/` → 评估旧册是否重渲
