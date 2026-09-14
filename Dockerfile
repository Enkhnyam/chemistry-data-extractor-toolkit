FROM python:3.12-slim

# docling's imaging stack (opencv, via the OCR engine) links against X11 and GL shared
# objects that python:*-slim does not ship. Without these the image builds and the server
# starts, and then every single parse fails on "libxcb.so.1: cannot open shared object file"
# -- a runtime-only failure no build log would have shown.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libxcb1 libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

# CPU-only torch, installed before the project. docling pulls torch for its layout and OCR
# models, and torch's default PyPI wheel carries the whole CUDA runtime -- about 1.5 GB of
# nvidia-* packages that can never be used in a container with no GPU passed through. Taking
# the CPU wheel first means the project install below finds the requirement already satisfied.
RUN uv pip install --system --no-cache \
      --index-url https://download.pytorch.org/whl/cpu \
      torch==2.14.0 torchvision

# uv.lock is copied so the image installs the versions this was tested with; without it every
# rebuild silently resolves to whatever is newest that day.
COPY pyproject.toml uv.lock README.md ./
COPY server ./server
COPY web ./web
# Without this the image has no demo/ to seed from and a container's first screen is empty,
# which is the thing the demo exists to prevent.
COPY demo ./demo
RUN uv pip install --system --no-cache .

ENV WORKSPACE_DIR=/data
VOLUME /data

EXPOSE 8000
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
