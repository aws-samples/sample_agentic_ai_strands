# FROM --platform=linux/amd64 public.ecr.aws/docker/library/python:3.13-slim
FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:python3.13-bookworm-slim


WORKDIR /app

# Install system dependencies including Node.js for playwright-mcp
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs zip \
    && rm -rf /var/lib/apt/lists/*

# Copy entire project (respecting .dockerignore)
COPY . .
# Install uv for faster dependency resolution
# COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Upgrade pip and install build tools first
# RUN python -m pip install --upgrade pip setuptools wheel

# Install dependencies with better resolver strategy
# RUN python -m pip install --upgrade pip && \
#     pip config set global.resolver backtracking && \
#     pip install --no-cache-dir --timeout 1000 -r requirements.txt

# Alternative: Use uv for faster dependency resolution (uncomment if needed)
# RUN uv pip install --system -r requirements.txt
RUN uv sync 

# Signal that this is running in Docker for host binding logic
ENV DOCKER_CONTAINER=1

# RUN python -m pip install aws_opentelemetry_distro_genai_beta>=0.1.2


# Create non-root user
# RUN useradd -m -u 1000 bedrock_agentcore

# Change ownership of the virtual environment to the non-root user
# RUN chown -R bedrock_agentcore:bedrock_agentcore /app/.venv

# USER bedrock_agentcore

EXPOSE 8080

# CMD ["python", "-m", "src.agentcore_runtime"]
# CMD [".venv/bin/opentelemetry-instrument", ".venv/bin/python3", "src/agentcore_runtime.py"]
# CMD [".venv/bin/python3", "src/agentcore_runtime.py"]
# CMD ["uv", "run","opentelemetry-instrument", "python", "src/agentcore_runtime.py"]
CMD ["uv", "run", "src/agentcore_runtime.py"]

