#统一选择证据，并给所有来源一个总长度预算
import math
import re
from collections import Counter

def tokens(text):
    text = text.lower()
    result = re.findall(r"[a-z0-9]+", text)

    for chinese in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(chinese) == 1:
            result.append(chinese)
        else:
            result.extend(
                chinese[i:i + 2]
                for i in range(len(chinese) - 1)
            )
    return result

# bM25 就是搜索引擎经典相关性打分算法：**词频 + 逆文档频率 + 文档长度惩罚**，分数越高越相关
def bm25_scores(query, passages):
    documents = [Counter(tokens(text)) for text in passages]
    if not documents:
        return []

    query_terms = set(tokens(query))
    document_count = len(documents)
    average_length = (
        sum(sum(doc.values()) for doc in documents) / document_count
    ) or 1

    document_frequency = {
        term: sum(term in doc for doc in documents)
        for term in query_terms
    }

    scores = []
    for doc in documents:
        length = sum(doc.values())
        score = 0.0

        for term in query_terms:
            frequency = doc.get(term, 0)
            if not frequency:
                continue

            count = document_frequency[term]
            idf = math.log1p(
                (document_count - count + 0.5) / (count + 0.5)
            )
            score += idf * frequency * 2.5 / (
                frequency + 1.5 * (0.25 + 0.75 * length / average_length)
            )

        scores.append(score)

    return scores



class ContextManager:
    def __init__(self, max_sources=6, max_chars=5000):
        self.max_sources = max_sources
        self.max_chars = max_chars

    def select_context(self, query, pages):
            # 把每个网页里的段落拆出来，组成候选：(page, paragraph)
            candidates = []
            for page in pages:
                for paragraph in page.get("paragraphs", []):
                    if paragraph.strip():
                        candidates.append((page, paragraph))

            # 给所有段落算BM25分数
            scores = bm25_scores(
                query,
                [paragraph for _, paragraph in candidates],
            )
            # 从高分到低分排序
            ranked_indexes = sorted(
                range(len(candidates)),
                key=lambda index: scores[index],
                reverse=True,
            )

            sources_by_url = {} # key:url，存这个网页的信息+证据片段
            seen_text = set()    # 指纹，用来去重相似文本
            used_chars = 0       # 已经用掉多少字符

            for index in ranked_indexes:
                if scores[index] <= 0: # 分数<=0直接不要
                    break

                page, paragraph = candidates[index]
                url = page["url"]
                excerpt = paragraph[:700].strip() # 每个片段最多截取700字
                # 文本指纹：去掉空白、小写，用来判断两段是不是几乎一样
                fingerprint = re.sub(r"\s+", "", excerpt).lower()

                # 跳过空片段 / 和已经收录的文本重复
                if not excerpt or fingerprint in seen_text:
                    continue
                # 加上这个片段会超过总字符上限，跳过
                if used_chars + len(excerpt) > self.max_chars:
                    continue
                # 还没收录这个url，但是来源已经满6个了，跳过
                if url not in sources_by_url and len(sources_by_url) >= self.max_sources:
                    continue

                # 如果是新url，新建一条来源记录
                if url not in sources_by_url:
                    sources_by_url[url] = {
                        "title": page["title"],
                        "url": url,
                        "origin": page.get("origin", "web"),
                        "evidence": [], # 这个网页下最多存2段证据
                    }

                source = sources_by_url[url]
                if len(source["evidence"]) == 2:
                    continue # 同一个网页最多拿2个段落，防止一个网页占满上下文

                source["evidence"].append(excerpt)
                seen_text.add(fingerprint)
                used_chars += len(excerpt)

            return list(sources_by_url.values())

# 输入
# pages = [
#     {
#         "url": "shturl.cc/AnMxarI",
#         "title": "AI发展简史",
#         "paragraphs": [
#             "1956年达特茅斯会议提出人工智能概念。",
#             "深度学习在2012年后迎来爆发。"
#         ]
#     },
#     {
#         "url": "shturl.cc/KOWUXEr",
#         "title": "大模型入门",
#         "paragraphs": [
#             "大模型属于人工智能的一个分支。"
#         ]
#     }
# ]

# 输出
# [
#     {
#         "title": "AI发展简史",
#         "url": "shturl.cc/AnMxarI",
#         "origin": "web",
#         "evidence": [
#             "1956年达特茅斯会议提出人工智能概念。",
#             "深度学习在2012年后迎来爆发。"
#         ]
#     },
#     {
#         "title": "大模型入门",
#         "url": "shturl.cc/KOWUXEr",
#         "origin": "web",
#         "evidence": [
#             "大模型属于人工智能的一个分支。"
#         ]
#     }
# ]



# ## 函数：提取关键词（用来做简单文本匹配打分）
# def keywords(text):
#     text = text.lower()
#     words = set(re.findall(r"[a-z0-9]+", text))

#     for chinese_text in re.findall(r"[\u4e00-\u9fff]+", text):
#         for position in range(len(chinese_text) - 1):
#             words.add(chinese_text[position:position + 2])
# # 滑窗：两两取中文，比如 "人工智能" → "人工"、"智能"
#     return words

# 类：上下文管理器，从一堆网页里挑最相关的段落，控制总长度、来源数量
# class ContextManager:
#     def __init__(self, max_sources=5, max_chars=4500):
#         self.max_sources = max_sources
#         self.max_chars = max_chars

#     #从每个网页中挑选最符合的两段，且不重复
#     def select_context(self, query, pages):
#         sources = []
#         seen_paragraphs = set()
#         used_chars = 0

#         # pages = [
#         #     {
#         #         "search_query": "宋雨琦 籍贯 家乡",
#         #         "paragraphs": ["网页正文的第一段", "网页正文的第二段"],
#         #         "title": "网页标题",
#         #         "url": "https://example.com/page",
#         #     }
#         # ]
#         for page in pages:
#             query_words = keywords(query + " " + page["search_query"])
#             ranked = []

#             for paragraph in page["paragraphs"]:
#                 score = len(query_words & keywords(paragraph))
#                 if score > 0:
#                     ranked.append((score, paragraph))

#             ranked.sort(key=lambda item: item[0], reverse=True)
#             evidence = []

#             # 从高分段落开始挨个拿
#             for _, paragraph in ranked:
#                 # 截取前700个字，去掉首尾空白
#                 excerpt = paragraph[:700].strip()
#                 # 生成指纹：把所有空白删掉+小写，用来判断两段是不是几乎一样
#                 fingerprint = re.sub(r"\s+", "", excerpt).lower()

#                 if fingerprint in seen_paragraphs:
#                     continue
#                 if used_chars + len(excerpt) > self.max_chars:
#                     continue

#                 evidence.append(excerpt)
#                 seen_paragraphs.add(fingerprint)
#                 used_chars += len(excerpt)

#                 # 每个网页最多挑2段证据，够了就不再拿这个网页的其他段落
#                 if len(evidence) == 2:
#                     break

#             if evidence:
#                 sources.append({
#                     "title": page["title"],
#                     "url": page["url"],
#                     "evidence": evidence,
#                 })

#             if len(sources) >= self.max_sources:
#                 break

#         return sources