# Git 入门教程（针对零基础用户）

> 本教程为 judge_net 项目维护者编写，假设你从未用过 git。
> 目标：让你能看懂并执行"保存进度""查看历史""回到过去"三个核心操作。

## 一、Git 是什么（一分钟理解）

Git 是一个**版本控制工具**——可以把它想象成给文件夹拍快照：

- 每次你觉得工作到一个阶段了，就"拍一张快照"（叫 **commit**）。
- 快照只记录变化的部分，不占太多空间。
- 你可以随时回到任意一张快照，查看或恢复。
- 多人协作时，各自拍快照，最后合并。

**核心概念只有三个**：

| 概念 | 类比 | 说明 |
|---|---|---|
| 工作区 | 你正在改的文件 | 当前硬盘上的文件 |
| 暂存区 | 购物车 | 决定哪些改动要"结账" |
| 仓库 | 相册 | 已拍下的快照历史 |

## 二、首次设置（一次性，做完不用再做）

打开终端（PowerShell 或 bash），输入：

```bash
git config --global user.name "你的名字"
git config --global user.email "你的邮箱@example.com"
```

这告诉 git "这些快照是谁拍的"。**只需设置一次**，所有项目通用。

> 邮箱建议用 GitHub 注册邮箱（如果你将来要上传到 GitHub）。本项目暂不上传远程，写什么都行。

## 三、第一次使用 judge_net 项目

### 3.1 初始化仓库（只需做一次）

在 judge_net 目录下：

```bash
cd /mnt/d/project/judge_net
git init
```

这会创建一个隐藏的 `.git/` 文件夹，里面存所有快照历史。**不要动这个文件夹**。

### 3.2 查看当前状态

```bash
git status
```

这是你**最常用的命令**。它会告诉你：
- 哪些文件改了还没"放进购物车"（红色）
- 哪些文件已放进购物车还没"结账"（绿色）
- 当前在哪个分支

**养成习惯**：每次操作前先 `git status` 看一眼。

### 3.3 第一次提交

```bash
git add .
git commit -m "初始化 judge_net 项目：提示词、知识库、金标准、回归脚本"
```

解释：
- `git add .` 把当前目录所有文件放进购物车（`.` 表示全部）。
- `git commit -m "..."` 结账，拍一张快照，`-m` 后是这张快照的说明。

**提交信息写法**：
- 首行简短描述（≤50 字），用中文。
- 例如"完善 system_prompt.md 第 8 节不各打五十大板原则"。

## 四、日常三件套（最常用）

### 4.1 查看改了什么

```bash
git status      # 看哪些文件变了
git diff        # 看具体改了哪些内容（红色删的，绿色加的）
```

`git diff` 会用分屏显示变化，按 `q` 退出查看。

### 4.2 保存进度

```bash
git add 文件名              # 只加某个文件
git add .                   # 加全部改动
git commit -m "这次改了什么"
```

**什么时候该提交**：
- 完成一个独立的小改动就提交一次（如"修好 case_03 的断言"）。
- 不要攒一大堆改动才提交——那样快照粒度太粗，不好回溯。
- 提交前先 `git status` + `git diff` 检查一遍。

### 4.3 查看历史

```bash
git log --oneline -10
```

会列出最近 10 条快照，每条一行：

```
a1b2c3d 完善回归脚本
e4f5g6h 添加 case_05
i7j8k9l 初始化项目
```

前面那串字母数字是**提交 ID**（commit hash），是这张快照的身份证。

按 `q` 退出查看。

## 五、回到过去（撤销操作）

### 5.1 改了文件还没 add，想放弃改动

```bash
git checkout -- 文件名
```

文件会恢复到上次提交的样子。**注意：改动会丢失，不可恢复。**

### 5.2 已经 add 进购物车，想拿出来

```bash
git reset HEAD 文件名
```

文件回到"改了但没 add"状态，改动还在。

### 5.3 查看某个历史版本的文件内容

```bash
git show 提交ID:文件路径
```

例如：

```bash
git show a1b2c3d:system_prompt.md
```

会显示那个版本的 system_prompt.md 内容。只读，不影响当前文件。

### 5.4 误提交了想撤销最近一次提交（保留改动）

```bash
git reset --soft HEAD~1
```

最近一次提交被撤销，但文件改动保留在购物车里，可以重新调整后再提交。

> **警告**：不要用 `git reset --hard`，它会永久删除改动。本项目维护中用不到。

## 六、judge_net 项目的典型工作流

### 6.1 改了提示词后

```bash
# 1. 看改了什么
git status
git diff system_prompt.md

# 2. 跑回归测试验证没改坏
python3 scripts/regression_test.py

# 3. 通过后提交
git add system_prompt.md
git commit -m "调整 system_prompt.md 第 X 节 ..."
```

### 6.2 跑回归测试失败了

```bash
# 1. 看 docs/regression_report.md 哪个案例失败
# 2. 改提示词
# 3. 重跑失败的案例
python3 scripts/regression_test.py case_03

# 4. 全部通过后，用已有输出生成报告
python3 scripts/regression_test.py --report-only
```

## 七、.gitignore 的作用

项目根目录的 `.gitignore` 文件列出了**不该提交的文件**：

```
.env               # 密钥，绝不提交
__pycache__/       # Python 缓存
.venv/             # 虚拟环境
docs/regression_report.md      # 生成的报告
docs/regression_outputs/       # 生成的输出
```

这些文件要么含密钥，要么是生成物，不该进版本历史。git 会自动忽略它们。

**重要**：`.env` 文件（含 paratera API Key）必须被忽略。本项目复用 `../scholar_agent/.env`，本仓库内不创建含密钥的文件。

## 八、常见问题

### Q1：`git commit` 报错"nothing to commit"

说明自上次提交后没有改动。用 `git status` 确认。

### Q2：`git diff` 没输出

可能改动还没保存，或改动文件被 .gitignore 忽略。用 `git status` 检查。

### Q3：不小心提交了 .env

```bash
git rm --cached .env
echo ".env" >> .gitignore
git add .gitignore
git commit -m "移除误提交的 .env"
```

`--cached` 表示从 git 跟踪中移除，但保留本地文件。

### Q4：想看某次提交改了什么

```bash
git show 提交ID
```

### Q5：想撤销最近一次提交但保留改动

```bash
git reset --soft HEAD~1
```

### Q6：命令太多记不住

记住三个就够日常用：
- `git status`（看状态）
- `git add . && git commit -m "说明"`（保存）
- `git log --oneline -10`（看历史）

其他用到再查。

## 九、judge_net 项目的首次提交建议

初始化后，第一次提交包含全部交付物：

```bash
cd /mnt/d/project/judge_net
git init
git status                        # 检查所有文件
git add .
git status                        # 再看一眼，确认 .env 没被加进去
git commit -m "初始化 judge_net：系统提示词、7 个知识库、5 个金标准案例、回归脚本、设计文档"
git log --oneline                 # 确认提交成功
```

之后每次改动（提示词调整、案例增删）都做一次小提交，积累版本历史。

## 十、进一步学习

本教程只覆盖本项目所需的最小集合。想深入：

- [Git 官方文档](https://git-scm.com/book/zh/v2)（Pro Git 中文版，免费）
- [Learn Git Branching](https://learngitbranching.js.org/?locale=zh_CN)（交互式可视化练习）

但本项目维护**不需要**深入——上述三件套足够。
