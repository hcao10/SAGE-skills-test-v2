# SAGE Skills Test v2

本仓库为 **技能型 Agent（Skill Agent）** 的演示工程：在工业泵轴承振动诊断场景下，对比「通用大模型回答」与「可溯源、符合标准的技能流水线」的差异。

核心应用为 **PumpGuardian**（Streamlit），源码位于 `pump_guardian/`。

## 功能概览

- **双模式**：General AI（弱提示、无工具）与 Skill Agent（本地工具 + ISO 证据 + 工单）
- **技能加载**：按需披露技能资源（如 `SKILL.md`、脚本、参考数据）
- **本地诊断工具**：RMS、FFT、峰值检测等（`skills/bearing_analyzer/scripts/diag_tool.py`）
- **ISO 10816** 阈值检索与证据展示
- **结构化维护工单** 与 Markdown 导出
- **合成振动数据**（默认可呈现约 81 Hz 类故障特征）
- **右侧 Agent 追踪** 动画
- **可选 MiniMax**：配置 API Key 后启用真实 LLM 对比叙述
- **中 / 英** 界面切换

## 快速开始

```bash
cd pump_guardian
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
cp env.sample .env
# 编辑 .env，按需填写 MINIMAX_API_KEY 等（可选）

streamlit run app.py
```

浏览器打开 Streamlit 提示的本地地址即可。

## 配置说明

环境变量、`.env`、Streamlit `secrets.toml` 的优先级与变量名，见子目录文档：

→ **[pump_guardian/README.md](pump_guardian/README.md)**

## 仓库结构

```text
.
├── README.md                 # 本文件（仓库总览）
└── pump_guardian/            # PumpGuardian 应用
    ├── app.py
    ├── requirements.txt
    ├── core/                 # 路由、追踪、技能加载、工单、MiniMax、i18n 等
    ├── skills/bearing_analyzer/   # 示例技能（SKILL、脚本、ISO 参考、模板）
    ├── data/                 # 合成数据生成
    └── README.md             # 详细说明与 MiniMax 配置
```

## 演示预期

| 模式        | 典型表现 |
| ----------- | -------- |
| General AI  | 偏泛化建议，缺少 FFT、ISO 依据与结构化工单 |
| Skill Agent | 完整流水线、可追溯步骤、FFT 与标准对照、可导出工单 |

## 许可证

若需对外发布，请在本仓库补充 `LICENSE` 文件。
