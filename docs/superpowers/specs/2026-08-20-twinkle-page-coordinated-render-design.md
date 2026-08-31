# TWINKLE 产品探索器设计规格

## 1. 权威与目标

本文件保存截至阶段 3 的唯一长期设计规格。2026-08-25 用户批准并收口阶段 1；2026-08-26 用户因效果不佳取消并收口阶段 2，禁止恢复绿色/红色滤片路线；阶段 3 最终采用 `lossless-png-sequence`，以获批 Exact-Boolean linefix 画面和单自由度 motion-only 机械运动生成正式成对 PNG，并经人工终验收口。兼容矩阵为 Chrome 151、Chrome for Testing 150、Edge 151；Edge 150 未验证且不得宣称支持。后续阶段仍需独立授权。

用户是希望在本地测试站理解 TWINKLE 结构和光学价值的潜在客户。产品探索器采用有限总览环绕、热点发现、专属聚焦、锁定相机下的展示性抽离和按需讲解；不实现任意角度实时 WebGL，也不把展示动画宣称为维修路线或碰撞验证。

两个正式热点不使用 J/F 业务代号：

| 中文名称 | 稳定语义 ID | 设计权威 |
|---|---|---|
| 双通道采集光学舱 | `dual_channel_collection_optics_chamber` | Codex 会话 `01a02ff9-18a2-7da3-a250-12dc45e86ff9` 的人工裁决，以及迁移前 `.twinkle-bottom-side-simultaneous-stable-light-20260824` manifest |
| 聚光镜组件 | `dual_channel_condenser_lens_assembly` | 本规格、阶段记录，以及稳定参考 `scripts/assets/twinkle_condenser_legacy_reference.png`（SHA-256 `12364CBBE6AA9F9AC0A382530506A5B16236AFDF55910D3EEB05A01481A8DC0A`） |

冻结 `.blend` 中的 `SHOWCASE_GROUP__f_dual_acl_housing` 只作为 `legacySourceObjectId` 留在解析边界；页面、阶段、正式文件名、manifest 业务键和测试不得继续使用 J/F 指代热点。

## 2. 范围与非目标

阶段 1 范围：锁定两个具名热点的最终观察机位、机械抽离扫掠、统一模型/灯光/材质/色彩管理规则、正式七帧和人工审核材料；迁移有效证据后清理阶段 1 独占临时控制面。

阶段 1 非目标：内部滤片示意、闭合路线、A/B 聚焦路线、交互样本、生产页面集成、部署、发布、任意角度旋转、材质重建、商业黑盒内部结构、精确未核验型号和维修指导。

所有源/候选 `.blend`、许可和来源资料、阶段 1 前冻结链、Permission Denied 或混合归属目录均保持不动。非活动链在阶段 8 只读形成清算清单，阶段 9 仅执行用户逐项批准的清算。

Streamlit 不属于本 TWINKLE 设计的功能开发范围；TWINKLE 不修改、停用或重新解释既有 Streamlit 业务流程。其现有测试保持仓库默认行为并继续参与全量回归。TWINKLE 生产页面入口的占位交互仅在对应页面集成阶段另行验收，不以跳过或标记整个 workbench 为 inactive 的方式隔离。

## 3. 阶段 1 统一渲染契约

### 3.1 唯一模型

- 源模型：由操作者在运行时提供；必须先通过下述 SHA-256 门禁。
- 源 SHA-256：`5458C6A3033DF6D1CFD3CAD4B11F3A7DF69BB278D3EE7853767B96E412E7AF81`
- 唯一正式渲染模型：由操作者在运行时提供；必须先通过下述候选 SHA-256 门禁。
- 候选 SHA-256：`584EBB7F8F5F5CAEB7AF469DBF02A465DE7016D67A9D64539A018E9F6DDD4FD6`

两个热点必须由 `scripts/build_twinkle_route1_camera_board.py` 在同一次受控批次生成，不得按热点调用独立渲染器。

### 3.2 共享 render profile

- Blender 5.2.0 LTS、Eevee、1280×900、PNG、`taa_render_samples=512`。
- AgX、AgX Medium High Contrast、Exposure `-1.6`、Gamma `1.0`、非透明背景。`-1.1/-1.35/-1.6` 同条件包围及 Khronos PBR Neutral 对照后，`-1.6` 能显著压下银白高光且聚光镜组件暗部仍可读。
- 场景灯：`WS_Key_Softbox`、`WS_Fill_Softbox`、`WS_Rim_Light`、`WS_Front_Bounce`。
- 共享技术灯：10 W / 0.10 m / `[0.34,0.48,0.48]` 与 3.5 W / 0.14 m / `[0.24,0.66,0.52]`；两灯均瞄准采集光学舱锁定 target，但在全部七帧保持同一位置、能量和方向。12 W + 5 W 版本经人工审核确认银白底板与圆环过曝；8 W + 2.5 W、10 W + 3.5 W、11 W + 4 W 同条件包围测试后选择中档，以保留高光和暗部层次。
- 共享可见性规则：全部七帧隐藏 `WS_Studio_Floor`，渲染后恢复；不得作为某一热点专属分支。
- 共享材质规则：`DetectBoxTopPlate :: 实体1` 在全部七帧使用运行时材质副本，把唯一 Normal Map strength 从 `0.08` 设为 `0`；渲染后恢复原槽并删除副本。
- manifest 每帧记录相同 `modelSha256`、`renderBatchId`、`renderProfileId`、`lightRigHash`、`materialRuleHash` 和 `colorManagementHash`。

允许不同的只有两个热点各自获批的相机位姿、焦距、target 和获批机械对象矩阵。

七张基础帧继续共享上述 profile。采集光学舱讲解终态另有一张已批准的内部检查灯资产：真实 Blender Area 灯只生成独立照明通道，锁定机位暗部遮罩只把内部增量合回基础终态，遮罩外像素必须保持不变；该资产不改变七张基础帧的 `renderProfileId`。

## 4. 双通道采集光学舱

