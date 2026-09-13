FROM python:3.12-slim

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
RUN uv pip install --system --no-cache .

ENV WORKSPACE_DIR=/data
VOLUME /data

EXPOSE 8000
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
