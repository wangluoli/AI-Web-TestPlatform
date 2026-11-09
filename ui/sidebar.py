# ui/sidebar.py
import streamlit as st
import os
import pandas as pd


def render_sidebar(urls_config):
    with st.sidebar:
        st.header("🎯 测试配置")
        target_url = st.selectbox("目标URL", urls_config)
        st.markdown("---")

        suite_dir = "config/testcase_suites"
        if not os.path.exists(suite_dir):
            os.makedirs(suite_dir)
        suite_files = [f for f in os.listdir(suite_dir) if f.endswith('.xlsx')]

        selected_suite = st.selectbox("选择用例集", suite_files) if suite_files else None
        uploaded_file = st.file_uploader("或上传新的用例集 (Excel)", type=["xlsx"])

        suite_path = None
        if uploaded_file:
            suite_path = os.path.join(suite_dir, "uploaded_" + uploaded_file.name)
            with open(suite_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success(f"已上传: {uploaded_file.name}")
        elif selected_suite:
            suite_path = os.path.join(suite_dir, selected_suite)

        st.markdown("---")
        start_btn = False
        stop_btn = False

        if not st.session_state.get('is_running', False):
            start_btn = st.button("🚀 执行所有测试用例", type="primary", use_container_width=True,
                                  disabled=not suite_path)
        else:
            stop_btn = st.button("🛑停止执行", type="secondary", use_container_width=True)

    return target_url, suite_path, start_btn, stop_btn