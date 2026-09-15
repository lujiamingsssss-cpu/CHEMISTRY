# 项目接管指南

本文面向首次进入本仓库的开发者和编码 Agent，提供完成项目交接所需的稳定基础：产品边界、权威规则、仓库地图、开发模式、关键资源、验证方式和接管检查清单。

本文不是任务状态、里程碑流水或发布授权。当前工作状态必须以目标 checkout 的 Git、根目录 `CURRENT_WORK.md`（如存在）、代码和新鲜验证结果为准。

## 1. 项目概览

本仓库同时维护两个相互隔离的产品方向。

### 1.1 Chemical Trade AI Copilot

面向内部化工外贸人员的私人证据工作台。系统只使用企业批准的 TDS/SDS，把中英文询盘拆解为技术、合规、商务和物流要求，并输出有来源约束的产品判断、证据缺口、追问和可编辑英文回复草稿。

核心边界：

- 不是公开商城、通用 PDF 问答、CRM、ERP 或自动发信系统；
- 当前资料范围由 `materials_catalog.json` 唯一控制；
- 正式 PDF、索引、模型缓存、凭据和客户资料位于 Git 外；
- 检索主链为 multilingual E5 + Chroma；
- 高风险化工事实必须绑定条件、文件和物理页，并经过确定性门禁；
- 模型不能代替资料、安全、合规或专业化工人工判断。

长期产品约束见 `PROJECT_SPEC.md`，界面约束见 `docs/UI_STYLE_GUIDE.md`。

### 1.2 南京睿扬光电公开展示前台

面向外部客户的品牌与产品展示 Demo，覆盖光学材料、器件能力、应用方向、产品目录和技术需求入口。它使用独立的静态 HTML/CSS/JavaScript 前台，不与内部 Streamlit 工作台共用页面或产品模型。

核心边界：

- 企业事实、第三方公开信息和概念演示必须清晰区分；
- 概念视觉不得冒充真实产品、设备、厂房、工艺或测试结果；
- 公司与产品主张必须有可访问来源及适用边界；
- 新前台先在隔离预览中验收，未经批准不得覆盖正式页面、资料清单或索引；
- 不因“统一架构”预建共享平台，只有真实调用方和固定失败案例才能触发薄层复用。

架构决定见 `docs/adr/0001-public-showcase-product-transition.md`，视觉与内容规范见 `docs/SHOWCASE_UI_STYLE_GUIDE.md`。

### 1.3 TWINKLE 产品探索器

TWINKLE 是公开展示前台中的受控交互样机。它以预渲染 PNG、有限路线、明确状态机和可验证 manifest 展示开放光学系统、双通道采集光学舱与聚光镜组件。

TWINKLE 的关键原则：

- 阶段 1–4 的模型、相机、路线、语义 ID、机械动作和人工批准事实不可在后续集成中悄然改写；
- 阶段 5 采用单一状态权威协调总览、聚焦、机械动作、检查灯、退出和返回；
- 机器测试、历史证据和前一人工门禁都不能代签下一人工门禁；
- 阶段完成不自动授权下一阶段、提交、推送、PR、发布或部署；
- 正式运行资产、完整验收证据和临时实验产物必须分层管理。

完整设计权威见 `docs/superpowers/specs/2026-08-20-twinkle-page-coordinated-render-design.md`。

## 2. 权威规则与冲突处理

### 2.1 固定优先级

发生冲突时，严格按以下顺序裁决：

1. 用户当前明确要求；
2. 当前 checkout 根目录的 `AGENTS.md`；
3. 与当前任务匹配的根目录 `CURRENT_WORK.md`；
4. 已接受且仍有效的 ADR；
5. `docs/ENGINEERING_PLAYBOOK.md`；
6. 当前代码、测试和 Git 可验证事实。

旧聊天、旧交接、历史任务说明和模型记忆只能辅助定位，不能覆盖上述权威。指定 Codex 任务中的结论也必须回到当前仓库交叉验证。

### 2.2 每次任务的强制启动顺序

进入仓库后先执行：

```powershell
git rev-parse --show-toplevel
git worktree list --porcelain
git branch --show-current
git status --short
```

