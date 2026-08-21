# 腾讯云轻量服务器部署指引

> 本文件指导你把 judge_net 部署到腾讯云轻量服务器，对外提供公网访问。
> 模式参考 `../scholar_agent`：服务器本地 build Docker 镜像 + `.env` 注入密钥 + 公网域名反代。

## 一、前置准备

### 1.1 服务器要求

| 项 | 最低 | 推荐 |
|---|---|---|
| CPU | 2 核 | 4 核 |
| 内存 | 4 GB | 8 GB |
| 磁盘 | 20 GB | 40 GB |
| 系统 | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| 公网带宽 | 3 Mbps | 5 Mbps+ |
| Docker | 已安装 | 已安装 |

若未装 Docker，参考 [Docker 官方 Ubuntu 安装指南](https://docs.docker.com/engine/install/ubuntu/)。

### 1.2 必备资源清单

| 资源 | 用途 | 获取方式 |
|---|---|---|
| 腾讯云轻量服务器 | 部署宿主 | 腾讯云控制台购买 |
| 公网域名 | 评委访问 | 已有，或腾讯云注册 .com / .cn |
| paratera API Key | LLM 调用 | `../scholar_agent/.env` 复用 |
| Tavily API Key | 联网检索 | 注册 https://tavily.com（免费 1000 次/月） |
| paratera GLM-4V 模型名 | OCR | 登录 paratera 控制台查看 vision 模型列表，默认 `glm-4v` |

### 1.3 本地准备

确认本仓库完整：

```bash
ls /mnt/d/project/judge_net
# 应看到：AGENTS.md README.md app/ static/ knowledge/ ... Dockerfile requirements.txt .env.example
```

## 二、上传代码到服务器

### 2.1 方式 A：scp 上传（推荐，简单）

在本地终端执行：

```bash
# 把整个项目打包上传（排除 .venv 与 .git）
cd /mnt/d/project
tar --exclude='.venv' --exclude='.git' --exclude='__pycache__' \
    -czf judge_net.tar.gz judge_net/

# scp 到服务器（替换 your-server-ip 与 your-user）
scp judge_net.tar.gz your-user@your-server-ip:~/

# ssh 上服务器解压
ssh your-user@your-server-ip
tar -xzf judge_net.tar.gz
cd judge_net
```

### 2.2 方式 B：git clone（若你已推远程）

```bash
ssh your-user@your-server-ip
git clone <your-repo-url> judge_net
cd judge_net
```

> 本项目当前未推远程，方式 A 更直接。

## 三、配置环境变量

### 3.1 创建 .env

在服务器上 `judge_net/` 目录下：

```bash
cp .env.example .env
nano .env   # 或 vim
```

填入真实值：

```dotenv
LLM_BASE_URL=https://llmapi.paratera.com/v1
LLM_API_KEY=sk-your-real-paratera-key

LLM_MODEL_REASONING=GLM-5.2
LLM_MODEL_VISION=glm-4v
LLM_MODEL_EMBEDDING=GLM-Embedding-2

TAVILY_API_KEY=tvly-your-real-tavily-key

PORT=7860
AUTH_ENABLED=false

SESSION_TTL_SECONDS=3600
LLM_MAX_TOKENS=16384
LLM_TEMPERATURE=0.3

ENV=production
```

### 3.2 确认 .env 不入 git

```bash
cat .gitignore | grep ".env"
# 应有 .env 行
```

## 四、构建 Docker 镜像

```bash
cd ~/judge_net
docker build -t judge-net .
```

首次构建约 3-5 分钟（下载 Python 依赖）。后续构建有缓存，约 30 秒。

构建成功后检查：

```bash
docker images | grep judge-net
```

## 五、启动容器

### 5.1 首次启动

```bash
docker run -d \
  --name judge-net \
  -p 7860:7860 \
  --env-file .env \
  --restart always \
  judge-net
```

参数说明：
- `-d`：后台运行
- `--name judge-net`：容器名
- `-p 7860:7860`：宿主 7860 映射容器 7860
- `--env-file .env`：注入环境变量
- `--restart always`：服务器重启或容器异常退出后自动重启

### 5.2 验证启动

```bash
# 看日志
docker logs -f judge-net

# 健康检查
curl http://localhost:7860/healthz
# 应返回 {"status":"ok","model":"GLM-5.2","vision_model":"glm-4v"}

# 准备检查
curl http://localhost:7860/readyz
# 应返回 {"ready":true,"auth_enabled":false,"search_configured":true,"vision_configured":true}
```

若 ready=false，检查 .env 中 LLM_API_KEY 是否填了；search_configured=false 则 Tavily Key 未填。

### 5.3 浏览器访问

```
http://your-server-ip:7860
```

应看到 judge_net 前端单页。粘贴对话 → 提交 → 等待裁决报告。

## 六、配置公网域名（可选但强烈推荐）

### 6.1 域名解析

在域名服务商（腾讯云 DNSPod 等）添加 A 记录：

```
judge.your-domain.com  A  your-server-ip
```

### 6.2 nginx 反代 + HTTPS

服务器装 nginx：

```bash
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx
```

创建站点配置：

```bash
sudo nano /etc/nginx/sites-available/judge-net
```

内容：

```nginx
server {
    listen 80;
    server_name judge.your-domain.com;

    client_max_body_size 20M;  # 允许上传截图

    location / {
        proxy_pass http://127.0.0.1:7860;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # LLM 长调用可能 90s+，超时设长
        proxy_read_timeout 240s;
        proxy_write_timeout 240s;
    }
}
```

启用 + 重载：

```bash
sudo ln -s /etc/nginx/sites-available/judge-net /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

申请 HTTPS：

```bash
sudo certbot --nginx -d judge.your-domain.com
# 按提示同意条款，选自动重定向到 HTTPS
```

访问 https://judge.your-domain.com 验证。

## 七、更新迭代流程

修改代码或提示词后：

```bash
# 本地：scp 新代码到服务器，或服务器 git pull
ssh your-user@your-server-ip
cd ~/judge_net
# 若用 scp，先在本地重传覆盖

# 重新 build + 重启容器
docker build -t judge-net .
docker rm -f judge-net
docker run -d \
  --name judge-net \
  -p 7860:7860 \
  --env-file .env \
  --restart always \
  judge-net

# 验证
curl http://localhost:7860/healthz
```

## 八、监控与运维

### 8.1 看日志

```bash
docker logs -f judge-net                # 实时
docker logs --tail 200 judge-net        # 最近 200 行
```

### 8.2 重启容器

```bash
docker restart judge-net
```

### 8.3 进入容器排查

```bash
docker exec -it judge-net bash
# 在容器内：
ls /app
curl http://localhost:7860/healthz
```

### 8.4 资源监控

```bash
docker stats judge-net
# 看 CPU/内存/网络
```

## 九、常见问题

### Q1：容器启动后立即退出

```bash
docker logs judge-net
```

常见原因：
- `.env` 路径不对（docker run 须在 `judge_net/` 目录执行，或用绝对路径 `--env-file /home/user/judge_net/.env`）
- 端口 7860 被占用（`sudo lsof -i :7860`）

### Q2：裁决请求超时

- 检查 paratera API Key 是否有效：`curl http://localhost:7860/readyz` 应 ready=true
- LLM 调用可能慢，确认 nginx `proxy_read_timeout` ≥ 240s
- 看日志是否在重试：`docker logs judge-net | grep retry`

### Q3：截图 OCR 失败

- 确认 `LLM_MODEL_VISION` 配置正确（在 paratera 后台查 vision 模型名）
- 看 `readyz` 的 `vision_configured` 是否 true
- 截图太大可能超 base64 体积限制，建议 < 5MB

### Q4：Tavily 搜索不工作

- 确认 `TAVILY_API_KEY` 已填
- 看 `readyz` 的 `search_configured` 是否 true
- 免费额度 1000 次/月用尽会 403，看日志

### Q5：评委访问慢

- 轻量服务器带宽低，首次加载 marked.js CDN 慢，可改本地引入
- LLM 推理本身慢，前端已有"正在生成"提示
- 若并发高，考虑升级服务器或加 Nginx 缓存

## 十、回填公网地址到 README

部署完成后，把公网 URL（如 `https://judge.your-domain.com`）填入 `README.md` 顶部"在线体验地址"占位符，commit：

```bash
# 本地
nano README.md
# 替换 <!-- 待回填 ... --> 那行

git add README.md
git commit -m "回填公网访问地址"
```

## 十一、部署自检清单

| # | 项 | 命令 | 期望 |
|---|---|---|---|
| 1 | 容器运行 | `docker ps \| grep judge-net` | Up 状态 |
| 2 | 健康检查 | `curl http://localhost:7860/healthz` | status=ok |
| 3 | 准备检查 | `curl http://localhost:7860/readyz` | ready=true |
| 4 | 公网访问 | 浏览器开 `http://ip:7860` | 看到前端 |
| 5 | 域名访问 | 浏览器开 `https://judge.your-domain.com` | HTTPS 正常 |
| 6 | 提交裁决 | 粘贴 case_01 对话 | 返回 12 节报告 |
| 7 | 上诉 | 点"提起上诉"填条目+理由 | 返回二审备忘录 |
| 8 | 话术 opt-in | 点"请求应答话术" | 触发 opt-in 确认 |
| 9 | 截图 OCR | 上传一张社交截图 | 识别发言方 |
| 10 | 自动重启 | `docker restart judge-net` 后访问 | 恢复正常 |
