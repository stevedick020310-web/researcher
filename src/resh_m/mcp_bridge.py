# 导入 Python 异步编程库，用于运行异步的 MCP 客户端调用
import asyncio
# 导入 JSON 模块，用于解析 MCP 返回的结构化字符串
import json
# 导入系统模块，用于获取当前 Python 解释器的执行路径
import sys
# 导入路径处理工具，用于获取当前工作目录
from pathlib import Path


# ============================================================
# 类名：MCPNotesRetriever
# 功  能：封装 MCP 客户端调用逻辑，对外提供与 LocalDocsRetriever 完全一致的 load_pages 接口
#        实现「本地笔记检索」通过 MCP 协议统一接入，上层代码无需感知底层差异
# ============================================================
class MCPNotesRetriever:
    # ============================================================
    # 方法名：load_pages（同步对外接口）
    # 功  能：同步包装层。对外提供同步调用方式，内部用 asyncio.run 执行异步逻辑
    #        上层调用方不用写异步代码，直接和普通函数一样调用即可
    # 输  入：query: str  查询关键词
    # 返  回：list[dict]  标准化的文本块列表，每个元素是一个 page 字典
    # ============================================================
    def load_pages(self, query):
        # 运行异步函数 _load_pages，阻塞等待结果返回
        return asyncio.run(self._load_pages(query))

    # ============================================================
    # 方法名：_load_pages（异步核心实现，内部方法，下划线开头表示私有）
    # 功  能：启动 MCP 子进程服务 → 建立客户端连接 → 调用 search_notes 工具
    #        → 解析返回结果 → 校验格式 → 统一包装返回
    # 输  入：query: str  查询关键词
    # 返  回：list[dict]  标准化的 page 字典列表
    # ============================================================
    async def _load_pages(self, query):
        # 延迟导入：在函数内部才导入 MCP 相关依赖
        # 好处：1. 避免顶层加载依赖过重；2. 避免循环导入；3. 没装 MCP 库时类本身不会报错
        from mcp import Client, StdioServerParameters

        # 配置 MCP 服务的启动参数：用标准输入输出（stdio）方式启动子进程
        server = StdioServerParameters(
            # 命令：用当前运行的 Python 解释器，保证环境一致
            command=sys.executable,
            # 参数：以模块方式运行 resh_m.mcp_server（就是你之前写的那个 MCP 服务端脚本）
            args=["-m", "resh_m.mcp_server"],
            # 工作目录：当前脚本运行的目录
            cwd=str(Path.cwd()),
        )

        # 异步上下文管理器：自动创建 MCP 客户端、连接服务、用完自动关闭
        async with Client(server) as client:
            # 异步调用 MCP 服务上注册的工具 search_notes，传入查询参数
            result = await client.call_tool(
                "search_notes",       # 工具名，和服务端 @mcp.tool() 注册的函数名一致
                {"query": query},     # 工具参数，字典形式传入
            )

        # ========== 第一步：错误校验 ==========
        # 如果 MCP 工具返回了错误，主动抛出运行时异常，终止流程
        if result.is_error:
            raise RuntimeError(f"MCP 工具返回错误：{result.content}")

        # ========== 第二步：兼容提取返回文本 ==========
        # MCP 不同版本/实现返回结构可能不同，这里做了两层兼容
        structured = result.structured_content
        # 情况1：返回是结构化字典，且 result 字段是字符串（JSON 字符串）
        if isinstance(structured, dict) and isinstance(
            structured.get("result"), str
        ):
            raw = structured["result"]
        # 情况2：返回是内容块列表，逐个取出 text 字段拼接成完整字符串
        else:
            raw = "".join(
                getattr(block, "text", "")
                for block in result.content
            )

        # ========== 第三步：JSON 反序列化 ==========
        # 把服务端返回的 JSON 字符串，转回 Python 的列表对象
        pages = json.loads(raw)
        # 格式校验：必须是列表，否则抛异常
        if not isinstance(pages, list):
            raise ValueError("MCP 工具没有返回页面列表。")

        # ========== 第四步：清洗、统一格式后返回 ==========
        return [
            # 展开原 page 的所有字段，追加 origin 标记为 "mcp"，区分来源
            {**page, "origin": "mcp"}
            # 只取前 30 条结果，控制数量
            for page in pages[:30]
            # 过滤：只保留是字典、且 paragraphs 字段是列表的有效条目
            if isinstance(page, dict)
            and isinstance(page.get("paragraphs"), list)
        ]
