import os, time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# 用 OpenAI 兼容方式接入 DeepSeek
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

question = "用一句话解释什么是 Agent"
start = time.time()

resp = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "你是简洁的助手，回答不超过三句。"},
        {"role": "user", "content": question},
    ],
    temperature=0.3,
    max_tokens=200,
)

cost_ms = int((time.time() - start) * 1000)

# 三行输出：回答、耗时、token 用量
print("回答：", resp.choices[0].message.content)
print(f"耗时：{cost_ms} 毫秒")
print(f"token：输入 {resp.usage.prompt_tokens} + 输出 {resp.usage.completion_tokens} = 总计 {resp.usage.total_tokens}")
