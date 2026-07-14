#!/usr/bin/env python3
"""快速预扫 — 纯正则 0 Token 机械检查

对标 rules.md 28条规则中可自动化的项。扫描论文文本，输出结构化报告。

用法：
    python3 quick_scan.py <论文文件>
    python3 quick_scan.py -       # 从 stdin 读取

覆盖：
    1. 句长统计 (2.2)
    2. 禁词扫描 (4.4)
    3. AI 高频警示词 (4.4)
    4. 缩写计数 (4.9)
    5. 名词化检测 (2.4)
    6. 被动语态占比 (2.1)
    7. 空转短语 (6.1 A #3)
    8. 万能结尾 (6.1 A #4 + B #12)
    9. 宣告式膨胀 (6.1 B #9)
    10. EN 宣告式动词 (6.1 B #7) [EN only]
    11. EN 句尾 -ing 空转 (6.1 B #8) [EN only]
    12. EN filler 短语 (6.1 B #11) [EN only]
    13. ZH 万能空话 (6.1 B #15) [ZH only]
    14. 中文 AI 腔 (6.1 B #16-18) [ZH only]

6.1 A 层 #2/#5/#6（对称排比/读出声/完美闭环）需人读出声，不在自动扫描范围内。
"""

import re
import sys
from collections import Counter

# ─── 配置 ────────────────────────────────────────────

# 2.2 句长
MAX_SENTENCE_LEN_EN = 35       # 英文单句上限
MAX_SENTENCE_LEN_ZH = 50       # 中文单句上限（中文自然更长）
TARGET_AVG_RANGE_EN = (15, 25) # 英文目标平均句长
TARGET_AVG_RANGE_ZH = (20, 35) # 中文目标平均句长
CONSECUTIVE_LONG = 3           # 连续 N 句长句触发警告

# 4.4 禁词（绝对禁止）
BANNED_WORDS_EN = [
    "revolutionary", "first-ever", "the first time ever",
    "to the best of our knowledge, the first",
    "fundamentally new", "it is obvious that",
    "undoubtedly", "without doubt",
]
BANNED_WORDS_ZH = [
    "革命性的", "史无前例", "根本性创新",
    "显然", "不言而喻",
]

# 4.4 需数字支撑的自我评价词
SELF_PRAISE_EN = ["significantly", "dramatically", "substantially"]
SELF_PRAISE_ZH = ["显著优于", "大幅提升", "极大改进"]

# 4.4 AI 高频警示词（阈值 = 出现次数上限）
AI_FLAG_WORDS_EN = {
    "pivotal": 0, "showcase": 0, "underscore": 0, "delve": 0,
    "tapestry": 0, "testament": 0, "vibrant": 0, "interplay": 0,
    "fostering": 0, "invaluable": 0, "crucial": 1,
    "landscape": 1, "furthermore": 2, "moreover": 2, "notably": 2,
}
AI_FLAG_WORDS_ZH = {
    "毋庸置疑": 0, "不言而喻": 0, "显而易见": 0, "众所周知": 0,
    "不可否认的是": 0, "必须承认的是": 0,
    "具有重要的理论意义和现实意义": 0,
}
AI_FLAG_PATTERNS_ZH = {
    "不仅……而且……": re.compile(r"不仅[^。！？\n]{0,30}?而且"),
    "从而……进而……最终……": re.compile(r"从而[^。！？\n]{0,20}?进而[^。！？\n]{0,20}?最终"),
}

# 4.4 需出现在句中的 self-eval（simple/elegant/powerful）
SELF_EVAL_EN = ["simple", "simply", "elegant", "powerful", "strongly", "effective"]

# 2.4 名词化后缀
NOMINALIZATION_SUFFIX = re.compile(
    r"\b\w+(tion|sion|ment|ance|ence|ity)\b", re.IGNORECASE
)

# 2.1 被动语态
PASSIVE_PATTERN = re.compile(
    r"\b(?:is|are|was|were|been|be)\s+(\w+(?:ed|en|t))\b", re.IGNORECASE
)
PASSIVE_EXCLUDES = {
    "used", "based", "related", "involved", "required",
    "expected", "applied", "limited", "fixed", "designed",
    "published", "reported", "noted",
}

# 6.1 A 空转短语
FILLER_PHRASES_ZH = [
    "值得注意的是", "从某种意义上说", "不言而喻",
    "换言之", "换句话来说", "综上所述",
]
FILLER_PHRASES_EN = [
    "it is worth noting", "in this regard", "it is important to note",
    "due to the fact that",
]

