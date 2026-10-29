# 单节证据

材料范围为本仓库当前版本的初始化器和 [实际观察](observation.json)。观察文件保存参与执行的源码 SHA-256；复跑脚本验证输入均为临时目录中的测试数据。

| 编号 | 主张 | 原始依据与证据类型 | 支持范围 |
| --- | --- | --- | --- |
| E1 | 初始化按所选研究路径补建目录及入口 | scripts/init_workspace.py 的 build_layout、PROFILE_DIRECTORIES；源码 | 描述配置和生成逻辑，不等于研究已完成 |
| E2 | 目标及中间目录在写入前检查，新文件以独占方式创建 | initialize、validate_before_write、is_link_or_reparse；源码 | 存在这些检查和拒绝路径，不推出原子防竞态或失败回滚 |
| E3 | 已有文件被保留，扩充时返回接续事项 | initialize、CONTINUATION_ACTIONS；源码 | 保留逻辑与提示内容；阶段更新仍由执行者依据实际反馈完成 |
| E4 | 本次预览零写入，analysis 创建四份记录，intake 补两份并保留分析记录，扩充 software 新增十三份文件并返回六份接续项 | observation.json 中 preview_wrote_nothing、analysis_created_files、intake_created_files、analysis_records_preserved_on_intake、upgrade_created_files、continuation_paths；实际运行观察 | 本次临时目录和脚本调用序列，不是实际完成分析或作者确认 |
| E5 | 本次扩充保留原字节和时间戳，重复执行没有新增文件 | observation.json 中 existing_file_bytes_preserved、existing_file_mtimes_preserved、repeat_created_files、repeat_all_bytes_and_mtimes_preserved；实际比较 | 本次样例，不推导所有异常和并发条件下均安全 |

定稿只使用以上主张。没有运行浏览器、数据库或文档渲染，不能增加有关测试、性能和学校格式的结果。
