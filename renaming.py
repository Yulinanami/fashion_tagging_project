# renaming.py
import shutil
from pathlib import Path

from tagging import tag_image

# renaming.py

def safe_str(s) -> str:
    """把任意值变成适合文件名的字符串：None -> "", 去掉特殊字符。"""
    if s is None:
        return ""
    # 如果不是字符串，先转成字符串（大模型有时会给数字、列表）
    if not isinstance(s, str):
        s = str(s)

    s = s.strip()
    for ch in ['/', '\\', ':', '*', '?', '"', '<', '>', '|', ',', '，']:
        s = s.replace(ch, '')
    s = s.replace(' ', '-')
    return s

def build_new_name(tags: dict, index: int, ext: str) -> str:
    """根据标签构造新的文件名（对缺失/为 None 的字段做防御）"""

    gender = safe_str(tags.get("gender", ""))
    style = safe_str(tags.get("overall_style", ""))

    # 防御：top / bottom 可能是 None、字符串、列表等鬼东西
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
        # 有时模型会返回字符串而不是列表
        occasion = safe_str(occasions) if isinstance(occasions, str) else ""

    parts = [gender, style, top_cat, bottom_cat, season, occasion]
    parts = [p for p in parts if p]   # 去掉空字段

    base = "_".join(parts) if parts else "outfit"
    return f"{base}_{index:03d}{ext}"

def batch_tag_and_rename(
    src_dir: str = "images/to_rename",
    dst_dir: str = "images/renamed"
):
    """遍历 src_dir，对每张图片打标签并重命名复制到 dst_dir。"""
    src = Path(src_dir)
    dst = Path(dst_dir)
    dst.mkdir(parents=True, exist_ok=True)

    image_files = [
        p for p in src.iterdir()
        if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
    ]

    if not image_files:
        print("[INFO] 没有找到待处理图片。请把图片放到 images/to_rename/ 目录下。")
        return

    for idx, img_path in enumerate(sorted(image_files), start=1):
        print(f"\n[INFO] 处理第 {idx} 张：{img_path.name}")

        try:
            tags = tag_image(img_path)
        except Exception as e:
            print(f"[ERROR] 标注失败，跳过：{img_path.name}，错误：{e}")
            continue

        new_name = build_new_name(tags, idx, img_path.suffix.lower())
        target_path = dst / new_name

        # 防止重名
        num = 1
        while target_path.exists():
            target_path = dst / f"{target_path.stem}_{num}{img_path.suffix.lower()}"
            num += 1

        shutil.copy2(img_path, target_path)
        print(f"[OK] 重命名为：{target_path.name}")
