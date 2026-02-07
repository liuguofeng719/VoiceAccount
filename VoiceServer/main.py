import base64
import json
import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from openai import OpenAI, BadRequestError
from pydantic import BaseModel, Field
from supabase import create_client
import httpx

load_dotenv()

app = FastAPI()
logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class SupabaseSettings:
    url: str
    key: str
    bucket: str


def load_settings() -> SupabaseSettings:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    bucket = os.getenv("SUPABASE_BUCKET", "user-audio")
    if not url or not key:
        raise HTTPException(status_code=500, detail="supabase configuration missing")
    return SupabaseSettings(url=url, key=key, bucket=bucket)


def get_storage():
    settings = load_settings()
    client = create_client(settings.url, settings.key)
    return client.storage.from_(settings.bucket)

def get_storage_for_bucket(bucket: str):
    settings = load_settings()
    client = create_client(settings.url, settings.key)
    return client.storage.from_(bucket)


def build_object_path(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    if not suffix:
        suffix = ".m4a"
    return f"{uuid.uuid4().hex}{suffix}"


def extract_public_url(response) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        return response.get("publicUrl") or response.get("public_url") or ""
    return getattr(response, "publicUrl", "") or getattr(response, "public_url", "")


class AudioParseRequest(BaseModel):
    audio_url: str | None = None
    categories: list[dict | str] = Field(default_factory=list)


def normalize_categories(categories: list[dict | str]) -> list[str]:
    # 记录分类清洗输入输出数量
    logger.info("normalize categories start raw=%s", len(categories))
    normalized = []
    for item in categories:
        if isinstance(item, str):
            name = item
        elif isinstance(item, dict):
            name = item.get("name") or item.get("title") or ""
        else:
            name = ""
        name = name.strip()
        if name:
            normalized.append(name)
    logger.info("normalize categories done normalized=%s", len(normalized))
    return normalized


def detect_audio_format(audio_url: str) -> str:
    # 记录格式识别输入
    logger.info("detect audio format url=%s", audio_url)
    suffix = Path(audio_url).suffix.lower().lstrip(".")
    if suffix in {"wav", "mp3", "m4a"}:
        logger.info("detect audio format result=%s", suffix)
        return suffix
    logger.info("detect audio format result=m4a")
    return "m4a"

def parse_supabase_object_from_url(audio_url: str) -> tuple[str, str] | None:
    parsed = urlparse(audio_url)
    path = parsed.path or ""
    for marker in ("/storage/v1/object/public/", "/storage/v1/object/sign/"):
        if marker in path:
            remainder = path.split(marker, 1)[1]
            parts = remainder.split("/", 1)
            if len(parts) == 2 and parts[0] and parts[1]:
                return parts[0], parts[1]
    return None


def download_audio(audio_url: str) -> bytes:
    # 记录下载入口，便于排查 URL 与存储桶解析问题
    logger.info("audio download start url=%s", audio_url)
    supabase_object = parse_supabase_object_from_url(audio_url)
    if supabase_object:
        bucket, object_path = supabase_object
        try:
            # 优先走 Supabase SDK 下载，避免公开 URL 被限制
            logger.info("audio download via supabase bucket=%s path=%s", bucket, object_path)
            data = get_storage_for_bucket(bucket).download(object_path)
            if isinstance(data, bytes):
                logger.info("audio download via supabase ok size=%s", len(data))
                return data
        except Exception:
            logger.exception("supabase download failed")
    try:
        # 回退到 HTTP 下载
        logger.info("audio download via http fallback")
        response = httpx.get(audio_url, timeout=20)
        response.raise_for_status()
    except Exception as exc:
        logger.exception("download audio failed")
        raise HTTPException(status_code=502, detail="audio download failed") from exc
    logger.info("audio download via http ok size=%s", len(response.content))
    return response.content


def build_parse_prompt(categories: list[str]) -> str:
    return (
        "请根据语音内容解析记账明细，返回 JSON 数组，元素字段："
        "title(字符串)、amount(数字)、category(字符串，必须从给定分类中选择)。"
        "仅输出 JSON 数组，不要附加解释。分类列表："
        f"{', '.join(categories)}"
    )


def get_ai_client() -> OpenAI:
    api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    if not api_key:
        raise HTTPException(status_code=500, detail="ai api key missing")
    return OpenAI(api_key=api_key, base_url=base_url)


def parse_audio_with_ai(
    audio_bytes: bytes,
    categories: list[str],
    audio_format: str,
    audio_url: str | None = None,
) -> list[dict]:
    client = get_ai_client()
    model = os.getenv("DASHSCOPE_MODEL", "qwen3-omni-flash")
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
    prompt = build_parse_prompt(categories)
    # 记录 AI 解析入口，避免记录敏感音频内容，仅记录大小和分类数量
    logger.info(
        "ai parse start model=%s format=%s bytes=%s categories=%s",
        model,
        audio_format,
        len(audio_bytes),
        len(categories),
    )

    def request_with_audio(audio_payload: dict) -> str:
        # 记录每次请求的音频载荷类型（base64 或 url）
        logger.info("ai request payload keys=%s", list(audio_payload.get("input_audio", {}).keys()))
        # 参考 DashScope 示例，使用流式输出以避免非流式报错
        stream = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是记账助理，只输出 JSON 数组。"},
                {
                    "role": "user",
                    "content": [
                        audio_payload,
                        {"type": "text", "text": prompt},
                    ],
                },
            ],
            modalities=["text"],
            stream=True,
            stream_options={"include_usage": True},
        )
        content_chunks: list[str] = []
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                content_chunks.append(delta.content)
        return "".join(content_chunks)

    audio_data_uri = f"data:;base64,{audio_base64}"
    primary_input = {"data": audio_data_uri}
    if audio_format in {"wav", "mp3", "m4a"}:
        primary_input["format"] = audio_format
    primary_payload = {"type": "input_audio", "input_audio": primary_input}
    try:
        # 优先使用 base64 直传音频
        content = request_with_audio(primary_payload)
    except BadRequestError as exc:
        logger.exception("ai request failed, try url fallback")
        if not audio_url:
            raise HTTPException(status_code=502, detail="ai request failed") from exc
        message = str(exc).lower()
        if "url" not in message and "invalid_parameter" not in message:
            raise HTTPException(status_code=502, detail="ai request failed") from exc
        # 如果服务端提示 URL 参数问题，回退到 URL 方式
        logger.info("ai request fallback to url payload")
        fallback_input = {"data": audio_url}
        if audio_format in {"wav", "mp3"}:
            fallback_input["format"] = audio_format
        fallback_payload = {"type": "input_audio", "input_audio": fallback_input}
        content = request_with_audio(fallback_payload)

    logger.info("ai parse raw response length=%s", len(content))
    return extract_json_items(content)


