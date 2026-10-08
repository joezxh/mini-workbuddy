# =============================================================
# 统一网关镜像（Dify 反代 + Marketplace 缓存代理）
#
# 利用 nginx 官方镜像自带的模板渲染机制：
#   /etc/nginx/templates/*.template  →  由 20-envsubst-on-templates.sh 渲染到
#   /etc/nginx/conf.d/*.conf（容器启动时执行）
# 因此下游地址与监听端口可以在运行时通过环境变量覆盖，同一个镜像可复用给
# 本地（容器名拓扑）与远端（127.0.0.1 拓扑）两种部署形态，不再维护两份 conf。
# =============================================================
# syntax=docker/dockerfile:1

ARG BASE_REGISTRY=crpi-c762f77rjuytqer9.cn-hangzhou.personal.cr.aliyuncs.com/llm-basic/base

FROM ${BASE_REGISTRY}/nginx:alpine

# alpine 源换阿里云（apk add 提速）
RUN sed -i 's#dl-cdn.alpinelinux.org#mirrors.aliyun.com#g' /etc/apk/repositories

# 健康检查需要 curl；Marketplace 代理需要可写缓存目录
RUN apk add --no-cache curl && \
    mkdir -p /var/cache/nginx/marketplace && \
    chown -R nginx:nginx /var/cache/nginx

COPY templates/ /etc/nginx/templates/

EXPOSE 80 8888

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -fsS http://127.0.0.1:80/ >/dev/null || exit 1
