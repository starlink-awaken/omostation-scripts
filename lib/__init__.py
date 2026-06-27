"""scripts/lib — 共享基础设施包。

为 scripts/ 下的所有脚本提供统一的:
- workspace root 发现 (bootstrap.py)
- .omo/ 4-plane 路径常量 (paths.py)
- YAML 读写 (yaml_utils.py)
- argparse CLI base (cli.py)

使用方式:
    # 顶层脚本 (python3 scripts/foo.py, scripts/ 在 sys.path)
    from lib.bootstrap import workspace_root
    from lib.paths import OMO_DIR, SYSTEM_YAML

    # omo/ 子目录脚本 (需先加 scripts/ 到 path)
    import sys; sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from lib.bootstrap import workspace_root
"""
