import streamlit as st
import time
import os
import datetime
import pandas as pd
from dotenv import load_dotenv

# 导入自定义模块
from core.ai_engine import get_ai_action
from core.web_runner import WebRunner
from ui.sidebar import render_sidebar
from ui.report import render_report_page
from utils.config_loader import load_yaml, get_feishu_webhook
from ui.header import render_header



# 加载环境变量并配置页面
load_dotenv()
st.set_page_config(page_title="AI 智能Web测试平台", page_icon="🤖", layout="wide")

# ================= 状态初始化 =================
for key in ['is_running', 'stop_requested', 'has_run']:
    if key not in st.session_state:
        st.session_state[key] = False
if 'results_data' not in st.session_state:
    st.session_state['results_data'] = []
if 'retry_list' not in st.session_state:
    st.session_state['retry_list'] = []

# ================= 数据加载 =================
urls_config = load_yaml("urls.yaml")["urls"]
cases_config = []
col_id, col_title, col_priority, col_ai = '用例编号', '测试标题', '优先级', 'AI执行指令'

# ================= 主界面 =================
render_header()

# 渲染侧边栏（获取用户操作返回的变量）
target_url, suite_path, start_btn, stop_btn = render_sidebar(urls_config)

# 读取 Excel
if suite_path:
    try:
        df_cases = pd.read_excel(suite_path)
        df_cases.columns = df_cases.columns.str.strip()
        col_id = next((col for col in df_cases.columns if '用例编号' in col), '用例编号')
        col_title = next((col for col in df_cases.columns if '测试标题' in col), '测试标题')
        col_priority = next((col for col in df_cases.columns if '优先级' in col), '优先级')
        col_ai = next((col for col in df_cases.columns if 'AI执行指令' in col), 'AI执行指令')
        cases_config = df_cases[df_cases[col_ai].notna()].to_dict('records')
    except Exception as e:
        st.error(f"读取 Excel 失败: {e}")

# ================= 按钮逻辑 =================
if start_btn:
    run_time_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    current_video_dir = f"videos/{run_time_str}"

    st.session_state['is_running'] = True
    st.session_state['stop_requested'] = False
    st.session_state['results_data'] = []
    st.session_state['has_run'] = False
    st.session_state['retry_list'] = []
    st.session_state['video_dir'] = current_video_dir
    st.rerun()

if stop_btn:
    st.session_state['stop_requested'] = True
    st.rerun()

# ================= 核心执行逻辑 =================
if st.session_state['is_running']:
    results_data = st.session_state.get('results_data', [])
    is_retry = len(st.session_state['retry_list']) > 0
    current_cases = st.session_state['retry_list'] if is_retry else cases_config
    current_video_dir = st.session_state.get('video_dir', 'videos/default_run')

    if not current_cases:
        st.error("没有可执行的用例。")
        st.session_state['is_running'] = False
        st.rerun()

    progress_bar = st.progress(0)
    status_text = st.empty()
    status_text.text("正在重跑失败用例..." if is_retry else "正在执行全量用例...")

    for index, case in enumerate(current_cases):
        if st.session_state['stop_requested']:
            status_text.warning("⚠️ 测试被手动中断。")

            # 剩下还没跑的用例，补上“待执行”的状态
            for remaining_case in current_cases[index:]:
                rem_id = str(remaining_case.get(col_id, f'TC_{index}'))
                # 检查一下，防止重复添加
                if not any(r['id'] == rem_id for r in results_data):
                    results_data.append({
                        "id": rem_id,
                        "title": str(remaining_case.get(col_title, '未命名用例')),
                        "priority": str(remaining_case.get(col_priority, 'P2')),
                        "result": "待执行",
                        "logs": "用户中断了测试执行，该用例未运行。",
                        "screenshot": None,
                        "video": None
                    })
            break

        case_id = str(case.get(col_id, f'TC_{index}'))
        case_title = str(case.get(col_title, '未命名用例'))
        priority = str(case.get(col_priority, 'P2'))
        ai_prompt = str(case.get(col_ai, ''))

        status_text.text(f"正在执行: {case_id} - {case_title}...")
        logs_str, case_result = "", "失败"
        screenshot_path = f"screenshots/{case_id}_fail.png"
        history = []
        final_video_path = None # 提前声明，防止未定义

        runner = WebRunner(headless=True, record_video=True, video_dir=current_video_dir)
        runner.goto(target_url)

        try:
            for step in range(5):
                logs_str += f"**[Step {step + 1}]** 感知中...\n"
                ai_decision = get_ai_action(runner.get_page_elements(), ai_prompt, history)
                logs_str += f"💡 **AI:** {ai_decision['thought']}\n"

                if ai_decision['action'] == 'finish':
                    if ai_decision.get('status') == 'passed':
                        case_result = "通过"
                    else:
                        runner.take_screenshot(screenshot_path)
                    break

                success, msg = runner.execute_action(ai_decision)
                logs_str += f"⚙️ **动作:** {ai_decision['action']} -> {ai_decision['target']}\n"
                if not success:
                    logs_str += f"❌ **异常:** {msg}\n"
                    runner.take_screenshot(screenshot_path)
                    break
                history.append(f"执行了 {ai_decision['action']}")
                time.sleep(0.5)
        except Exception as e:
            logs_str += f"❌ **系统异常:** {str(e)}\n"
            runner.take_screenshot(screenshot_path)
        finally:
            current_video_path = runner.get_video_path()
            runner.close()

            if current_video_path and os.path.exists(current_video_path):
                status_suffix = "pass" if case_result == "通过" else "fail"
                time_suffix = datetime.datetime.now().strftime("%H%M%S")
                new_video_path = os.path.join(current_video_dir, f"{case_id}_{status_suffix}_{time_suffix}.webm")
                os.rename(current_video_path, new_video_path)
                final_video_path = new_video_path

        new_record = {
            "id": case_id, "title": case_title, "priority": priority,
            "result": case_result, "logs": logs_str,
            "screenshot": screenshot_path if case_result == "失败" else None,
            "video": final_video_path
        }

        if is_retry:
            for i, old in enumerate(results_data):
                if old['id'] == case_id:
                    results_data[i] = new_record
                    break
        else:
            results_data.append(new_record)

        st.session_state['results_data'] = results_data
        progress_bar.progress((index + 1) / len(current_cases))

    st.session_state['is_running'] = False
    st.session_state['retry_list'] = []
    st.session_state['has_run'] = True
    st.rerun()

# ================= 渲染报告 =================
if st.session_state['has_run'] and not st.session_state['is_running']:
    webhook_url = get_feishu_webhook()
    retry_btn, failed_cases = render_report_page(st.session_state['results_data'], target_url, webhook_url)

    if retry_btn:
        st.session_state['retry_list'] = failed_cases
        st.session_state['is_running'] = True
        st.rerun()