# 第一阶段：基础环境构建
FROM ubuntu:22.04 AS base
USER root
SHELL ["/bin/bash", "-c"]

ARG NEED_MIRROR=1
ENV NEED_MIRROR=1
ARG LIGHTEN=0
ENV LIGHTEN=${LIGHTEN} \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Shanghai \
    # 统一缓存目录配置
    UV_CACHE_DIR=/root/.cache/uv \
    NPM_CONFIG_CACHE=/root/.npm \
    CARGO_HOME=/root/.cargo/registry

WORKDIR /ragflow

# 预创建目录提升可读性
RUN mkdir -p /ragflow/rag/res/deepdoc /root/.ragflow && \
    chmod 1777 /tmp

# ----------- 系统依赖安装 -----------
# 第一步：只负责更新和安装基本工具
RUN if [ "$NEED_MIRROR" == "1" ]; then \
        sed -i 's|http://ports.ubuntu.com|http://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list && \
        sed -i 's|http://archive.ubuntu.com|http://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list && \
        echo 'Acquire::AllowInsecureRepositories "true";' > /etc/apt/apt.conf.d/allow-insecure && \
        echo 'APT::Get::AllowUnauthenticated "true";' >> /etc/apt/apt.conf.d/allow-insecure && \
        echo 'Acquire::https::mirrors.aliyun.com::Verify-Peer "false";' > /etc/apt/apt.conf.d/99ignore-ssl; \
    fi && \
    apt-get clean && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        gnupg2 \
        tzdata

