#!/usr/bin/env python
"""摸清本机底细：能不能训 0.6B、能开多大 batch、大概要多久。

只依赖标准库。装了 torch 会多报一些信息。
用法：
    uv run python scripts/check_env.py
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ---- 模型假设（Qwen3-0.6B 参考配置）----
PARAMS_B = 0.6
LAYERS, KV_HEADS, HEAD_DIM = 28, 8, 128
SEQ_LEN = 512
GPUS = 1
EFFECTIVE_TFLOPS = 5.0  # 3060 Laptop 量级，利用率 ~0.4


def gpu_rows() -> list[list[str]]:
    """返回 [[name, total_MiB, free_MiB, driver], ...]，拿不到就空列表。"""
    if not shutil.which("nvidia-smi"):
        return []
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    rows = []
    for line in out.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 4:
            rows.append(parts[:4])
    return rows


def torch_summary() -> str:
    try:
        import torch  # noqa: F401
    except Exception:
        return "未安装（P2 阶段再装）"
    bits = [
        f"torch {torch.__version__}",
        f"cuda {torch.version.cuda}",
        f"available={torch.cuda.is_available()}",
    ]
    if torch.cuda.is_available():
        bits.append(f"device={torch.cuda.get_device_name(0)}")
    return " | ".join(bits)


def kv_mb(batch: int, seq: int = SEQ_LEN, elem: int = 2) -> float:
    """KV cache 显存：2 * layers * kv_heads * head_dim * seq * batch * bytes。"""
    return 2 * LAYERS * KV_HEADS * HEAD_DIM * seq * batch * elem / 1024 / 1024


def train_vram_gb(batch: int, seq: int = SEQ_LEN, grad_ckpt: bool = True) -> float:
    """粗估：权重 + adapter + 激活。误差 ±50%，以实测为准。"""
    weights = PARAMS_B * 2  # fp16
    adapter = 0.15  # LoRA + AdamW 状态
    act = batch * seq * 1e-4 * (2.0 if grad_ckpt else 8.0)
    return weights + adapter + act


def train_minutes(n_samples: int, avg_tokens: int, epochs: int) -> float:
    total_tokens = n_samples * avg_tokens * epochs
    flops = 6 * PARAMS_B * 1e9 * total_tokens
    seconds = flops / (GPUS * EFFECTIVE_TFLOPS * 1e12)
    return seconds / 60


def line(title: str) -> None:
    print(f"\n== {title} " + "=" * max(0, 58 - len(title)))


def main() -> int:
    line("系统")
    print(f"python      : {sys.version.split()[0]}  (需要 >= 3.11，建议用 uv 管理)")
    print(f"platform    : {platform.platform()}")
    print(f"cpu         : {platform.processor() or '未知'}")
    print(f"repo        : {ROOT}")

    line("显卡")
    gpus = gpu_rows()
    free_mib = 0
    if not gpus:
        print("没找到 nvidia-smi（无独显或驱动未装）")
    for name, total, free, driver in gpus:
        print(f"{name}")
        print(f"  显存 {int(total)} MiB / 空闲 {int(free)} MiB / 驱动 {driver}")
        free_mib = max(free_mib, int(free))
    print(f"torch       : {torch_summary()}")

    line("训练预算（Qwen3-0.6B + LoRA）")
    print(f"{'batch':>6} {'seq':>5} {'ckpt':>6} {'显存(GiB)':>10} {'放得下?':>8}")
    for bs in (4, 8, 16):
        for ckpt in (True, False):
            gb = train_vram_gb(bs, grad_ckpt=ckpt)
            ok = "是" if free_mib and gb * 1024 < free_mib * 0.85 else "存疑"
            print(f"{bs:>6} {SEQ_LEN:>5} {str(ckpt):>6} {gb:>10.2f} {ok:>8}")

    line("时间预算（4000 条 × 256 token × 3 epoch）")
    mins = train_minutes(4000, 256, 3)
    print(f"总 token    : {4000 * 256 * 3 / 1e6:.2f} M")
    print(f"预计耗时    : {mins:.0f} 分钟（有效算力 {EFFECTIVE_TFLOPS} TFLOPS）")
    print("如果实跑超过这个数 2 倍，先查配置，别干等。")

    line("推理显存（KV cache，seq=512，fp16）")
    print(f"{'batch':>6} {'KV(MiB)':>9} {'权重q8(MiB)':>12} {'合计(MiB)':>10}")
    for bs in (8, 16, 32, 48, 64):
        kv = kv_mb(bs)
        total = kv + 600
        print(f"{bs:>6} {kv:>9.0f} {600:>12} {total:>10.0f}")

    line("结论")
    if free_mib >= 4096:
        print("[OK]   可以训 0.6B + LoRA（建议 batch<=8, seq=512, 开梯度检查点）")
    elif free_mib > 0:
        print("[WARN] 显存偏紧：先关掉占显存的程序，或改用 4bit QLoRA")
    else:
        print("[FAIL] 没有可用 GPU：训练改走租卡，或用 CPU + 0.5B 极小规模试水")

    disk = shutil.disk_usage(ROOT)
    print(f"磁盘剩余    : {disk.free / 1e9:.0f} GB")
    if disk.free < 20e9:
        print("[WARN] 磁盘不足 20 GB，torch + 模型权重可能装不下")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
