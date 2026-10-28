# Thesis Project Writer · 论文定位与写作助手

**让论文写作有路径，让每一段内容有来处。**

一个围绕真实材料工作的 AI 论文写作 Skill，把选题定位、材料整理、章节规划、写作与审查串成可接续的工作流。你可以从一个软件项目、一份数据、一组文献，或者已经写好的两段文字开始，逐步推进到当前任务需要的成果。

想清楚要研究什么，找到能够支撑论述的材料，再把它们写成结构清楚、表述自然的正文。Thesis Project Writer 为这个过程提供具体步骤、材料组织方式和审查规则，也让下一次修改有迹可循。

[开始使用](#获取与使用) · [看看实际样例](examples/initialization-study/README.md) · [下载发行包](https://github.com/zengxiaokan/thesis-project-writer/raw/refs/heads/main/dist/thesis-project-writer.zip)

当前版本 [0.1.0](VERSION) · [MIT 开源](LICENSE) · [跨平台 CI](https://github.com/zengxiaokan/thesis-project-writer/actions)

## 从你正在做的事开始

| 你的当前状态 | 它怎样协助你 |
| --- | --- |
| 有研究兴趣，还没确定题目 | 分轮梳理目标、材料和条件，提出可讨论的论文定位 |
| 手里有软件项目，准备写毕业论文 | 从源码、SQL、配置和真实运行记录整理证据，组织需求、设计、实现与测试的论述 |
| 准备基于数据、实验或文献开展研究 | 按研究路径安排材料、方法和章节主线，登记需要补齐的证据 |
| 已经有蓝图或写了一部分 | 读取已有进度与决定，接续有关章节，保留已确认的工作 |
| 只想改顺几段，或核查一项结论 | 聚焦指定范围，分别处理表达问题和事实依据 |
| 当前环境缺少某些工具 | 检查已有能力，给出必要补充和可执行的替代路径 |

## 值得放进写作流程的几个理由

- **方向先明确。** 把“想研究什么”和“现在能做什么”放在一起考虑，让题目、方法与手头材料相互对应。
- **材料有归处。** 按需组织证据、章节蓝图、正文、图源与审查记录，给关键论述留下可回查的来源。
- **认真对待你的原稿。** 沿用作者指定的正式稿与同步方向，按本轮范围续写、审查或润色。
- **进度能接续。** 复用已有答案、蓝图与有效证据，把已完成内容和下一步记录下来。
- **执行贴合实际条件。** 文档、浏览器、MCP 和本地工具按可用能力选择；条件变化时说明替代方案及交付差距。

## 一条可以持续推进的写作主线

```text
了解目标 → 确认定位 → 整理证据 → 设计章节 → 撰写正文 → 事实与方法审查 → 表达审查 → 核对交付
```

新论文从目标与定位开始，已有论文从当前任务进入。流程里的步骤可以复用已有成果，作者提供的决定、原始材料和真实结果始终是依据。

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