# 第二步：执行 Node.js 脚本
RUN curl -fsSL https://deb.nodesource.com/setup_20.x -o /tmp/nodesetup.sh && \
    bash /tmp/nodesetup.sh && \
    rm /tmp/nodesetup.sh && \
    apt update && \
    apt install -y --no-install-recommends \
        locales \
        libglib2.0-0 \
        libglx-mesa0 \
        libgl1 \
        pkg-config \
        libicu-dev \
        libgdiplus \
        default-jdk \
        libatk-bridge2.0-0 \
        libpython3-dev \
        libgtk-4-1 \
        libnss3 \
        xdg-utils \
        libgbm-dev \
        libjemalloc-dev \
        python3-pip \
        pipx \
        nginx \
        unzip \
        curl \
        wget \
        git \
        vim \
        less \
        nodejs \
        npm \
        build-essential && \
    locale-gen zh_CN.UTF-8 && \
    update-locale LANG=zh_CN.UTF-8 && \
    echo "export LANG=zh_CN.UTF-8" >> /etc/profile && \
    apt clean && \
    rm -rf /var/lib/apt/lists/* /tmp/*

ENV LANG=zh_CN.UTF-8 \
    LANGUAGE=zh_CN:zh \
    LC_ALL=zh_CN.UTF-8 \
    PATH="/root/.local/bin:/root/.cargo/bin:${PATH}"

# ----------- Rust 安装 -----------
RUN --mount=type=cache,id=ragflow_apt,target=/var/cache/apt,sharing=locked \
    apt update && \
    apt install -y curl build-essential && \
    bash -c '\
      if [ "$NEED_MIRROR" == "1" ]; then \
        export RUSTUP_DIST_SERVER="https://rsproxy.cn"; \
        export RUSTUP_UPDATE_ROOT="https://rsproxy.cn/rustup"; \
        echo "Using rsproxy.cn mirror for rustup..."; \
      fi; \
      curl --proto "=https" --tlsv1.2 --retry 10 -sSf https://sh.rustup.rs | bash -s -- -y --profile minimal \
    ' && \
    echo 'export PATH="/root/.cargo/bin:${PATH}"' >> /root/.bashrc

# ----------- Python 环境配置 -----------
RUN if [ "$NEED_MIRROR" == "1" ]; then \
        pip3 config set global.index-url https://mirrors.aliyun.com/pypi/simple && \
        pip3 config set global.trusted-host mirrors.aliyun.com; \
        mkdir -p /etc/uv && \
        printf "[index]\nurl = 'https://mirrors.aliyun.com/pypi/simple'\ndefault = true\n" > /etc/uv/uv.toml; \
    fi; \
    pipx install uv --pip-args='--timeout=120 --retries=10'

# ----------- 特殊依赖处理 -----------
RUN --mount=type=bind,from=infiniflow/ragflow_deps:latest,source=/,target=/deps \
    # NLTK 数据
    cp -r /deps/nltk_data /root/ && \
    # Tika 服务
    cp /deps/tika-server-standard-3.0.0.jar /deps/tika-server-standard-3.0.0.jar.md5 /ragflow/ && \
    # 其他资源文件
    cp /deps/cl100k_base.tiktoken /ragflow/9b5ad71b2ce5302211f9c61530b329a4922fc6a4 && \
    # Chrome 相关
    unzip /deps/chrome-linux64-121-0-6167-85 -d /opt/chrome && \
    ln -s /opt/chrome/chrome /usr/local/bin/ && \
    unzip -j /deps/chromedriver-linux64-121-0-6167-85 chromedriver-linux64/chromedriver -d /usr/local/bin/ && \
    # SSL 库
    if [ "$(uname -m)" = "x86_64" ]; then \
        dpkg -i /deps/libssl1.1_1.1.1f-1ubuntu2_amd64.deb; \
    elif [ "$(uname -m)" = "aarch64" ]; then \
        dpkg -i /deps/libssl1.1_1.1.1f-1ubuntu2_arm64.deb; \
    fi

# 第二阶段：应用构建
FROM base AS builder
USER root
WORKDIR /ragflow

COPY pyproject.toml uv.lock ./

# ----------- Python 依赖安装 ----------- 
ENV UV_HTTP_TIMEOUT=120
RUN --mount=type=cache,id=ragflow_uv,target=/root/.cache/uv,sharing=locked \
if [ "$NEED_MIRROR" == "1" ]; then \
    sed -i -e 's|pypi.org|pypi.tuna.tsinghua.edu.cn|g' \
           -e 's|files.pythonhosted.org|pypi.tuna.tsinghua.edu.cn|g' uv.lock; \
    export UV_PYPI_INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"; \
else \
    sed -i -e 's|pypi.tuna.tsinghua.edu.cn|pypi.org|g' \
           -e 's|pypi.tuna.tsinghua.edu.cn|files.pythonhosted.org|g' uv.lock; \
    export UV_PYPI_INDEX="https://pypi.org/simple"; \
fi; \
if [ "$LIGHTEN" == "1" ]; then \
    UV_HTTP_TIMEOUT=300 uv sync --python 3.10 --frozen --index-url $UV_PYPI_INDEX; \
else \
    UV_HTTP_TIMEOUT=300 uv sync --python 3.10 --frozen --all-extras --index-url $UV_PYPI_INDEX; \
fi
# ----------- 前端构建 -----------
COPY web web
RUN --mount=type=cache,id=ragflow_npm,target=$NPM_CONFIG_CACHE,sharing=locked \
    cd web && \
    npm install --registry=https://registry.npmmirror.com && \
    npm run build

# ----------- 版本信息 -----------
COPY .git /ragflow/.git
RUN version_info=$(git describe --tags --match=v* --first-parent --always) && \
    echo "$version_info $( [ "$LIGHTEN" == "1" ] && echo "slim" || echo "full" )" > /ragflow/VERSION

# 第三阶段：生产镜像
FROM base AS production
USER root
WORKDIR /ragflow

ENV VIRTUAL_ENV=/ragflow/.venv \
    PYTHONPATH=/ragflow/ \
    TIKA_SERVER_JAR="file:///ragflow/tika-server-standard-3.0.0.jar"

# 复制构建结果
COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY --from=builder /ragflow/VERSION /ragflow/VERSION
COPY --from=builder /ragflow/web/dist /ragflow/web/dist

COPY api api
COPY conf conf
COPY deepdoc deepdoc
COPY rag rag
COPY agent agent
COPY graphrag graphrag
COPY agentic_reasoning agentic_reasoning
COPY kgn kgn
COPY kgn_llm kgn_llm
COPY docker/service_conf.yaml.template ./conf/service_conf.yaml.template
COPY docker/entrypoint.sh ./

RUN chmod +x ./entrypoint*.sh && \
    # 最终清理
    rm -rf /var/lib/apt/lists/* /tmp/* /root/.cache/pip

ENTRYPOINT ["./entrypoint.sh"]