然后：

1. 从 `git rev-parse --show-toplevel` 返回的根目录读取 `AGENTS.md`；
2. 开发、修复、重构、依赖、数据或配置变更还要读取 `docs/ENGINEERING_PLAYBOOK.md`；
3. 检查根目录是否存在 `CURRENT_WORK.md`；
4. 只要存在，就先运行 `python scripts/check_current_work_hygiene.py --repo .`；
5. 门禁失败时只能修复该任务的状态载体，不能进入实现；
6. 阅读与请求直接相关的代码、测试、配置和最近 Git 变更；
7. 明确范围、非目标、验收证据和停止条件后再行动。

工作树绝对路径只能从 `git worktree list --porcelain` 的注册记录取得，不得凭聊天文本或目录命名手工拼接。

### 2.3 任务路由

先判断是否只读。需要改动时只选择一种类型：

| 类型 | 适用场景 | 必要流程 |
|---|---|---|
| Read-only | 解释、调研、诊断、审查、状态报告 | 不修改文件、外部系统或 Git 历史 |
| Bug | 已有行为与明确预期不一致 | 复现 → 根因 → 失败回归测试 → 最小修复 → 验证 |
| Feature | 增加或改变用户可观察能力 | 场景与范围 → 成熟方案 → 设计批准 → 验收案例 → 最小实现 → 验证 |
| Task | 重构、依赖、测试、文档、构建、数据或运行操作 | 与真实风险相称的范围、门禁和验证 |

随后只追加两个判断：是否为长任务、是否为高风险。任一为“是”时，在实现前创建根目录 `CURRENT_WORK.md`；高风险任务还必须记录人工批准点和回滚路径。

### 2.4 `CURRENT_WORK.md` 的地位

`CURRENT_WORK.md` 是长任务跨会话续接的唯一权威状态载体，不是永久项目文档。它必须符合工程手册模板和卫生门禁，包含当前范围、非目标、权威状态、批准与回滚、复杂度预算、临时产物生命周期及唯一下一动作。

- 一个分支或工作树同时只能有一个；
- 已有文件属于另一任务时不得覆盖或跳过；
- 新会话核验一致后直接执行唯一下一动作，不重复已完成工作；
- 完成全部任务并通过新鲜验证后，同一收口中删除；
- 不另建第二份状态、计划、交接快照或历史流水文档。

## 3. 仓库与 Worktree

### 3.1 当前机器的注册位置

以下位置是本指南编写时 Git 注册记录的示例；接管时仍必须重新运行 `git worktree list --porcelain`：

| 用途 | 分支 | 注册路径 |
|---|---|---|
| 主工作树 | `main` | `F:/半导体材料产品展示` |
| TWINKLE Stage 5 集成 | `codex/twinkle-stage5-integration` | `F:/半导体材料产品展示/.worktrees/twinkle-stage5-integration` |
| TWINKLE 热点页面修订 | `codex/twinkle-hotspot-page-revision` | `F:/半导体材料产品展示/.worktrees/twinkle-hotspot-page-revision` |

远程仓库当前配置为 `https://github.com/lujiamingsssss-cpu/CHEMISTRY.git`。远程地址、分支领先关系和工作树状态都是可变事实，使用前必须重新核验。

### 3.2 Git 操作边界

- 工作树可能包含用户改动和来源不明的未跟踪资产，未经确认不得清理、移动、覆盖或纳入提交；
- 未经用户明确要求，不提交、不推送、不创建 PR、不部署；
- 不使用 `git reset --hard` 或其他破坏性恢复手段；
- 提交前必须检查范围、差异、未跟踪文件、凭据和生成物；
- PNG 是否受 LFS 管理以 `.gitattributes` 和 `git lfs ls-files` 的实际结果为准。

## 4. 技术栈与运行边界

### 4.1 Python 证据工作台

`pyproject.toml` 规定：

- Python `>=3.11,<3.14`；
- Streamlit 1.60；
- ChromaDB 1.5；
- sentence-transformers 5.6；
- OpenAI Python SDK 2.x；
- PyMuPDF、Pydantic 和 LangChain text splitters；
- pytest 9 与 pytest-cov 7 为开发依赖；
- 包采用 `src/` 布局，命令入口为 `chemical-trade-copilot`。