# 6.1 A #4 万能结尾
FILLER_ENDINGS_ZH = [
    "未来研究可以进一步探索", "有待进一步研究",
    "为后续研究提供了方向", "仍有待深入探讨",
]
FILLER_ENDINGS_EN = [
    "future research should explore",
    "future work will focus on",
    "remains to be seen",
    "paves the way for future",
]

# 6.1 B #7 EN 宣告式动词（替代简单 is/has）
EN_INFLATED_VERBS = ["serves as", "stands as", "boasts", "acts as"]

# 6.1 B #8 EN 句尾 -ing 空转（语义模糊类）
EN_ING_FILLER = re.compile(
    r"\b(?:highlighting|underscoring|emphasizing|showcasing|demonstrating|reflecting|illustrating|revealing)\s+(?:its|the|their|this|our)\s+\w+",
    re.IGNORECASE,
)

# 6.1 B #9 EN+ZH 宣告式膨胀
EN_GRANDIOSE = [
    "marks a pivotal moment", "represents a significant shift",
    "setting the stage for", "paves the way for",
    "a major step forward", "a significant milestone",
]
ZH_GRANDIOSE = [
    "标志着关键的转折", "代表了重大转变",
    "为……奠定了基础", "迈出了重要一步",
    "具有重要的理论意义和现实意义",
    "为……做出了重要贡献",
]

# 6.1 B #11 EN filler 短语
EN_FILLER_PHRASES = [
    "in order to", "due to the fact that",
    "it is important to note that",
    "at this point in time", "in the event that",
]

# 6.1 B #12 EN+ZH 万能结尾
EN_BOILERPLATE_ENDINGS = [
    "the future looks bright", "this represents a major step forward",
    "holds great promise", "opens up new possibilities",
]
ZH_BOILERPLATE_ENDINGS = [
    "未来可期", "前景广阔", "大有可为",
    "开启新的篇章", "迎来新的机遇",
]

# 6.1 B #15 ZH 万能空话
# 6.1 B #15 ZH 万能空话（与 B #9 ZH_GRANDIOSE 不重复——已被 #9 覆盖的不再列入）
ZH_EMPTY_PRAISE = [
    "具有重要的实践价值",
    "具有深远的影响",
]

# 6.1 B 中文 AI 腔
ZH_AI_PATTERNS = {
    "范畴词赘余": re.compile(r"(?:在)([^。！？\n]{2,8})(?:方面|领域|过程|角度)"),
    "X性通胀": re.compile(r"(重要性|可行性|必要性|可能性|鲁棒性|有效性|合理性)"),
    "虚词框架": re.compile(r"(?:通过)([^。！？\n]{2,10})(?:的方式)"),
}

# ─── Markdown 清洗 ────────────────────────────────────

def clean_markdown(text: str) -> str:
    """清洗 Markdown 标记，保留正文内容
    
    跳过：代码块、内联代码、表格、URL、路径、标题、块引用
    """
    text = re.sub(r"```[\s\S]*?```", " ", text)      # 代码块
    text = re.sub(r"`[^`]+`", " ", text)              # 内联代码
    text = re.sub(r"^\|.*\|$", " ", text, flags=re.MULTILINE)  # 表格行
    text = re.sub(r"https?://\S+", " ", text)         # URL
    text = re.sub(r"(?:^|\s)/[\w.-]+(?:/[\w.-]+)+", " ", text, flags=re.MULTILINE)  # 路径（至少两级目录）
    text = re.sub(r"^#{1,6}\s.*$", " ", text, flags=re.MULTILINE)  # 标题
    text = re.sub(r"^>\s.*$", " ", text, flags=re.MULTILINE)       # 块引用
    text = re.sub(r"!\[.*?\]\(.*?\)", " ", text)      # 图片
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # 链接（保留文字）
    return text


# ─── 分词工具 ─────────────────────────────────────────

def split_sentences_en(text):
    """简单英文分句"""
    return re.split(r"(?<=[.!?])\s+", text)

def split_sentences_zh(text):
    """简单中文分句"""
    sents = re.split(r"[。！？\n]+", text)
    return [s.strip() for s in sents if s.strip()]

def is_chinese_text(text):
    """判断是否主要为中文文本"""
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    total_alpha = len(re.findall(r"[a-zA-Z]", text))
    return chinese_chars > total_alpha


# ─── 检查函数 ─────────────────────────────────────────

