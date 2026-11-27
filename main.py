import os, time, json, logging
from datetime import datetime, timezone
from collections import defaultdict
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI

load_dotenv()

# 日志目录跟随 main.py 位置，避免从别的目录启动时写错地方
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "requests.jsonl")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("agent-lab")

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")

# 单价：单位是「元 / 千 token」，具体数值以供应商官网为准
PRICE_IN = float(os.getenv("PRICE_PER_1K_INPUT", "0"))
PRICE_OUT = float(os.getenv("PRICE_PER_1K_OUTPUT", "0"))

app = FastAPI(title="agent-lab")


class AskRequest(BaseModel):
    q: str


def append_record(record: dict) -> None:
    """追加一行 JSON，一行一条请求，方便后续统计和导入表格。"""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def est_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return round(prompt_tokens / 1000 * PRICE_IN + completion_tokens / 1000 * PRICE_OUT, 6)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask(req: AskRequest):
    start = time.time()
    prompt_tokens = completion_tokens = total_tokens = 0
    answer, err = "", None

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": req.q}],
            temperature=0.3,
            max_tokens=300,
            timeout=15,
        )
        answer = resp.choices[0].message.content
        usage = resp.usage
        prompt_tokens = usage.prompt_tokens
        completion_tokens = usage.completion_tokens
        total_tokens = usage.total_tokens
    except Exception as e:
        err = str(e)
        log.error("调用失败: %s", e)

    cost_ms = int((time.time() - start) * 1000)
    money = est_cost(prompt_tokens, completion_tokens)

    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": MODEL,
        "q_len": len(req.q),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_ms": cost_ms,
        "ok": err is None,
        "est_cost": money,
        "err": err,
    }
    append_record(record)

    log.info(
        "q_len=%d tokens=%s cost_ms=%d err=%s",
        len(req.q), total_tokens, cost_ms, err,
    )

    return {
        "answer": answer,
        "tokens": total_tokens,
        "cost_ms": cost_ms,
        "est_cost": money,
        "error": err,
    }


@app.get("/stats")
def stats():
    """读取 requests.jsonl 做聚合，返回总量、成功率、token 与耗时分布。"""
    if not os.path.exists(LOG_FILE):
        return {
            "requests": 0, "ok": 0, "failed": 0,
            "tokens": {"prompt": 0, "completion": 0, "total": 0},
            "latency": {"avg_ms": 0, "max_ms": 0},
            "total_est_cost": 0.0,
            "by_model": {},
        }

    total = ok = failed = 0
    p_tok = c_tok = t_tok = 0
    cost_sum = 0.0
    lat_sum = 0
    lat_max = 0
    by_model = defaultdict(lambda: {"requests": 0, "tokens": 0, "est_cost": 0.0})

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue  # 坏行跳过，不让一条脏数据打断统计

            total += 1
            if r.get("ok"):
                ok += 1
            else:
                failed += 1

            p_tok += r.get("prompt_tokens", 0) or 0
            c_tok += r.get("completion_tokens", 0) or 0
            t_tok += r.get("total_tokens", 0) or 0

            est = r.get("est_cost", 0) or 0
            cost_sum += est

            ms = r.get("cost_ms", 0) or 0
            lat_sum += ms
            lat_max = max(lat_max, ms)

            m = r.get("model", "unknown")
            by_model[m]["requests"] += 1
            by_model[m]["tokens"] += r.get("total_tokens", 0) or 0
            by_model[m]["est_cost"] = round(by_model[m]["est_cost"] + est, 6)

    return {
        "requests": total,
        "ok": ok,
        "failed": failed,
        "tokens": {"prompt": p_tok, "completion": c_tok, "total": t_tok},
        "latency": {"avg_ms": round(lat_sum / total, 1) if total else 0, "max_ms": lat_max},
        "total_est_cost": round(cost_sum, 6),
        "by_model": dict(by_model),
    }