主要模块：

| 路径 | 责任 |
|---|---|
| `src/chemical_trade_copilot/materials.py` | 资料清单、启用状态与指纹 |
| `pdf_pages.py` | PDF 物理页读取 |
| `embeddings.py`、`retrieval.py` | E5 向量和检索 |
| `index_lifecycle.py` | 暂存重建、切换、状态和回滚 |
| `evaluation.py` | golden retrieval gate |
| `inquiry_analysis.py`、`verified_facts.py` | 结构化分析和高风险事实门禁 |
| `workflow.py` | 业务编排 |
| `evidence_viewer.py` | 受控 PDF 证据查看 |
| `streamlit_app.py`、`ui_*` | 内部工作台界面 |
| `cli.py` | `preflight`、`rebuild`、`status`、`verify`、`rollback`、`query`、`analyze` |

本地常用命令：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m chemical_trade_copilot.cli --help
.\.venv\Scripts\python.exe -m streamlit run src\chemical_trade_copilot\streamlit_app.py
```

涉及真实资料和索引时，必须按 `docs/MATERIAL_EXPANSION_RUNBOOK.md` 使用批准资料根目录、清单和暂存切换流程，不能把示例路径当成当前机器事实。

### 4.2 公开展示前台

公开前台位于 `showcase/homepage/`，以浏览器原生 HTML/CSS/ES modules 为主：

- `index.html`：主页信息架构、来源链接、TWINKLE 入口和技术联系入口；
- `hero-flowmap.js`：首页视觉动效；
- `product-items.mjs`、`preview-runtime.mjs`：产品数据与运行时辅助；
- `catalog/`：材料产品环形画廊；
- `twinkle-entry.css`、`twinkle-entry.js`：TWINKLE 入口、悬停序列、全屏 iframe、关闭和减少动态策略；
- `assets/vendor/` 与 `catalog/assets/vendor/`：本地化前端依赖，避免正式演示依赖公共 CDN。

静态页面必须通过 HTTP 服务访问，不能依赖 `file://` 的偶然行为。例如：

```powershell
.\.venv\Scripts\python.exe -m http.server 8000
```

然后访问 `http://127.0.0.1:8000/showcase/homepage/index.html`。是否具备完整 TWINKLE iframe 依赖，必须结合打包产物、正式运行资产和当前验证目标判断；不能仅凭首页能打开就宣称 H2 完整。

### 4.3 TWINKLE 工具链

TWINKLE 使用 Python 生成器与校验器、原生 JavaScript、Playwright/Chromium、Blender 渲染结果、PNG 序列和 JSON manifest。核心入口包括：

- `scripts/build_twinkle_stage3_motion.py`：机械动作契约与资产；
- `scripts/build_twinkle_stage4_orbit.py`：360° 总览、聚焦路线、状态轨迹和阶段关闭；
- `scripts/build_twinkle_stage5_homepage.py`：受控首页集成；
- `scripts/package_twinkle_stage5.py`：Stage 5 打包与可移植性检查；
- `scripts/build_twinkle_stage5_h2_full_flow_review.py`：H2 完整流程审核页与严格证据验证；
- `scripts/twinkle_stage5_h2_evidence.py`：内容寻址证据包；
- `registry/twinkle/`：运行资产、来源 manifest 和精简 evidence receipt 的权威登记。

从仓库根目录调用需要导入 `scripts` 的生成器时，优先使用模块方式或 pytest 中已验证的调用方式，不要假定直接执行文件一定能解析仓库包路径。

## 5. 三层资产与证据模型

TWINKLE 交接必须区分以下三层，不能把所有 `output/` 或所有 PNG 视为同一性质。

### 5.1 第一层：Git 内产品代码与可复现契约

包括产品代码、测试、registry、collector/validator、本地化依赖、少量 synthetic fixtures、必要 golden 截图和精简 evidence receipt。默认 `pytest` 应仅依赖已提交内容并可在 clean checkout 运行。

