#!/usr/bin/env python3
"""中文一句話重點：挑選文章、合併 Claude 寫好的摘要。

  python3 scripts/zh_summaries.py todo  [--top N]     # 產生 work/zh_todo.jsonl（待撰寫清單）
  python3 scripts/zh_summaries.py merge work/zh_new.json  # 合併到 site/zh/<週次>.json

挑選範圍：共識／指引、系統性回顧／統合分析全部；原著與綜論預設不寫（--top N 可另加 IF 最高的 N 篇）。
已寫過的文章不會重複列出。只用 Python 標準函式庫。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from fetch_pubmed import classify  # noqa: E402

DATA = ROOT / "site" / "data.json"
ZH_DIR = ROOT / "site" / "zh"
WORK = ROOT / "work"
MAX_LEN = 80   # 中文重點上限字數（目標約 40 字）


def load_week():
    d = json.loads(DATA.read_text(encoding="utf-8"))
    week = d.get("week") or d.get("to", "")[:10]
    return d, week


def zh_path(week):
    return ZH_DIR / f"{week}.json"


def load_zh(week):
    try:
        return json.loads(zh_path(week).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def key_text(abstract, limit=600):
    """優先取摘要的結論段落，否則取最後幾句，控制長度。"""
    parts = abstract.split("\n")
    concl = [p for p in parts if re.match(r"(CONCLUSIONS?|INTERPRETATION|IMPLICATIONS|DISCUSSION)\b", p, re.I)]
    res = [p for p in parts if re.match(r"RESULTS?\b|FINDINGS\b", p, re.I)]
    txt = " ".join(concl) or " ".join(res[-1:]) or abstract
    if len(txt) > limit:
        txt = txt[-limit:]
        txt = txt[txt.find(" ") + 1:]
    return txt


def todo(top):
    d, week = load_week()
    done = load_zh(week)
    arts = d["articles"]
    for a in arts:
        a["_cat"] = classify(a.get("pubTypes", []), a.get("title", ""))
    must = [a for a in arts if a["_cat"] in ("Guideline", "Meta")]
    rest = sorted((a for a in arts if a["_cat"] not in ("Guideline", "Meta")),
                  key=lambda a: (a.get("if", 0), a.get("sortDate", "")), reverse=True)[:top]
    picked, seen = [], set()
    for a in must + rest:
        if a["pmid"] in seen or a["pmid"] in done:
            continue
        seen.add(a["pmid"])
        picked.append({"pmid": a["pmid"], "type": a["_cat"], "journal": a.get("journal", ""),
                       "title": a.get("title", ""), "key": key_text(a.get("abstract", ""))})
    WORK.mkdir(exist_ok=True)
    out = WORK / "zh_todo.jsonl"
    out.write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in picked) + ("\n" if picked else ""),
                   encoding="utf-8")
    print(f"week {week}: {len(must)} guideline/meta + top {top} others; "
          f"already done {len(done)}; to write {len(picked)} -> {out}")


def merge(path):
    d, week = load_week()
    valid = {a["pmid"] for a in d["articles"]}
    new = json.loads(Path(path).read_text(encoding="utf-8"))
    zh = load_zh(week)
    added, skipped = 0, []
    for pmid, text in new.items():
        text = " ".join(str(text).split())
        if pmid not in valid or not text or len(text) > MAX_LEN:
            skipped.append(pmid)
            continue
        zh[pmid] = text
        added += 1
    ZH_DIR.mkdir(parents=True, exist_ok=True)
    zh_path(week).write_text(json.dumps(zh, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"week {week}: merged {added}, total {len(zh)}; skipped {len(skipped)} {skipped[:10]}")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "todo":
        n = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 0
        todo(n)
    elif len(sys.argv) >= 3 and sys.argv[1] == "merge":
        merge(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)
