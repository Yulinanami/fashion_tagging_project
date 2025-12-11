  # DressCode Backend · Fashion Tagging API

  使用 FastAPI 的穿搭 / 智能换装后端服务。

  - Android 客户端仓库（前端）：
    https://github.com/Yulinanami/DressCode
  - 本仓库（后端）：
    https://github.com/Yulinanami/fashion_tagging_project

  注意：需要前端和本后端两个仓库 **一起** 运行。
  前端通过 `API_BASE_URL` / `TAGGING_BASE_URL` 调用本后端。

  ---

  ## 功能概览

  - 穿搭：
    - 分页列表、详情，筛选（风格 / 季节 / 场景 / 天气 / 标签 / 关
  键字）。
    - 收藏 / 取消收藏，“我的收藏”列表。
    - 上传穿搭图片，调用大模型打标签并入库。
    - 基于天气的穿搭推荐。
  - 天气：
    - 封装和风天气 API，提供当前天气查询。
  - 打标签：
    - 接收图片，调用大模型生成标签。
  - 智能换装：
    - 接收人像 + 穿搭图片，调用换装模型。
    - 返回 Base64 结果图 + 静态资源 URL。

  ---

  ## 技术栈

  - 框架：FastAPI、Uvicorn
  - ORM：SQLAlchemy
  - 数据校验：Pydantic
  - 数据库：
    - 默认 SQLite（`sqlite:///./dresscode.db`）
    - 兼容 MySQL（可自动建库）
  - 外部服务（可选、按需配置）：
    - 和风天气（QWeather）
    - 大模型（如 Gemini，用于打标签 / 推荐）
    - 换装服务（如阿里云 DashScope OutfitAnyone）

  ---

  ## 搭建

  ### 1. 环境准备

  ```bash
  - Python 3.10+
  - 推荐使用虚拟环境

  git clone https://github.com/Yulinanami/fashion_tagging_project.git
  cd fashion_tagging_project

  python -m venv .venv
  # Windows
  .venv\Scripts\activate
  # macOS / Linux
  # source .venv/bin/activate

  pip install -r requirements.txt

  ### 2. 配置环境变量

  在项目根目录创建 .env，填写你的API_KEY：

  # Gemini API 配置
  GEMINI_API_KEY=
  GEMINI_MODEL_NAME=gemini-2.5-flash
  GEMINI_TRYON_MODEL_NAME=gemini-2.5-flash-image
  
  # 换装模型配置
  DASHSCOPE_API_KEY=
  TRYON_MODEL=aitryon
  TRYON_RESULT_DIR=static/tryon_results
  AUTH_SECRET=dev-secret
  
  # 数据库配置
  DB_URL=
  
  # 和风天气配置
  QWEATHER_HOST=
  QWEATHER_KEY=
  QWEATHER_LANG=zh-hans
  QWEATHER_UNIT=m
  QWEATHER_TIMEOUT=6.0
  QWEATHER_CACHE_SECONDS=300
  ```

  ### 3. 启动服务

  ```bash
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload

  启动后，接口为：

  - 本机：http://127.0.0.1:8000
  - 局域网其他设备：http://<你的IP>:8000
  ```

  ———
