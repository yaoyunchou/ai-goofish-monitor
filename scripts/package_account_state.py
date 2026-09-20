#!/usr/bin/env python3
"""打包 / 恢复闲鱼账号登录态目录（默认 state/*.json）。"""
from __future__ import annotations

import argparse
import sys
import tarfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from src.infrastructure.config.env_manager import env_manager  # noqa: E402


def _state_dir() -> Path:
    raw = env_manager.get_value("ACCOUNT_STATE_DIR", "state") or "state"
    raw = raw.strip().strip("\"'")
    p = Path(raw)
    if not p.is_absolute():
        p = _REPO / p
    return p


def cmd_export(out: Path) -> int:
    state = _state_dir()
    if not state.is_dir():
        print(f"目录不存在: {state}", file=sys.stderr)
        return 1
    files = sorted(state.glob("*.json"))
    if not files:
        print(f"未找到 JSON: {state}", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    arcname_root = state.name
    with tarfile.open(out, "w:gz") as tar:
        for fp in files:
            tar.add(fp, arcname=f"{arcname_root}/{fp.name}")
    print(f"已导出 {len(files)} 个账号 -> {out}")
    return 0


def cmd_import(archive: Path, *, force: bool) -> int:
    if not archive.is_file():
        print(f"文件不存在: {archive}", file=sys.stderr)
        return 1
    state = _state_dir()
    state.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        members = [m for m in tar.getmembers() if m.isfile() and m.name.endswith(".json")]
        if not members:
            print("压缩包内无 .json 文件", file=sys.stderr)
            return 1
        for m in members:
            name = Path(m.name).name
            dest = state / name
            if dest.exists() and not force:
                print(f"已存在，跳过（用 --force 覆盖）: {dest}", file=sys.stderr)
                continue
            extracted = tar.extractfile(m)
            if extracted is None:
                continue
            dest.write_bytes(extracted.read())
            print(f"写入 {dest}")
    print("导入完成")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="闲鱼 state 目录打包与恢复")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_exp = sub.add_parser("export", help="导出 state/*.json 为 tar.gz")
    p_exp.add_argument("--out", type=Path, required=True)

    p_imp = sub.add_parser("import", help="从 tar.gz 恢复到 state/")
    p_imp.add_argument("--archive", type=Path, required=True)
    p_imp.add_argument("--force", action="store_true", help="覆盖已存在文件")

    args = parser.parse_args()
    if args.cmd == "export":
        return cmd_export(args.out)
    return cmd_import(args.archive, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
