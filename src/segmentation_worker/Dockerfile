# M3: real SAM 3 + OpenCV 5 on a CUDA base. Requires an NVIDIA GPU host.
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

# 2) OpenCV 5 (headless — no GUI needed in a container).
RUN pip install "opencv-python-headless>=5,<6"

# 3) SAM 3 from source. Pin SAM3_REF to a specific commit for reproducibility.
ARG SAM3_REF=main
RUN git clone https://github.com/facebookresearch/sam3.git /opt/sam3 \
    && cd /opt/sam3 \
    && git checkout ${SAM3_REF} \
    && pip install -e .

# 4) The worker package + its (CPU-light) dependencies.
COPY pyproject.toml ./
COPY worker ./worker
RUN pip install .

CMD ["python", "-m", "worker.worker"]