### 5.2 第二层：正式运行资产

阶段 5 正式运行时资产由 `registry/twinkle/stage5-runtime-assets.json` 机械登记。既定契约包含 248 张 PNG，并只允许 `showcase/homepage/assets/twinkle/**/*.png` 的精确 Git LFS 规则；不得扩大为全仓 `*.png`。

来源 manifest 的逐字节副本位于 `registry/twinkle/stage5-source-manifests/`。迁移和打包必须拒绝路径逃逸、reparse point、缺失或额外文件、哈希/字节数漂移及未物化 LFS pointer。

### 5.3 第三层：完整里程碑证据包

完整 H2 闭包体积大、包含真实审核依赖，不适合全部写入普通 Git。它按内容寻址、不可变 bundle 管理，由 `registry/twinkle/stage5-h2-evidence-receipt.json` 保存 bundle SHA、文件数、字节数、正式结果哈希和结果摘要。

严格 validator 必须显式接受 evidence root，先验证 bundle SHA 和 inventory，再验证真实闭包。没有外部 evidence 不能伪装成通过；默认测试可跳过显式外部证据合同，但必须清楚报告跳过原因。

### 5.4 临时实验与诊断产物

Playwright session、trace、日志、失败候选、低清/插值/RGBA/focus pilot、Blender preflight 和可重建中间资产通常属于临时或隔离层。是否能删除不能只看目录名、Git ignore 或“可重建”标签；必须确认绝对路径、归属、内容范围、恢复方式和当前任务授权。

### 5.5 机器本地 SHA-pinned 证据链

TWINKLE Stage 5 H2 审核链**刻意绑定本机产物**。这是设计，不是缺陷，也不得“修复”：

- `scripts/build_twinkle_stage5_h2_full_flow_review.py` 的 `EXPECTED_HASHES` 硬 pin 7 个文件的 SHA256，其中 **5 个是未跟踪的本机产物**：`output/twinkle-stage5-formal-model-motion-candidates/work/two-component-asset-contract.json`、同目录 `model-motion-manifest.json`、`output/playwright/twinkle-stage5-lowres-mapping-review.html`、`.superpowers/brainstorm/936-1788488553/content/generated-rail-push-motion-v18.html`、`output/twinkle-stage5-blender-product-film/preview-v2/dip-to-black-loop-v2/dip-to-black-loop-review.mp4`。
- `scripts/build_twinkle_stage5_a192_full_sequence.py` 的 `_protected_snapshot()` 同样按 sha256 快照两个本机 pilot 测试文件；因此它在 clean checkout 上会抛 `FileNotFoundError`，这是设计使然。
- 仓库已有守卫：`tests/test_twinkle_stage5_h2_portability.py::test_sha_bound_authorities_are_stored_verbatim_in_git` 只校验 `EXPECTED_HASHES` 中以 `scripts/` 开头的部分，主动排除本机产物；`test_sha_bound_core_authorities_disable_checkout_eol_conversion` 则保证这些文件的字节不被 checkout 行尾转换改写。

**因此这些脚本与 manifest 只能在本机工作树内运行。修改它们会使上述守卫测试失败，并让已归档的 H2 证据包无法逐字节复现。**

## 6. 关键资源地图

| 资源 | 用途 | 权威性质 |
|---|---|---|
| `AGENTS.md` | 仓库常驻工程规则 | 最高仓库级权威 |
| `docs/ENGINEERING_PLAYBOOK.md` | 规则执行方法、模板和验证矩阵 | 通用流程权威 |
| `PROJECT_SPEC.md` | 内部化工工作台长期产品与安全边界 | 产品约束 |
| `materials_catalog.json` | 批准资料清单 | 资料单一事实源 |
| `docs/MATERIAL_EXPANSION_RUNBOOK.md` | 已验证的资料扩展、索引切换和回滚流程 | 运行手册 |
| `docs/UI_STYLE_GUIDE.md` | Streamlit 工作台界面契约 | UI 权威 |
| `docs/SHOWCASE_UI_STYLE_GUIDE.md` | 公开展示前台视觉、内容和来源规范 | UI/内容权威 |
| `docs/adr/0001-public-showcase-product-transition.md` | 双产品隔离决定 | 已接受 ADR |
| `docs/superpowers/specs/2026-08-20-twinkle-page-coordinated-render-design.md` | TWINKLE 阶段 1–5 设计、人工门禁和阶段边界 | TWINKLE 设计权威 |
| `registry/twinkle/stage5-runtime-assets.json` | 248 张正式 runtime 资产的路径、哈希和字节数 | 运行资产权威 |
| `registry/twinkle/stage5-h2-evidence-receipt.json` | 外部 H2 evidence bundle 收据 | 证据定位与完整性权威 |
| `tests/fixtures/golden_retrieval_cases.json` | 检索正向 golden cases | 检索验收证据 |
| `tests/test_twinkle_stage*.py` | TWINKLE 各阶段契约、事务、失败和回滚测试 | 可执行行为证据 |

