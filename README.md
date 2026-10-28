# 论文定位与写作技能

`thesis-project-writer` 基于真实材料协助选题定位、取证、章节规划、写作、续写、审查与润色。新论文按缺失信息分轮访谈；已有论文直接接续本轮任务，保护作者指定的正式稿与同步方向。当前版本见 [VERSION](VERSION)，采用 [MIT 许可证](LICENSE)。

## 获取与使用

- [下载发行包](https://github.com/zengxiaokan/thesis-project-writer/raw/refs/heads/main/dist/thesis-project-writer.zip)：含使用说明、许可、版本、技能指引、脚本、测试和公开样例；解压得到 `thesis-project-writer/`
- [技能入口](SKILL.md)：任务分流与写作规则
- [宿主适配指南](references/host-adapters.md)：Codex 用法及其他环境的手动加载方式
- [单节流程样例](examples/initialization-study/README.md)：从真实运行材料到证据、蓝图、草稿、审查与单节定稿
- [评估改进记录](docs/evaluation-follow-up.md) 与 [更新记录](CHANGELOG.md)

### Codex

把解压后的文件夹放入目标项目的 `.agents/skills/` 或个人的 `~/.agents/skills/`，按 [官方说明](https://learn.chatgpt.com/docs/build-skills) 加载，并调用：

```text
请使用 $thesis-project-writer，先读我提供的材料和已有进度，识别本轮论文任务。
沿用已确认的决定和正式稿，检查必要能力与替代路径，完成指定范围的工作。
```

### 其他宿主

使用该宿主已经支持的技能加载方式，或明确要求读取本目录的 `SKILL.md` 和相关参考。可用以下通用提示词：

```text
请读取我指定目录中的 SKILL.md，先识别本轮论文任务，再读取有关参考文件。
沿用已有决定和正式稿，按当前环境实际提供的工具执行；缺少能力时给替代路径。
不要假定支持某个平台的调用语法、自动读取规则或 MCP。
```

通用规则可以手动使用；本仓库没有对其他宿主的自动发现、工具连接或整篇写作质量作兼容认证。

## 初始化工作区

脚本仅使用标准库。在技能仓库目录执行，把参数替换为目标项目的绝对路径：

```text
python scripts/init_workspace.py --root "<目标项目目录>" --dry-run
```

默认 intake 只建立五份最小记录。确认定位后才选择 `software`、`empirical`、`experimental`、`literature`、`theoretical` 或 `mixed`。直接接续已有论文目录：

```text
python scripts/init_workspace.py --workspace "<已有论文目录>" --profile software --dry-run
```

`--workspace` 与 `--root`、`--directory` 互斥。确认位置后去掉 `--dry-run` 才会实际补建，已有文件保留并返回接续清单。中文路径在 JSON 中用 ASCII 转义输出，解析后的值不变。

在可信且没有并发改变目录结构的工作区使用。全量预检及每次写入前的复查可以拒绝已发现的路径变化，但不是原子防竞态，也不提供失败自动回滚。详见 [工作区指南](references/workspace.md)。

## 验证与发行

```text
python -B -m unittest discover -s tests -v
python -B scripts/run_worked_example.py
python -B scripts/build_release.py
python -B scripts/build_release.py --check
```

[CI 运行记录](https://github.com/zengxiaokan/thesis-project-writer/actions) 检查 Linux/Windows 与 Python 3.8、3.12、3.14；是否已通过以对应提交的实际运行结果为准。Windows 特有测试在其他平台明确跳过；权限不足或 Python 未提供 Junction 接口时也会报告跳过，不计为通过。

脚本目标兼容 Python 3.8+。本机验证环境与 CI 结果分别记录；语法兼容检查不代替解释器运行。运行不依赖模型 API 或第三方 Python 包。宿主仍需提供写作模型，以及任务实际需要的文件、检索、文档或浏览器能力。

发行包按明确文件范围、LF 文本、固定顺序和时间戳生成，使用不受压缩库版本影响的 ZIP 存储方式。`--check` 验证完整字节及本地文档链接；`.github/`、`dist/` 自身、本机 `workspace/` 与缓存不重复装入包中。

## 质量边界

公开样例使用本仓库真实源码和实际临时目录运行记录，只覆盖一个工程论文小节的生产流程。四个原有 eval 是文字行为场景，均不能代替真实完整论文、Word 页面、跨题目稳定性或跨学科方法验收。缺关键材料时保留具体缺口；已有工具并不能补造研究结果。
