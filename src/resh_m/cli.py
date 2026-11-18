# from pathlib import Path

# from dotenv import load_dotenv

# from .agent import GPTResearcher


# def main():
#     load_dotenv(Path.cwd() / ".env")

#     query = input("请输入研究问题：").strip()
#     if not query:
#         print("研究问题不能为空。")
#         return

#     researcher = GPTResearcher(query)

#     try:
#         sources = researcher.conduct_research()
#     except Exception as error:
#         print(f"研究阶段失败：{error}")
#         return

#     if not sources:
#         print("没有找到可用资料；未调用写作模型，旧 report.md 未更新。")
#         return

#     try:
#         report = researcher.write_report()
#     except Exception as error:
#         print(f"报告生成或引用检查失败：{error}")
#         return

#     Path("report.md").write_text(report, encoding="utf-8")
#     print(f"完成：使用 {len(sources)} 篇来源，已保存 report.md。")

# 导入 JSON 模块，用于序列化任务状态、证据等结构化数据
import json
# 从 dataclasses 导入 asdict，用于把 TaskState 数据类对象转换成普通字典，方便存成 JSON
from dataclasses import asdict
# 导入路径处理工具，用于创建目录、读写文件
from pathlib import Path

# 导入 dotenv 库的 load_dotenv，用于从 .env 文件加载环境变量（API密钥、模式开关等）
from dotenv import load_dotenv

# 导入核心研究代理类 GPTResearcher，就是上一节讲的总调度类
from .agent import GPTResearcher


# ============================================================
# 函数名：main
# 功  能：命令行程序主入口。负责交互输入、调度核心流程、异常捕获、结果归档
# 输  入：无（通过控制台交互输入问题）
# 输  出：无返回值，直接在控制台打印进度，并将结果写入文件
# ============================================================
def main():
    # 加载当前工作目录下的 .env 文件，把里面的配置项读入系统环境变量
    # 比如 API_KEY、SOURCE_MODE、ENABLE_MCP 等配置都写在 .env 里
    load_dotenv(Path.cwd() / ".env")

    # 控制台交互：提示用户输入研究问题，去除首尾空白
    query = input("请输入研究问题：").strip()
    # 输入校验：空问题直接提示并退出
    if not query:
        print("研究问题不能为空。")
        return

    # 实例化核心研究代理，传入用户问题
    researcher = GPTResearcher(query)

    try:
        # ========== 第一步：执行多源检索，筛选证据资料 ==========
        sources = researcher.conduct_research()

        # 如果没搜到任何有效资料，直接提示结束，不调用大模型写作，节省token
        if not sources:
            print("没有可用证据；本次未调用写作模型。")
            return

        # ========== 第二步：调用大模型生成研究报告 ==========
        report = researcher.write_report()
        # 把报告写入当前目录下的 report.md 文件，方便直接查看
        Path("report.md").write_text(report, encoding="utf-8")
        # 控制台打印成功提示
        print(f"完成：使用 {len(sources)} 篇来源，已保存 report.md。")

    # ========== 异常捕获：任何环节出错都在这里兜底 ==========
    except Exception as error:
        # 记录错误到任务状态
        researcher.state.add_error("cli", error)
        # 更新任务状态为失败
        researcher.state.step("failed")
        # 控制台打印失败原因
        print(f"任务失败：{error}")

    # ========== finally：无论成功失败，一定会执行，归档本次任务所有数据 ==========
    finally:
        # 构造本次任务的归档目录：runs/任务ID/
        run_dir = Path("runs") / researcher.state.task_id
        # 创建目录，parents=True 表示父目录不存在也一起建，exist_ok=True 表示已存在也不报错
        run_dir.mkdir(parents=True, exist_ok=True)

        # 归档1：完整任务状态 → state.json
        # 用 asdict 把 dataclass 转成字典，再序列化为格式化的 JSON，中文不转义
        (run_dir / "state.json").write_text(
            json.dumps(
                asdict(researcher.state),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # 归档2：筛选后的证据资料 → evidence.json
        (run_dir / "evidence.json").write_text(
            json.dumps(
                researcher.state.sources,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # 归档3：如果生成了报告，单独存一份 report.md
        if researcher.state.report:
            (run_dir / "report.md").write_text(
                researcher.state.report,
                encoding="utf-8",
            )

        # 控制台提示归档目录位置
        print(f"本次任务记录：{run_dir}")
