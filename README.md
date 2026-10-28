# 论文定位与写作技能

`thesis-project-writer` 根据真实材料协助选题定位、取证、章节规划、写作、续写、审查与润色。新论文按缺失信息分轮访谈；已有论文直接接续本轮任务，保护作者指定的正式稿和同步方向。

## 文件

- [技能入口](SKILL.md)：任务分流、工作阶段与使用规则
- [下载分享包](dist/thesis-project-writer.zip)：与技能目录一致的源码、指南、初始化脚本和回归用例
- [初始化脚本](scripts/init_workspace.py)：只补缺，支持多种研究路径和既有工作区接续
- [场景用例](evals/evals.json)：四个文字交互场景及检查点

## 使用

下载或克隆本仓库，将整个 `thesis-project-writer/` 文件夹放入目标项目的 `.agents/skills/`，或个人的 `~/.agents/skills/`。在 Codex 中调用：

```text
请使用 $thesis-project-writer，先读取我提供的材料和已有进度，识别本轮论文任务。沿用已确认的决定和正式稿，检查必要能力与可行替代路径，完成指定范围的工作。
```

本地技能目录和调用方式见 [OpenAI 官方说明](https://learn.chatgpt.com/docs/build-skills)。

新工作区默认只建五份访谈、定位、环境及入口记录。定位确认后，再按软件工程、调查实证、实验、文献综述、理论分析或混合路径扩充。缺少工具时采用已可用的替代方式；关键证据缺少时保留具体缺口。

在本技能仓库目录执行，将目标项目参数替换为论文工作区父目录的绝对路径：

```text
python scripts/init_workspace.py --root "<目标项目目录>" --dry-run
```

直接接续已有论文目录：

```text
python scripts/init_workspace.py --workspace "<已有论文目录>" --profile software --dry-run
```

`--workspace` 与 `--root`、`--directory` 互斥；`software` 只用于已确认的系统实现路径。确认位置后去掉 `--dry-run` 才会实际补建文件，既有入口和进度按返回的接续清单继续维护。

## 验证

```text
python -B -m unittest discover -s tests -v
```

本次在 Windows / Python 3.14.6 执行 20 项检查：19 通过，1 项因符号链接权限不足跳过；四项 Windows 目录联接检查全部通过。脚本目标兼容 Python 3.8+，已检查其语法及所用 API，尚未用 Python 3.8 解释器运行验证。

文字场景只用于检查任务范围和回答行为，不能代替真实论文写作、文档页面或跨学科方法验收。
