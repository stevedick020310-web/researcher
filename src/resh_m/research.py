import os
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote, urlsplit

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS

from .context import ContextManager
from .planner import plan_queries


def search_web(query):
    backend = os.getenv("SEARCH_BACKEND", "auto")
    return DDGS(timeout=15).text(
        query,
        max_results=3,
        backend=backend
    )


def source_key(url):
    """给同一网页生成去重标识。"""
    parsed = urlsplit(url)
    # 举个网址例子：
    # `https://www.baidu.com:8080/abc/search?name=123#top`

    # 拆开对应：

    # - `parsed.scheme` → `https` 协议（http /https/ftp）
    # - `parsed.hostname` → `www.baidu.com` 域名（不带端口）
    # - `parsed.port` → `8080` 端口（上面例子里的）
    # - `parsed.path` → `/abc/search` 路径
    # - `parsed.query` → `name=123` 问号后面的查询参数
    # - `parsed.fragment` → `top` # 后面的锚点

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None

    #拿到 url 路径 → 解码中文 / 转义字符 → 去掉末尾多余斜杠 → 统一小写
    host = parsed.hostname.lower().removeprefix("www.")
    path = unquote(parsed.path).rstrip("/").lower()

    # 当前报告中，维基百科同一条目的语言网址属于同一来源。
    if host == "wikipedia.org" or host.endswith(".wikipedia.org"):
        article = path.rsplit("/", 1)[-1].replace("_", " ")
        return ("wikipedia", article)

    return (host, path, parsed.query)


def fetch_paragraphs(url):
    if source_key(url) is None:
        return []

    try:
        response = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
            #- 如果不写 headers，requests 默认 UA 长得像：`python-requests/2.31.0`
            # 网站一眼就能认出：这是 Python 爬虫，很多网站直接拒绝访问、返回 403。
            # - 写上 `User-Agent: Mozilla/5.0`，伪装成浏览器，骗网站：**我是浏览器，不是爬虫**
        )
        response.raise_for_status()
        #requests 语法：如果返回码是 404、500 这类错误，自动抛出异常，进入下面 except

        if "text/html" not in response.headers.get("Content-Type", "").lower():
            return []
        #判断返回的是不是 html 网页；如果是 pdf、图片，直接跳过，返回空列表

        soup = BeautifulSoup(response.content, "html.parser")

        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        #一次性选中这些标签（js、css、导航栏、页脚），`.decompose()` 直接从文档里面删掉这些垃圾内容

        paragraphs = []
        for tag in soup.find_all("p"):
            text = tag.get_text(" ", strip=True)
            if len(text) >= 40:
                paragraphs.append(text)

        return paragraphs

    except requests.RequestException as error:
        print(f"抓取失败：{url}；原因：{error}")
        return []

class ResearchConductor:
    def __init__(self):
        self.subqueries = []
        self.visited_urls = set()
        self.context_manager = ContextManager()

    def conduct_research(self, query):
        initial_results = search_web(query) or []
        print(f"原问题搜索：{len(initial_results)} 条结果。")

        if not initial_results:
            return []

        try:
            self.subqueries = plan_queries(query, initial_results)
        except Exception as error:
            print(f"规划失败，使用初始结果继续：{error}")
            self.subqueries = []

        print(f"子查询：{self.subqueries or '无'}")

        groups = [(query, initial_results)]

        if self.subqueries:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [
                    pool.submit(search_web, subquery)
                    for subquery in self.subqueries
                ]
                # futures = [
                #     <Future 对象：搜索“宋雨琦 出生地”>,
                #     <Future 对象：搜索“宋雨琦 籍贯”>,
                # ]
                # 关键是：futures[0] 还不是搜索结果，它是第一条
                # 搜索任务。调用 futures[0].result()，才会拿到
                # search_web("宋雨琦 出生地") 返回的结果；
                # 如果这项搜索失败，.result() 会抛出异常。

                for subquery, future in zip(self.subqueries, futures):
                    try:
                        results = future.result() or []
                        print(f"子查询「{subquery}」：{len(results)} 条结果。")
                        groups.append((subquery, results))
                    except Exception as error:
                        print(f"子查询「{subquery}」失败：{error}")

        #轮流从原问题和各子查询取结果，避免前三个来源都来自同一查询。
        candidates = []
        seen_keys = set()
        longest_group = max(len(results) for _, results in groups)
        # groups = [
        #     ("原问题",   ["A1", "A2", "A3"]),
        #     ("子查询一", ["B1", "B2"]),
        #     ("子查询二", ["C1"]),
        # ]

        for position in range(longest_group):
            for search_query, results in groups:
                if position >= len(results):
                    continue

                item = results[position]
                url = item.get("href") or item.get("link") or item.get("url") or ""
                key = source_key(url)

                if key is None or key in seen_keys:
                    continue

                seen_keys.add(key)
                candidates.append({
                    "search_query": search_query,
                    "title": item.get("title") or "无标题",
                    "url": url,
                })
                # candidates = [
                #     {
                #         原问题,
                #         A1tittle,
                #         A1url,
                #     },
                #     {
                #         子查询一,
                #         B1tittle,
                #         B1url,
                #     }
                # ]
                if len(candidates) == 8:
                    break

            if len(candidates) == 8:
                break

        self.visited_urls = {item["url"] for item in candidates}
        # 如果 candidates 是：

        # ```
        # candidates = [
        #     {"url": "a.com"},
        #     {"url": "b.com"},
        #     {"url": "a.com"},  # 重复了
        # ]
        # ```

        # 执行完之后：

        # ```
        # self.visited_urls = {"a.com", "b.com"}
        # ```
        print(f"合并去重后，准备抓取 {len(candidates)} 篇网页。")

        pages = []

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [
                pool.submit(fetch_paragraphs, item["url"])
                for item in candidates
            ]

            for item, future in zip(candidates, futures):
                try:
                    paragraphs = future.result()
                except Exception as error:
                    print(f"网页处理失败：{item['url']}；原因：{error}")
                    continue

                if paragraphs:
                    pages.append({**item, "paragraphs": paragraphs})

        sources = self.context_manager.select_context(query, pages)
        print(f"抓取后可用网页 {len(pages)} 篇，选入上下文 {len(sources)} 篇。")
        return sources
