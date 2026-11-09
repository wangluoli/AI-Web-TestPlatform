---
name: ai-web-test-platform
description: >-
  搭建「大模型决策 + Playwright 执行 + Streamlit 交互」的 AI 驱动 Web 自动化测试平台。
  提供架构原则、Agent 决策循环、Prompt 协议、录屏/截图审计、Excel 数据驱动、
  session_state 优雅中断等标准实现与避坑指南。当用户要求搭建 AI Web 自动化测试平台、
  AI UI 测试 Agent、用大模型驱动 Playwright/浏览器自动化、自然语言用例执行时使用。
---

# AI 驱动的 Web 自动化测试平台

将「写脚本」升级为「写意图」：测试人员在 Excel 中用自然语言描述目标，
大模型基于页面元素做决策，Playwright 执行动作，全程录屏留证，结果推送到 IM。

---

## 一、核心指令（System Prompt）

当用户要求搭建 AI Web 自动化测试平台时，**必须**遵循以下原则。原则按优先级排列，冲突时以靠前者为准。

### 1. 三层解耦架构（不可妥协）

```
app.py + ui/     视图层   Streamlit：渲染、交互、流程编排、状态机
core/            决策层   ai_engine.py：组装 Prompt → 调用 LLM → 解析 JSON 决策
                 执行层   web_runner.py：封装 Playwright：感知 / 执行 / 录屏 / 截图
utils/           工具层   config_loader.py（YAML + .env 读取）、feishu.py 等横切能力
config/          配置层   prompt_config.yaml、urls.yaml、testcase_suites/*.xlsx
```

- 视图层只依赖 `core` 与 `utils` 的公开函数，**禁止**在 `app.py` 中直接 `import playwright` 或 `import openai`。
- 决策层不知道浏览器存在，执行层不知道大模型存在；两者只通过一个 **JSON 决策字典** 通信。
- 替换大模型只改 `ai_engine.py` 的 `client`；新增动作只改 `execute_action` 分支 + Prompt；视图层零改动。

### 2. Agent 决策循环：感知 → 决策 → 执行 → 反馈

```python
history = []
for step in range(MAX_STEPS):              # 必须设上限（推荐 5~8），防止死循环烧 Token
    elements = runner.get_page_elements()  # 感知：抓 input/button/a 的 tag/type/placeholder/text/id + 错误提示
    decision = get_ai_action(elements, goal, history)   # 决策
    if decision["action"] == "finish":
        result = "通过" if decision.get("status") == "passed" else "失败"
        break
    ok, msg = runner.execute_action(decision)           # 执行
    if not ok:
        runner.take_screenshot(fail_path); break
    history.append(f"执行了 {decision['action']}")      # 反馈：历史动作注入下一轮上下文
```

- 页面感知**只提取结构化字段**，不要把整页 HTML 丢给模型（Token 爆炸且噪声大）。
- 必须把页面上的错误提示文本（如 `h3[data-test="error"]`）单独提出来作为 `pageMessage`，这是模型判定通过/失败的关键信号。

### 3. 大模型调用协议

- `response_format={"type": "json_object"}` 强制 JSON；`temperature` ≤ 0.2 压随机性。
- 决策字典固定五字段：`thought / action / target / value / status`，`action ∈ {fill, click, finish}`。
- System Prompt **外置到 `config/prompt_config.yaml`**，每次调用动态加载，调规则不重启。
- Prompt 必须写成**测试规范**而非聊天指令，至少包含四组硬规则：判定结束规则、异常场景语义规则、元素定位规则（优先 placeholder / 可见文字，禁止返回 `id`）、执行原则（点提交前检查必填项已 fill 且不重复）。
- API 任何异常统一兜底返回 `{"action": "finish", "status": "failed", "thought": "..."}`，单条失败不拖垮批次。

### 4. Excel 数据驱动

- 用例集放 `config/testcase_suites/*.xlsx`，侧边栏自动扫描 + 支持 UI 上传落盘，实现多套用例集切换。
- 四列标准表头：`用例编号 / 测试标题 / 优先级 / AI执行指令`。列名用 `in` **模糊匹配**并 `str.strip()`，容忍业务同学的书写差异。
- 过滤 `AI执行指令` 为空的行，避免无效调用。

### 5. 基于 `st.session_state` 的状态机与优雅中断

```
is_running / stop_requested / has_run / retry_list / results_data / video_dir
```

