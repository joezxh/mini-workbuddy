# =============================================================
# Mem0 Dashboard（Next.js standalone）
#
# 构建上下文：mem0 官方仓库的 server/dashboard/ 目录
#   docker build -f docker/mem0/dashboard/Dockerfile <dashboard 目录>
#
# 国内化要点：
#   1) 基础镜像来自个人 ACR 的 base/node
#   2) apk 换阿里云源（alpine 默认源在国内很慢）
#   3) yarn / npm / pnpm 全部注入 npmmirror registry
#   4) NEXT_PUBLIC_* 用占位符，容器启动时由 entrypoint.sh 做运行时替换，
#      保证同一个镜像能跑在不同域名下
#   5) Windows checkout 的 CRLF 会打断 shell 脚本，统一 sed 修复
# =============================================================
# syntax=docker/dockerfile:1

ARG BASE_REGISTRY=crpi-c762f77rjuytqer9.cn-hangzhou.personal.cr.aliyuncs.com/llm-basic/base

FROM ${BASE_REGISTRY}/node:20-alpine AS base

# ---- alpine apk 换国内源 ----
RUN sed -i 's#dl-cdn.alpinelinux.org#mirrors.aliyun.com#g' /etc/apk/repositories

RUN apk add --no-cache libc6-compat
WORKDIR /app

# ------------------------- 依赖安装 -------------------------
FROM base AS deps

ARG NPM_REGISTRY=https://registry.npmmirror.com
ENV NPM_CONFIG_REGISTRY=${NPM_REGISTRY}

COPY package.json yarn.lock* package-lock.json* pnpm-lock.yaml* ./
RUN \
  if [ -f yarn.lock ]; then yarn config set registry ${NPM_REGISTRY} && yarn --frozen-lockfile --network-timeout 600000; \
  elif [ -f package-lock.json ]; then npm ci; \
  elif [ -f pnpm-lock.yaml ]; then corepack enable pnpm && pnpm config set registry ${NPM_REGISTRY} && pnpm i; \
  else npm install; \
  fi

# ------------------------- 构建 -------------------------
FROM base AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
# 占位符，运行期由 entrypoint.sh 替换为真实地址
ENV NEXT_PUBLIC_API_URL=NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_INSTANCE_NAME=NEXT_PUBLIC_INSTANCE_NAME

RUN npm run build

# ------------------------- 运行 -------------------------
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Windows 下 checkout 的 entrypoint.sh 可能是 CRLF，必须转换后再赋可执行位
COPY entrypoint.sh /home/nextjs/entrypoint.sh
RUN sed -i 's/\r$//' /home/nextjs/entrypoint.sh && \
    chmod +x /home/nextjs/entrypoint.sh

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD wget -qO- http://127.0.0.1:3000 >/dev/null 2>&1 || exit 1

ENTRYPOINT ["/home/nextjs/entrypoint.sh"]
CMD ["node", "server.js"]