- 相机 ID：`collection-optics-chamber-side-underside`。
- location `[0.411294,0.420016,0.371682]`；target `[0.285227,0.622304,0.585193]`；55 mm；sensor 36 mm；shift `[0,0]`。
- 底盖根对象：`DetectBox_Bottom_Mala2020:1`，沿 `-Z` 完整移动 `0.14 m`。
- 侧板根对象：`Side2_optics:1`，沿 `-Y` 完整移动 `0.10 m`。
- 两对象从同一时刻开始，使用同一归一化进度，不旋转、不先后错开、不使用 `hide_render`。
- 相机到位停稳后保持 200 ms；用 240 ms 走到 6% 接缝状态；随后用 760 ms 同步加速并平滑减速到终点。
- 6% 时底盖移动 8.4 mm、侧板移动 6 mm，两者都满足“沿法线先脱离 5–10 mm”的压缩表达。
- 讲解面板固定写：“紧固件解除后，底盖/侧板沿法线移开。”不演示逐颗紧固件拆卸。
- 四张审核帧：`focused-settled`、`fasteners-released-seam`、`extract-mid`、`extract-end`。
- 讲解终态内部灯：Area `10 W`、size `0.11 m`，相机相对偏移 `[-0.012,0.008,0.250] m`，aim depth `0.115 m`；进入 `900 ms`、保持 `500 ms`、退出 `700 ms`。遮罩只接收原图近黑内部表面，外壳像素保持基础帧。
- 中心 `mirror 3` 身份保持 `REFERENCE_ONLY`；阶段 1 只批准整个“双通道采集光学舱”热点，不宣称该件精确型号。

## 5. 聚光镜组件

- 相机 ID：`condenser-lens-front-hero-right-15mm`。
- location `[0.43536043,0.3241443,0.56380999]`；target `[0.45065495,0.62336338,0.57699472]`；72 mm；sensor 36 mm；shift `[0,0.02]`。该位姿是旧机位和 target 沿相机右向量共同平移 `15 mm`，用于消除板边多零件投影遮挡。
- 根对象：`SHOWCASE_GROUP__f_dual_acl_housing`；展示位移 `[0.034,0.012,-0.016] m`。
- 三张审核帧：`focused-settled`、`extract-mid`、`extract-end`，空间进度 0%、50%、100%。
- 旧人工批准三帧只作为构图和主体感参考，SHA-256：
  - `F60DE02B9A9612036FBDAB7E4EF35792CD2F20F59D47565CAE72D6D444BF837D`
  - `2B886A06E115F410582A7E1CA45F751CEB5D6D4A44E00A758754D5470DA20C34`
  - `BD605CD7018B9505B0394623D1858428926CE5580E0F4A3764A28342240D1FBC`
- 统一重渲染必须在新旧对照中保持蓝色光学面、黑色前箱、连接面、主体占幅和终点间隙可读。
- 聚光镜组件不启用检查灯。首候选的 FFmpeg `removelogo` 位图遮罩只保留为失败基线；唯一返修固定使用右侧银板临时网格副本 limited dissolve、独立临时材质、真实 `FrontCover`/`Side1` CAD 遮挡组随动和 Blender 原生 F-Curve，不再使用像素后处理。所有临时网格、材质、Action 和父子关系必须在退出前恢复或删除，候选 `.blend` 不得保存。

## 6. 正式资产与阶段 1 门禁

正式目录固定为 `output/twinkle-route1-camera-board-r1-1`，准确包含：七张基础 PNG、采集光学舱一张内部灯 PNG、`camera-board-manifest.json`、七帧联系表、聚光镜组件新旧对照表和内部灯前后对照表。三张审核表均须把文件名和 SHA-256 写入 manifest。不得包含 GIF、遮罩、原始灯通道、FFmpeg 中间帧、HTML、`.blend`、临时测试、临时设计或缓存。

机器门禁：七帧同批同 profile；语义 ID 准确；双板矩阵同步；源/候选哈希不变；图片 1280×900 且哈希匹配；正式库存准确；场景相机、渲染设置、可见性、对象矩阵、材质槽、临时灯和临时数据块全部恢复；无残留 Blender 进程。

人工门禁：采集光学舱四态清楚表达原位、接缝、同步移动和终态；内部灯只增亮内部且外壳保持基础亮度；聚光镜组件不比旧批准构图退化且无黑边/细痕；两个热点的基础光感、材质、背景和阴影规则一致。2026-08-25 用户已通过该门禁；manifest 必须记录批准来源、仅限阶段 1 的范围，以及阶段 2/部署/发布均未授权。

## 7. 固定阶段线路

| 阶段 | 任务 | 交付后停止点 |
|---|---|---|
| 0 | 整合规格冻结 | 冻结唯一规格、名称、来源映射、线路和审核点 |
| 1 | 双通道采集光学舱／聚光镜组件终点机位与抽离扫掠 | 七帧、统一 profile、清理报告和人工审核材料；等待用户批准 |
| 2 | 内部滤片示意 | 用户主动取消并跳过；不生成绿/红候选，不设置审核点 |
| 3 | 两热点动作与素材契约 | 只处理阶段 1 已批准两热点；按步骤 1–7 完成暂停恢复、展开/闭合素材和人工终验；等待阶段 4 另行授权 |
| 4 | 两热点聚焦路线 A/B 选择 | 只比较双通道采集光学舱／聚光镜组件；等待路线选择 |
| 5 | 生产等效本地交互样本 | 第 1 步统一制作阶段 1 两热点共用的网页讲解层；随后完成本地样本与交互证据；等待批准 |
| 6 | 生产页面候选集成 | 只接入阶段 5 已批准的双热点讲解层和阶段 1 资产；等待批准 |
| 7 | 生产页面人工终验 | 只复核生产候选，不扩大功能、不清理资产 |
| 8 | 非活动链清算清单与逐项批准 | 只读精确清单；等待用户逐项批准 |
| 9 | 执行获批清算并完成收口 | 只执行获批项，完成新鲜验证和长期约束迁移 |

一次人工回复默认最多批准一个阶段。当前阶段、交付物和获批范围不一致时立即停止。

## 8. 阶段 2 取消与双热点边界

### 8.1 当前决定

2026-08-26 用户明确取消绿色滤片与红色滤片的低清候选、正式资产和页面讲解，不再执行原阶段 2 内部滤片路线。阶段 2 视为主动跳过，不设绿色/红色人工审核点，也不得生成 `candidate-03`、红色候选、正式滤片图或任何替代技术插图。

后续产品探索器只讲解阶段 1 已审核通过的两个热点：

- 双通道采集光学舱：`dual_channel_collection_optics_chamber`；
- 聚光镜组件：`dual_channel_condenser_lens_assembly`。

绿色/红色滤片不得成为页面热点、子状态、控制按钮、图片资产或独立讲解条目；旧 J/F 业务代号仍不得回到用户可见界面。

### 8.2 权威资产

两个热点继续只使用阶段 1 正式目录 `output/twinkle-route1-camera-board-r1-1`、其 `camera-board-manifest.json`、七张基础 PNG、采集光学舱内部灯 PNG 和已记录人工批准。阶段 1 的稳定语义 ID、名称、相机、render profile、来源/许可、商业黑盒边界与恢复审计继续有效。

