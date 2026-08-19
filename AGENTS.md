# AGENTS.md — judge_net 项目协作约定

> 本文件用于指导 opencode（或其他 AI 编码助手）在本仓库中工作。请先完整阅读后再动手。

## 1. 项目定位

**项目名**：judge_net（网络冲突法官智能体）

**目标**：构建一个能在网络争论中担任"法官"角色的智能体，对用户提交的网络对话（文本粘贴或截图）做出清晰、公正、客观、有温度的裁决报告，以促进网络和谐健康为核心原则。

**赛道**：DIY 低代码（智谱清言自定义智能体 + 分享链接交付）。

**核心交付物**：
1. `system_prompt.md` — 智谱清言智能体的主提示词（核心战场）。
2. `knowledge/*.md` — 上传到智谱清言知识库的 7 个支撑文件。
3. `golden_cases/*.md` — 5 个匿名化中文社交语境案例 + 期望输出。
4. `scripts/regression_test.py` — 用 paratera API 跑金标准回归。
5. `docs/design.md` + `docs/git_tutorial.md` — 设计文档与给用户的 git 教程。
6. `deploy/chatglm_agent_config.md` — 用户在智谱清言平台上线的操作指引。
7. `README.md` — 设计哲学 + 智能体分享链接占位。

## 2. 技术栈与外部依赖

| 依赖 | 用途 | 说明 |
|---|---|---|
| 智谱清言（chatglm.cn） | 智能体宿主平台 | 用户手动上线，opencode 不代登 |
| GLM-5.2（paratera MaaS） | 本地回归测试的 reasoning 模型 | 复用 `../scholar_agent/.env` |
| GLM-4V（paratera MaaS） | 视觉 OCR 验证 | 同上 |
| Python 3.10+ | 仅用于 `scripts/regression_test.py` | 不构建 Web 服务 |
| openai SDK | paratera API 是 OpenAI 兼容 | `pip install openai python-dotenv` |
| Git | 版本控制 | 用户暂未掌握，需附带教程 |

**不使用**：FastAPI / Flask / LangChain / AutoGen / FAISS / 任何 Web 框架。本项目是低代码路线，所有逻辑在提示词与知识库中。

## 3. 目录布局约定

```
judge_net/
├── AGENTS.md                          # 本文件
├── README.md                          # 对外门面
├── system_prompt.md                   # 核心：法官人格 + 全流程指令 + 护栏
├── knowledge/                         # 智谱清言知识库（7 个 .md）
│   ├── fallacy_taxonomy.md
│   ├── conflict_typology.md
│   ├── source_credibility.md
│   ├── verdict_template.md
│   ├── appeal_protocol.md
│   ├── response_script_guardrails.md
│   └── safety_refuselist.md
├── golden_cases/                      # 5 个匿名化案例 + 期望输出
│   ├── case_01_weibo_knowledge_debate.md
│   ├── case_02_zhihu_accidental_quarrel.md
│   ├── case_03_bilibili_cib_water_army.md
│   ├── case_04_reddit_conspiracy.md
│   ├── case_05_xiaohongshu_ai_scam.md
│   └── expected_outputs/
├── scripts/
│   ├── regression_test.py
│   └── requirements.txt
├── docs/
│   ├── design.md
│   └── git_tutorial.md
└── deploy/
    └── chatglm_agent_config.md
```

**命名约定**：
- 全部小写 + 下划线。
- markdown 文件名见名知意。
- 金标准案例以 `case_NN_平台_类型.md` 命名。
- 不使用中文文件名（兼容性考虑）。

## 4. 文件编辑规则

- **markdown 优先**：所有产物为 markdown，不写 Python 应用代码（除回归脚本）。
- **不添加注释**：除 Python 回归脚本外，markdown 文件不写代码注释风格的注释。
- **不动 `.env`**：复用 `../scholar_agent/.env`，不在本仓库内创建含密钥的文件；如需本地配置，写 `.env.example` 占位。
- **编辑前先读**：用 `Read` 工具读取目标文件后再 `Edit`，避免盲改。
- **新文件用 Write**：不存在时直接 Write 创建。
- **保持 UTF-8 + LF**：换行用 LF，编码 UTF-8 无 BOM。
- **中文为主**：所有面向用户的内容用简体中文；代码标识符与文件名用英文。

