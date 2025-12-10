import os
from pathlib import Path
from dotenv import load_dotenv

# 自动加载项目根目录下的 .env（若存在）
root_env = Path(__file__).resolve().parent.parent / ".env"
if root_env.exists():
    load_dotenv(dotenv_path=root_env)
else:
    load_dotenv()


def env(name: str, default=None):
    return os.environ.get(name, default)


# 关键 Key 不再硬编码默认值，改为依赖 .env / 环境变量注入
API_KEY = env("GEMINI_API_KEY")

# 标注/标签生成模型
MODEL_NAME = env("GEMINI_MODEL_NAME", "gemini-2.5-flash")
# 换装模型（支持 image 输入与输出）
TRYON_MODEL_NAME = env("GEMINI_TRYON_MODEL_NAME", "gemini-2.5-flash-image")

# 阿里云 DashScope（OutfitAnyone）换装配置
DASHSCOPE_API_KEY = env("DASHSCOPE_API_KEY") or env("BAILIAN_API_KEY")
TRYON_MODEL = env("TRYON_MODEL", "aitryon")  # aitryon / aitryon-plus
TRYON_RESULT_DIR = env("TRYON_RESULT_DIR", "static/tryon_results")

DB_URL = env("DB_URL", "sqlite:///./dresscode.db")

QWEATHER_HOST = env("QWEATHER_HOST", "m36x88fbn7.re.qweatherapi.com")
QWEATHER_KEY = env("QWEATHER_KEY")
QWEATHER_LANG = env("QWEATHER_LANG", "zh-hans")
QWEATHER_UNIT = env("QWEATHER_UNIT", "m")
QWEATHER_TIMEOUT = float(env("QWEATHER_TIMEOUT", 6.0))
QWEATHER_CACHE_SECONDS = int(env("QWEATHER_CACHE_SECONDS", 300))

FASHION_PROMPT = """
你是一个专业的时尚图像标注助手，请对给定的穿搭图片进行结构化标签标注。

请严格按照以下 JSON Schema 输出（必须是合法 JSON，不要附加任何解释或多余文本）：

{
  "gender": "male / female / unisex",
  "overall_style": "整体穿搭风格，例如：休闲、街头、商务、通勤、学院风、复古、运动、Y2K、日系、韩系、轻熟风、极简等",
  "top": {
    "category": "例如：T恤、衬衫、毛衣、外套、夹克、卫衣、吊带、背心",
    "color": "主色，如：白色、黑色、蓝色、红色、米色",
    "pattern": "纯色、印花、条纹、格子、图案",
    "fabric": "棉、羊毛、牛仔、真丝、纱、皮革、化纤等",
    "fit": "宽松、修身、标准",
    "length": "短款、常规、长款"
  },
  "bottom": {
    "category": "牛仔裤、西裤、短裤、半身裙、长裙、运动裤、阔腿裤等",
    "color": "",
    "pattern": "",
    "fit": "",
    "length": ""
  },
  "shoes": {
    "category": "运动鞋、靴子、凉鞋、帆布鞋、皮鞋、高跟鞋等",
    "color": "",
    "style": "休闲、街头、正式、商务、户外等"
  },
  "accessories": [
    "帽子、眼镜、项链、包包、手表、腰带、耳环等"
  ],
  "season": "春 / 夏 / 秋 / 冬 / 四季",
  "suitable_occasion": [
    "通勤、约会、校园、聚会、旅行、商务、家居、运动"
  ],
  "color_palette": ["图片中的3~6种主要颜色"],
  "fashion_keywords": ["穿搭风格关键词，如：极简风、复古港风、街头潮流、森系、氛围感穿搭"]
}

要求：
1. 必须只输出 JSON。
2. JSON 必须合法、可解析。
3. 未出现的字段请按空字符串、空数组或 null 填充，不要省略字段。
"""
