# Running SAM 3 for inference: a reproducible recipe

Field notes from getting Meta's [SAM 3](https://github.com/facebookresearch/sam3)
image model running end-to-end as a containerized GPU service (the worker in
this repo). The demos are excellent; the packaging is research-grade. SAM 1 and
SAM 2 had the same reputation — gorgeous results, a rough install. This is the
recipe that actually worked, plus the *reasoning* behind each non-obvious step,
so you don't have to rediscover it.

Verified end-to-end on **AWS `g4dn.xlarge` (NVIDIA T4, 16 GB) / Ubuntu 24.04**,
SAM 3 image model, text-prompted segmentation.

---

## TL;DR — the stack that worked

| Layer | Choice | Why it matters |
| --- | --- | --- |
| GPU host | T4 16 GB (or anything ≥ 16 GB; 12 GB works for image inference) | T4 is pre-Ampere → no Flash Attention, falls back to the math kernel (slower, fine) |
| NVIDIA driver | `nvidia-driver-580-server` (≥ 560 branch) | Must support **CUDA ≥ 12.6** to run the container |
| Container base | `nvidia/cuda:12.6.2-cudnn-runtime-ubuntu24.04` | cuDNN runtime; matches the driver |
| PyTorch | `torch torchvision --index-url .../cu126` | CUDA 12.6 wheels |
| OpenCV | `opencv-python-headless` **4.x** | **OpenCV 5 is not on PyPI** — 4.13 is the latest |
| SAM 3 | `pip install -e .` from source **+ an extra dependency closure** | `pip install -e .` alone is **not** enough (see below) |
| Inference | run inside `torch.autocast("cuda", dtype=torch.bfloat16)` | the model has hard-coded bf16 casts; without this, matmuls fail |

The full, working Dockerfile is [`src/segmentation_worker/Dockerfile`](../src/segmentation_worker/Dockerfile)
and the inference wrapper is [`worker/segmentation.py`](../src/segmentation_worker/worker/segmentation.py).

---

## 1. The GPU host

These bite before you ever touch SAM 3:

- **GPU quota.** New AWS accounts have a `0` vCPU limit for G-type instances —
  request an increase to "Running On-Demand G and VT instances" *first* (it can
  take a day).
- **AMI choice.** AWS's own Deep Learning AMIs are free; some **Marketplace** GPU
  AMIs add a per-hour software fee. Either use the Amazon-published one, or a
  plain Ubuntu AMI and install the stack yourself.
- **The driver is the gate.** On plain Ubuntu, `ubuntu-drivers` isn't installed
  (`apt-get install ubuntu-drivers-common`), and `ubuntu-drivers install --gpgpu`
  may silently install nothing. Install a driver directly — and it **must be the
  ≥ 560 branch** so it supports the container's CUDA 12.6:
  ```sh
  sudo apt-get install -y nvidia-driver-580-server && sudo reboot
  # verify: nvidia-smi shows "CUDA Version: 12.6" or higher
  ```
- **NVIDIA Container Toolkit** needs its apt repo added before
  `apt-get install nvidia-container-toolkit` — a bare install fails on stock
  Ubuntu. Then `nvidia-ctk runtime configure --runtime=docker`.

Full host setup: [`test-on-aws.md`](./test-on-aws.md) and [`deploy.md`](./deploy.md).

## 2. OpenCV 5 doesn't exist (yet)

The reflex is `pip install "opencv-python>=5"`. It fails:

```
ERROR: Could not find a version that satisfies the requirement opencv-python-headless<6,>=5
  (from versions: ... 4.12.0.88, 4.13.0.90, 4.13.0.92)
```

The `opencv-python` PyPI packages top out at **4.13.x** — OpenCV 5 has no wheel.
Pin `opencv-python-headless>=4.10,<5`. The `cv2` APIs used for mask overlays
(`addWeighted`, `rectangle`, `putText`, `imencode`, `cvtColor`) are stable across
4.x → 5.x, so nothing else changes.

## 3. The dependency closure (the hard part)

`pip install -e .` on SAM 3 installs its declared core deps — and then `import
sam3` still crashes, repeatedly, on missing modules:

```
ModuleNotFoundError: No module named 'einops'        # then pycocotools, then psutil, ...
```

**Why:** SAM 3's `__init__.py` eagerly imports its training / data / video code,
which depends on libraries SAM 3 declares only under optional extras
(`train` / `dev` / `notebooks`) — or, like `psutil`, declares *nowhere*. So even
pure image inference drags them in, but `pip install -e .` doesn't install them.

