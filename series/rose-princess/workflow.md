# 蔷薇公主系列 · 工作流程

## A. 新增一本分册

1. 在本目录下新建 `epNN-主题/`（序号连续，如 `ep03-garden-party/`）
2. 放入 `index.html`、`assets/`、`prompts.md`
3. `prompts.md` 开头写明：角色与画风见本系列根目录（`../character-bible.md` 等）
4. 在仓库根目录 `index.html` 的 `stories` 数组增加一条：
   - `series: "蔷薇公主系列"`
   - `cover` / `link` 指向 `series/rose-princess/epNN-主题/...`
5. 若有长期新角色：先写入 `character-bible.md`，再生成 `refs/` 标准照
6. 「返回故事目录」链接使用 `../../../index.html`

## B. 为已有故事生成 / 替换一页配图

1. 打开 `character-bible.md` → 复制出场角色固定段  
2. 打开 `prompt-template.md` → 拼完整 Prompt  
3. 挂上 `refs/` 参考图 → 按 `style-guide.md` 参数生成  
4. 验收（见下）→ 替换该册 `assets/page-XX.jpg`  
5. 把最终 Prompt 写入该册 `prompts.md` 对应页  
6. 浏览器打开首页，点「强制刷新」确认

## C. 出图验收清单

并排对比 `refs/` 标准照，检查：

- [ ] 发色、发型一致
- [ ] 裙子主色一致
- [ ] 发饰仍在且颜色对
- [ ] 仍是同一 Q 版比例与脸型感
- [ ] 无恐怖 / 无违和配角造型

不通过：同一参考图 + 同一固定段，只改可变段重生成；**不要为了过关而改角色描述**。

## D. 修改角色外形（慎重）

1. 修改 `character-bible.md`
2. 重渲并替换 `refs/` 全套相关标准照
3. 评估旧书是否重渲（至少封面、含该角色的关键页）
4. 各册 `prompts.md` 里旧 Prompt 中的外形句同步替换为新固定段
