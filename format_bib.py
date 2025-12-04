import sys
import re
import bibtexparser
from bibtexparser.model import Entry
import string
import spacy

# 简单停用词列表（英文）
STOP_WORDS = {
    'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were'
}

def extract_title_abbreviation(title: str, use_nlp=True, n=2):
    """
    从标题提取缩写，例如:
      "A Deep Learning Approach to Image Recognition" → "dl"
      "Question Answering with Transformers" → "qa"
    """
    if not title:
        return ""
    
    # 1. 清理标点，转小写
    clean = re.sub(rf'[{re.escape(string.punctuation)}]', ' ', title.lower())
    words = clean.split()
    
    # 2. 去停用词
    content_words = [w for w in words if w not in STOP_WORDS and len(w) > 1]
    
    if not content_words:
        return ""
    
    # 3. 如果安装了 spaCy，用 POS 标注只取名词/形容词（更准）
    if use_nlp:
        try:
            nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
            doc = nlp(" ".join(content_words))
            important = [token.text for token in doc if token.pos_ in {"NOUN", "ADJ", "PROPN"}]
            if important:
                content_words = important
        except Exception:
            pass  # fallback to simple method
    
    # 4. 取前1-2个词
    selected = content_words[n-2:n]
    
    # 5. 如果词很短（如 GAN, CNN, QA），直接用全大写；否则用首字母
    abbr_parts = []
    for word in selected:
        if len(word) <= 3 or word.upper() == word:  # 如 "GPT", "QA"
            abbr_parts.append(word.upper())
        else:
            abbr_parts.append(word[0].lower())
    
    return "".join(abbr_parts)[:3]  # 最多3个字符


def extract_lastname(author):
    if not author: return "unknown"
    first = re.split(r'\s+and\s+', author, flags=re.IGNORECASE)[0].strip()
    if ',' in first:
        last = first.split(',')[0]
    else:
        last = first.split()[-1] if first.split() else "unknown"
    return re.sub(r'[^a-zA-Z]', '', last).lower() or "unknown"

def get_field(entry, key, default=""):
    f = entry.fields_dict.get(key)
    return f.value if f else default


def clean_title_for_key(title: str) -> str:
    """
    清理 BibTeX title 字段：
      - 移除所有 { 和 }
      - 保留字母、数字、空格、连字符 '-'、撇号 "'" 等
    """
    if not title:
        return ""
    # 仅移除花括号，其他保留
    cleaned = title.replace('{', '').replace('}', '')
    # 可选：规范化多个空格为单个空格
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


#--------------------------------------main
if len(sys.argv) != 2:
    print("Usage: python script.py input.bib")
    sys.exit(1)

input_file = sys.argv[1]
output_file = input_file + ".reformatted"
lib = bibtexparser.parse_file(input_file)


#check if duplication exist or not in initial file 
from bibtexparser.model import DuplicateBlockKeyBlock
duplicate_blocks = [
        block for block in lib.blocks
        if isinstance(block, DuplicateBlockKeyBlock)
    ]


if duplicate_blocks:
    print("❌ Error: Duplicate BibTeX keys found in input file!", file=sys.stderr)
    for dup in duplicate_blocks:
        print(f"   - Key '{dup.key}' is duplicated at line {dup.start_line + 1}", file=sys.stderr)
    print("\nPlease ensure all entry keys are unique before running this script. Please modify these lines first!!", file=sys.stderr)
    sys.exit(1) 


seen_titles = set()
key_usage = {}
entry_replacements = {}  # start_line -> formatted string

# 第一遍：处理所有 entry，生成新 key 和格式化字符串
for block in lib.blocks:
    if isinstance(block, Entry):
        title = get_field(block, 'title', "").strip()
        title = clean_title_for_key(title)
        if title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())
        if "author" in block.fields_dict:
            author = get_field(block, 'author', "")
        elif "AUTHOR" in block.fields_dict:
            author = get_field(block, 'AUTHOR', "")
        else:
            author = "unknown"
    
        if "year" in block.fields_dict:
            year = get_field(block, 'year', "").strip()
        elif "YEAR" in block.fields_dict:
            year = get_field(block, 'YEAR', "").strip()
        else:
            year = "0000"

        year = year if re.fullmatch(r'\d{4}', year) else "0000"
        key = extract_lastname(author) + year

        # 记录冲突
        info = {"title": title, "orig_key": block.key, "line": block.start_line}
        n=2
        while key in key_usage:
            key = key + extract_title_abbreviation(title, use_nlp=True, n=n)
            n=2*n
        key_usage.setdefault(key, []).append(info)

        # 格式化 entry：key 和 title 同行
        other = [f for f in block.fields if f.key != "title"]
        lines = [f"@{block.entry_type}{{{key}, title = {{{title}}},"]
        lines.extend(f"  {f.key} = {{{f.value}}}," for f in other)
        if len(lines) > 1:
            lines[-1] = lines[-1].rstrip(',')
        lines.append("}")
        entry_replacements[block.start_line] = "\n".join(lines)

# 报告 key 冲突
for key, items in key_usage.items():
    if len(items) > 1:
        print(f"\n⚠️ Key conflict: '{key}'")
        for it in items:
            print(f"  Line {it['line']}: {it['title']} (orig: {it['orig_key']})")

# 第二遍：写入文件
with open(output_file, 'w', encoding='utf-8') as out:
    for block in lib.blocks:
        if isinstance(block, Entry):
            if block.start_line in entry_replacements:
                out.write(entry_replacements[block.start_line] + "\n")
            # else: 被去重，跳过
        else:
            # 原样写入 comment / string / preamble
            raw = getattr(block, 'raw', None)
            if raw is not None:
                out.write(raw)
                if not raw.endswith('\n'):
                    out.write('\n')
            else:
                # fallback（理论上不会触发）
                out.write("% [block preserved]\n")

print(f"\n✅ Output written to {output_file}")
print(f"   Kept {len(entry_replacements)} unique entries.")