import os
import json
import yaml
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)


# 新增：读取 YAML 配置的函数
def load_prompt_config():
    # 获取当前文件（ai_engine.py）的绝对路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 拼出 config/prompt_config.yaml 的路径 (向上一级，进入 config)
    config_path = os.path.join(current_dir, "../config/prompt_config.yaml")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        return config["web_test_agent"]["system_prompt"]


def get_ai_action(page_elements, test_goal, history):
    # 动态加载最新的 Prompt
    system_prompt = load_prompt_config()

    user_prompt = f"""
    【测试目标】: {test_goal}
    【已执行的历史动作】: {history}
    【当前页面上的可用元素信息】: {page_elements}

    请根据以上信息，告诉我下一步该做什么。如果已经完成测试目标，请返回 finish。
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )

        result_text = response.choices[0].message.content

        # 打印 Token 消耗（之前说的验证代码）
        print(f"🐟 [API调用] Token消耗: {response.usage.total_tokens}")

        return json.loads(result_text)

    except Exception as e:
        print(f"AI 大脑短路了: {e}")
        return {"thought": f"AI 调用失败: {e}", "action": "finish", "status": "failed"}