阶段 2 生成器、测试和研究候选不属于产品资产，不得被生产页面、阶段 3–7 或正式 manifest 引用。两张绿色失败候选只证明被取消路线的实验事实，不构成视觉基线、人工批准或未来红色实现入口。

### 8.3 后续阶段

- 阶段 3 的闭合展示与展开承接只处理上述两个阶段 1 热点。
- 阶段 4 的路线选择只比较上述两个热点的聚焦路线，不增加内部滤片分支。
- 阶段 5 第 1 步统一制作网页讲解层，只为“双通道采集光学舱”和“聚光镜组件”提供一致的状态标题、说明正文、来源/非维修边界和无障碍状态反馈；整体视图只保留中性状态提示，不增加第三个热点讲解。
- 阶段 6 只把阶段 5 已批准的双热点讲解层和阶段 1 视觉资产接入正式页面，不重新设计，不接入任何滤片候选。
- 阶段 7 只人工终验这两个热点；阶段 8/9 再按逐项授权处理非活动链清算。

每次人工回复仍默认最多批准一个阶段；取消阶段 2 不自动授权阶段 3、阶段 5、生产页面修改、发布或部署。

### 8.4 阶段 2 已收口

2026-08-26 用户批准提前退役归属明确的取消路线产物。`scripts/build_twinkle_stage2_filter_detail.py`、`tests/test_twinkle_stage2_filter_detail.py` 和 `output/.twinkle-stage2-filter-camera-study-r1-active` 已移入 Windows 回收站：共 5 个文件、669,726 bytes，可在回收站保留期内还原。清理未触碰阶段 1 正式资产、Permission Denied 目录、来源/许可资料或其他任务改动。

退役后，阶段 1 两热点相关测试与 TWINKLE 活动回归均退出 0，阶段 1 正式 manifest SHA-256 保持 `8DB0B2055838FA69C6381719587A99A2B132FE526F40EA6F0C231264AD908378`，且无 Blender/FFmpeg 残留。阶段 2 因用户取消而正式收口；不得恢复旧测试、生成器、候选或滤片状态，除非用户重新批准范围和设计。

### 8.5 阶段 3：两热点动作与素材契约

#### 8.5.1 当前阶段位置与七步实施计划

阶段 3 必须使用以下七步编号；SDD、审核材料和状态报告不得使用另一套编号或把后续步骤提前记为完成：

1. **审计现有资产与旧契约**：列明可复用、必须废弃、仅供参考和缺失内容，等待用户确认。2026-08-26 用户已确认该清单；旧 motion sample、旧 prototype 和历史页面文件不因契约废弃而自动删除。
2. **完善阶段 3 SDD/TDD**：把本节状态、素材、人工视觉门禁、停止条件、复杂度上限和 RED–GREEN 路径写入唯一 SDD，并等待用户批准书面版本。2026-08-26 用户已批准本节书面版本；该批准只允许按后续步骤逐步执行，不替代步骤 3–7 的独立人工门禁。
3. **视频与图片序列可行性实验**：提交细节对照与 Windows 11 Chrome/Edge 当前及前一稳定主版本的真实兼容证据，决定 H.264/MP4 或无损 PNG 图像序列；等待用户确认格式裁决。
4. **双通道采集光学舱低清动作候选**：人工检查展开、闭合、暂停恢复和检查灯；等待批准。
5. **聚光镜组件低清动作候选**：人工检查展开、闭合、暂停恢复和画风一致性；等待批准。
6. **生成阶段 3 正式动作素材**：机器验证后制作正式人工审核材料；机器通过不得记作人工通过。
7. **阶段 3 人工终验与收口**：只有用户明确通过后才收口；随后停止，等待阶段 4 另行授权。

任何一步到达停止点后不得自动进入下一步。步骤 3 的格式裁决、步骤 4/5 的低清视觉批准、步骤 6 的机器通过和步骤 7 的阶段人工终验是不同批准对象，不得互相替代。

#### 8.5.2 步骤 1 审计裁决

**可复用权威**：

- `output/twinkle-route1-camera-board-r1-1` 的 12 个阶段 1 正式文件；manifest SHA-256 为 `8DB0B2055838FA69C6381719587A99A2B132FE526F40EA6F0C231264AD908378`。
- 两个正式语义 ID：`dual_channel_collection_optics_chamber`、`dual_channel_condenser_lens_assembly`。
- 阶段 1 的无损端点 PNG、固定相机、对象矩阵、共享 render profile、灯光/材质/色彩管理、采集光学舱检查灯 PNG 及恢复审计。
- `scripts/build_twinkle_route1_camera_board.py` 与 `tests/test_twinkle_route1_camera_board.py` 已验证的哈希保护、场景恢复、准确库存和原子发布模式。
- 源 `.blend` SHA-256 `5458C6A3033DF6D1CFD3CAD4B11F3A7DF69BB278D3EE7853767B96E412E7AF81`；唯一正式渲染候选 SHA-256 `584EBB7F8F5F5CAEB7AF469DBF02A465DE7016D67A9D64539A018E9F6DDD4FD6`。

**必须废弃的契约**（仅表示不得继承为阶段 3 权威，不授权删除文件）：

- 旧 motion sample 的 `j_green_filter_subassembly`、`f_dual_acl_housing`、J/F 用户语义和旧 `experiment-manifest.json` 权威入口。
- `returnPath.direction=reverse` 作为公开反向能力、`loop=0` 无限 GIF、自动展开—闭合循环、展开完成后自动返回。
- 旧 prototype 的 `overview/focusing/focused/returning` 顶层状态、动作中点击/反向/跨热点切换/排队及 `activeTimeline` 存在时简单拒绝交互的行为契约。
- 旧页面中的滤片热点、J/F 控件/讲解、阶段 2 绿色或红色失败候选，以及“闭合后恢复进入热点前环绕状态”的设想。

**仅供参考**：

- 旧 motion sample 的单调 progress、smoothstep 采样、场景复位、联系表和输出存在时拒绝覆盖的工程模式；其画面、对象、状态和正式库存不得复用。
- 旧 prototype 的时间轴暂停/继续技术模式；其实时 WebGL 路线、状态、热点身份和 UI 不得继承。
- 阶段 1 联系表、历史视觉样片和历史“镜头先稳定、机械后展开、闭合后回总览”研究，用于防止视觉退化和为阶段 4 提供路线参考。
- W3C Web Animations、WCAG G4/2.2.2、WHATWG media 与 FFmpeg 官方资料，分别作为时间保持、暂停恢复、媒体播放和编码候选依据；本项目帧数、采样数、CRF 和返修次数仍是项目有界参数，不冒充行业标准。