def check_sentence_length(text):
    """1. 句长统计 (2.2)"""
    is_zh = is_chinese_text(text)
    if is_zh:
        sents = split_sentences_zh(text)
        unit = "字"
        max_len = MAX_SENTENCE_LEN_ZH
        target_avg = TARGET_AVG_RANGE_ZH
    else:
        sents = split_sentences_en(text)
        unit = "词"
        max_len = MAX_SENTENCE_LEN_EN
        target_avg = TARGET_AVG_RANGE_EN

    lens = [len(s.split()) if not is_zh else len(s) for s in sents]
    result = {
        "label": "句长统计 (2.2)",
        "total": len(sents),
        "avg": round(sum(lens) / len(lens), 1) if lens else 0,
        "max": max(lens) if lens else 0,
        "unit": unit,
        "issues": [],
    }

    if result["avg"] < target_avg[0] or result["avg"] > target_avg[1]:
        result["issues"].append(
            f"平均句长 {result['avg']}{unit}，建议范围 {target_avg[0]}-{target_avg[1]}{unit}"
        )

    over_max = [(i, l) for i, l in enumerate(lens) if l > max_len]
    if over_max:
        result["issues"].append(
            f"{len(over_max)} 句超过上限 {max_len}{unit}"
        )

    # 连续长句
    consec = 0
    consec_starts = []
    for i, l in enumerate(lens):
        if l > max_len * 0.8:  # 接近上限
            consec += 1
            if consec >= CONSECUTIVE_LONG:
                consec_starts.append(i - consec + 1)
                consec = 0
        else:
            consec = 0
    if consec_starts:
        result["issues"].append(
            f"{len(consec_starts)} 处连续 ≥{CONSECUTIVE_LONG} 句接近长度上限"
        )

    m = len(result["issues"])
    result["status"] = "✅" if m == 0 else ("⚠️" if m <= 2 else "❌")
    return result


def check_banned_words(text):
    """2. 禁词扫描 (4.4)"""
    is_zh = is_chinese_text(text)
    banned = BANNED_WORDS_ZH if is_zh else BANNED_WORDS_EN
    found = []

    for w in banned:
        if w.lower() in text.lower():
            found.append(w)

    # + self-praise without numbers
    praise_list = SELF_PRAISE_ZH if is_zh else SELF_PRAISE_EN
    for w in praise_list:
        if w.lower() in text.lower():
            found.append(f"{w} (需具体数字)")

    result = {
        "label": "禁词扫描 (4.4)",
        "found": found,
        "status": "✅" if not found else "❌",
    }
    return result


def check_ai_flag_words(text):
    """3. AI 高频警示词 (4.4)"""
    is_zh = is_chinese_text(text)
    result = {"label": "AI 高频警示词 (4.4)", "issues": []}

    if is_zh:
        for word, threshold in AI_FLAG_WORDS_ZH.items():
            count = text.count(word)
            if count > threshold:
                result["issues"].append(f"{word}: 出现 {count} 次（阈值 {threshold}）")

        for label, pattern in AI_FLAG_PATTERNS_ZH.items():
            matches = pattern.findall(text)
            if len(matches) > 1:
                result["issues"].append(f"{label}: {len(matches)} 次（建议 ≤1）")
    else:
        for word, threshold in AI_FLAG_WORDS_EN.items():
            count = len(re.findall(r"\b" + word + r"\b", text, re.IGNORECASE))
            if count > threshold:
                result["issues"].append(f"{word}: {count} (threshold {threshold})")

        # "serves as", "stands as", "boasts"
        for w in ["serves as", "stands as", "boasts"]:
            count = len(re.findall(r"\b" + w + r"\b", text, re.IGNORECASE))
            if count > 0:
                result["issues"].append(f"{w}: {count}")

    result["status"] = "✅" if not result["issues"] else "⚠️"
    return result


def check_abbreviations(text):
    """4. 缩写计数 (4.9)
    
    只检查定义型缩写（如 "BERT (Bidirectional...)"），
    跳过普通大写 token（文本已在入口清洗过 Markdown）。
    """
    # 优先找定义型缩写："BERT (Bidirectional Encoder...)" 或 "(BERT)"
    def_abbrs = set(re.findall(r"\b([A-Z]{2,})\s*\([^)]+\)", text))
    paren_abbrs = set(re.findall(r"\(([A-Z]{2,})\)", text))

    # 如果定义型很少，放宽到紧随全称之后的缩写
    if len(def_abbrs | paren_abbrs) < 3:
        loose = set(re.findall(r"[（(]([A-Z]{2,})[）)]", text))
    else:
        loose = set()

    abbrs = def_abbrs | paren_abbrs | loose

    over = len(abbrs) - 5 if len(abbrs) > 5 else 0

    result = {
        "label": "缩写计数 (4.9)",
        "total": len(abbrs),
        "abbrs": sorted(abbrs),
        "status": "⚠️" if over > 0 else "✅",
    }
    if over:
        result["issues"] = [f"缩写 {len(abbrs)} 个，超过建议上限 5 个"]
    return result


