from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

def now():
    return datetime.now(timezone.utc).isoformat()
    # `.isoformat()`：转成标准 ISO 时间字符串，示例：`2026-11-13T08:22:30.123456`

def new_task_id():
    date = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    # `trftime("%Y%m%d-%H%M%S")` 格式化 UTC 时间：`20261113-082230`
    return f"{date}-{uuid4().hex[:6]}"
#     - `uuid4().hex`：uuid 转 32 位十六进制字符串；`[:6]` 取前 6 位，缩短 ID
#     - 最终 ID 样例：`20261113-082230-a7f2bc`

@dataclass
class TaskState:
    query: str
    task_id: str = field(default_factory=new_task_id)
    status: str = "created"
    subqueries: list[str] = field(default_factory=list)
    visited_urls: list[str] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    report: str = ""
# 字段	作用
# query	用户原始问题，必填
# task_id	任务唯一标识，日志、存缓存、追踪用
# status	任务状态：created /searching/parsing /finished/failed
# subqueries	拆分出来的子查询，比如大问题拆成多个小搜索词
# visited_urls	已经爬过的 url，用来去重，防止重复请求网页
# sources	收集到的网页源数据：url、标题、摘要等
# errors	任务全流程错误日志
# events	状态变更流水（时间线），可以做前端进度展示、调试
# report	最后整理好给用户的回答文本

    def step(self, status, detail=""):
        self.status = status
        self.events.append({
            "time": now(),
            "status": status,
            "detail": detail,
        })
        # 1. 每次改状态自动打一条事件日志，记录时间 + 详情
        # 2. 代码规范，以后要加埋点、上报、打印日志，只改这一处

        # 示例调用：

        # ```
        # task.step("searching", "开始批量请求搜索接口")
        # task.step("finished", "报告生成完成")
        # ```

        # `events` 就会变成一条一条时间线，复盘任务流程非常方便。

    def add_error(self, stage, error):
        self.errors.append({
            "time": now(),
            "stage": stage,
            "message": str(error),
        })
