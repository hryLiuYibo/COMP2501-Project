# -*- coding: utf-8 -*-
"""
convert_ncm_to_mp3.py
=====================

把网易云 .ncm 加密音频批量转成 .mp3。

⚠️ 当前状态：抽象接口已写好，但具体 CLI 后端还未选定。
   网络恢复后需要：
   1. 在候选里选一个 CLI 工具：
      - ncmdump  (https://github.com/anonymous5l/ncmdump, Go, 单文件 exe)
      - ncmdump-py (pip install ncmdump-py, Python wrapper)
      - 或本仓库内的 Trans.exe（GUI 拖拽工具，不能命令行调用 — 见 fallback 分支）
   2. 把下面的 _NCMDUMP_BACKEND 改成实际可用的命令行
   3. 实现对应的 convert_one() / convert_many()

为什么用抽象接口
----------------
- 后端工具可能更换（ncmdump → 新版 / 弃用 / 找更好的替代品）
- 上层调用代码（下载器、嵌入脚本）只依赖 NcmConverter，不关心具体工具
- 测试容易：可以 mock 出一个 fake converter 验证流水线逻辑

用法
----
$ python convert_ncm_to_mp3.py \
    --src data/ncm \
    --dst data/mp3
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("convert_ncm_to_mp3")


# ---------------------------------------------------------------------------
# 抽象接口
# ---------------------------------------------------------------------------

class NcmConverter(ABC):
    """ncm → mp3 转换器的统一抽象。具体后端在子类里实现。"""

    @abstractmethod
    def convert_one(self, ncm_path: Path, mp3_path: Path) -> None:
        """
        把单个 .ncm 转成 .mp3。
        失败抛 RuntimeError,调用方负责重试/跳过。
        """
        raise NotImplementedError

    def convert_many(self, items: Iterable[tuple[Path, Path]]) -> tuple[int, int]:
        """
        批量转换。返回 (成功数, 失败数)。
        """
        ok = 0
        fail = 0
        for ncm, mp3 in items:
            try:
                self.convert_one(ncm, mp3)
                ok += 1
            except Exception as e:
                log.warning("转换失败 %s: %s", ncm, e)
                fail += 1
        return ok, fail


# ---------------------------------------------------------------------------
# CLI 后端候选
# ---------------------------------------------------------------------------

# TODO: 网络恢复后选定下列之一,启用对应类
#
# 候选 1: ncmdump (Go 单文件 exe)
#   安装: 从 https://github.com/anonymous5l/ncmdump/releases 下载 windows .exe
#   命令: ncmdump.exe <input.ncm> [-o output_dir]
#
# 候选 2: ncmdump-py (Python wrapper)
#   安装: pip install ncmdump-py
#   用法: from ncmdump import dump; dump(input_path, output_path)
#
# 候选 3: Trans.exe (本仓库的 GUI 工具,命令行不可调用)
#   ❌ 不可用,只能 GUI 拖拽

class NcmdumpCliConverter(NcmConverter):
    """
    调用 ncmdump.exe (https://github.com/anonymous5l/ncmdump) 的实现。

    典型用法:
        ncmdump.exe input.ncm
        ncmdump.exe input.ncm -o output_dir
    """
    def __init__(self, exe_path: str | Path = "ncmdump.exe"):
        self.exe_path = Path(exe_path)
        if not self.exe_path.exists():
            raise FileNotFoundError(
                f"ncmdump.exe 未找到: {self.exe_path}\n"
                "请从 https://github.com/anonymous5l/ncmdump/releases 下载后放到 PATH 里"
            )

    def convert_one(self, ncm_path: Path, mp3_path: Path) -> None:
        mp3_path.parent.mkdir(parents=True, exist_ok=True)
        # ncmdump 默认把 .mp3 写到输入文件同目录,文件名相同仅扩展名不同
        # 所以先转到临时目录,再 mv 到目标位置
        tmp_dir = mp3_path.parent / "_tmp_ncmdump"
        tmp_dir.mkdir(exist_ok=True)
        try:
            cmd = [str(self.exe_path), str(ncm_path), "-o", str(tmp_dir)]
            log.debug("执行: %s", " ".join(cmd))
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"ncmdump 失败 (rc={result.returncode}): {result.stderr.strip()}"
                )
            produced = tmp_dir / (ncm_path.stem + ".mp3")
            if not produced.exists():
                raise RuntimeError(f"ncmdump 未产出期望文件: {produced}")
            shutil.move(str(produced), str(mp3_path))
        finally:
            tmp_dir.rmdir() if tmp_dir.exists() else None


class NcmdumpPyConverter(NcmConverter):
    """
    用 pip 装的 ncmdump-py 包 (Python wrapper)。

    pip install ncmdump-py
    """
    def convert_one(self, ncm_path: Path, mp3_path: Path) -> None:
        # TODO: 网络恢复后,根据实际包的 API 调整
        # 大致用法可能是:
        #   from ncmdump import dump
        #   dump(str(ncm_path), str(mp3_path))
        # 但 ncmdump-py 的实际 API 需要核实
        raise NotImplementedError(
            "NcmdumpPyConverter 尚未实现,ncmdump-py 包的 API 需要先核实"
        )


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def collect_jobs(src_dir: Path, dst_dir: Path) -> Iterable[tuple[Path, Path]]:
    """
    扫描 src_dir 下所有 .ncm,产出 (输入, 输出) 对。
    已存在输出文件的会被跳过(断点续跑)。
    """
    if not src_dir.exists():
        log.warning("源目录不存在: %s", src_dir)
        return
    for ncm_path in sorted(src_dir.glob("*.ncm")):
        mp3_path = dst_dir / (ncm_path.stem + ".mp3")
        if mp3_path.exists():
            log.debug("跳过已存在: %s", mp3_path)
            continue
        yield ncm_path, mp3_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="批量把 .ncm 转成 .mp3")
    parser.add_argument("--src", type=Path, required=True, help="输入目录(包含 .ncm 文件)")
    parser.add_argument("--dst", type=Path, required=True, help="输出目录")
    parser.add_argument("--backend", default="ncmdump",
                        choices=["ncmdump", "ncmdump-py"],
                        help="CLI 后端")
    parser.add_argument("--exe", type=Path, default=None,
                        help="CLI 可执行文件路径(仅 ncmdump 后端需要)")
    args = parser.parse_args(argv)

    # 选择后端
    if args.backend == "ncmdump":
        converter: NcmConverter = NcmdumpCliConverter(args.exe or "ncmdump.exe")
    elif args.backend == "ncmdump-py":
        converter = NcmdumpPyConverter()
    else:
        log.error("未知后端: %s", args.backend)
        return 2

    args.dst.mkdir(parents=True, exist_ok=True)
    jobs = list(collect_jobs(args.src, args.dst))
    log.info("待转换: %d 个 .ncm 文件 (%s → %s)", len(jobs), args.src, args.dst)

    if not jobs:
        log.info("没有待处理任务,退出")
        return 0

    ok, fail = converter.convert_many(jobs)
    log.info("完成: 成功 %d, 失败 %d", ok, fail)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())