def check_nominalization(text):
    """5. 名词化检测 (2.4)"""
    paragraphs = [p for p in text.split("\n\n") if len(p) > 50]
    issues = []

    for i, para in enumerate(paragraphs):
        nom_words = NOMINALIZATION_SUFFIX.findall(para)
        if len(nom_words) >= 3:
            issues.append(f"第{i+1}段: {len(nom_words)} 个名词化词 ({', '.join(nom_words[:5])}...)")

    result = {
        "label": "名词化检测 (2.4)",
        "paragraphs_scanned": len(paragraphs),
        "issues": issues,
        "status": "⚠️" if issues else "✅",
    }
    return result


def check_passive_voice(text):
    """6. 被动语态占比 (2.1)"""
    is_zh = is_chinese_text(text)
    if is_zh:
        # 中文被动: "被" + verb
        passive_count = len(re.findall(r"被\w{1,4}", text))
        total_sents = len(split_sentences_zh(text))
        passive_ratio = passive_count / total_sents if total_sents else 0
    else:
        total_sents = len(split_sentences_en(text))
        active_matches = len(re.findall(r"\bwe\b", text, re.IGNORECASE))
        passive_matches = len(PASSIVE_PATTERN.findall(text))
        # 估计被动语态句（排除常见描述性用法）
        estimated_passive = max(0, passive_matches - 15)  # rough baseline
        passive_ratio = estimated_passive / total_sents if total_sents else 0

    result = {
        "label": "被动语态占比 (2.1)",
        "ratio": f"{passive_ratio:.1%}",
        "total_sentences": total_sents,
        "status": "✅" if passive_ratio < 0.3 else "⚠️",
    }
    if passive_ratio >= 0.3:
        result["issues"] = [f"被动语态估计占比 {passive_ratio:.1%}，建议 <30%"]
    return result


def check_filler_phrases(text):
    """7. 空转短语 (6.1 A #3)"""
    is_zh = is_chinese_text(text)
    fillers = FILLER_PHRASES_ZH if is_zh else FILLER_PHRASES_EN
    found = []

    for f in fillers:
        count = text.lower().count(f.lower())
        if count > 0:
            found.append(f"{f} ({count}次)")

    result = {
        "label": "空转短语 (6.1 A #3)",
        "found": found,
        "status": "⚠️" if found else "✅",
    }
    return result


def check_boilerplate_endings(text):
    """9. 万能结尾 (6.1 A #4 + B #12)"""
    is_zh = is_chinese_text(text)
    endings_zh = FILLER_ENDINGS_ZH + ZH_BOILERPLATE_ENDINGS
    endings_en = FILLER_ENDINGS_EN + EN_BOILERPLATE_ENDINGS
    endings = endings_zh if is_zh else endings_en
    found = []

    for e in endings:
        count = text.lower().count(e.lower())
        if count > 0:
            found.append(f"{e} ({count}次)")

    return {
        "label": "万能结尾 (6.1 A #4 + B #12)",
        "found": found,
        "status": "⚠️" if found else "✅",
    }


def check_en_inflated_verbs(text):
    """10. EN 宣告式动词替代 (6.1 B #7) — 仅英文文本"""
    if is_chinese_text(text):
        return None
    found = []
    for v in EN_INFLATED_VERBS:
        count = text.lower().count(v.lower())
        if count > 0:
            found.append(f"{v} ({count}次)")
    return {
        "label": "宣告式动词 (6.1 B #7)",
        "found": found,
        "status": "⚠️" if found else "✅",
    }


def check_en_ing_filler(text):
    """11. EN 句尾 -ing 空转 (6.1 B #8) — 仅英文文本"""
    if is_chinese_text(text):
        return None
    matches = EN_ING_FILLER.findall(text)
    return {
        "label": "句尾 -ing 空转 (6.1 B #8)",
        "found": [m[:50] + "..." if len(m) > 50 else m for m in matches],
        "status": "⚠️" if matches else "✅",
    }