**当前缺失**：阶段 3 生成器/专项测试、格式实验与四浏览器证据、两个低清候选、正式动作素材/manifest/审核材料、阶段 4 聚焦路线，以及步骤 2–7 各自的后续人工批准。

#### 8.5.3 三状态与控制契约

顶层状态严格互斥，任一时刻恰有一个：

- `global`：全局展示；内部 `globalOrbit` 为 `running` 或 `paused`。
- `action`：当前热点的局部动作；内部 `actionPhase` 为 `focus`、`expand`、`close` 或 `overviewReturn`，`actionPlayback` 为 `running` 或 `paused`，`progress` 位于 `[0,1]`。
- `explanation`：热点完全展开且稳定，显示讲解并等待用户返回。

阶段 3 只为 `focus` 和 `overviewReturn` 定义可暂停的局部时间轴接口，不生成镜头素材；阶段 4 选择路线后填充这两个 segment。阶段 3 实现范围只包含机械 `expand/close` 素材与检查灯交接。

除模型上的热点外，以下五个按钮在三个顶层状态始终显示，不能通过隐藏改变布局：

1. 双通道采集光学舱名称按钮；
2. 聚光镜组件名称按钮；
3. 一个全局展示切换按钮，文案在“暂停展示／开始展示”之间切换；
4. 一个局部动作切换按钮，文案在“暂停动作／继续动作”之间切换；
5. 底部“返回”按钮。

| 顶层状态 | 模型热点 | 两个名称按钮 | 全局展示切换 | 局部动作切换 | 返回 |
|---|---|---|---|---|---|
| `global` | 显示且可触发 | 可触发 | 可用；按环绕状态显示“暂停展示”或“开始展示” | 显示“暂停动作”且禁用 | 显示且禁用 |
| `action` | 隐藏 | 显示且禁用 | 显示且禁用 | 唯一可用控件；运行时“暂停动作”，暂停时“继续动作” | 显示且禁用 |
| `explanation` | 隐藏 | 显示且禁用 | 显示且禁用 | 显示“暂停动作”且禁用 | 显示且可用 |

用户在 `global/running` 或 `global/paused` 均可通过模型热点或名称按钮选择热点。进入 `action` 时全局环绕冻结；局部暂停必须保持同一 `progress` 和原方向，继续只能从同一进度沿原方向运行。当前需求不包含中途反向、动作中热点点击、跨热点切换、排队或竞态分支；这些事件在 `action`/`explanation` 因控件禁用而不可发生。

采集光学舱的展开完成后先执行阶段 1 已批准的检查灯 `900 ms` 渐入；灯完全稳定后才进入 `explanation`，并持续点亮到用户点击返回。返回后必须先等待阶段 5 讲解层发出 `detailExited` 交接事件，再执行检查灯 `700 ms` 渐出，随后才开始机械闭合。聚光镜组件没有检查灯，展开终态稳定后直接进入 `explanation`。

机械闭合完成后，经阶段 4 `overviewReturn` 接口返回总览；最终一律进入 `global/paused`，不得自动恢复环绕。用户必须点击“开始展示”才能恢复。

`prefers-reduced-motion: reduce` 或动作素材加载/播放失败时，不播放聚焦或机械位移，改用短淡入淡出在阶段 1 无损闭合/展开 PNG 之间切换；仍使用相同三个顶层状态、按钮矩阵、讲解和返回流程。静态回退不得伪造动作播放成功证据。

#### 8.5.4 素材格式可行性门禁

阶段 3 不预先批准视频为正式格式。步骤 3 必须先执行一次有界实验：

- 从阶段 1 聚光镜组件三张正式无损 PNG 组成一段细节压力候选，因为该组同时包含蓝色光学面、细小颜色边缘、黑色前箱、银白板、金属高光和暗部。
- 只允许一组 H.264/MP4 候选参数：1280×900、24 fps、无声、`libx264`、`preset=slow`、High profile、CRF 10、`yuv420p`、显式 BT.709、`faststart`、全帧可独立定位。CRF 10 是本项目实验参数，不能单凭数值声称无损。
- 对原始 PNG 与解码帧制作同位置、同倍率的整体对照和固定细节裁切；检查源图存在的文字、细边、蓝色光学面、金属高光、暗部和颜色边缘。PSNR/SSIM、尺寸、时间戳、哈希和 ffprobe 记录仅作辅助，不能替代人工视觉裁决。
- 本步骤兼容范围固定为 Windows 11 上 Chrome 151、Chrome for Testing 150 与 Edge 151。2026-08-26 用户针对当前中国 Windows 桌面产品展示场景明确取消 Edge 150 作为本步骤硬性前置条件；用户提供的裁决依据是该矩阵直接覆盖约 77% 的中国桌面 Chrome+Edge 用户并覆盖主要 Chromium 内核路径，同时本机 Windows Home 不支持 Windows Sandbox，完整 VM 的成本与虚拟显卡/解码偏差不适合本次格式实验。该覆盖率是用户提供的业务判断，不由本步骤机器证据代签。
- Edge 150 明确记为 `not-tested`，不得宣称支持，也不得由 Chrome for Testing 150、Edge 151 或共同 Chromium 内核结果代签。若目标市场、浏览器支持承诺、操作系统环境或发布要求变化并要求覆盖 Edge 150，必须回滚本矩阵裁决，重新准备真实 Edge 150 环境并获得新的书面批准。
- 每个浏览器真实验证静音脚本播放、暂停时 current time 保持、同点继续、准确 `ended`、从起点再次播放、无黑帧和无明显色偏。

任一关键细节出现肉眼可见损伤，或 Chrome 151、Chrome for Testing 150、Edge 151 中任一目标浏览器无法稳定播放、暂停、继续或结束时，视频路线立即失败，`selectedFormat` 固定为 `lossless-png-sequence`；不得测试第二组 CRF/preset 或降低验收标准。只有三个目标浏览器全部机器证据与用户人工批准齐全时，才可固定 `selectedFormat=h264-mp4`。Edge 150 的未验证状态不阻塞本步骤，但始终限制支持声明。

2026-08-26 步骤 3 实际裁决：唯一 H.264 候选的离线细节指标和 Chrome 151 核心播放控制通过，但三次有界 harness 均未形成稳定的多时间点 Canvas 色彩证据，因此视频路线按上述门禁失败。Chrome for Testing 150 与 Edge 151 记为 `not-run-after-video-route-failure`，Edge 150 记为 `not-tested`；这些状态不得写成通过或互相代签。用户已明确批准 `selectedFormat=lossless-png-sequence`。该批准只固定步骤 3 格式，不授权步骤 4、正式素材、生产页面、提交或发布。

