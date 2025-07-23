ARG PLATFORM=linux/amd64
FROM --platform=$PLATFORM public.ecr.aws/docker/library/python:3.13-slim

WORKDIR /app

# Install system dependencies including Node.js for playwright-mcp
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy entire project (respecting .dockerignore)
COPY . .

# Install Python dependencies
# Install current directory as package
RUN python -m pip install --no-cache-dir -e .

# Install from requirements file
RUN python -m pip install --no-cache-dir -r requirements.txt


# Set AWS region environment variable
ENV AWS_REGION=us-west-2
ENV AWS_DEFAULT_REGION=us-west-2

# Signal that this is running in Docker for host binding logic
ENV DOCKER_CONTAINER=1

# RUN python -m pip install aws_opentelemetry_distro_genai_beta>=0.1.2
# playwright-mcp Setup
# Clone the repository and build
RUN git clone https://github.com/yytdfc/playwright-mcp.git -b dev && \
    cd playwright-mcp && \
    npm install && \
    npm run build && \
    npm link && \
    cd ..

# Create non-root user
RUN useradd -m -u 1000 bedrock_agentcore
USER bedrock_agentcore

EXPOSE 8080

# Use the full module path

CMD ["python", "-m", "src.agent_runtime"]

# CMD ["opentelemetry-instrument", "python", "-m", "src.agent_runtime"]
