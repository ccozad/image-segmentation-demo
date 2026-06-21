# M3: real SAM 3 + OpenCV on a CUDA base. Requires an NVIDIA GPU host.
# CPU is not supported.
FROM nvidia/cuda:12.6.2-cudnn-runtime-ubuntu24.04

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    # Cache the (large, gated) checkpoint download in a mounted volume so
    # subsequent boots reuse it instead of re-downloading several GB.
    HF_HOME=/opt/hf-cache

# Python 3.12 (default on Ubuntu 24.04), git for the SAM 3 clone, and the
# runtime libs OpenCV needs.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv git \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Use an isolated venv so we can pip-install freely on Ubuntu 24.04 (PEP 668).
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN pip install --upgrade pip

WORKDIR /app

# 1) PyTorch + torchvision, CUDA 12.6 wheels.
#    The issue specifies PyTorch 2.10; pin exactly once verified against the
#    cu126 index (https://download.pytorch.org/whl/cu126).
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126

# 2) OpenCV (headless — no GUI in a container).
#    NOTE: OpenCV 5 is not on PyPI yet — the opencv-python packages top out at
#    4.13.x. Our overlay uses stable cv2 APIs that are unchanged in 5.x, so we
#    pin to the latest 4.x; bump the ceiling once 5.x wheels ship.
RUN pip install "opencv-python-headless>=4.10,<5"

# 3) SAM 3 from source. Pin SAM3_REF to a specific commit for reproducibility.
ARG SAM3_REF=main
RUN git clone https://github.com/facebookresearch/sam3.git /opt/sam3 \
    && cd /opt/sam3 \
    && git checkout ${SAM3_REF} \
    && pip install -e .

# SAM 3's package __init__ eagerly imports its training/data code, which depends
# on libraries SAM 3 only declares under optional extras (`train`/`dev`/
# `notebooks`) — so `pip install -e .` above doesn't pull them, yet plain
# `import sam3` (needed for inference) requires them. Install the runtime ones in
# one layer. (Excludes lint/test tools and the notebook UI / decord / yt-dlp /
# full opencv that we don't need; opencv is already installed headless above.)
RUN pip install \
    einops pycocotools pandas numba python-rapidjson \
    scipy scikit-image scikit-learn \
    hydra-core omegaconf submitit tensorboard torchmetrics fvcore fairscale zstandard

# 4) The worker package + its (CPU-light) dependencies.
COPY pyproject.toml ./
COPY worker ./worker
RUN pip install .

# Run as an unprivileged user; ensure the HF cache + app dirs are writable.
RUN useradd --system --uid 1001 appuser \
    && mkdir -p /opt/hf-cache \
    && chown -R appuser /app /opt/hf-cache /opt/venv
USER appuser

# Liveness: worker.py touches /tmp/worker-ready once it has connected to NATS
# and subscribed. The long start-period covers first-boot checkpoint download.
HEALTHCHECK --interval=30s --timeout=5s --start-period=600s --retries=5 \
    CMD test -f /tmp/worker-ready || exit 1

CMD ["python", "-m", "worker.worker"]