无论选择何种格式，完全闭合、完全展开及采集光学舱检查灯亮态都必须逐字节引用阶段 1 正式 PNG，供讲解静止态、加载失败和减少动态模式使用。临时编码候选、浏览器 harness、解码帧和裁切对照不进入正式库存。

#### 8.5.5 动作、低清门禁与正式库存

两个热点的机械动作统一为 `1000 ms`、24 fps。采集光学舱保持 `240 ms` 接缝段与 `760 ms` 完整抽离；聚光镜组件使用相同总时长平滑展开/闭合。每热点正式机械源帧最多 25 张（包含两端）；闭合素材由同一源帧集反序形成，不再调用 Blender 重渲染闭合，但产品状态机不暴露运行中反向能力。

步骤 4 采集光学舱低清候选固定为 640×450、64 samples，且必须继承阶段 1 相机、对象范围、灯光、材质、色彩管理和机械矩阵。人工材料必须包含：

- 展开与闭合的 0/25/50/75/100% 联系表；
- 25/50/75% 三处暂停、保持、同点同方向继续证据；
- 检查灯渐入、稳定持续、返回后渐出与闭合交接；
- 双板同步、6% 接缝、路径、终态、暗部、金属高光、外壳亮度、闪烁和黑帧检查。

2026-08-26 步骤 4 首候选实际结果：使用 25 张无损 PNG 机械源帧和反序闭合索引，渲染参数为 640×450、64 samples、24 fps、1000 ms；0/24 端点与检查灯稳定态继续绑定阶段 1 正式 PNG。机器报告黑帧 0、相邻重复帧 0、端点半尺寸 MAE 0.0；真实浏览器单次播放、暂停保持、同向继续和最终停止通过，控制台 0 error/0 warning。用户已明确批准该候选，记录为 `humanVisualApproved=true`、`scope=stage3-step4-chamber-lowres-only`、`authorizesStep5=false`；该批准不得解释为步骤 5 或后续授权。

步骤 5 聚光镜组件只有在步骤 4 人工批准后才可生成，使用相同 640×450、64 samples、24 fps、1000 ms 契约。人工检查蓝色光学面、黑色前箱、连接面、主体占幅、终点间隙、右侧板清理连续性、展开/闭合端点和两热点画风一致性。

2026-08-26 步骤 5 首候选实际结果：使用 25 张无损 PNG 机械源帧和反序闭合索引，渲染参数为 640×450、64 samples、24 fps、1000 ms；0/24 端点继续绑定阶段 1 正式 PNG。23 张中间帧使用阶段 1 `ffmpeg-removelogo-bitmap-mask` 几何清理，mask 外变化 0、边界单调连续。机器报告黑帧 0、相邻重复帧 0、端点半尺寸 MAE 0.0；真实浏览器 50 个静态请求全部 HTTP 200，console 0 error/0 warning，单次播放、暂停保持、同向继续和最终停止通过。人工视觉尚未批准，`humanVisualApproved=false`、`authorizesStep6=false`；不得以机器或代理预审代签步骤 5，也不得自动进入步骤 6。

2026-08-26 步骤 5 唯一返修实际结果：6/12/18 帧根因对照确认竖线来自 `ACL25416U_MOUNT_Red2 :: 实体1` 的 CAD 三角化几何及表面法线，不是 `removelogo` 或 UV/normal 贴图；`FrontCover`/`Side1` 为可复用真实 CAD 遮挡件。返修把右侧银板临时网格从 3,240 面 limited dissolve 到 1,325 面，复用两件真实遮挡网格随根运动，并用 3 条 Blender 原生 F-Curve、每通道 25 个 `BEZIER`/`AUTO_CLAMPED` 关键帧驱动 0–24 帧；无 `removelogo`，未保存 `.blend`，临时网格/材质/Action/父子关系全部恢复。机器报告黑帧 0、相邻重复帧 0；真实浏览器 62 个静态请求无失败，console 0 error/0 warning，暂停保持“展开 7/25”、同向继续到“展开 14/25”、单次播放最终停止。唯一返修额度已使用；`humanVisualApproved=false`、`authorizesStep6=false`，当前必须停止等待人工视觉裁决。

### 步骤 5 r1 Exact-Boolean 单项消线

2026-08-27 用户撤回继续根治白角、灰板和纸板式运动的范围，要求以 `condenser-lowres-r1` 为唯一行为/画面基线，只让右侧黑线达到 `屏幕截图 2026-08-27 223115.png` 的消线观感。实现必须复用该截图对应的原 Exact-Boolean front-skin proxy，不得重新编写像素修补或引入同一历史 worker 的宽盒 liner。以下旧第二返修方案比较、内腔与机械运动小节仅记录被撤回历史，不再授权执行。

#### 方案比较与决定

1. **probe-r1 已失败：局部硬表面 render proxy + 固定 3D cavity liner。** 该 probe 只替换问题正面的渲染拓扑并把遮挡体固定于机壳，但未满足固定视觉门禁。单自由度机械行程尚未实现或获得视觉批准。
2. **否决：继续修原 CAD 全网格。** 第一返修已证明 limited dissolve 从 3,240 面降至 1,325 面仍残留线；继续提高阈值会破坏孔位、倒角和真实轮廓。只改 normal、材质、Weighted Normal 或 Voxel Remesh 同样不能满足固定失败案例。
3. **否决：视觉掩盖。** `removelogo`、裁相机、改背景色、白色平面、让 `FrontCover`/`Side1` 随动或 bounce/elastic 假物理均已被截图、本地基线或真实性边界否决。

#### 几何清理

- 目标对象固定为 `ACL25416U_MOUNT_Red2 :: 实体1`；源对象、源网格和 `.blend` 不修改、不保存。
- 2026-08-27 `probe-r1` 证明 Exact Boolean 覆盖层仍保留 29 px 右边线，且单一共面层只识别出 1 个开口。候选建议是在目标网格临时副本中删除缺陷正面，只保留原 CAD 侧面、孔壁、紧固件和光学件；从包含倒角的完整正面区域提取一个外边界环和全部内孔边界环，按真实环重建干净硬表面。该建议当前未获恢复执行授权。
- 重建正面使用 Blender 2D Curve/边界环填充生成带孔平面，再 Solidify `0.2 mm`、Bevel `0.05 mm`；不再与原 CAD 求交，也不让原缺陷正面继续渲染。材质从原银板复制，断开不稳定 normal/粗糙度纹理后使用固定金属度/粗糙度。
- probe 必须显式记录并相等比较外环数、内环数、每环顶点数/周长和开口投影中心；结果非空、无非流形边、无零面积面、正面偏移小于 `0.1 mm`。任一门禁失败即停止，不用更大容差、Voxel Remesh、Boolean 覆盖层或像素补丁兜底。