## 7. 开发模式

### 7.1 小步、证据优先

- 一次变更只解决一个清晰问题；
- 先建立失败案例或可执行验收，再写最小实现；
- 大型重构与 Feature/Bug 分开；
- 新依赖必须说明现有方案为何不足、维护状态、许可证、成本和回退方式；
- 不预建没有当前调用方的抽象、服务或第二套事实源。

### 7.2 疑难问题升级

一次有界诊断仍不能确定根因或下一项有效验证、同一路径连续失败两次，或问题涉及陌生技术/外部集成/成熟通用能力时，停止猜测性补丁。按顺序检查：

1. 仓库已有代码、测试、配置和 Git 历史；
2. 适用版本的官方文档、参考实现、变更记录和上游问题；
3. 维护良好的开源实现和行业模式；
4. 用固定失败案例做最小适用性验证。

只有证据证明成熟方案不适用、不足或成本不可接受，才允许编写最小自定义实现。

### 7.3 人工批准点

下列操作不能由 Agent 自行推定授权：

- 新页面或明显用户流程变化；
- 新数据库、索引、模型、外部服务、权限或安全边界；
- 数据迁移、正式索引切换、外部发送、发布、部署或线上覆盖；
- TWINKLE 的人工视觉选择、阶段关闭和下一阶段启动；
- 删除归属不明、不可恢复或混合目录中的资产。

批准必须记录具体对象、范围、条件和回滚。前一阶段“继续”不等于扩大范围。

## 8. 验证模式

最低验证以 `docs/ENGINEERING_PLAYBOOK.md` 的矩阵为准：

| 变更 | 最低证据 |
|---|---|
| 纯文档 | 文件、链接/术语、范围和 Git 差异 |
| 业务逻辑 | 新测试、相关测试、全量测试 |
| UI | 自动化测试、真实浏览器正负路径、关键交互 |
| 模型/RAG | 固定 golden、真实模型调用、证据门禁负例 |
| PDF/文件 | 解析、真实页面、路径和元数据 |
| 数据/索引 | 预检、暂存构建、完整性、切换、失败保持和回滚 |
| 外部集成 | 受控目标、错误路径、权限和重复调用安全 |

判断“默认 `pytest` 是否与 clean checkout 等价”时，**唯一权威方法是逐文件干净克隆运行**，不得用静态代码扫描替代：正则匹配 `output/`、`showcase/` 会漏掉 `Path(...) / "output" / ...` 这类分段写法与 `.superpowers` 间接路径。干净克隆时可用 `GIT_LFS_SKIP_SMUDGE=1` 作为更严格条件，能同时证明测试不依赖 LFS 二进制资产。

