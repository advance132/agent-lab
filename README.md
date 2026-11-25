# agent-lab

把「调一次大模型」从随手写的脚本，升级成一个可观测的 HTTP 服务。

> 当前版本 v0.1（第 1 周）：两个接口、结构化日志、密钥外置。后续见文末路线图。

## 这个仓库是什么

- 一个跑在本地、能被 curl 或浏览器直接调用的模型服务
- 一次最小但完整的分层：配置 → 客户端 → 接口 → 日志
- 用来验证模型应用开发的基本功：把第三方 API 包成自己的服务，并且出问题时看得见

它**不是**业务系统：没有鉴权、限流、持久化，也还没接 RAG 和工具调用。

## 接口

| 方法 | 路径 | 用途 | 返回 |
| --- | --- | --- | --- |
| GET | `/health` | 探活，部署后第一个该调的接口 | `{"status":"ok"}` |
| POST | `/ask` | 单轮问答 | `answer` / `tokens` / `cost_ms` / `error` |

`/ask` 请求体：

```json
{"q": "用一个比喻解释什么是向量数据库"}
```

正常返回（真实调用 deepseek-flash）：

```json
{
  "answer": "向量数据库就像按「意思」检索的图书馆……",
  "tokens": 97,
  "cost_ms": 753,
  "error": null
}
```

失败时不会抛 500，原因进 `error` 字段，接口照常返回：

```json
{"answer": "", "tokens": 0, "cost_ms": 12, "error": "Error code: 401 - Authentication Fails"}
```

这样设计的原因见「设计说明」第 2 条。

## 快速开始

环境要求：Python 3.10+（本机实测 3.10.11）

**1. 克隆并进入目录**

```bash
git clone https://github.com/advance132/agent-lab.git
cd agent-lab
```

**2. 创建虚拟环境**

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**3. 安装依赖**

```bash
python -m pip install -r requirements.txt
```

**4. 配置密钥**

把 `.env.example` 复制为 `.env`，填入自己申请的 key（DeepSeek 控制台 → API keys）：

```
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_MODEL=deepseek-flash
```

`.env` 已被 `.gitignore` 拦住，不会进仓库。真实 key 不要写进 `.env.example`，也不要写进任何 `.py` 文件。

**5. 启动服务**

```bash
python -m uvicorn main:app --reload
```

看到 `Application startup complete.` 即成功，服务地址 http://127.0.0.1:8000

**6. 验证**

最省事的方式是浏览器打开 http://127.0.0.1:8000/docs ，点 `/ask` → `Try it out` → `Execute`，能看到完整 JSON 返回。

命令行方式（PowerShell 发中文请求要传字节，否则请求体会被控制台编码转坏）：

```powershell
$json = @{ q = "你好，请用中文回答" } | ConvertTo-Json -Compress
$bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
Invoke-RestMethod -Uri "http://127.0.0.1:8000/ask" -Method Post -ContentType "application/json; charset=utf-8" -Body $bytes
```

## 目录结构

```
agent-lab/
├── main.py             # 客户端初始化、两个接口、请求日志
├── requirements.txt
├── .env.example        # 变量模板，无真实密钥
└── .gitignore          # .env / .venv / __pycache__
```

刻意保持单文件：这一阶段的重点是把链路跑通、每一步都看得见，而不是提前搭工程骨架。等需求真的长出来再拆模块。

## 设计说明（三个刻意的选择）

**1. 用 OpenAI 兼容 SDK，而不是各家原生 SDK。**

换模型只改三处：`base_url`、`api_key` 的变量名、`model` 名，业务代码不动。以后接豆包、通义、OpenAI 都是同一套写法，这也是这类项目最常见的工程做法。

**2. 异常收进 `error` 字段，不在接口层抛出。**

调用失败时不会 500，调用方可以统一按四个字段处理；失败原因同时落日志。代价是返回体宽了一点，换来排查成本下降。

**3. 每次请求记一行结构化日志。**

`q_len=… tokens=… cost_ms=… err=…` 四个字段分别回答：输入多长、花了多少 token、多慢、有没有错。排查时不用翻代码猜。

已知偏差：失败请求的 `tokens` 记 0，因为异常时拿不到 usage。所以这个数字只统计成功请求，做成本核算时会偏低估。

## 已知限制

- 无鉴权、无限流，只适合本地运行，不要直接对公网暴露
- 单轮对话，没有上下文记忆
- `max_tokens` 固定 300，长回答会被截断
- 模型名会随供应商调整。DeepSeek 当前支持 `deepseek-flash` 与 `deepseek-v4-pro`；若返回 `The supported API model names are…`，说明配置里的名字过期了

## 路线图

- [x] W1 仓库搭建 + 密钥管理 + 首次调用 + HTTP 接口 + 请求日志
- [ ] W2 多模型路由 + 成本统计
- [ ] W3 RAG 知识库问答（语料用本人实训报告），带 30 条评测集
- [ ] W4 工具调用 Agent（接 MySQL）
- [ ] W5 多步工作流 + 评测脚本

## 环境问题备忘

Windows 下 `git push` 报连接被重置，多半是链路抖动，重试通常能过；可先 `git config --global http.version HTTP/1.1` 再推。中文在 PowerShell 里显示成 `ä½ å¥½` 是控制台编码问题，数据本身没坏，执行 `chcp 65001` 即可。

---

作者：武姜华 · 河北工业职业技术大学 · 人工智能工程技术
