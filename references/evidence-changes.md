# 可选的证据变更提示

用于材料更新后定位需要复核的主张、正文、图表和测试说明。它复用稳定主张 ID、已有来源和正文位置，按需补指纹及关联；旧稿不用整体迁移。这个工具比较已登记来源的指纹，不解释业务语义，也不改写或认定主张错误。

## 什么时候用

已有取证记录且材料发生变化、用户问“这次修改影响论文哪里”、跨会话接续需要核对已登记基线时，可运行 `scripts/check_evidence_changes.py`。没有登记的主张与材料不在检查范围内，不能据此判断全篇仍然有效。只润色一段、没有相关来源变化时无需为调用工具补全全篇记录。

工具不联网，不导入或执行待查项目，不创建日志、缓存或新基线，只向标准输出交 JSON。来源、登记文件、目标正文与图源保持只读。是否更新基线及如何修订正文，仍要回查材料并依据本轮授权处理；工具没有“接受最新基线”或自动替换来源的操作。

## 最小登记格式

所有来源、目标及候选路径均相对于显式的读取根。读取根可以是项目根；如果论文目录中的证据引用外层源码，应选择能同时覆盖它们的项目根，并使用 `thesis/...` 路径，不通过 `../` 越出读取根。

```json
{
  "schema_version": 1,
  "claims": [
    {
      "claim_id": "C-STATE",
      "statement": "该条件决定处理能否继续",
      "sources": [
        {
          "path": "source/service.py",
          "sha256": null,
          "hash_mode": "text-lf",
          "locator": "handle_request 中的状态判断"
        }
      ],
      "targets": [
        {"kind": "chapter", "path": "chapters/ch5.md", "locator": "5.2/P3"},
        {"kind": "figure", "path": "figures/source/state.dot", "locator": "FIG-501"},
        {"kind": "test", "path": "tests/state.md", "locator": "CASE-STATE"}
      ]
    }
  ],
  "rename_candidates": [],
  "rename_roots": []
}
```

这里 `sha256: null` 是“基线尚未登记”，不是已验证基线。示例会报告 `baseline_missing`。实际比较须填入从该来源取得且已记录在证据中的 SHA-256，不能用任意示意字符串冒充真实指纹。完整的已登记小样稿与变更演示见 [只读检查样例](../examples/readonly-checks/README.md)。

`claim_id` 必须是非空、无换行、唯一的字符串；`statement` 可省略。每个 `sources` 项需要文件 `path`，`hash_mode` 省略时为 `bytes`。`locator` 是可选的单行定位文本，供人回查；它是登记位置，不表示工具已经识别该行发生了语义变化。`targets` 的 `kind` 可为 chapter、figure、test 或其他实际类别，工具只保留其关联，不解释类型内容。声明数组、主张 ID、路径、指纹格式、模式或 schema 版本不合法时返回输入错误。

没有来源、目标或指纹的记录也会如实列为缺口，不以“未发现变化”掩盖未登记。额外元数据不会参与比较；工具没有核实其中的版本、状态或文字解释。

## 运行与退出码

```text
python -B <技能路径>/scripts/check_evidence_changes.py --root "<项目或论文读取根>" --manifest "evidence/claims.json"
```

`--manifest` 可以是读取根内的绝对路径，也可以是根内相对路径。登记中的文件路径始终为根内相对路径。工具拒绝指向根外的路径，以及读取路径中的符号链接或 Windows Junction；需要外部材料时先由用户明确选择合适读取根或提供可读副本，不自动扩大范围。

| 退出码 | 含义 |
| --- | --- |
| 0 | 登记来源指纹没有检出变化，且未检出登记缺口；不是主张真实性或全文有效性证明 |
| 1 | 有需复核的变化、失效路径、缺基线或关联缺口等发现 |
| 2 | 输入格式、范围或执行错误，检查未完整完成 |

正常报告和读取/格式错误以 ASCII 转义 JSON 输出，中文解析后保持原值；参数用法错误由命令行解析器提示。默认不在磁盘保存报告；需要留存时由调用方按实际路径另存到报告位置，不能重定向覆盖待查材料。

## 怎样理解结果

- `findings` 提供发现代码、源路径或登记路径、主张 ID 与登记数组位置；有 `locator` 时同时保留原登记定位。
- `claims` 分别记录每个来源的 `unchanged`、`changed`、`missing` 或 `baseline_missing`，以及目标是否存在。变化只使相应主张成为 `needs_review`。
- `needs_review_claim_ids` 和 `affected_targets` 将变化或缺口关联到登记的章节、图表与测试说明；不将没有关联的全篇正文自动失效。
- `unaffected_claim_ids` 仅表示该记录所有已登记来源指纹未变、目标未缺失。它不证明来源完整、事实仍真或图文一致。
- `coverage` 列出实际读取文件、登记来源数量、指纹比较数量、目标路径及重命名搜索范围。没有读目标正文、没有查页面等范围同时明示。

常见发现代码为 `source_changed`、`source_missing`、`baseline_missing`、`sources_unregistered`、`targets_unregistered`、`target_missing`；空主张清单报告 `no_claims`。不合法的路径或记录属于退出码2的输入错误。一个来源变化与主张被证伪是不同判断：注释、格式或配置值的改变都可能导致指纹变化，仍应回查实际影响。

## 指纹模式与重命名候选

`bytes` 比较原始文件字节，适合源文件以及 Word、PDF、图片等二进制文件。`text-lf` 只把 CRLF 归一为 LF 后比较，不删除注释、空格、BOM 或其他字符，也不解析语言。文本换行差异可据任务选择归一模式；不能用它给二进制格式作语义等价认证。

默认不搜索重命名。只有旧来源路径失效且已有基线时，才在 `rename_candidates` 明确列出的文件和 `rename_roots` 明确列出的目录范围内匹配同一模式的指纹。目录下的符号链接/Junction 会被拒绝，不借它们扩大读取范围。候选文件或目录失效时会报告 `rename_candidate_missing` 或 `rename_root_missing`。

单个匹配输出 `unique_candidate`，多个匹配输出 `ambiguous_candidates`，没有匹配输出 `no_candidate`。相同指纹也可能是副本，因此单个候选仍只是提示：旧路径保持 missing，登记不被自动改写。搜索范围要选具体来源目录，不为找一个文件枚举全机。

源指纹改变、路径失效、候选重命名和目标缺失均需人工或模型回查；文件内容存在并不证明正文表达正确，图源存在不证明导出或页面已检查。工具不代替技术、学术、引用及版面审查。
