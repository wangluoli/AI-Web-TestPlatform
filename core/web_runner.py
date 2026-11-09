import os
from playwright.sync_api import sync_playwright


class WebRunner:
    def __init__(self, headless=False, record_video=False, video_dir="videos"):
        self.playwright = sync_playwright().start()
        # 忽略证书错误，防止私密系统报错
        self.browser = self.playwright.chromium.launch(headless=headless, args=['--ignore-certificate-errors'])
        self.record_video = record_video

        # 核心修复：无论是否录屏，都统一创建 context
        if record_video:
            if not os.path.exists(video_dir):
                os.makedirs(video_dir)
            self.context = self.browser.new_context(
                record_video_dir=video_dir,
                record_video_size={"width": 1280, "height": 720}
            )
        else:
            self.context = self.browser.new_context()

        self.page = self.context.new_page()

    def goto(self, url, max_retries=3):
        """访问 URL，增加重试机制应对网络抖动"""
        for attempt in range(max_retries):
            try:
                self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    raise Exception(f"访问 {url} 失败，已重试 {max_retries} 次。最后错误: {e}")
                print(f"⚠️ 访问 {url} 失败，正在重试第 {attempt + 1} 次...")
                # 优化：等待一下，然后尝试刷新页面重试
                self.page.wait_for_timeout(2000)

    def get_page_elements(self):
        """提取当前页面上所有可交互的元素以及提示文本，给 AI 看"""
        elements = self.page.evaluate('''() => {
            const els = document.querySelectorAll('input, button, a');
            const elementsData = Array.from(els).map(el => ({
                tag: el.tagName.toLowerCase(),
                type: el.type || '',
                placeholder: el.placeholder || '',
                text: el.innerText || '',
                id: el.id || ''
            })).filter(e => e.placeholder || e.text || e.id);

            const h3Text = document.querySelector('h3[data-test="error"]') ? document.querySelector('h3[data-test="error"]').innerText : '';

            return {
                elements: elementsData,
                pageMessage: h3Text
            };
        }''')
        return str(elements)

    def execute_action(self, action_data):
        action = action_data.get("action")
        target = action_data.get("target")
        value = action_data.get("value")

        try:
            if action == "fill":
                # 1. 定位输入框（兼容 placeholder 和 label）
                locator = self.page.get_by_placeholder(target, exact=False)
                if locator.count() == 0:
                    locator = self.page.get_by_label(target, exact=False)

                target_input = locator.first

                # 2. 模拟真实用户：先点击，再清空，再输入
                target_input.click()
                target_input.fill("")  # 强制清空
                target_input.fill(value)

                # 3. 核心自检逻辑（专治幻觉）
                self.page.wait_for_timeout(500)  # 给前端框架一点反应时间
                actual_value = target_input.input_value()

                if actual_value != value:
                    # 如果发现没填进去，强制用键盘输入方式再试一次
                    print(f"⚠️ 发现元素 {target} 填充失败，正在强制重试...")
                    target_input.press_sequentially(value, delay=50)  # 模拟人打字，每字延迟50ms
                    self.page.wait_for_timeout(500)

            elif action == "click":
                # 点击逻辑保持不变
                locator = self.page.get_by_text(target, exact=False).or_(
                    self.page.locator(f"[id='{target}']")).or_(
                    self.page.locator(f"[name='{target}']")).first
                locator.click(timeout=5000)

            self.page.wait_for_timeout(1000)
            return True, "执行成功"
        except Exception as e:
            return False, str(e)

    def take_screenshot(self, path="screenshot.png"):
        self.page.screenshot(path=path)
        return path

    def get_video_path(self):
        """获取录屏文件的路径（必须在 close 之前调用）"""
        if self.record_video and self.page.video:
            return self.page.video.path()
        return None

    def close(self):
        """统一的关闭方法，确保视频能正常保存落盘"""
        # 如果有录屏，必须等 page 和 context 都 close 后，视频文件才会真正生成
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()