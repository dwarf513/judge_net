# judge_net · 网络冲突法官智能体

> 网络争吵的公正裁决者：厘清事实、辨别谬误、看见降温路径，促进网络和谐健康。

**在线体验地址**：http://judge-net.icu:8080

**GitHub 仓库**：https://github.com/dwarf513/judge_net

**赛道**：DIY 高代码（FastAPI 后端 + 原生前端 + Docker 部署到腾讯云轻量服务器）

---

## 一、它解决什么问题

互联网降低了表达门槛，也放大了冲突烈度。当一场网络争吵发生时：

- 当事方陷入"当局者迷"，情绪驱动论证，难以看见自身谬误。
- 旁观者缺乏对议题的深入认知与论证分析能力，常被话术带节奏。
- 平台只管内容合规，不评判对错。
- 专业仲裁成本高，触达不到日常网络口角。

结果：大量冲突在"各说各话—情绪升级—群体站队—群体撕裂"路径上耗散，伤害网络生态与个体心理。

**judge_net 的切入点**：用一个 AI 法官补位"旁观者理性分析"的空缺——给争议一份结构化、有信源、可上诉的技术性裁决，以网络和谐为最高原则。

## 二、核心特性

| 特性 | 说明 |
|---|---|
| 三层分析框架 | 事实层（信源分层四态）+ 逻辑层（21 谬误分类法）+ 情绪修辞层（6 类战术） |
| 不各打五十大板 | A/E/F 类争议明确判定较正确一方；价值分歧显式声明不裁决对错 |
| 冲突类型学 | A 诚意争辩 / B 偶发口角 / C CIB 协同造假 / D 营销引流 / E 阴谋论 / F 谣言AI骗局 |
| 特殊情形检测器 | 水军信号、阴谋论叙事签名、AI 生成内容、查无信源 |
| 上诉机制 | 指明条目 + 提供新证据 → 局部重审 → 二审备忘录 |
| 应答话术模式 | opt-in + 7 类拒绝清单 + 5 种风格（默认降温退场） |
| 安全拒裁护栏 | 未成年人/未决司法/暴力威胁/心理危机/人肉/极端意识形态 → 转介专业资源 |
| 12 节裁决报告 | 强制结构，便于自动化校验与可解释性 |

## 三、快速体验

1. 点击上方"智能体分享链接"（待回填）。
2. 在对话框粘贴一段网络对话原文，或上传社交平台截图。
3. 确认发言方归属后，agent 输出 12 节裁决报告。
4. 对裁决不服？指明条目 + 提供新证据发起上诉。
5. 你是当事方想回话？输入"我是当事方，请求应答话术"进入 opt-in 流程。

## 四、仓库结构

```
judge_net/
├── system_prompt.md                   # 核心：法官人格 + 全流程指令 + 护栏（558 行）
├── knowledge/                         # 7 个 .md，由后端 prompt_builder 注入（1181 行）
│   ├── fallacy_taxonomy.md            #   谬误分类法（21 + 6 条）
│   ├── conflict_typology.md           #   冲突类型 A–F + 决策树
│   ├── source_credibility.md          #   信源可信度 Tier-1 到 Tier-4
│   ├── verdict_template.md            #   裁决报告 12 节模板
│   ├── appeal_protocol.md              #   上诉协议 + 二审备忘录
│   ├── response_script_guardrails.md  #   应答话术护栏 + 5 风格库
│   └── safety_refuselist.md           #   安全拒裁 R1-R6
├── app/                               # FastAPI 后端
│   ├── main.py                        #   FastAPI 工厂 + lifespan + 路由挂载
│   ├── config.py                      #   pydantic-settings
│   ├── api/                           #   /v1/adjudicate /v1/appeal /v1/reply-script
│   └── core/                          #   llm ocr search pipeline session 等
├── static/                            # 原生 HTML/JS 单页前端
│   ├── index.html
│   ├── style.css
│   └── app.js
├── golden_cases/                      # 5 个匿名化金标准案例 + 期望输出
│   ├── case_01_weibo_knowledge_debate.md      # A 类：LK-99 超导
│   ├── case_02_zhihu_accidental_quarrel.md    # B 类：粽子甜咸
│   ├── case_03_bilibili_cib_water_army.md     # C 类：UP 主被黑稿
│   ├── case_04_reddit_conspiracy.md           # E 类：阿波罗登月
│   ├── case_05_xiaohongshu_ai_scam.md         # F 类：明星代言骗局
│   └── expected_outputs/                       # 每案期望结构（回归断言）
├── scripts/
│   ├── regression_test.py             # HTTP 调本地服务跑金标准回归
│   └── requirements.txt
├── tests/
│   └── test_pipeline.py               # pytest 单元测试
├── docs/
│   ├── design.md                      # 设计哲学 + 五环节拓展 + 黑天鹅叙事
│   └── git_tutorial.md               # 零基础 git 入门
├── deploy/
│   └── deployment_guide.md           # 腾讯云轻量服务器部署指引
├── Dockerfile                         # Docker 镜像构建
├── requirements.txt                   # Python 依赖
├── .env.example                       # 环境变量占位
├── AGENTS.md                          # opencode 协作约定
└── README.md                          # 本文件
```

## 五、设计哲学

