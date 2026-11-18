# 示例服务把 mcp_notes/ 里的笔记作为一个 search_notes 工具提供：

# 导入 JSON 序列化模块，用于把 Python 字典/列表转成 JSON 字符串，方便跨语言/跨程序传输
import json

# 从 MCP 服务端库导入 MCPServer 类，用于创建 MCP 服务、注册工具、和大模型通信
from mcp.server import MCPServer

# 从同目录下的 local_docs 模块，导入我们之前讲过的本地文档检索加载器
from .local_docs import LocalDocsRetriever


# ============================================================
# 创建一个 MCP 服务端实例，服务名称为 "resh-m-notes"
# 名称用于标识这个工具服务，大模型侧会看到这个工具来源
# ============================================================
mcp = MCPServer("resh-m-notes")


# ============================================================
# 装饰器：把下面的函数注册为 MCP 工具，大模型可以按名字调用它
# 函数名 search_notes 就是工具名，函数文档字符串就是工具的描述，大模型能看到
# ============================================================
@mcp.tool()
def search_notes(query: str) -> str:
    """读取 mcp_notes 中可供研究的本地笔记。"""
    # 1. 实例化本地文档检索器，指定根目录为 mcp_notes 文件夹
    # 2. 调用 load_pages 方法，传入查询词，得到所有文本块列表（格式和网页搜索结果一致）
    pages = LocalDocsRetriever("mcp_notes").load_pages(query)

    # 取前 30 个结果，转成 JSON 字符串返回
    # ensure_ascii=False：保证中文正常显示，不会变成 \uXXXX 编码
    return json.dumps(pages[:30], ensure_ascii=False)


# ============================================================
# 程序入口：直接运行本文件时，启动 MCP 服务
# 启动后会保持运行，等待大模型端的调用请求
# ============================================================
if __name__ == "__main__":
    mcp.run()
