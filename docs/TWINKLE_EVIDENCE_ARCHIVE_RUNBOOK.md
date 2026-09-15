# TWINKLE 证据包私有归档运行手册

本手册记录把**已存在**的 TWINKLE H2 evidence bundle 归档到独立私有 GitHub 仓库 Release，并完成上传后回传核验的流程。流程已在本机真实执行成功两次（draft 阶段一次、发布后一次），两次均通过严格校验。

**本流程不重建、不修改 bundle。** 若 bundle 本身需要变更，先走生成与验证流程，再回到本手册。

## 前置条件

- `registry/twinkle/stage5-h2-evidence-receipt.json` 存在且通过仓库内严格 validator；
- bundle 已构建并位于内容寻址目录 `<evidence-root>/<bundleSha256>/files/...`；
- GitHub 凭据具备 `repo` 作用域（本机由 Git Credential Manager 提供）；
- 目标为**独立私有仓库**；不得上传到公开代码仓，不得创建公开 tag。

## 步骤

### 1. 上传前严格校验（不重建）

```powershell
.\.venv\Scripts\python.exe -c "import sys,json;from pathlib import Path;root=Path('.').resolve();sys.path.insert(0,str(root));from scripts import twinkle_stage5_h2_evidence as ev;r=json.loads((root/'registry/twinkle/stage5-h2-evidence-receipt.json').read_text(encoding='utf-8'));b=ev.validate_evidence_bundle(root/'registry/twinkle/stage5-h2-evidence-receipt.json', Path(r'<evidence-root>')/r['bundleSha256']);print('PASS',b.bundle_sha256,len(b.inventory_paths))"
```

必须同时确认：目录名 == `bundleSha256`；实际文件数与字节数 == receipt 的 `bundleFileCount` / `bundleBytes`。

### 2. 上传前敏感内容扫描（硬门禁）

对 bundle 内所有文件扫描：私钥、GitHub/OpenAI/AWS/Google/Slack token、JWT、Bearer、密码赋值、`Set-Cookie`，以及邮箱、手机号、身份证号等 PII 线索。文本/二进制以首个 8 KiB 内是否含 NUL 判定。

**命中任何真实密钥、浏览器凭据或客户资料时立即停止**，改用私有对象存储并考虑客户端加密。

### 3. 创建私有仓库并双重确认

创建后必须做**两次独立确认**：

1. 已认证 `GET /repos/{owner}/{repo}` → 断言 `private == true` 且 `visibility == "private"`；
2. **匿名**（不带凭据）请求同一端点 → 必须返回 **404**，证明对外不可见。

只做第 1 步不够：第 2 步才是对外不可见的独立证据。

### 4. 制作归档

GitHub Release 资产是**扁平命名空间**，无法保留目录结构，因此必须打包为**单个归档**，且顶层目录名必须等于 `bundleSha256`，以便解压后直接跑 validator。

使用 ZIP `ZIP_STORED`（不压缩；PNG/MP4 无压缩收益且拖慢流程），条目按路径排序以保证可复现。归档后记录其字节数与 SHA-256。

### 5. 创建 draft Release

先建 draft，上传并核验通过后再发布。Release 正文应写明：receipt 路径、来源提交、`bundleSha256`、文件数、字节数、正式结果摘要、归档字节数与 SHA-256、上传前核验结论、以及复核方式。

### 6. 上传并比对服务端 digest

上传完成后 GitHub 会返回 `digest` 字段。**该值必须与本地计算的归档 SHA-256 一致**——这是服务端的独立完整性确认，不要跳过。

### 7. 回传下载到**新的**临时目录

必须重新下载，不能只信上传时的返回值。断言下载文件的大小与 SHA-256 均与本地一致。

### 8. 解压并对 receipt 严格校验

**解压目标必须使用短路径**（见“已实测的坑”）。解压后断言：目录名 == `bundleSha256`；文件数与字节数 == receipt；对 receipt 跑严格 validator 必须 PASS。

### 9. 发布 Release

全部核验一致后才发布（`draft: false`）。发布后 `refs/tags/<tag>` 才会真实生成。

### 10. 发布后再核验一次

draft 阶段与发布后的资产理论上相同，但应**重新下载已发布附件**再核验一次，把“远程副本可信”这个前提钉死。仅比对 API digest 不足以替代。

### 11. 清理临时产物

上传归档、回传下载、解压副本与克隆目录均属本流程临时产物，核验完成后可清理；清理前先记录体积，清理后回验源 bundle、`output/` 与工作树状态未变。

## 已实测的坑

- **MAX_PATH**：解压到默认临时目录会因路径过长报 `FileNotFoundError`。这不是数据损坏。解压目标改用短根目录（如 `F:\ev-verify`）。
- **`git lfs ls-files --ref <ref>` 不是有效参数**：它会输出 usage 文本，按行数统计会得到虚假计数。需要判断远程是否有 LFS 对象时，用 `git ls-tree` 比对。
- **PowerShell `@($null).Count` 等于 1**：对空 JSON 数组做 `@(Invoke-RestMethod ...).Count` 会得到 1 而非 0。判定“无评论/无检查”必须看原始响应体是否为 `[]`，或用 `$null -eq` 判断。
- **`Invoke-WebRequest` 在非交互模式不可用**：改用 .NET `HttpClient`；上传下载大文件时设 `Timeout` 并流式读写。
- **敏感扫描的正则假阳性**：`\b\d{17}[\dXx]\b` 会命中 JSON 浮点尾数（如 `0.017409630083823555`）。命中后必须看上下文再判定，不能直接当身份证号处理。
- **跳过 LFS smudge 的克隆是更严格的验证条件**：`GIT_LFS_SKIP_SMUDGE=1` 下仍能通过的测试，同时证明它不依赖 LFS 二进制资产。
- **切换 worktree 分支会移除该分支未跟踪、但已存在于 main 的文件**：内容在 Git 中，不是数据丢失，但会改变该工作树的本地文件集合。

## 回滚

- Release 与附件：需**单独明确授权**后删除；本流程本身不包含删除。
- 私有仓库：同上。
- 归档过程对本地 bundle 只读，任何一步失败都不影响源 bundle；失败时保留临时产物以便定位。
