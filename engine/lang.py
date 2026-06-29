# 语言检测 —— 按 CJK 字符占比判断中/英。
# collect/backfill 入库时打标，compose 据此做「6 中 + 2 英」编排。
def detect_lang(text):
    if not text:
        return 'en'
    cjk = sum(1 for ch in text if '一' <= ch <= '鿿')
    latin = sum(1 for ch in text if ('a' <= ch.lower() <= 'z'))
    if cjk == 0:
        return 'en'
    # 只要有一定比例的中文字符就算中文（中文标题里夹英文品牌名很常见）
    return 'zh' if cjk >= max(2, 0.15 * (cjk + latin)) else 'en'
