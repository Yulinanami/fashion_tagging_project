# json_writer.py
import json
from pathlib import Path
from typing import Any, Dict, List


def append_record_to_json(
    record: Dict[str, Any],
    json_path: str = "metadata/dataset.json"
) -> None:
    """
    将一条记录追加写入到一个 JSON 文件中。
    JSON 结构为一个数组，每个元素是一条记录。

    如果文件不存在，则创建并写入 [record]
    如果文件存在且是数组，则在数组后 append 再整体重写。
    """

    path = Path(json_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data: List[Dict[str, Any]] = []

    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                existing = json.load(f)
            # 如果原来就是数组，直接用；否则包装一下
            if isinstance(existing, list):
                data = existing
            else:
                data = [existing]
        except Exception:
            # 如果原文件损坏/格式不对，就从头来，避免整个流程崩掉
            data = []

    data.append(record)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