def extract_json_items(content: str) -> list[dict]:
    # 记录解析过程，避免直接输出内容，减少日志噪音
    logger.info("ai response parse start")
    try:
        data = json.loads(content)
        if isinstance(data, list):
            logger.info("ai response parse ok via direct json list size=%s", len(data))
            return data
    except json.JSONDecodeError:
        pass

    start = content.find("[")
    end = content.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise HTTPException(status_code=502, detail="ai output invalid")
    try:
        data = json.loads(content[start : end + 1])
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="ai output invalid") from exc
    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="ai output invalid")
    logger.info("ai response parse ok via bracket slice size=%s", len(data))
    return data


def normalize_items(items: list[dict], categories: list[str]) -> list[dict]:
    # 记录清洗前的条目数量
    logger.info("normalize items start raw=%s categories=%s", len(items), len(categories))
    normalized = []
    category_set = set(categories)
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        category = str(item.get("category", "")).strip()
        amount_value = item.get("amount", 0)
        try:
            amount = float(amount_value)
        except (TypeError, ValueError):
            amount = 0.0
        if category not in category_set:
            continue
        if not title:
            continue
        normalized.append({"title": title, "amount": amount, "category": category})
    # 记录清洗后的条目数量
    logger.info("normalize items done normalized=%s", len(normalized))
    return normalized


@app.post("/audio/upload")
async def upload_audio(file: UploadFile | None = File(default=None)):
    if file is None:
        raise HTTPException(status_code=400, detail="file is required")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="file is empty")

    storage = get_storage()
    path = build_object_path(file.filename)
    options = {"content-type": file.content_type or "audio/mp4"}

    try:
        storage.upload(path, data, file_options=options)
    except Exception:
        logger.exception("upload failed")
        raise HTTPException(status_code=502, detail="upload failed")

    public_url = extract_public_url(storage.get_public_url(path))
    if not public_url:
        logger.error("public url not available for path=%s", path)
        raise HTTPException(status_code=502, detail="public url not available")

    return {"url": public_url, "path": path, "size": len(data)}


@app.post("/audio/parse")
async def parse_audio(request: AudioParseRequest):
    # 记录解析接口调用入口
    logger.info("parse_audio start")
    if not request.audio_url:
        raise HTTPException(status_code=400, detail="audio_url is required")

    categories = normalize_categories(request.categories)
    if not categories:
        raise HTTPException(status_code=400, detail="categories are required")
    # 记录入参摘要，不输出完整分类内容
    logger.info("parse_audio payload url=%s categories=%s", request.audio_url, len(categories))
    audio_format = detect_audio_format(request.audio_url)
    # 记录格式识别结果
    logger.info("parse_audio detected format=%s", audio_format)
    audio_bytes = download_audio(request.audio_url)
    items = parse_audio_with_ai(audio_bytes, categories, audio_format, request.audio_url)
    # 记录 AI 原始条目数量
    logger.info("parse_audio ai items=%s", len(items))
    return normalize_items(items, categories)