#### 内腔遮挡

- 恢复仓库成熟策略：`FrontCover :: 实体1`、`Side1 :: 实体1` 保持原父级、原世界矩阵和 `preserve` 策略，绝不跟随抽取组件。
- `probe-r1` 的单个宽盒 liner 虽消除左下近白像素，却在产品下方形成大块灰色矩形且仍留下 184 个中央白角像素。候选建议是使用两块局部有深度黑色楔形 liner：分别由 `lowerLeftBoard` 和 `centralWhiteCorner` 固定 ROI 的四条相机射线，在真实开口后的近/远深度面求交并闭合挤出；不得扩大为覆盖整个产品宽度的盒体。该建议当前未获恢复执行授权。
- 两块楔体固定于静态机壳、位于可见开口之后，使用哑光黑材质；25 个采样中与移动组件 AABB 间隙至少 `0.5 mm`。manifest 记录 `classification=render-only-cavity-liner`、`linerCount=2`、每块射线 ROI、8 个世界顶点、最小间隙和 `productStructureClaimed=false`。
- 固定像素门禁覆盖用户截图区域：白角 ROI 与新增白板 ROI 近白像素必须为 0；两个楔体在各自 ROI 外的像素变化必须为 0，不能形成可见矩形或灰色底板。该门禁与人工审核并列，不能互相代替。

#### 机械运动

- 以下内容只保留为未验证候选。第一返修的原生 F-Curve 已随“纸板式运动”被用户驳回；当前没有固定视觉案例或人工审核能够证明本候选有效改善工业重量感。
- 移动单元保持 `SHOWCASE_GROUP__f_dual_acl_housing` 刚性，不捏造内部零件相对运动；静态遮挡件和 liner 不动。
- 使用一个临时自定义属性 `travel ∈ [0,1]` 作为唯一自由度；三轴位置只由该标量和已批准位移 `[0.034,0.012,-0.016] m` 派生，25 帧均须与同一直线轨迹共线，禁止各轴独立漂移。
- 只设置五个关键姿态：frame/value 为 `0/0`、`3/0`、`7/0.06`、`19/0.90`、`24/1.0`。语义依次为初始承力保持、预载释放、主行程、受控减速、终点就位；使用 `BEZIER`、`AUTO_CLAMPED` 和 Continuous Acceleration，不使用 overshoot、bounce 或 elastic。
- 速度门禁：0–3 帧位移为 0；4–7 帧峰值速度低于 8–19 帧主行程峰值；20–24 帧速度单调降至 0；全过程 progress 单调、无反向、无超调。闭合使用同一帧序列反序，暂停必须保持同一帧并沿原方向继续。

#### 验收、回滚和停止

- TDD 先新增三个会因第一返修失败的断言：右板线 ROI、两个白色泄漏 ROI、五关键姿态/单自由度速度契约；确认 RED 原因准确后才修改生成器。
- 只允许一个 `condenser-lowres-r3` 完整候选。候选需通过 25 帧黑帧/重复帧、几何完整性、白色泄漏、轨迹/速度、哈希、临时数据块恢复、真实浏览器 0 console error/0 资源失败、暂停/继续/单次停止和人工视觉审核。
- `.blend`、源/候选哈希、原父子关系、原材质槽和原网格必须恢复；临时 proxy、liner、材质、Action、driver 和约束必须全部移除。失败保留隔离 staging 和报告，不覆盖前两候选，也不生成第四个候选。
- 第二返修机器通过后仍记录 `humanVisualApproved=false`、`authorizesStep6=false` 并停止。若用户再次驳回，步骤 5/阶段 3 停止，除非用户另行改变范围和预算。

2026-08-27 `probe-r1` 实际停点：结构审计通过（非流形 0、零面积面 0、liner 间隙 `1.00001 mm`），但右板黑线仍为 `29 px`（要求 `<=12`）、中央白角仍为 `184` 个近白像素（要求 `0`），宽盒 liner 在产品下方形成明显灰色矩形，且孔数匹配只识别出一个共面开口。该 probe 安全失败，未生成 r3，新增完整返修候选额度未消耗。用户已要求停在这里；不得执行候选修订、机械运动或任何截图停点之后的工作，除非再次获得明确授权。

2026-08-27 r1 单项消线实际结果：从原 Codex 会话 JSONL 恢复 `probe-r1` 的薄 slab、`INTERSECT + EXACT` Boolean、`0.05 mm` 正面偏移和稳定银板材质子步骤；明确删除同一 worker 的 liner 创建段，并沿用 r1 的 25 帧 progress、反序闭合和审核页。独立候选 `output/.twinkle-stage3-condenser-r1-linefix-20260827/condenser-lowres-r1-linefix` 为 640×450、64 samples、25 帧；黑帧 0、相邻重复 0、`linerCount=0`、`postprocess=none`、临时数据块 0，源/候选 `.blend` 哈希未变。真实浏览器 26 个静态请求全部 200，console 0 error/0 warning，暂停/同向继续/单次停止通过。用户已明确批准该视觉基线；linefix manifest 记录 `humanVisualApproved=true`、`authorizesStep6=false`。

2026-08-28 motion-only 实际结果：用户恢复并批准固定单自由度方案。移动根 `SHOWCASE_GROUP__f_dual_acl_housing` 只使用一个 `travel` F-Curve 和五个语义姿态 `0/0、3/0、7/0.06、19/0.90、24/1.0`；三轴严格由 `[0.034,0.012,-0.016] m * travel` 派生，内部组件最大相对矩阵漂移 `5.96e-8`。25 帧、正/反序、暂停保持和同向继续通过机器及真实浏览器门禁，用户人工确认工业重量感改善；motion manifest 记录 `humanVisualApproved=true`、`authorizesR3=false`、`authorizesStep6=false`。

2026-08-28 步骤 5 收口结果：用户授权把上述两项已批准结果整理为唯一低清 r3。`output/.twinkle-stage3-condenser-lowres-r3-20260828/condenser-lowres-r3` 的 25 帧逐帧 SHA-256 与已批准 motion-only `newFrames` 相等；晋级过程不重渲染、不改像素、不保存 `.blend`。r3 manifest 固定两个来源 manifest 哈希、批准继承链、运动 runtime、正/反序播放证据和精确库存，记录 `humanVisualApproved=true`、`step5Closed=true`、`authorizesStep6=false`。步骤 5 到此停止，不得把收口解释为步骤 6 授权。

