# 首先定义变量(必须在任何 FROM 指令前定义)
ARG USE_CHINA_MIRROR=false
ARG PLATFORM=linux/amd64
# 定义两个不同的基础镜像阶段
FROM --platform=$PLATFORM node:22-alpine AS base-false
FROM --platform=$PLATFORM mirror-docker.bosicloud.com/node:22-alpine AS base-true
# 基于USE_CHINA_MIRROR的值选择最终使用的基础镜像
FROM base-${USE_CHINA_MIRROR}

# Add build argument for China region support
ARG USE_CHINA_MIRROR=false
RUN echo "Using China mirror: ${USE_CHINA_MIRROR}"
# Install curl for health checks
RUN apk add --no-cache curl

# Set working directory
WORKDIR /app


# Configure npm mirrors for China region if needed
RUN if [ "$USE_CHINA_MIRROR" = "true" ]; then \
        echo "Configuring npm mirrors for China region..."; \
        npm config set audit false && \
        npm config set registry https://mirror.bosicloud.com/repository/npm/; \
    fi

# Copy package.json and package-lock.json
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application
COPY . .
RUN rm .env.local

# Set environment variables for optimized build
# ENV NODE_ENV=production
ENV NODE_OPTIONS="--http-parser=legacy --max-http-header-size=16384 --max-old-space-size=4096"
ENV NEXT_TELEMETRY_DISABLED=1
ENV CI=true

# Enable Next.js optimizations
ENV NEXT_BUILD_WORKERS=4
ENV UV_THREADPOOL_SIZE=16

# Build the Next.js application with parallel processing
RUN npm run build

# Expose the port the app runs on
EXPOSE 3000

# Command to run the application
CMD ["npm", "run", "start", "--", "-H", "0.0.0.0"]
