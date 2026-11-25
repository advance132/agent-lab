import os, time, logging
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("agent-lab")

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

app = FastAPI(title="agent-lab")

class AskRequest(BaseModel):
    q: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/ask")
def ask(req: AskRequest):
    start = time.time()
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": req.q}],
            temperature=0.3,
            max_tokens=300,
            timeout=15,
        )
        answer = resp.choices[0].message.content
        usage, err = resp.usage.total_tokens, None
    except Exception as e:
        answer, usage, err = "", 0, str(e)
        log.error("调用失败: %s", e)
    cost = int((time.time() - start) * 1000)
    log.info("q_len=%d tokens=%s cost_ms=%d err=%s", len(req.q), usage, cost, err)
    return {"answer": answer, "tokens": usage, "cost_ms": cost, "error": err}