每个热点只允许首候选加最多一次返修。返修必须先记录具体失败证据并新增能暴露该失败的回归断言；第二候选仍失败时立即停止阶段 3，不进入下一热点或正式批次。

步骤 6 只有在步骤 3 格式裁决与步骤 4/5 两个低清人工门禁全部通过且用户另行明确授权后才可执行。2026-08-28 用户已明确批准步骤 5 并授权开始步骤 6。正式参数为 1280×900、512 samples、24 fps；不得改变获批低清相机、矩阵、灯光、材质、色彩管理、时间或对象范围。

- 视频路线：每热点展开/闭合各一段无声 MP4，共 4 个；无损端点仍引用阶段 1 PNG。
- PNG 回退路线：每热点一套无损源帧及正/反序索引；不产生 MP4。
- 两路线均须包含唯一 `twinkle-stage3-dual-hotspot-motion-v1` manifest、成对联系表、有限播放预览、暂停点对照、减少动态对照和准确浏览器/机器证据；不得包含无限 GIF、网页控件、讲解栏、`.blend` 或临时候选。
- 步骤 6 初始正式目录固定为 `output/twinkle-stage3-dual-hotspot-motion-r1`，只能从同级 staging 原子发布；目标或 backup 已存在时拒绝覆盖。若步骤 7 人工驳回后用户明确批准隔离返修范围，返修只有在完整正式审核页再次获得用户人工通过后才可晋级为不覆盖 r1 的 `output/twinkle-stage3-dual-hotspot-motion-r2`。

步骤 6 机器通过只说明正式候选可提交人工审核。步骤 7 必须由用户确认两个热点动作、暂停恢复、检查灯、画风、格式细节和正式库存后才能标记阶段 3 通过；随后停止等待阶段 4。

2026-08-28 步骤 6 实际结果：唯一正式目录 `output/twinkle-stage3-dual-hotspot-motion-r1` 从同级 staging 原子发布；两个热点各 25 张 1280×900、512 samples、24 fps 无损 PNG，端点引用阶段 1 正式 PNG，正式库存不含 MP4、`.blend`、临时候选或生产页面。两份 Blender audit 固定获批相机、root objects、full offsets 及 light/material/color hashes，临时数据块 0，源/候选 `.blend` 哈希未变。Chrome 151、Chrome for Testing 150、Edge 151 的本地隔离 harness 均通过全部帧加载、暂停保持、同向继续、反序闭合到 0 和减少动态稳定；console error 0、request failure 0，Edge 150 继续标记 `not-tested`。两热点黑帧 0、相邻重复 0；manifest 记录 `step6MachinePassed=true`、`humanVisualApproved=false`、`authorizesStep7=false`。当前必须停止等待步骤 7 人工终验。

2026-08-28 步骤 7 实际结果：用户驳回 r1 审核页的聚光镜高清黑线和检查灯审核缺口后，批准沿既有 front-skin proxy、`INTERSECT + EXACT`、朝镜头 `0.05 mm` 偏移、稳定银色材质、无 liner、无后处理及 motion-only 运动生成返修。最终 `output/twinkle-stage3-dual-hotspot-motion-r2` 复用 r1 的采集光学舱 25 帧，并以相同获批 worker 新鲜渲染聚光镜完整 25 帧；两个热点均为 1280×900、512 samples、24 fps、黑帧 0、相邻重复 0。正式审核页完整执行展开、暂停恢复、检查灯 `900 ms` 渐入与稳定保持、闭合前 `700 ms` 渐出、反序闭合和减少动态端点；Chrome 151 机器门禁与 Playwright headed 视觉检查通过。用户明确回复“通过审核”，r2 manifest 记录 `humanVisualApproved=true`、`authorizesStage3Close=true`、`stage3Closed=true`、`authorizesStage4=false`；阶段 3 到此收口并停止，阶段 4 仍须另行授权。

#### 8.5.6 TDD 顺序与预期证据

书面 SDD/TDD 获批后，阶段 3 才按以下顺序进入实现：

1. **权威与纯契约 RED**：新建 `tests/test_twinkle_stage3_motion.py`，首次运行必须因 `scripts.build_twinkle_stage3_motion` 不存在而产生预期 `ModuleNotFoundError`；不得通过跳过测试制造 RED。
2. **纯契约 GREEN**：新建 `scripts/build_twinkle_stage3_motion.py`，只实现 schema、权威路径/哈希、两个语义 ID、三状态/控件矩阵、阶段 4 segment 接口和参数校验。专项测试必须拒绝旧 experiment manifest、J/F 用户语义、滤片、生产页面写入和现有输出覆盖。
3. **状态轨迹 RED–GREEN**：表驱动测试覆盖三状态、固定按钮可见/启用/文案矩阵、模型热点可见性、局部暂停保持进度/方向、继续同点同方向、禁用控件无操作、检查灯交接、聚光镜无灯路径、`global/paused` 终态、减少动态和加载失败回退。`focus/overviewReturn` 只使用 stub segment，不生成阶段 4 镜头资产。
4. **格式实验 RED–GREEN–人工停点**：先因候选、解码帧、裁切、ffprobe 和四浏览器证据缺失而 RED；生成唯一候选后使机器契约 GREEN，再停在用户格式裁决。人工字段初始必须为 false，只有明确回复才能记录批准。
5. **逐热点低清 RED–GREEN–人工停点**：每个热点先因准确低清库存缺失而 RED，再生成最小候选使机器契约 GREEN；机器通过后停止等待人工。返修时测试先行。
6. **正式库存 RED–GREEN**：正式库存缺失先 RED；获批参数不变，只提升分辨率/采样并原子发布。根据 `selectedFormat` 对 4 个 MP4 或无损 PNG/索引实施互斥库存断言。
7. **阶段终验**：运行阶段 3 专项、camera-board 与相关 TWINKLE 回归、仓库默认全量 `pytest`、`check_current_work_hygiene.py`、`git diff --check`、阶段 1/源/候选哈希、正式库存和 Blender/FFmpeg/浏览器残留进程检查；然后提交步骤 7 人工终验，不自动进入阶段 4。

每个 RED 必须因当前节点缺失而失败；每个 GREEN 只实现满足该节点的最小变更。机器 GREEN、历史测试或代理审查均不得代签人工视觉批准。

#### 8.5.7 复杂度、保护和停止条件

