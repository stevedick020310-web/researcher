# from .research import ResearchConductor
# from .writer import ReportGenerator


# class GPTResearcher:
#     def __init__(self, query):
#         self.query = query
#         self.context = []
#         self.research_conductor = ResearchConductor()
#         self.report_generator = ReportGenerator()

#     def conduct_research(self):
#         self.context = self.research_conductor.conduct_research(self.query)
#         return self.context

#     def write_report(self):
#         return self.report_generator.write_report(
#             self.query,
#             self.context,
#         )

# 导入操作系统模块，用于读取环境变量，控制运行模式
import os

# 导入上下文筛选器：BM25 相关性排序 + 多规则过滤，选出最相关的段落
from .context import ContextManager
# 导入本地文档检索器：扫描本地 docs 目录，读取 md/txt 文件并分块
from .local_docs import LocalDocsRetriever
# 导入联网研究执行器：就是你之前学的 collect_sources 整套逻辑，联网搜索+抓网页+提取证据
from .research import ResearchConductor
# 导入任务状态类：@dataclass 定义的数据类，全程记录任务的进度、子查询、链接、资料、报错等
from .state import TaskState
# 导入报告生成器：调用大模型，基于筛选好的上下文资料撰写最终报告
from .writer import ReportGenerator


# ============================================================
# 类名：GPTResearcher
# 功  能：研究报告系统的主门面类。统一调度「多源检索 → 上下文筛选 → 报告生成」全流程
#        对外屏蔽底层复杂逻辑，使用者只需调用两个方法即可完成完整研究
# 初始化参数：
#   query: str    用户的研究问题/查询词
# ============================================================
class GPTResearcher:
    # 初始化方法：实例化所有底层组件，初始化任务状态
    def __init__(self, query):
        # 保存用户的原始查询问题
        self.query = query
        # 初始化任务状态对象，全程记录任务进度、数据、错误
        self.state = TaskState(query=query)
        # 存放最终筛选好的上下文资料（给大模型写报告用）
        self.context = []
        # 实例化联网研究执行器
        self.research_conductor = ResearchConductor()
        # 实例化上下文筛选器（BM25 打分 + 多规则限流去重）
        self.context_manager = ContextManager()
        # 实例化报告生成器（调用大模型写报告）
        self.report_generator = ReportGenerator()

    # ============================================================
    # 方法名：conduct_research
    # 功  能：执行多源检索 + 上下文筛选，得到最终可用的参考资料
    #        支持三种数据源模式，可通过环境变量切换；单个数据源失败不影响整体
    # 输  入：无（使用初始化时传入的 query）
    # 返  回：list[dict]，筛选后的上下文资料列表，每个元素含 title/url/evidence 等
    # ============================================================
    def conduct_research(self):
        # 统一存放所有数据源的原始候选段落，格式全部统一为 pages 标准结构
        pages = []

        # 从环境变量读取数据源模式，默认 hybrid（混合模式）
        # 可选值：web（仅联网）、local（仅本地文档）、hybrid（联网+本地混合）
        mode = os.getenv("SOURCE_MODE", "hybrid").lower()

        # 参数校验：模式不合法直接抛出异常，提前终止
        if mode not in {"web", "local", "hybrid"}:
            raise ValueError("SOURCE_MODE 只能是 web、local 或 hybrid。")

        # ========== 数据源1：联网网页检索 ==========
        # web 模式或 hybrid 模式下执行
        if mode in {"web", "hybrid"}:
            # 记录任务状态：开始执行联网检索步骤
            self.state.step("web_research")
            try:
                # 调用联网研究器，执行完整的「原词搜索→子查询扩展→并发抓取→筛选证据」流程
                # 返回的 web_sources 是已经筛选好的带证据的来源列表
                web_sources = self.research_conductor.conduct_research(self.query)

                # 把联网结果统一转换成 pages 标准格式，和本地文档、MCP 格式对齐
                for source in web_sources:
                    pages.append({
                        "title": source["title"],
                        "url": source["url"],
                        "origin": "web",          # 标记来源为网页
                        "search_query": self.query,
                        "paragraphs": source["evidence"],  # 证据段落作为候选段落
                    })
            except Exception as error:
                # 联网检索失败，只记录错误，不抛出，不影响其他数据源执行
                self.state.add_error("web_research", error)

            # 把联网过程中产生的子查询、访问过的链接，同步保存到任务状态里
            self.state.subqueries = self.research_conductor.subqueries
            self.state.visited_urls = sorted(
                self.research_conductor.visited_urls
            )

        # ========== 数据源2：本地文档检索 ==========
        # local 模式或 hybrid 模式下执行
        if mode in {"local", "hybrid"}:
            # 记录任务状态：开始执行本地文档检索步骤
            self.state.step("local_retrieval")
            try:
                # 实例化本地文档检索器，读取 docs 目录，分块后直接追加到 pages
                pages.extend(
                    LocalDocsRetriever("docs").load_pages(self.query)
                )
            except Exception as error:
                # 本地检索失败只记录错误，不中断整体流程
                self.state.add_error("local_retrieval", error)

        # ========== 数据源3：MCP 笔记检索（可选开关） ==========
        # 只有环境变量 ENABLE_MCP 设置为 "1" 时才启用
        if os.getenv("ENABLE_MCP") == "1":
            # 记录任务状态：开始执行 MCP 笔记检索步骤
            self.state.step("mcp_retrieval")
            try:
                # 延迟导入：用到的时候才导入，没装 MCP 依赖也不影响主程序
                from .mcp_bridge import MCPNotesRetriever

                # 调用 MCP 检索器，通过子进程调用 MCP 服务，拿到笔记分块结果
                pages.extend(
                    MCPNotesRetriever().load_pages(self.query)
                )
            except Exception as error:
                # MCP 检索失败只记录错误，不中断整体流程
                self.state.add_error("mcp_retrieval", error)

        # ========== 统一上下文筛选 ==========
        # 记录状态：开始上下文筛选，同时记录候选段落总数
        self.state.step("context_selection", f"候选段落来源：{len(pages)}")

        # 所有数据源的 pages 汇总后，统一交给上下文管理器做 BM25 打分 + 规则筛选
        # 这就是「接口统一设计」的核心：不管来源是哪里，格式一样，一套筛选逻辑通用
        self.context = self.context_manager.select_context(
            self.query,
            pages,
        )

        # 把最终筛选好的资料源保存到任务状态
        self.state.sources = self.context

        # 根据筛选结果更新状态：无资料 / 准备就绪
        if not self.context:
            self.state.step("no_sources")
        else:
            self.state.step("ready_to_write", f"选中来源：{len(self.context)}")

        # 返回筛选好的上下文资料
        return self.context

    # ============================================================
    # 方法名：write_report
    # 功  能：基于已筛选好的上下文资料，调用大模型生成最终研究报告
    # 输  入：无（使用 self.query 和 self.context）
    # 返  回：str，生成好的完整报告文本
    # ============================================================
    def write_report(self):
        # 记录状态：开始撰写报告
        self.state.step("writing_report")

        try:
            # 调用报告生成器，传入原始问题 + 上下文资料，生成报告
            report = self.report_generator.write_report(
                self.query,
                self.context,
            )
        except Exception as error:
            # 生成失败，记录错误，更新状态为失败，再向上抛出异常
            self.state.add_error("writing_report", error)
            self.state.step("failed")
            raise

        # 生成成功，把报告存入任务状态
        self.state.report = report
        # 更新状态为全部完成
        self.state.step("complete")
        # 返回报告文本
        return report
