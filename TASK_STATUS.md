# Chemical Trade AI Copilot 任务状态

## 当前阶段

阶段一：资料与最小可行性验证（已完成并推送）。

当前会话进入交接收尾，不执行阶段二代码。下一开发会话从阶段二“可信 RAG 核心”开始。

## 已完成并验证

- 已完整读取参考会话 `019fa403-480a-73f2-99ce-3d97a9275c9b` 的最新权威基线，并在发现越界后撤回阶段二代码。
- 已在 `F:\外贸化工` 初始化 Git `main` 分支，并配置远程 `https://github.com/lujiamingsssss-cpu/CHEMISTRY.git`。
- 已安全读取 `G:\桌面\化工外贸api.md` 并验证 DeepSeek 鉴权；密钥未写入项目。API 当前返回 `deepseek-v4-flash`、`deepseek-v4-pro`。
- 已盘点和渲染检查资料目录全部初始 PDF；均可提取文本，无扫描件阻塞。
- 已更正 `Acclaim® 4200N` 为 `Acclaim® 4220N`。
- 已将错误重复的 `Desmodur® I` 移到 `_excluded`。
- 已用 2020 英文 SDS 替换 D.E.R. 331 的 2001 MSDS；旧文件保留在 `_excluded`。
- 已新增 EPON Resin 8280 的完整 TDS/SDS 组。
- D.E.N. 438 只有 2026 SDS，独立 TDS 需要账号，已放入 `_excluded`，不进入索引。
- 正式白名单现有 4 份 PDF、36 个非空物理页：
  - D.E.R. 331：TDS 5 页、SDS 13 页；
  - EPON Resin 8280：TDS 5 页、SDS 13 页。
- 已实现显式白名单发现、TDS/SDS 成对校验、PyMuPDF 页级抽取、页内分块、本地 E5、Chroma 持久化及 ingest/query CLI。
- 白名单同时在资料发现层和 CLI 层强制执行；CLI 不提供产品覆盖参数，并拒绝根目录外或未审批产品。
- 真实模型索引已动态建立；明确英文询盘可命中 `TDS - Hexion EPON Resin 8280 - Rev 2016.pdf` 第 3 页。
- 技术调研采用成熟组件：Sentence Transformers、Microsoft E5、Chroma、LangChain text splitters；未自建向量算法。

## 剩余收口事项

阶段一无剩余事项。阶段性交接文档 `HANDOFF.md` 已建立；本轮仅提交和推送文档更新。

## 人工检查点

- 产品和 TDS/SDS 对应关系原本是阶段一人工停止点；用户已明确授权本会话代为完成资料操作。已通过产品名、文档类型、页数、哈希、文本提取和页面渲染复核完成。
- 下一人工检查点是阶段三 UI 审批；阶段一结束后不自动触发。
- 阶段四需要人工抽查推荐、参数、页码和邮件。

## 最近状态

- 自动化测试：2026-07-27，最终运行 `9 passed in 5.80s`。
- 依赖检查：2026-07-27，`pip check` 返回 `No broken requirements found`。
- 真实动态验证：2026-07-27，精简版成功建立 4 文档、36 个非空页的索引；询盘 `EPON Resin 8280 heat deflection temperature MPDA cure schedule` 的第 1 名为 `TDS - Hexion EPON Resin 8280 - Rev 2016.pdf` 第 3 页。
- Git 提交：阶段一实现提交 `62e6c9a`（`feat: complete phase one retrieval validation`）。
- Git 推送：2026-07-27，已成功创建并推送远程 `origin/main`；本状态更新作为同轮交付收尾提交，最终哈希以 Git 历史为准。
- 交接提交：2026-07-28，`e169881`（`docs: add phase one handoff and refresh baseline`）已推送；其后的状态收尾提交以 Git 历史为准。
- 云端验证：交接提交已到达 GitHub `main`；状态收尾提交后再次核对本地与远程 HEAD。

## 当前风险与非阻塞问题

- 宽泛中文询盘对英文 TDS 的召回尚不稳定，必须由阶段二 golden cases 驱动改进。
- top-k 未召回不能被解释为原始资料不存在。
- PDF 表格中的参数与固化条件可能跨块，生成前必须校验条件绑定。
- 当前没有环境、API、资料或 Git 授权阻塞。

## 下一轮继续位置

阅读 `HANDOFF.md` 和更新后的 `PROJECT_SPEC.md`，从阶段二开始。第一步是建立固定中英文检索案例及目标页并测量当前 Hit@K；不得直接恢复本轮被撤回的查询改写或生成输出，也不得直接进入 Streamlit。
