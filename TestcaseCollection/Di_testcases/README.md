# Di 测试用例集（随仓库分发）

- **来源**：`data_test/Di_testcases/`（外部评审给出的用例集），原样拷贝，未做修改。
- **数量**：497 个 `TC-*.json`；格式说明见 [`docs/DI_TESTCASES.md`](../../docs/DI_TESTCASES.md)。
- **只读约定**：这些文件是评审基线，**不要就地改动**；需要调整门控位/标签映射时，
  改 `data/DI_Config/` 下的配置，而不是改用例本身。
- **解析**：`can_data_tools.di_case_parser`（旧格式解析链路不受影响，用
  `can_data_tools.case_format` 开关区分）。
- **快速体检**：`python -m scripts.run_di_cases --summary-only`
