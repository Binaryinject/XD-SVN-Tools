# XD SVN Tools

[English](README.en.md) · **简体中文**

[![Windows build](https://github.com/Binaryinject/XD-SVN-Tools/actions/workflows/build-windows.yml/badge.svg)](https://github.com/Binaryinject/XD-SVN-Tools/actions/workflows/build-windows.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

用于 Adobe XD 本地 `.xd` 文件的 Windows 对比与三方合并工具，可直接接入 TortoiseSVN。

支持按节点 ID 查看结构变化、逐行着色、自动合并独立修改和逐项解决冲突。默认跟随 Windows 的应用主题，也可手动选择浅色或深色。

> 这是独立开发的试用工具，并非 Adobe 官方 SDK。合并后请在 XD 中检查布局、组件和交互，再在 SVN 中标记冲突已解决。建议先用项目副本试用。

## 下载与安装

**[下载安装包](https://github.com/Binaryinject/XD-SVN-Tools/releases/latest/download/XD-SVN-Tools-Setup.exe)** · [下载便携版](https://github.com/Binaryinject/XD-SVN-Tools/releases/latest/download/XD-SVN-Tools-win-x64.zip) · [SHA-256 校验文件](https://github.com/Binaryinject/XD-SVN-Tools/releases/latest/download/SHA256SUMS.txt) · [全部版本](https://github.com/Binaryinject/XD-SVN-Tools/releases)

运行 `XD-SVN-Tools-Setup.exe`，点击“安装并接入 TortoiseSVN”。上述固定链接始终指向最新正式版；预发布版请从“全部版本”选择。

开发构建仍可在 [GitHub Actions](https://github.com/Binaryinject/XD-SVN-Tools/actions/workflows/build-windows.yml) 成功运行页面底部的 **Artifacts** 下载，下载 Actions 产物需要登录 GitHub。

安装器会将程序安装到 `%LOCALAPPDATA%\Programs\XD-SVN-Tools`，为当前用户自动注册 `.xd` 的对比和合并工具。无需管理员权限、Python、Node.js 或 Git。要从 SVN 中调用，请先安装 TortoiseSVN。

支持覆盖升级；卸载入口在 Windows 已安装的应用中。卸载会恢复安装前的 `.xd` 配置；若安装后手动改用了其他工具，则保留后来修改的配置。

构建产物包含：

| 文件 | 用途 |
| --- | --- |
| `XD-SVN-Tools-Setup.exe` | Release 安装器，安装、升级并自动接入 TortoiseSVN |
| `XD-SVN-Tools-win-x64.zip` | Release 便携版，完整解压后运行 `XD-SVN-Tools.exe` |
| `SHA256SUMS.txt` | 对应 Release 文件名的 SHA-256 校验值 |

Actions 和本地构建的文件名额外包含版本号，例如 `XD-SVN-Tools-Setup-0.1.3.exe`。

当前构建面向 Windows x64，已在 Windows 11 验证。安装器需要 .NET Framework 4.8。生成的安装器目前未做代码签名。

## 功能

- **结构对比**：按包内文件和节点 ID 分组，查看 JSON 属性变化。
- **逐行对比**：左右对齐、原始行号、同步滚动、上一处/下一处变化；删除为红色，新增为绿色，修改为黄色，修改字符加深显示。
- **三方合并**：以共同祖先 BASE 对比 MINE 和 THEIRS，自动组合独立修改。
- **明确状态**：绿色“已自动合并”、红色“需解决冲突”、蓝色“已手动解决”，并显示分类数量。
- **安全保存**：有未解决冲突或基本引用检查错误时禁止保存；覆盖输出前生成 `.bak`，验证 ZIP 后替换。
- **系统外观**：默认跟随 Windows 应用主题，系统切换后约一秒内同步；手动外观选择可记忆。

## 使用方式

### 对比两个版本

选择旧版本 BASE 与新版本 MINE，点击“对比版本”。展开左侧文件可查看具体属性变化；右侧显示逐行差异。

### 三方合并

1. BASE 选择双方共同祖先，MINE 为自己的修改，THEIRS 为对方修改。
2. 选择合并输出，点击“分析三方合并”。
3. 在合并状态中检查自动结果，逐项为冲突选择 BASE、MINE 或 THEIRS。
4. 在结构差异中选择 `BASE ↔ 合并结果` 审阅候选结果。
5. 冲突全部解决且基本校验通过后保存。随后在 XD 中打开、检查并另存，再在 TortoiseSVN 中标记解决。

文件名可以是 `.xd`、`.r123`、`.mine` 等 SVN 临时名称，程序按包内结构识别。工具不会自动执行 `svn resolve` 或提交仓库。

### 手动接入 TortoiseSVN

安装器会自动完成此步骤。便携版可在 TortoiseSVN 设置 → 外部程序 → 对应工具的“高级”中，为 `.xd` 添加以下命令，替换 EXE 路径：

对比：

```text
"D:\Tools\XD-SVN-Tools\XD-SVN-Tools.exe" diff --base "%base" --mine "%mine"
```

合并：

```text
"D:\Tools\XD-SVN-Tools\XD-SVN-Tools.exe" merge --base "%base" --mine "%mine" --theirs "%theirs" --merged "%merged"
```

便携包中的 `Register-TortoiseSVN.ps1` 也可以注册当前用户设置，使用 `-Uninstall` 恢复。注册后请勿移动便携目录。若 SVN 的二进制比较入口未调用外部工具，可导出版本后手动传入本工具。

## 命令行

```powershell
# 导出包内 JSON 结构
python xd_svn.py extract design.xd design.json

# 无界面分析；不写回合并文件
python xd_svn.py check --base base.xd --mine mine.xd --theirs theirs.xd --report report.json
```

打包后的 EXE 支持相同子命令。`check` 的退出码：无冲突和引用错误为 `0`，存在冲突或引用错误为 `1`，输入或运行错误为 `2`。报告包含自动合并项、冲突路径和引用检查错误。GUI 合并保存成功返回 `0`，取消返回 `1`。

## 本地开发与构建

需要 Windows x64、Python 3.14（官方 Windows 发行版，含 Tcl/Tk）及 .NET Framework C# 编译器。Actions 使用 Python 3.14.4 和 `windows-2022`。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt

# 从源码启动
.\.venv\Scripts\python.exe xd_svn.py

# 运行测试、构建并检查打包后的 EXE
.\scripts\build-windows.ps1 -Python .\.venv\Scripts\python.exe
```

产物位于 `artifacts/`，中间文件位于 `.build/`，均不进入 Git。构建不会安装程序、修改 SVN 配置或访问生产仓库。

单独运行测试：

```powershell
python -m unittest discover -v
```

版本号只在 [`VERSION`](VERSION) 中维护。应用读取该文件，构建脚本据此生成安装器版本和产物名称。

## GitHub Actions

工作流 [`build-windows.yml`](.github/workflows/build-windows.yml) 在以下情况运行：

- 推送到 `main`。
- 向 `main` 发起 Pull Request。
- 推送 `v*` 标签，标签必须与 `VERSION` 一致，例如 `v0.1.3`。
- 在 Actions 页面选择 **Run workflow** 手动触发。

工作流自动运行测试、构建 EXE 与安装器，并对打包后的程序执行无界面检查。产物上传到构建页面的 Artifacts，保留 30 天。

推送版本标签时，构建成功后会自动创建 GitHub Release，上传安装器、便携 ZIP 和校验文件；所有附件上传完成后才发布。含 `-` 的版本号发布为预发布版，不影响最新正式版下载链接。已成功发布的版本重跑时会检查附件并保留现有文件。

发布新版本：

```powershell
# 先更新 VERSION，提交并推送；标签必须与 VERSION 一致
git tag v0.1.3
git push origin v0.1.3
```

构建任务只有仓库读取权限；仅标签推送触发的独立发布任务有 `contents: write` 权限，并使用内置 `GITHUB_TOKEN`。PR 和普通分支构建不会发布，无需额外密钥，也不会向 PyPI 发布。

## 合并规则与限制

- 仅支持 ZIP 格式的本地 `.xd`，不支持云文档 `.xdc`。
- 对象属性做三方比较。仅当数组元素全部具有唯一字符串 `id` 时按 ID 对齐；其他数组整体处理。
- 不随意排序图层。双方同时改变节点集合或顺序且结果不同时，需要人工整体选择。
- 预览图和其他二进制文件也可能发生冲突，需要选边。PNG 预览来自包内缓存，可能过期；工具不会重新渲染 XD 画布。
- 校验覆盖 ZIP、严格 JSON、必需条目和部分已知引用，不等于 XD 完整语义验证。复杂组件状态、插件数据、跨文档资源及不同 XD 版本交叉合并仍需人工验收。
- 建议双方使用相同 XD 版本。压缩包单项解压后上限 256 MiB，总计上限 1 GiB。
- 大文本显示最多 200 万字符，每个包内文件最多列出 5000 条属性差异；合并仍处理完整数据。

## 许可与致谢

本项目采用 [MIT License](LICENSE)。解包与合并流程参考了 [xd-scenegraph-toolkit](https://github.com/dilitirio/xd-scenegraph-toolkit) 和 [git-xd-merge](https://github.com/theseion/git-xd-merge)。原项目及运行时许可见 [`THIRD_PARTY_NOTICES.txt`](THIRD_PARTY_NOTICES.txt) 和 [`licenses/`](licenses)。
