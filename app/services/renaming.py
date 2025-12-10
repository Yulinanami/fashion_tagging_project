def safe_str(s) -> str:
    """把任意值变成适合文件名的字符串：None -> "", 去掉特殊字符。"""
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)

    s = s.strip()
    for ch in ["/", "\\", ":", "*", "?", '"', "<", ">", "|", ",", "，"]:
        s = s.replace(ch, "")
    s = s.replace(" ", "-")
    return s


def build_new_name(tags: dict, index: int, ext: str) -> str:
    """根据标签构造新的文件名（对缺失/为 None 的字段做防御）"""

    gender = safe_str(tags.get("gender", ""))
    style = safe_str(tags.get("overall_style", ""))

    top_raw = tags.get("top") or {}
    if not isinstance(top_raw, dict):
        top_raw = {}

    bottom_raw = tags.get("bottom") or {}
    if not isinstance(bottom_raw, dict):
        bottom_raw = {}

    top_cat = safe_str(top_raw.get("category", ""))
    bottom_cat = safe_str(bottom_raw.get("category", ""))

    season = safe_str(tags.get("season", ""))

    occasions = tags.get("suitable_occasion") or []
    if isinstance(occasions, list) and occasions:
        occasion = safe_str(occasions[0])
    else:
        occasion = safe_str(occasions) if isinstance(occasions, str) else ""

    parts = [gender, style, top_cat, bottom_cat, season, occasion]
    parts = [p for p in parts if p]

    base = "_".join(parts) if parts else "outfit"
    return f"{base}_{index:03d}{ext}"