### Don't whack-a-mole — scan the imports

Instead of rebuilding once per missing module (painful on a remote GPU box),
clone the package and let an AST walk enumerate every third-party import, then
classify each by whether it's actually a hard, module-load import on the
`import sam3` path:

```python
import ast, sys
from pathlib import Path

stdlib = set(sys.stdlib_module_names)
installed = {...}  # what your image already provides

mods = {}
for p in Path("sam3").rglob("*.py"):
    tree = ast.parse(p.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                mods.setdefault(n.name.split(".")[0], set()).add(p)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            mods.setdefault(node.module.split(".")[0], set()).add(p)

for m in sorted(mods):
    if m not in stdlib and m not in installed:
        print(m, "->", sorted(mods[m])[0])
```

Then classify the hits — only the **hard, module-top, on-the-load-path** ones
need installing:

| Class | Examples | Action |
| --- | --- | --- |
| Hard import on the load path | `einops`, `pycocotools`, `psutil` | **install** |
| Bundled with PyTorch | `triton` | already present |
| Guarded by `try/except` | `xformers`, `tensordict`, `tidecv` | skip |
| Lazy / function-level, video-only | `decord`, `torchcodec` | skip — never called for image inference |
| In code paths that never load | `detectron2`, `openai`, `matplotlib` (agent/eval/viz) | skip |

This technique generalizes to *any* loosely-packaged research repo.

### The resulting install (image inference)

```sh
pip install \
  einops pycocotools psutil pandas numba python-rapidjson \
  scipy scikit-image scikit-learn \
  hydra-core omegaconf submitit tensorboard torchmetrics fvcore fairscale zstandard
```

(Heavy/UI/video deps — jupyter, decord, yt-dlp, full `opencv-python` — are
deliberately excluded.)

## 4. The bfloat16 autocast contract

With everything imported and the checkpoint loaded, the first real inference
fails with:

```
inference failed: mat1 and mat2 must have the same dtype, but got BFloat16 and Float
```

SAM 3's image model has **hard-coded `.to(torch.bfloat16)` casts** internally and
expects inference to run inside a bf16 autocast context. Its own
`examples/sam3_image_interactive.ipynb` does exactly this before running:

```python
torch.autocast("cuda", dtype=torch.bfloat16).__enter__()
model = build_sam3_image_model(...)
processor = Sam3Processor(model)
```

Three non-obvious details:

1. **It must be `bfloat16`, not `float16`.** The casts are hard-coded to bf16;
   fp16 autocast just produces a *different* mismatch.
2. **autocast is thread-local.** If your inference runs in a worker thread (here,
   via `asyncio.to_thread`), enter the context *inside the inference call*, not
   at model-build time — otherwise it doesn't apply.
3. **bf16 tensors can't go straight to NumPy.** Cast outputs to `float32` before
   `.numpy()` (e.g. for an OpenCV overlay), or you'll hit
   "Got unsupported ScalarType BFloat16".

The implementation: [`worker/segmentation.py`](../src/segmentation_worker/worker/segmentation.py).

On a T4 (no Ampere) bf16 still computes — via the math kernel, not tensor cores —
so it's correct, just a few seconds per image instead of sub-second.

## 5. Operational gotchas (not SAM-specific, but they cost time)

- **`docker compose up` doesn't rebuild on a Dockerfile change** — it reuses the
  existing image. After editing the Dockerfile you must `--build`, or you'll keep
  running the old image and "fixing" nothing.
- **The model checkpoint is multi-GB** and gated on Hugging Face. Cache it in a
  named volume (`HF_HOME`) so restarts don't re-download, and give container
  healthchecks a generous `start-period` (first boot can exceed 10 min).
- **Presigned object-storage URLs embed a host.** If you reach the app through an
  SSH tunnel, forward the storage port too (here MinIO `:9000`) — otherwise the
  job succeeds but images render as broken icons.

---

## What this recipe does *not* pin (be honest)

- `SAM3_REF` is `main` here, not a specific commit — pin it for true
  reproducibility.
- Base images use patch tags, not digests — pin to `@sha256:...` for supply-chain
  reproducibility.
- Verified on a T4 only. An Ampere+ card (A10G/A100) enables Flash Attention and
  is materially faster; the dependency/autocast story is unchanged.
