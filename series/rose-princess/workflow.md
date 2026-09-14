# 蔷薇公主系列 · 工作流程

## A. 新增一本分册

1. 在本目录下新建 `epNN-主题/`（序号连续，如 `ep03-garden-party/`）
2. 放入 `index.html`、`prompts.md`；高清图放入 `assets/src/`
3. 运行本地优化（生成网页内页与封面）：

   ```powershell
   python tools/optimize_images.py series/rose-princess/epNN-主题
   ```

4. `prompts.md` 开头写明：角色与画风见本系列根目录（`../character-bible.md` 等）
5. 根目录 `stories.json`：`stories` 增加一条，`series` 填本系列中文名；`cover` 指向 `.../assets/cover.jpg`
6. 若在 `seriesCatalog` 中尚无本系列，一并登记（`name` 须一致）
7. 若有长期新角色：先写入 `character-bible.md`，再生成 `refs/` 标准照
8. 「返回故事目录」链接使用 `../../../index.html`

## B. 为已有故事生成 / 替换一页配图

1. 打开 `character-bible.md` → 复制出场角色固定段  
2. 打开 `prompt-template.md` → 拼完整 Prompt  
3. 挂上 `refs/` 参考图 → 按 `style-guide.md` 参数生成高清图  
4. 验收后放入该册 `assets/src/page-XX.jpg`（覆盖源图）  
5. 再跑 `python tools/optimize_images.py <本册路径>`，更新网页用 `assets/page-XX.jpg`（若改了第 1 页会重出 `cover.jpg`）  
6. 把最终 Prompt 写入该册 `prompts.md` 对应页  
7. 浏览器打开首页，点「强制刷新」确认

## C. 出图验收清单

并排对比 `refs/` 标准照，检查外形；再单独检查姿态与信息量（见 `style-guide.md`「一页一事」）：

- [ ] 发色、发型一致
- [ ] 裙子主色一致
- [ ] 发饰仍在且颜色对
- [ ] 仍是同一 Q 版比例与脸型感
- [ ] 无恐怖 / 无违和配角造型
- [ ] **视角有变化**（非页页正面/同一侧面）
- [ ] **肢体动作清晰**（手脚在做事，非双手下垂呆站）
- [ ] 与上一页姿态 / 朝向不雷同
- [ ] **一页一事**：能指着说出本页唯一焦点（如「她慌了」）；非情绪+乱子+多人动作全挤一页
- [ ] 多角色同框时互动仍围绕同一焦点，非各干各的热闹堆砌

不通过：同一参考图 + 同一固定段，只改可变段重生成；**不要为了过关而改角色描述**。姿态不行就重写「视角 + 肢体动作」再出图。信息过载就拆成两页或收窄「构图重点」。

## D. 修改角色外形（慎重）

1. 修改 `character-bible.md`
2. 重渲并替换 `refs/` 全套相关标准照
3. 评估旧书是否重渲（至少封面、含该角色的关键页）
4. 各册 `prompts.md` 里旧 Prompt 中的外形句同步替换为新固定段