## 5. 内容写作规范

### 5.1 提示词写作（`system_prompt.md` 与 `knowledge/*.md`）
- 用**指令式**语气（"你必须……"），不用商量口吻。
- 每条指令配**反例与正例**或**触发条件**，避免抽象。
- 长提示词用 markdown 二级/三级标题分节，便于 LLM 定位。
- 涉及输出格式时，给出**字面模板**（用 ` ```text ` 代码块），不要只描述。
- 护栏类指令必须明确**触发条件 + 拒绝动作 + 替代行为**三要素。

### 5.2 金标准案例写作（`golden_cases/*.md`）
- **全部虚构匿名**：人名用"@用户A / @用户B"或虚构昵称，绝不使用真实账号。
- **平台语境真实**：微博/知乎/B站/小红书/Reddit 的语气、UI 暗示可保留。
- 每个案例包含：背景（隐含）、对话原文（按发言方分段）、冲突类型期望、关键谬误期望、信心度期望。
- `expected_outputs/` 下放期望裁决的**结构骨架**（不必逐字匹配，验证节标题与关键判定即可）。

### 5.3 设计文档（`docs/design.md`）
- 阐述设计哲学与黑天鹅奖叙事。
- 引用原始构想的五个环节并标注拓展点。
- 不写代码示例，重在思路。

## 6. 验证与回归

### 6.1 提示词自检
每次修改 `system_prompt.md` 或 `knowledge/*.md` 后，运行：

```bash
python scripts/regression_test.py
```

脚本会用 paratera API 跑 5 个金标准案例，断言：
- 输出包含全部 12 节标题。
- CIB 案例必须触发"特殊情形提示"。
- 阴谋论案例必须触发"逐条证伪"。
- AI 骗局案例必须触发"疑似 AI 生成"。
- 至少一案例必须出现明确的"较正确一方"判定（不能各打五十大板）。

### 6.2 lint / typecheck
- **无 npm/pip 应用代码**，故无 `npm run lint` / `ruff`。
- markdown lint：可选，用 `markdownlint-cli`，规则文件 `.markdownlint.json`（如创建）。
- Python 回归脚本：用 `python -m py_compile scripts/regression_test.py` 做语法检查。
- 若用户后续提供具体 lint 命令，应回填到本节。

### 6.3 验证流程
1. 编辑提示词或知识库文件 → 2. `python -m py_compile scripts/regression_test.py` 检查脚本可编译 → 3. `python scripts/regression_test.py` 跑金标准 → 4. 检查 `docs/regression_report.md` 输出 → 5. 失败则回到步骤 1。

## 7. 安全与隐私红线

- **金标准案例全部虚构**，绝不使用真实账号或可识别真人信息。
- 提示词中不得包含任何真实个人身份信息。
- `safety_refuselist.md` 列出的拒裁场景必须在 `system_prompt.md` 中被显式引用并强制执行。
- 应答话术护栏必须在 `system_prompt.md` 中以独立章节呈现，并要求用户 opt-in。
- 复用的 `../scholar_agent/.env` 不得被复制到本仓库或提交到 git。

## 8. Git 协作约定

- 用户暂未掌握 git，需配套 `docs/git_tutorial.md`。
- 仅在本地 `git init`，不推送远程。
- `.gitignore` 必须排除：`.env`、`__pycache__/`、`.venv/`、`*.pyc`、`docs/regression_report.md`（生成物）。
- commit message 用中文简短描述，首行 ≤ 50 字。
- 不使用 `--no-verify`、不强制 push、不修改 git config。

## 9. opencode 行为约束

- **不创建任何在线服务**，不部署 HF Spaces，不启动 Web 服务器。
- **不替代用户登录智谱清言**，平台侧操作全部写入 `deploy/chatglm_agent_config.md` 由用户手动执行。
- **不主动 commit**，仅在用户明确要求时执行 `git add` + `git commit`。
- **不修改 `../scholar_agent/`**，只读复用其 `.env`。
- **每完成一个交付物停顿**，等用户审阅后再继续下一步。
- **不写 emoji**，除非用户明确要求。
- **不写代码注释**（除 Python 脚本的 docstring）。

## 10. 当前进度

参见根目录 `README.md` 末尾的"项目进度"章节。每次完成一个交付物后，更新该章节。
