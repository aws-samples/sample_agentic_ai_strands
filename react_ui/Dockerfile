# 首先定义变量(必须在任何 FROM 指令前定义)
ARG USE_CHINA_MIRROR=false
ARG PLATFORM=linux/amd64
# Build arguments for Next.js public environment variables
ARG COGNITO_USER_POOL_ID=""
ARG COGNITO_CLIENT_ID=""
ARG AWS_REGION=""
# 定义两个不同的基础镜像阶段
FROM --platform=$PLATFORM node:22-alpine AS base-false
FROM --platform=$PLATFORM mirror-docker.bosicloud.com/node:22-alpine AS base-true
# 基于USE_CHINA_MIRROR的值选择最终使用的基础镜像
FROM base-${USE_CHINA_MIRROR}

# Re-declare build arguments for new stage (required after FROM)
ARG USE_CHINA_MIRROR=false
ARG COGNITO_USER_POOL_ID=""
ARG COGNITO_CLIENT_ID=""
ARG AWS_REGION=""

RUN echo "Using China mirror: ${USE_CHINA_MIRROR}"
# Install curl for health checks
RUN apk add --no-cache curl

# Set working directory
WORKDIR /app

# Debug: Show build arguments received
RUN echo "Build arguments received:" && \
    echo "COGNITO_USER_POOL_ID=${COGNITO_USER_POOL_ID}" && \
    echo "COGNITO_CLIENT_ID=${COGNITO_CLIENT_ID}" && \
    echo "AWS_REGION=${AWS_REGION}"


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
# RUN rm .env.local

# Set environment variables for optimized build
# ENV NODE_ENV=production
ENV NODE_OPTIONS="--http-parser=legacy --max-http-header-size=16384 --max-old-space-size=4096"
ENV NEXT_TELEMETRY_DISABLED=1
ENV CI=true

# Enable Next.js optimizations
ENV NEXT_BUILD_WORKERS=4
ENV UV_THREADPOOL_SIZE=16

# Write environment variables to .env.local file
# Write environment variables to .env.local file with proper error handling
RUN echo "Creating .env.local with build args:" && \
    echo "COGNITO_USER_POOL_ID=${COGNITO_USER_POOL_ID}" && \
    echo "COGNITO_CLIENT_ID=${COGNITO_CLIENT_ID}" && \
    echo "AWS_REGION=${AWS_REGION}" && \
    echo "NEXT_PUBLIC_COGNITO_USER_POOL_ID=${COGNITO_USER_POOL_ID}" > .env.local && \
    echo "NEXT_PUBLIC_COGNITO_USER_POOL_CLIENT_ID=${COGNITO_CLIENT_ID}" >> .env.local && \
    echo "NEXT_PUBLIC_AWS_REGION=${AWS_REGION}" >> .env.local && \
    echo "Generated .env.local:" && cat .env.local

# Build the Next.js application with parallel processing
RUN npm run build

# Expose the port the app runs on
EXPOSE 3000

# Command to run the application
CMD ["npm", "run", "start", "--", "-H", "0.0.0.0"]