常用基础验证：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q tests\test_twinkle_stage5_homepage.py tests\test_twinkle_stage5_packaging.py
.\.venv\Scripts\python.exe -m pytest -q tests\test_twinkle_stage5_h2_portability.py
git diff --check
git status --short
git lfs status
```

严格 H2 外部证据验证使用显式 evidence root；具体参数以脚本当前 `--help`、测试和 receipt 为准：

```powershell
.\.venv\Scripts\python.exe scripts\build_twinkle_stage5_h2_full_flow_review.py --help
```

历史测试记录只能称为历史基线。声称通过前必须在当前工作状态重新运行足以证明结论的命令，并报告退出码、失败、跳过和未运行项。

## 9. 接管清单

### 9.1 开始工作前

- [ ] 用 Git 注册记录确认目标 Worktree、分支和根目录；
- [ ] 读取当前 checkout 的 `AGENTS.md` 和适用工程手册；
- [ ] 检查并理解 `git status --short` 的每一类改动；
- [ ] 若有 `CURRENT_WORK.md`，先通过卫生 checker 并核验目标、批准与唯一下一动作；
- [ ] 确认任务属于内部证据工作台、公开展示前台或 TWINKLE，不跨边界顺手改造；
- [ ] 写明范围、非目标、验收证据、停止条件和回滚；
- [ ] 对长任务或高风险任务先建立合规 `CURRENT_WORK.md`；
- [ ] 对界面、视觉、数据、外部系统或下一阶段变更取得必要人工批准。

### 9.2 TWINKLE 专项接管

- [ ] 阅读 TWINKLE 设计规格中当前阶段，而不是仅依赖历史聊天；
- [ ] 核对 `registry/twinkle/` 中 runtime、来源 manifest 和 evidence receipt；
- [ ] 使用 `git lfs ls-files` 确认 248 张正式 runtime PNG 已物化；
- [ ] 区分 Git 内可复现契约、正式运行资产、外部 evidence bundle 和临时实验资产；
- [ ] 不把机器通过解释为人工视觉批准；
- [ ] 不把阶段关闭解释为下一阶段、提交或发布授权；
- [ ] 未确认归属前不清理 `output/`、`.superpowers/`、Playwright 或 Blender 产物；
- [ ] clean-checkout 测试与严格外部 evidence 验证分别报告，不能相互冒充。

### 9.3 完成或跨会话前

- [ ] 运行当前工作状态上的新鲜验证；
- [ ] 检查 Git 差异、未跟踪文件、LFS、凭据和生成物；
- [ ] 更新 `CURRENT_WORK.md` 的权威状态、批准、临时产物和唯一下一动作；
- [ ] 若任务完成，把长期价值迁移到代码、测试、必要 ADR 或已验证 runbook；
- [ ] 完成长任务后删除 `CURRENT_WORK.md`，不保留历史状态副本；
- [ ] 未经明确授权不提交、推送、创建 PR、发布或部署。

## 10. 常见误区

- 把主仓或另一个 Worktree 的 `AGENTS.md` 当成当前 checkout 权威；
- 因为 `CURRENT_WORK.md` 看似属于别的任务而跳过卫生 checker；
- 根据目录名推断 `output/`、缓存或测试产物可以删除；
- 把未跟踪文件自动视为当前任务成果或待提交文件；
- 只看到静态页面能加载，就宣称完整 TWINKLE 流程可复现；
- 把历史 SHA、截图或测试记录当成本轮新鲜验证；
- 把外部 evidence 缺失处理为“通过”；
- 为解决可移植性问题把数百 MB 审核闭包写入普通 Git；
- 扩大 LFS 为全仓 PNG，或把 LFS pointer 当作已物化资产；
- 通过降低断言、删除测试、吞异常或无界重试制造表面成功；
- 用聊天交接代替 `CURRENT_WORK.md`，或用永久文档记录活动任务流水；
- 用静态正则或目录名判断测试能否在 clean checkout 运行，而不做逐文件干净克隆验证；
- 试图“修复”机器本地 SHA-pinned 证据链中的脚本或其中看似悬空的引用（会破坏守卫测试并使已归档证据不可复现）。

## 11. 接管后的第一个安全动作

没有活动 `CURRENT_WORK.md` 时，先做只读现场审计：确认目标分支、HEAD、与主分支关系、工作树差异、LFS 状态、外部资料/证据可用性和相关测试入口。只有能够解释现有差异，并确定任务范围和验收证据后，才进入修改。

存在活动 `CURRENT_WORK.md` 时，先核验其中目标、分支、工作树、关键文件、批准条件和唯一下一动作；一致后执行该唯一下一动作，不重新发明路线，也不扩大授权。
