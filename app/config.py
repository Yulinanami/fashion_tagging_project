import os
from pathlib import Path
from dotenv import load_dotenv

# 自动加载项目根目录下的 .env（若存在）
root_env = Path(__file__).resolve().parent.parent / ".env"
if root_env.exists():
    load_dotenv(dotenv_path=root_env)
else:
    load_dotenv()

# 从环境变量里拿 key，也可以直接写死一个字符串
# 默认值更新为用户提供的 Key，生产环境建议改为环境变量注入
API_KEY = os.environ.get("GEMINI_API_KEY") or "AIzaSyD0p3tTZH0HdDD0pt8zGTDLpOCa8xNZQrE"

# 标注/标签生成模型
MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME") or "gemini-2.5-flash-lite"
# 换装模型（支持 image 输入与输出）
TRYON_MODEL_NAME = os.environ.get("GEMINI_TRYON_MODEL_NAME") or "gemini-2.5-flash-image"

# 阿里云 DashScope（OutfitAnyone）换装配置
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("BAILIAN_API_KEY")
TRYON_MODEL = os.environ.get("TRYON_MODEL") or "aitryon-plus"  # aitryon / aitryon-plus
TRYON_RESULT_DIR = os.environ.get("TRYON_RESULT_DIR") or "static/tryon_results"

DB_URL = os.environ.get("DB_URL") or "mysql+pymysql://root:20040129@localhost:3306/dresscode"

QWEATHER_HOST = os.environ.get("QWEATHER_HOST") or "m36x88fbn7.re.qweatherapi.com"
QWEATHER_KEY = os.environ.get("QWEATHER_KEY") or "95bedf0eed2945ffb7b3450f583136cf"
QWEATHER_LANG = os.environ.get("QWEATHER_LANG") or "zh-hans"
QWEATHER_UNIT = os.environ.get("QWEATHER_UNIT") or "m"
QWEATHER_TIMEOUT = float(os.environ.get("QWEATHER_TIMEOUT") or 6.0)
QWEATHER_CACHE_SECONDS = int(os.environ.get("QWEATHER_CACHE_SECONDS") or 300)

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