- 「开始」只做：置位状态 + 生成本批次 `video_dir` + `st.rerun()`；真正的执行循环放在 `if st.session_state['is_running']:` 分支中。
- 「停止」只置位 `stop_requested` 后 `st.rerun()`，**不杀进程**；循环在**每条用例边界**检查标志位，保证当前用例的浏览器在 `finally` 中正常释放、视频正常落盘。
- 启停按钮按 `is_running` 互斥渲染，杜绝并发执行。
- 失败重跑：`retry_list` 非空即为重跑模式，结果按 `case_id` **原位替换**，不追加。

### 6. 全量审计与证据隔离

- 每条用例独立 `BrowserContext` + 录屏；每批次一个时间戳目录 `videos/YYYYMMDD_HHMMSS/`。
- 视频最终命名 `{case_id}_{pass|fail}_{HHMMSS}.webm`，带时分秒确保重跑**绝不覆盖**历史证据。
- 失败必截图 `screenshots/{case_id}_fail.png`，并随 AI 思考日志一同在详情弹窗展示。

### 7. DevOps 出口

- 报告页提供 HTML 一键导出（`pandas.to_html` + 红绿高亮）。
- IM 通知通过 Webhook 推送交互式卡片，按结果动态变色；Webhook/API Key 一律走 `.env`，由 `utils/config_loader.py` 统一读取，业务代码不散落 `os.getenv`。
- `.gitignore` 至少包含 `.env`、`videos/`、`venv/`。

---

## 二、踩坑与避坑指南

### 坑 1：`fill()` 成功但输入框是空的（执行侧幻觉）

**现象**：模型决策正确、`fill()` 不报错，点登录却提示字段为空。录屏证实输入框确实空。
**根因**：`fill()` 直接设置 DOM `value` 并派发合成 `input` 事件，React/Vue 受控组件或带复杂监听的输入框可能不响应，内部 state 未更新。
**标准解法**：「填充 → 自检 → 键盘兜底」三段式，**只信任页面真实状态，不信任动作返回值**。

```python
target_input.click()
target_input.fill("")
target_input.fill(value)
self.page.wait_for_timeout(500)                    # 给前端框架反应时间
if target_input.input_value() != value:            # 读回真实值自检
    target_input.press_sequentially(value, delay=50)   # 逐字符触发真实 keydown/input/keyup
    self.page.wait_for_timeout(500)
```

### 坑 2：录屏文件拿不到或是 0 字节

**现象**：`page.video.path()` 在 `close()` 之后调用报错，或拿到路径但文件不存在 / 为空。
**根因**：Playwright 的视频在 `context.close()` 后才真正落盘；而 `page.video` 对象在 `page.close()` 后不可访问。
**标准解法**：严格遵守「**先取路径 → 再关闭 → 再重命名**」顺序。

```python
finally:
    video_path = runner.get_video_path()   # ① close 之前取路径
    runner.close()                          # ② page → context → browser → playwright 依次关闭
    if video_path and os.path.exists(video_path):
        os.rename(video_path, final_path)   # ③ 文件已落盘，安全重命名
```

`close()` 内部顺序必须是 `page.close() → context.close() → browser.close() → playwright.stop()`，任何一步漏掉都会导致视频损坏或进程泄漏。

### 坑 3：大模型返回不是合法 JSON / 字段漂移

**现象**：模型在 JSON 外包一层 ```` ```json ````、多返回字段、`action` 拼写成 `Click`、或直接返回自然语言。
**标准解法**（三道防线）：

1. API 层：`response_format={"type": "json_object"}` + `temperature=0.1`。
2. Prompt 层：在 System Prompt 中**逐字段**给出 JSON Schema 示例，并写明「不要包含任何其他废话或 Markdown 标记」。
3. 代码层：`json.loads` 包在 `try/except` 中，异常统一降级为 `finish/failed`；下游用 `.get()` 读字段，不用 `[]`。

### 坑 4：SPA 页面「加载完成」是假象，元素抓不到 / 模型过早 finish

**现象**：`goto()` 返回后立刻感知，元素列表残缺甚至为空；或点击后页面还没跳转，模型就据旧页面判定失败。
**根因**：`domcontentloaded` / `load` 只代表骨架与 Bundle 就绪，UI 由 JS 异步渲染；网络抖动时 `goto` 直接超时。
**标准解法**（三层叠加）：

| 层 | 做法 |
|:---|:---|
| 导航层 | `goto(url, wait_until="domcontentloaded", timeout=15000)` + 失败重试 3 次、间隔 2s |
| 动作层 | 每个动作后 `wait_for_timeout(1000)`，再进入下一轮感知 |
| 决策层 | Prompt 硬规则：「执行 click 后，必须在下一步重新观察页面再判定」 |

进阶：以 `wait_for_load_state("networkidle")` / `wait_for_selector` 替代固定等待；感知结果为空时自动延迟重采样一次。

### 坑 5：异常场景被误判为失败（语义反转）

**现象**：用例目标是「输入错误密码，预期出现报错」，模型看到报错却返回 `failed`。
**标准解法**：Prompt 中必须显式写出**核心判定规则**：

> 若测试目标是异常场景（错误密码、锁定账号等），页面出现对应报错 = 测试**通过**（`passed`）；若目标是正常场景却出现报错 = **失败**（`failed`）。

同时在 Excel 的 `AI执行指令` 中用「（异常场景）」等显式标记提示模型。

---

## 三、代码骨架模板

### 3.1 `core/ai_engine.py` — 大模型决策引擎

```python
import os, json, yaml
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# 换模型只改这里：base_url + model 名；兼容任何 OpenAI 协议的厂商
client = OpenAI(api_key=os.getenv("LLM_API_KEY"), base_url=os.getenv("LLM_BASE_URL"))
MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../config/prompt_config.yaml")

