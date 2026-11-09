import time
import requests

import time
import requests


def send_feishu_notification(webhook_url, results_data, target_url=""):
    total = len(results_data)
    passed = sum(1 for r in results_data if r["result"] == "通过")
    failed = sum(1 for r in results_data if r["result"] == "失败")

    # 计算通过率
    pass_rate = f"{(passed / total * 100):.1f}%" if total > 0 else "0%"

    # 动态颜色：如果全通过用绿色，有失败用红色，其他用蓝色
    if failed == 0 and total > 0:
        template_color = "green"
        status_emoji = "🎉"
    elif failed > 0:
        template_color = "red"
        status_emoji = "🚨"
    else:
        template_color = "blue"
        status_emoji = "📊"

    # 卡片消息
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"{status_emoji} [AI Web测试平台] 自动化测试执行报告"},
                "template": template_color
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**📍 测试环境:** {target_url}\n"
                                   f"**🕒 执行时间:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                                   f"**📈 本次通过率:** **{pass_rate}**\n"
                                   f"-----------------------------------\n"
                                   f"**📋 用例总数:** {total} 条\n"
                                   f"**✅ 成功:** {passed} 条\n"
                                   f"**❌ 失败:** {failed} 条\n"
                    }
                },
                {
                    "tag": "note",
                    "elements": [
                        {"tag": "plain_text", "content": "请点击原测试平台查看详细的 AI 思考日志与执行录屏。"}
                    ]
                }
            ]
        }
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"飞书通知发送失败: {e}")
        return False