# Current Work: TWINKLE 光学收集模块 Blender 流程样机

Status: active
Started: 2026-08-07
Branch/Worktree: `main` / `F:\半导体材料产品展示`

## Objective

在睿扬真实产品资料暂不充分的前提下，先审计 TWINKLE 开源双光子显微系统光学收集模块的实际下载包、CAD 层级、格式、单位、外部引用、许可和 Blender 转换可行性。审计通过并获得用户批准后，才制作明确标注为“基于开放光学系统资料制作的流程样机”的 Blender 技术演示资产。

## Scope

- 只执行 `docs/superpowers/plans/2026-08-07-flagship-product-blender-asset-production.md`。
- 当前阶段只做计划 Task 1 的资料与 CAD 审计。
- 形成“采用 / 有条件采用 / 不采用”报告及证据。
- 用户批准前不进入 Blender 建模、材质、动画或渲染。

## Non-goals

- 不把 TWINKLE 样机宣称为睿扬产品，不添加睿扬 Logo。
- 不推测下载包中存在 STEP、完整可拆分装配或可直接导入 Blender 的结构。
- 不自动切换到 OpenFlexure。
- 网站、网页交互、GLB/WebGL 接入和部署继续暂停。

## Acceptance Evidence

- 实际下载包的来源、许可、文件格式、单位、装配层级、外部引用和转换结果逐项可核验。
- 转换后分件完整性与丢失内容有明确清单。
- 报告明确给出采用结论、限制、风险、回退方案和需要人工批准的下一步。

## Stop Conditions

- 下载、许可或文件内容无法合法、可靠核验时停止。
- CAD 层级或转换结果不足以支撑流程样机时停止并报告，不用猜测补齐。
- 到达 Task 1 审计结论后停止，等待用户批准。

## Next Action

审查 TWINKLE 实际下载包、CAD 层级与格式、转换后的分件完整性及许可归属，形成“采用 / 有条件采用 / 不采用”报告；用户批准前不进入 Blender 建模。