1. **网络和谐健康优先于争论输赢本身**——拒裁清单会主动中止裁决，降温退场是应答话术默认推荐。
2. **不各打五十大板**——伪装中立是最大的不公正；A/E/F 类必须判定较正确一方。
3. **不冒充真理裁判**——价值/审美/道德取向只澄清前提差异；不可核实事宜显式声明。
4. **三层分析正交**——事实错误不算谬误，情绪本身不是错误，三者各司其职。
5. **提示词即架构**——所有逻辑沉淀在 markdown，无 Web 框架，便于迭代与审计。

详见 `docs/design.md`。

## 六、本地开发

### 6.1 环境准备

```bash
# 复用 ../scholar_agent/.env 的 paratera API Key，或自行准备 .env
cp .env.example .env
# 编辑 .env 填入 LLM_API_KEY / SEARCH_API_KEY / LLM_MODEL_VISION

python3 -m pip install -r requirements.txt
```

### 6.2 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 7860 --reload
```

浏览器打开 http://localhost:7860 即可使用。

### 6.3 跑回归测试

```bash
# 先确保服务已启动
python3 scripts/regression_test.py            # 跑全部 5 个案例
python3 scripts/regression_test.py case_03    # 只跑 case_03
python3 scripts/regression_test.py --report-only   # 仅从已有输出生成报告
```

报告输出到 `docs/regression_report.md`，原始输出到 `docs/regression_outputs/`（均已被 .gitignore）。

### 6.4 迭代流程

1. 改 `system_prompt.md` 或 `knowledge/*.md` 或 `app/core/pipeline.py`。
2. 重启服务（或依赖 `--reload`）。
3. 跑 `python3 scripts/regression_test.py` 验证。
4. 失败则定位案例 + 调整。
5. 通过后 `git add . && git commit -m "迭代说明"`（参见 `docs/git_tutorial.md`）。

## 七、部署到腾讯云轻量服务器

详见 `deploy/deployment_guide.md`。要点：

1. ssh 到服务器，`git clone` 仓库（或 scp 上传）。
2. `cp .env.example .env`，填入真实密钥（LLM_API_KEY / SEARCH_API_KEY / LLM_MODEL_VISION）。
3. `docker build -t judge-net .`
4. `docker run -d --name judge-net -p 7860:7860 --env-file .env --restart always judge-net`
5. 配置域名/反代指向 7860 端口（若有域名）。
6. 验证 `curl http://localhost:7860/healthz` 返回 `{"status":"ok"}`。

## 八、验证状态

最近一次回归测试结果（5/5 PASS）：

| 案例 | 平台 | 类型 | 12 节 | 关键判定 | 结果 |
|---|---|---|---|---|---|
| 01 | 微博 | A 诚意争辩 | OK | 较正确一方=B | PASS |
| 02 | 知乎 | B 偶发口角 | OK | 价值分歧不裁决 | PASS |
| 03 | B 站 | C CIB 协同造假 | OK | 特殊情形提示 | PASS |
| 04 | Reddit | E 阴谋论 | OK | 逐条证伪 + 谬误 | PASS |
| 05 | 小红书 | F 谣言AI骗局 | OK | 疑似 AI 生成 | PASS |

完整报告见 `docs/regression_report.md`（生成物，不入版本库）。

## 九、安全与伦理声明

- 金标准案例全部虚构匿名，不针对真实账号。
- 不收集用户对话用于训练。
- 涉及未成年人、未决司法、暴力威胁、心理危机时强制拒裁并转介专业资源。
- 应答话术模式有 opt-in + 7 类拒绝清单，防止被滥用为对线工具。
- 不评价当事人本身，只评价论点与论证。

## 十、局限

- 联网检索质量受平台工具限制。
- OCR 受视觉模型能力限制，复杂截图可能漏识别。
- 回归测试样本量 5 个，覆盖主要类型未覆盖所有边界。
- 上诉须在同一会话内完成（无跨会话持久记忆）。

## 十一、许可证与致谢

- 架构参考同目录 `../scholar_agent`（FastAPI + paratera MaaS + Docker 模式）。
- 信源分层灵感来自维基百科可靠来源指引与学术同行评议制度。
- 谬误分类参考维基百科谬误列表。
- CIB 检测灵感来自 Stanford Internet Observatory。

---

## 项目进度

| # | 交付物 | 状态 |
|---|---|---|
| 1 | `AGENTS.md` 协作约定 | 完成 |
| 2 | `knowledge/*.md` 7 个知识库文件 | 完成 |
| 3 | `system_prompt.md` 主提示词 | 完成 |
| 4 | `golden_cases/*.md` 5 案例 + 期望输出 | 完成 |
| 5 | `scripts/regression_test.py` 回归脚本 | 完成 |
| 6 | 本地回归测试 5/5 PASS | 完成 |
| 7 | `docs/design.md` + `docs/git_tutorial.md` | 完成 |
| 8 | `deploy/deployment_guide.md` 部署指引 | 完成 |
| 9 | `app/` FastAPI 后端 | 完成 |
| 10 | `static/` 单页前端 | 完成 |
| 11 | `tests/test_pipeline.py` 单元测试 | 完成 |
| 12 | `Dockerfile` + `requirements.txt` + `.env.example` | 完成 |
| 13 | `README.md` 门面文档 | 完成 |
| 14 | 部署到腾讯云轻量服务器 + 域名 + GitHub 推送 | 完成 |
| 15 | SSE 流式输出 + HTTPS 配置指引 | 完成 |