- 最多一个新生成器 `scripts/build_twinkle_stage3_motion.py` 和一个专项测试 `tests/test_twinkle_stage3_motion.py`；不新增 Python/Node 依赖，不新建或保存 `.blend`，不修改生产页面。
- 最多一个视频编码候选；两个热点各首候选加最多一次返修；最多一次正式成对批次；每热点正式机械源帧最多 25 张。
- 历史样片、正式输出、来源/许可资料和用户或混合归属内容不属于本 SDD 的自动清理范围；任何处理必须回到当时有效的仓库治理门禁和用户授权。
- 任一阶段 1 manifest、正式 PNG、源/候选 `.blend`、语义 ID、相机、矩阵、render profile、场景恢复、浏览器矩阵、正式库存或无残留进程证据漂移时立即停止。
- 低清候选若需要改相机、灯光、材质、对象范围或时间才能通过，必须停止并回到设计/人工批准，不得在返修预算内擅自扩大范围。
- 格式实验失败只触发已批准的无损 PNG 回退，不阻塞阶段；缺少 Chrome 151、Chrome for Testing 150 或 Edge 151 任一目标浏览器二进制、低清第二候选仍失败、正式参数偏离已批低清或原子发布无法安全完成时，必须停止并请求决定。Edge 150 不属于当前硬前置，但必须保留 `not-tested` 限制。
- 步骤 7 完成后停止；阶段 4 仍需独立授权，不自动提交、推送、发布或部署。

### 8.6 阶段 4：360° 总览、有限聚焦路线与关闭契约

#### 8.6.1 权威、范围与非目标

阶段 4 只处理阶段 1 已批准的“双通道采集光学舱”和“聚光镜组件”，并复用阶段 3 r2 的机械展开、闭合、暂停恢复、检查灯和静态回退。阶段 2 的绿色/红色滤片路线保持取消，不得恢复其 generator、test、候选、资产、热点或讲解逻辑。

阶段 4 采用 Blender 原生相机、Track To、有限 Curve/Follow Path、仓库投影模块、逐帧资格和无损 PNG 序列。它不实现任意实时 WebGL、第二状态机、通用寻路、生产详情面板、正式产品讲解、生产页面写入、发布或部署。

所有人工批准只约束本阶段已审核的候选。机器通过、历史证据或测试不得代签人工选择；阶段 4 关闭不授权阶段 5。

#### 8.6.2 360° 总览与入口

总览使用 `C360-F96`：96 个 `[0°, 360°)`、端点不重复的实体/逻辑帧，8,000 ms，3.75° 步进，640×450、64 samples、无损 PNG。闭环必须验证末帧到首帧的位置、朝向和像素连续性；任一帧加载失败时进入 error，不得跳帧或用其他媒体冒充完整加载。

模型热点只有在当前帧满足正深度、安全投影、表面朝向、无遮挡和完整装配可识别门禁时可见可用；非 `visible` 状态必须同步关闭 pointer 与 aria。两个固定中文名称按钮在任意总览帧始终显示可点。

入口帧语义为 `overview-exit-only`，只表示离开总览的获批出口，不是详情终点或机械状态。最终入口集合固定为：

- 双通道采集光学舱：`[6, 65]`
- 聚光镜组件：`[87, 8]`

名称按钮点击后沿 cyclic 最短方向转向最近获批入口，使用 250 ms 加速、250 ms 减速和 100 ms 稳定态，峰值角速度不超过约 90°/s，总转向不超过 2,000 ms；到达且速度归零后才可进入聚焦路线。

#### 8.6.3 C1/C2 路线与返回

每个入口只比较 A/B 两条聚焦曲线。两者除空间曲线形状外，共享起终点、target、焦距、shift、时长、缓动、停稳、朝向约束和机械启动时刻。聚焦停稳后才播放阶段 3 r2；r2 完全闭合后才返回总览。

完整进入与返回固定为：

```text
fullFocusTrace = orbitPrefixIndices + curveFrameIndices
overviewReturn = reverse(fullFocusTrace)
```

返回不得重新选择入口、重算路径或分段重拼；完成后必须回到捕获帧并进入 `global/paused`。减少动态、资源失败或超时时保留捕获帧，使用静态回退并记录失败原因，不得伪造路线完成。

C2 必须绑定关闭的阶段 3 r2、获批 C360 manifest、机器通过的 C1 路线集合、worker contract SHA、每帧 provenance 和完整库存 SHA。八条 C2 路线各有 25 张 focus PNG：每条复用 3 张 C1 端点/中点证据并新生成 22 张，总计 200 张 focus PNG，其中 176 张为 C2 新渲染、24 张为获批 C1 复用。

#### 8.6.4 最终人工选择与关闭状态

2026-08-31 的最终四项人工选择固定为：

- 双通道采集光学舱入口 `006`：路线 `A`
- 双通道采集光学舱入口 `065`：路线 `B`
- 聚光镜组件入口 `087`：路线 `A`
- 聚光镜组件入口 `008`：路线 `A`

`routeByUnit` 必须逐项记录上述入口、variant 和稳定 route ID；最终 `entryFrameSet` 必须保持光学舱 `[6, 65]`、聚光镜 `[87, 8]`。只有 production C2 validator、浏览器机器证据和四项人工选择全部匹配时，关闭事务才可写入：

```text
focusRouteGenerated = true
humanVisualApproved = true
stage4Closed = true
authorizesStage5 = false
```

关闭记录范围固定为 `stage4-step9-selection-record-and-closure-only`。它替换阶段 3 的 focus stub，但不授权阶段 5、生产页面、push、PR、发布或部署。

#### 8.6.5 验证、事务与回滚

正式 C2 机器门禁覆盖八条路线、200 张 focus PNG、r2/C1/C360 provenance、review 依赖本地化、桌面/移动 Chromium 路线覆盖、资源失败和有界超时探针。浏览器成功证据必须绑定 review inventory/page SHA；成功场景不得有 console、page 或 request error。

C2 builder 拒绝覆盖既有目标，只能在同级隔离 staging 生成并原子发布。浏览器证据记录、审核页刷新、陈旧浏览器门禁重开和 step9 关闭都必须保留不可变渲染资产，并在最终验证、rename 或写入失败时恢复原 manifest、review 和 browser-results。任何事务残留、SHA 漂移、未批准选择、生产写入或 `authorizesStage5 != false` 都必须失败关闭。

历史真实 Blender/Chromium 证据记录已执行事实；clean-checkout 自动回归使用最小上游 fixture 和 synthetic renderer 调用同一 production builder/validator、证据记录、关闭和回滚函数。合成回归不得代替历史视觉裁决，也不得提交正式 output。