def check_grandiose_phrases(text):
    """12. 宣告式膨胀 (6.1 B #9)"""
    is_zh = is_chinese_text(text)
    phrases = ZH_GRANDIOSE if is_zh else EN_GRANDIOSE
    found = []
    for p in phrases:
        count = text.lower().count(p.lower())
        if count > 0:
            found.append(f"{p} ({count}次)")
    return {
        "label": "宣告式膨胀 (6.1 B #9)",
        "found": found,
        "status": "⚠️" if found else "✅",
    }


def check_en_filler_phrases(text):
    """13. EN filler 短语 (6.1 B #11) — 仅英文文本"""
    if is_chinese_text(text):
        return None
    found = []
    for p in EN_FILLER_PHRASES:
        count = text.lower().count(p.lower())
        if count > 0:
            found.append(f"{p} ({count}次)")
    return {
        "label": "EN filler 短语 (6.1 B #11)",
        "found": found,
        "status": "⚠️" if found else "✅",
    }


def check_zh_empty_praise(text):
    """14. ZH 万能空话 (6.1 B #15) — 仅中文文本"""
    if not is_chinese_text(text):
        return None
    found = []
    for p in ZH_EMPTY_PRAISE:
        count = text.count(p)
        if count > 0:
            found.append(f"{p} ({count}次)")
    return {
        "label": "ZH 万能空话 (6.1 B #15)",
        "found": found,
        "status": "⚠️" if found else "✅",
    }


def check_zh_ai_patterns(text):
    """15. 中文 AI 腔 (6.1 B #16-18) — 仅中文文本"""
    if not is_chinese_text(text):
        return None

    issues = []
    for label, pattern in ZH_AI_PATTERNS.items():
        matches = pattern.findall(text)
        if len(matches) >= 3:
            issues.append(f"{label}: {len(matches)} 处")

    return {
        "label": "中文 AI 腔 (6.1 B #16-18)",
        "issues": issues,
        "status": "⚠️" if issues else "✅",
    }


# ─── 主流程 ───────────────────────────────────────────

def scan(text):
    # 全局清洗 Markdown，再传给各检查项
    text = clean_markdown(text)

    results = [
        check_sentence_length(text),
        check_banned_words(text),
        check_ai_flag_words(text),
        check_abbreviations(text),
        check_nominalization(text),
        check_passive_voice(text),
        check_filler_phrases(text),
        check_boilerplate_endings(text),
        check_grandiose_phrases(text),
    ]

    # EN-only checks
    for r in [check_en_inflated_verbs(text), check_en_ing_filler(text), check_en_filler_phrases(text)]:
        if r:
            results.append(r)

    # ZH-only checks
    for r in [check_zh_empty_praise(text), check_zh_ai_patterns(text)]:
        if r:
            results.append(r)

    return results


def print_report(results):
    print("=" * 60)
    print("快速预扫报告 — 纯正则 0 Token 检查")
    print("=" * 60)
    print()

    ok = sum(1 for r in results if r["status"] == "✅")
    warn = sum(1 for r in results if r["status"] == "⚠️")
    err = sum(1 for r in results if r["status"] == "❌")

    print(f"总计 {len(results)} 项：{ok} 通过 / {warn} 警告 / {err} 违规\n")

    for r in results:
        status = r["status"]
        print(f"  {status} {r['label']}")

        # 显示统计数据
        if "total" in r and r.get("unit"):
            print(f"      {r['total']} 句 · 平均 {r['avg']}{r['unit']} · 最长 {r['max']}{r['unit']}")
        elif "ratio" in r:
            print(f"      占比 {r['ratio']}")
        elif "total" in r:
            print(f"      {r['total']} 个缩写")

        # 显示问题
        if r.get("issues"):
            for issue in r["issues"]:
                print(f"      ⚠ {issue}")
        elif r.get("found") and r["status"] != "✅":
            for f in r["found"]:
                print(f"      ✗ {f}")

        print()

    print("-" * 60)
    print("💡 本报告为机械检查。深层论证质量需通过规范检查模式或模拟审稿。")
    print("   6.1 A 层 #2/#5/#6（对称排比/读出声/完美闭环）需人读出声，不在此处。")


def main():
    if len(sys.argv) < 2:
        print("用法: python3 quick_scan.py <文件> 或 python3 quick_scan.py -")
        sys.exit(1)

    target = sys.argv[1]
    if target == "-":
        text = sys.stdin.read()
    else:
        with open(target, "r", encoding="utf-8") as f:
            text = f.read()

    results = scan(text)
    print_report(results)

    # 返回码：有 ❌ → 1
    exit(1 if any(r["status"] == "❌" for r in results) else 0)


if __name__ == "__main__":
    main()
