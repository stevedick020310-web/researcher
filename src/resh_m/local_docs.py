# 导入 pathlib 路径处理工具，跨平台（Windows/Mac/Linux）处理文件和目录路径，替代手动拼接字符串
from pathlib import Path


# ============================================================
# 函数名：split_text
# 功  能：滑动窗口文本分块。将长文本切分为多个带首尾重叠的小块，避免完整语义被中间截断
# 输  入：
#   text: str          待切分的原始长文本
#   chunk_size: int    单个文本块的最大字符数，默认 600
#   overlap: int       相邻两个块的重叠字符数，默认 100
# 返  回：生成器（generator），逐个产出切分后的文本块字符串，节省内存
# ============================================================
def split_text(text, chunk_size=600, overlap=100):
    # 计算窗口每次向前滑动的步长 = 块总大小 - 重叠长度
    step = chunk_size - overlap

    # 从文本第 0 位开始，每次前进 step 个字符，遍历所有块的起始下标
    for start in range(0, len(text), step):
        # 切片取出当前块的文本，并去除块首尾的空格、换行符
        chunk = text[start:start + chunk_size].strip()
        # 过滤空块（文本末尾全是空白字符的情况）
        if chunk:
            # 生成器语法：逐个产出文本块，不一次性把所有块加载到内存
            yield chunk


# ============================================================
# 类名：LocalDocsRetriever
# 功  能：本地文档检索加载器。扫描指定目录、筛选合规文件、读取内容、分块包装，
#        输出格式与网页搜索结果完全统一，可直接对接 BM25 相关性筛选器
# 初始化参数：
#   directory: str    本地文档存放的目录路径，默认值为 "docs"
# ============================================================
class LocalDocsRetriever:
    # 初始化方法：创建实例时绑定文档目录
    def __init__(self, directory="docs"):
        # 将目录字符串转为 Path 对象，方便后续跨平台路径操作
        self.directory = Path(directory)

    # ============================================================
    # 方法名：load_pages
    # 功  能：递归扫描目录下所有文档，读取内容并分块，包装为标准 pages 列表
    # 输  入：
    #   query: str    查询关键词，仅作为元信息存入结果，不做筛选
    # 返  回：list[dict]，每个元素是一个文本块字典，字段与网页搜索结果完全兼容
    #         字典字段：title / url / origin / search_query / paragraphs
    # ============================================================
    def load_pages(self, query):
        # 校验：如果指定的目录不存在，直接返回空列表
        if not self.directory.is_dir():
            return []

        # 初始化结果列表，存放所有切分好的文本块
        pages = []

        # 递归遍历目录下所有文件和子目录，按名称排序保证每次运行结果顺序一致
        # rglob("*") = 递归匹配所有子路径
        for path in sorted(self.directory.rglob("*")):
            # 第一层过滤：跳过文件夹，只保留 .md / .txt 后缀的纯文本文件
            # suffix.lower() 转小写，兼容 .MD / .TXT 大写后缀
            if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
                continue

            # 第二层过滤：跳过大于 1MB 的文件，避免大文件拖慢处理速度
            # st_size 单位是字节；1_000_000 是 Python 数字可读性下划线，数值等于 1000000
            if path.stat().st_size > 1_000_000:
                continue

            # 以 UTF-8 编码读取文件全文
            # errors="replace"：遇到无法解码的乱码字符自动用替换符补齐，避免程序直接崩溃
            text = path.read_text(encoding="utf-8", errors="replace")

            # 计算文件相对于根目录的相对路径，并用正斜杠统一格式（兼容 Windows 反斜杠）
            relative_path = path.relative_to(self.directory).as_posix()

            # 调用分块函数，将整篇文档切分为多个块；number 为块编号，从 1 开始计数
            for number, chunk in enumerate(split_text(text), start=1):
                # 将每个文本块包装为标准 page 字典，与网页搜索结果格式完全一致
                pages.append({
                    "title": path.name,          # 文件名作为文档标题
                    "url": f"{self.directory.name}/{relative_path}#chunk-{number}",  # 路径+块编号，模拟锚点定位来源
                    "origin": "local",           # 标记来源为本地文档，与网页来源区分
                    "search_query": query,       # 关联的查询词元信息
                    "paragraphs": [chunk],       # 文本块内容，包装为列表与网页段落格式统一
                })

                # 数量上限：最多收集 80 个块就提前返回，平衡检索效果和计算速度
                if len(pages) >= 80:
                    return pages

        # 全部文件处理完成，返回最终结果
        return pages
