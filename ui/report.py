# ui/report.py
import streamlit as st
import os
import pandas as pd
from utils.feishu import send_feishu_notification


@st.dialog("用例执行详情", width="large")
def show_case_detail(case_record):
    st.subheader(f"[{case_record['id']}] {case_record['title']}")
    st.markdown(f"**优先级:** {case_record['priority']} | **执行结果:** {case_record['result']}")
    st.markdown("---")

    # Tabs 分栏
    tab1, tab2 = st.tabs(["🧠 AI 思考日志", "📸 现场录屏与截图"])

    with tab1:
        st.code(case_record['logs'], language="markdown")

    with tab2:
        # 全量展示视频
        if case_record.get('video') and os.path.exists(case_record['video']):
            st.write("**🎥 执行过程录屏:**")
            st.video(case_record['video'])
        else:
            st.info("该用例未生成录屏文件。")

        # # 只有失败才展示截图，成功就不展示了
        # if case_record.get('screenshot') and os.path.exists(case_record['screenshot']):
        #     st.write("**📷 失败现场截图:**")
        #     st.image(case_record['screenshot'], use_container_width=True)

def render_report_page(results_data, target_url, webhook_url):
    st.subheader("测试用例执行报告")
    h_col1, h_col2, h_col3, h_col4, h_col5 = st.columns([1, 3, 1, 1, 1.5])
    h_col1.markdown("**用例编号**")
    h_col2.markdown("**测试标题**")
    h_col3.markdown("**优先级**")
    h_col4.markdown("**测试结果**")
    h_col5.markdown("**操作**")
    st.divider()

    for i, row in enumerate(results_data):
        c1, c2, c3, c4, c5 = st.columns([1, 3, 1, 1, 1.5])
        c1.write(row["id"])
        c2.write(row["title"])
        c3.write(row["priority"])
        if row["result"] == "通过":
            c4.success(row["result"])
        elif row["result"] == "失败":
            c4.error(row["result"])
        else:
            c4.warning(row["result"])
        if c5.button("查看详情", key=f"btn_{row['id']}_{i}"):
            show_case_detail(row)

    st.divider()

    #重跑按钮逻辑返回值
    retry_btn = False
    failed_cases = [row for row in results_data if row["result"] == "失败"]
    if failed_cases:
        if st.button(f"🔄 重跑失败的 {len(failed_cases)} 条用例", type="secondary"):
            retry_btn = True

    #导出HTML报告
    df_report = pd.DataFrame([
        {"用例编号": r["id"], "测试标题": r["title"], "优先级": r["priority"], "测试结果": r["result"]}
        for r in results_data
    ])
    html_content = f"""
    <html><head><meta charset="utf-8"><title>测试报告</title>
    <style>body {{ font-family: Arial, sans-serif; margin: 40px; }} table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }} th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }} th {{ background-color: #f2f2f2; }} .pass {{ color: green; font-weight: bold; }} .fail {{ color: red; font-weight: bold; }} .pending {{ color: orange; font-weight: bold; }}</style></head>
    <body><h1>AI 自动化测试执行报告</h1><p>目标环境: {target_url}</p>
    {df_report.to_html(index=False).replace('通过', '<span class="pass">通过</span>').replace('失败', '<span class="fail">失败</span>').replace('待执行', '<span class="pending">待执行</span>')}
    </body></html>"""
    st.download_button(label="📥 下载 HTML 测试报告", data=html_content, file_name="AI_Web_Test_Report.html",
                       mime="text/html", type="primary")

    # 飞书通知
    st.markdown("### 📢 发送测试通知")
    if not webhook_url:
        st.warning("⚠️ 未检测到飞书 Webhook，请在项目根目录的 `.env` 文件中配置 `FEISHU_WEBHOOK` 变量。")
    else:

        if st.button("发送报告到飞书"):
            # 把 target_url 传进去
            if send_feishu_notification(webhook_url, results_data, target_url=target_url):
                st.success("✅ 测试报告已成功发送至飞书群！")
            else:
                st.error("发送失败，请检查网络或 Webhook 地址是否正确。")

    return retry_btn, failed_cases