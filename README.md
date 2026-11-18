# resh-m

一个用于学习研究型 Agent 流程的 Python 命令行项目：围绕研究问题检索资料，筛选证据，再调用模型生成带来源编号的中文报告。

## 主要流程

```text
输入问题 → 原问题检索 → 模型规划子查询 → 并发搜索和网页抓取
        → BM25 证据筛选 → 模型生成报告 → 引用编号检查 → 保存结果
```

- 使用 DDGS 搜索，通过 requests 和 BeautifulSoup 提取网页段落。
- 自写 BM25 相关性排序，结合去重、来源数量和字符预算筛选证据。
- 支持读取本地 Markdown/TXT 文件，并与网页资料混合筛选。
- 记录任务状态、证据和报告；另包含可选的 MCP 笔记检索模块。


## 环境要求

- Python 3.13 或以上。
- 已安装 uv。
- 可用的 DeepSeek API Key；联网研究还需要能访问搜索服务和目标网页。

当前查询规划和报告生成代码使用 `https://api.deepseek.com`，模型名为 `deepseek-flash`。运行前请确认账号支持该模型；模型名目前写在 `src/resh_m/planner.py` 和 `src/resh_m/writer.py` 中。

## 安装和运行

下载或克隆本仓库后，在项目根目录打开 PowerShell：

```powershell
uv sync --locked
Copy-Item .env.example .env
```

打开 `.env`，填写自己的密钥：

```dotenv
DEEPSEEK_API_KEY=填写你自己的密钥
SEARCH_BACKEND=auto
SOURCE_MODE=web
ENABLE_MCP=0
```

如果本地已有 `.env`，保留原文件，只参考模板补充配置，不要覆盖已有密钥。

启动命令：

```powershell
uv run resh-m
```

按提示输入研究问题。也可使用 `uv run python main.py` 启动。查询规划和报告生成会调用模型 API，可能产生费用。

## 配置

| 变量 | 作用 | 未设置时的代码默认值 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 模型 API 密钥 | 无，调用模型时需要填写 |
| `SEARCH_BACKEND` | DDGS 搜索后端 | `auto` |
| `SOURCE_MODE` | `web`、`local` 或 `hybrid` | `hybrid` |
| `ENABLE_MCP` | 设为 `1` 时启用 MCP 笔记检索 | 关闭 |

模板选择 `web` 模式，并关闭 MCP，便于先运行基本流程。搜索失败时可单独检查搜索后端和网络；无可用证据时不会调用写作模型。
