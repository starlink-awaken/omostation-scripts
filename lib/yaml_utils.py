"""yaml_utils.py — YAML 读写统一实现。

消除 3+ 套独立的 load_yaml() 实现。

用法:
    from lib.yaml_utils import load_yaml, load_yaml_multi, write_yaml_atomic
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    raise ImportError(
        "PyYAML is required. Install with: pip install pyyaml"
    )


def load_yaml(path: str | Path) -> Any:
    """加载单个 YAML 文档。

    Args:
        path: YAML 文件路径

    Returns:
        解析后的 Python 对象 (dict / list / scalar)

    Raises:
        FileNotFoundError: 文件不存在
        yaml.YAMLError: 解析失败
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_yaml_multi(path: str | Path) -> list[Any]:
    """加载多文档 YAML (--- 分隔)。

    Args:
        path: YAML 文件路径

    Returns:
        list of parsed documents

    Raises:
        FileNotFoundError: 文件不存在
        yaml.YAMLError: 解析失败
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return list(yaml.safe_load_all(f))


def write_yaml_atomic(data: Any, path: str | Path) -> None:
    """原子写入 YAML 文件 (先写临时文件再 rename)。

    Args:
        data: 要序列化的 Python 对象
        path: 目标文件路径
    """
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    os.replace(tmp, path)


def load_yaml_or_default(path: str | Path, default: Any = None) -> Any:
    """加载 YAML, 文件不存在时返回默认值。

    Args:
        path: YAML 文件路径
        default: 文件不存在时的返回值

    Returns:
        解析后的对象, 或 default
    """
    path = Path(path)
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