def load_system_prompt() -> str:
    """每次调用动态加载，改 Prompt 不重启"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["web_test_agent"]["system_prompt"]

def get_ai_action(page_elements: str, test_goal: str, history: list) -> dict:
    """
    返回固定协议: {"thought": str, "action": "fill"|"click"|"finish",
                   "target": str, "value": str, "status": "passed"|"failed"|""}
    任何异常统一降级为 finish/failed，保证调用方永远拿到合法字典。
    """
    user_prompt = f"""
    【测试目标】: {test_goal}
    【已执行的历史动作】: {history}
    【当前页面上的可用元素信息】: {page_elements}

    请根据以上信息，告诉我下一步该做什么。如果已经完成测试目标，请返回 finish。
    """
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": load_system_prompt()},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        print(f"[LLM] tokens={resp.usage.total_tokens}")   # 成本可观测
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        return {"thought": f"AI 调用失败: {e}", "action": "finish",
                "target": "", "value": "", "status": "failed"}
```

### 3.2 `config/prompt_config.yaml` — System Prompt 骨架

```yaml
web_test_agent:
  system_prompt: |
    你是一个资深严谨的 Web 自动化测试机器人。理解测试目标，决定下一步页面操作。
    只返回严格 JSON，不要包含任何其他文字或 Markdown 标记：
    {
      "thought": "为什么做这个动作",
      "action": "fill" | "click" | "finish",
      "target": "输入框的 placeholder 或按钮的可见文字",
      "value": "fill 时要输入的内容，否则为空字符串",
      "status": "仅 finish 时填写：passed 或 failed"
    }
    【判定结束规则】
    1. 执行 click 后，必须在下一步重新观察页面元素再判定。
    2. 出现 <成功标志词，如 inventory/Products> → finish, passed。
    3. 出现 <失败标志词，如 Error/not match> → 按下方核心规则判定。
    【元素定位规则】
    1. 输入框优先返回 placeholder；按钮优先返回可见文字；禁止返回源码 id。
    【执行原则】
    1. 点击提交前检查历史动作，确保所有必填项已 fill 且不重复 fill。
    【核心判定规则 - 必须严格遵守】
    1. 目标为异常场景且出现预期报错 → passed。
    2. 目标为正常场景却出现报错 → failed。
```

### 3.3 `core/web_runner.py` — Playwright 执行器

```python
import os
from playwright.sync_api import sync_playwright

class WebRunner:
    """一条用例一个实例：独立 Context、独立录屏、用完即 close()。"""

    def __init__(self, headless=True, record_video=False, video_dir="videos"):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=headless, args=["--ignore-certificate-errors"])
        self.record_video = record_video
        if record_video:
            os.makedirs(video_dir, exist_ok=True)
            self.context = self.browser.new_context(
                record_video_dir=video_dir,
                record_video_size={"width": 1280, "height": 720})
        else:
            self.context = self.browser.new_context()
        self.page = self.context.new_page()

    # ---------- 导航 ----------
    def goto(self, url, max_retries=3):
        for attempt in range(max_retries):
            try:
                self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    raise RuntimeError(f"访问 {url} 失败，已重试 {max_retries} 次: {e}")
                self.page.wait_for_timeout(2000)

    # ---------- 感知 ----------
    def get_page_elements(self) -> str:
        """只提取结构化字段喂给模型；错误提示单独提出来作为判定信号。"""
        data = self.page.evaluate("""() => {
            const els = document.querySelectorAll('input, button, a');
            const elements = Array.from(els).map(el => ({
                tag: el.tagName.toLowerCase(), type: el.type || '',
                placeholder: el.placeholder || '', text: el.innerText || '', id: el.id || ''
            })).filter(e => e.placeholder || e.text || e.id);
            const err = document.querySelector('<错误提示选择器, 如 h3[data-test="error"]>');
            return { elements, pageMessage: err ? err.innerText : '' };
        }""")
        return str(data)

    # ---------- 执行 ----------
    def execute_action(self, decision: dict):
        action, target, value = decision.get("action"), decision.get("target"), decision.get("value")
        try:
            if action == "fill":
                loc = self.page.get_by_placeholder(target, exact=False)
                if loc.count() == 0:
                    loc = self.page.get_by_label(target, exact=False)
                box = loc.first
                box.click(); box.fill(""); box.fill(value)
                self.page.wait_for_timeout(500)
                if box.input_value() != value:              # 自检 + 键盘兜底
                    box.press_sequentially(value, delay=50)
                    self.page.wait_for_timeout(500)
            elif action == "click":
                self.page.get_by_text(target, exact=False) \
                    .or_(self.page.locator(f"[id='{target}']")) \
                    .or_(self.page.locator(f"[name='{target}']")) \
                    .first.click(timeout=5000)
            # 新动作在此追加分支，并同步更新 prompt_config.yaml
            self.page.wait_for_timeout(1000)
            return True, "执行成功"
        except Exception as e:
            return False, str(e)

    # ---------- 审计 ----------
    def take_screenshot(self, path):
        self.page.screenshot(path=path)
        return path

    def get_video_path(self):
        """必须在 close() 之前调用。"""
        if self.record_video and self.page.video:
            return self.page.video.path()
        return None

    def close(self):
        """顺序不可变：page → context → browser → playwright。视频在 context.close() 后落盘。"""
        for obj in (self.page, self.context, self.browser):
            if obj:
                obj.close()
        if self.playwright:
            self.playwright.stop()
```

### 3.4 `app.py` — 单条用例执行骨架（视图层编排）

```python
runner = WebRunner(headless=True, record_video=True, video_dir=current_video_dir)
runner.goto(target_url)
logs, result, history, final_video = "", "失败", [], None
fail_png = f"screenshots/{case_id}_fail.png"
try:
    for step in range(5):
        decision = get_ai_action(runner.get_page_elements(), ai_prompt, history)
        logs += f"[Step {step+1}] 💡 {decision['thought']}\n"
        if decision["action"] == "finish":
            if decision.get("status") == "passed": result = "通过"
            else: runner.take_screenshot(fail_png)
            break
        ok, msg = runner.execute_action(decision)
        logs += f"⚙️ {decision['action']} -> {decision['target']}\n"
        if not ok:
            logs += f"❌ {msg}\n"; runner.take_screenshot(fail_png); break
        history.append(f"执行了 {decision['action']}")
except Exception as e:
    logs += f"❌ 系统异常: {e}\n"; runner.take_screenshot(fail_png)
finally:
    raw = runner.get_video_path()           # 先取路径
    runner.close()                          # 再关闭
    if raw and os.path.exists(raw):
        suffix = "pass" if result == "通过" else "fail"
        final_video = os.path.join(current_video_dir,
            f"{case_id}_{suffix}_{datetime.datetime.now():%H%M%S}.webm")
        os.rename(raw, final_video)         # 最后重命名，带时分秒不覆盖
```

---

## 四、交付检查清单

搭建完成后逐项确认：

- [ ] `app.py` 中不出现 `playwright` / `openai` 的直接导入
- [ ] LLM 调用使用 `json_object` + 低温度，异常兜底返回 `finish/failed`
- [ ] System Prompt 外置 YAML，含四组硬规则（结束 / 异常语义 / 定位 / 执行原则）
- [ ] `fill` 后有 `input_value()` 自检与 `press_sequentially` 兜底
- [ ] `get_video_path()` 在 `close()` 之前调用，视频命名含 `HHMMSS`
- [ ] 每批次独立 `videos/<时间戳>/` 目录
- [ ] Excel 列名模糊匹配，空指令行过滤，支持 UI 上传
- [ ] 停止按钮仅置位 `stop_requested`，循环在用例边界检查
- [ ] 失败重跑按 `case_id` 原位替换
- [ ] 密钥全部走 `.env` + `config_loader`，`.gitignore` 含 `.env / videos/ / venv/`
