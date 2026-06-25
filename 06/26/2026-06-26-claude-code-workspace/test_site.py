import asyncio
import json
import os
import base64

os.environ["no_proxy"] = "localhost,127.0.0.1"
os.environ["NO_PROXY"] = "localhost,127.0.0.1"
import websockets

TARGET_URL = "https://caicai.caicaitask.click/"
PAGE_WS = "ws://localhost:9222/devtools/page/1712627D72A468C009C53E1F9AFCDCE3"

async def cmd(ws, method, params=None):
    msg_id = getattr(cmd, "_id", 1)
    cmd._id = msg_id + 1
    payload = {"id": msg_id, "method": method}
    if params:
        payload["params"] = params
    await ws.send(json.dumps(payload))

async def recv_all(ws, timeout=3):
    results = []
    try:
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            results.append(json.loads(raw))
    except asyncio.TimeoutError:
        pass
    return results

async def test_site():
    print(f"=== 测试: {TARGET_URL} ===\n")

    async with websockets.connect(PAGE_WS, max_size=20*1024*1024) as ws:
        # Enable domains
        print("[1] 启用监听...")
        await cmd(ws, "Runtime.enable")
        await cmd(ws, "Network.enable")
        await cmd(ws, "Log.enable")
        await cmd(ws, "Page.enable")
        await cmd(ws, "DOM.enable")
        await asyncio.sleep(1)

        # Reload to capture all network activity
        print("[2] 重新加载以捕获完整网络活动...")
        await cmd(ws, "Page.reload")
        await asyncio.sleep(6)  # Wait for full load

        events = await recv_all(ws, timeout=3)

        # Analyze
        console_errors = []
        network_errors = []
        log_entries = []
        loaded_urls = []
        js_exceptions = []

        for evt in events:
            method = evt.get("method", "")
            params = evt.get("params", {})

            if method == "Log.entryAdded":
                entry = params.get("entry", {})
                text = entry.get("text", "")[:400]
                level = entry.get("level", "")
                log_entries.append(f"[LOG/{level}] {text}")

            elif method == "Network.responseReceived":
                resp = params.get("response", {})
                status = resp.get("status", 0)
                url = resp.get("url", "")
                mime = resp.get("mimeType", "")
                loaded_urls.append((status, mime, url))
                if status >= 400:
                    network_errors.append(f"HTTP {status}: {url[:200]} ({mime})")

            elif method == "Network.loadingFailed":
                network_errors.append(
                    f"加载失败: {params.get('url','')[:200]} - {params.get('errorText','')}"
                )

            elif method == "Runtime.consoleAPICalled":
                msg_type = params.get("type", "")
                args = params.get("args", [])
                parts = []
                for a in args:
                    v = a.get("value")
                    if v is not None:
                        parts.append(str(v))
                    elif a.get("description"):
                        parts.append(str(a["description"])[:200])
                text = " ".join(parts)[:400]
                if msg_type in ("error", "warning"):
                    console_errors.append(f"[{msg_type}] {text}")
                log_entries.append(f"[CONSOLE/{msg_type}] {text}")

            elif method == "Runtime.exceptionThrown":
                exc = params.get("exceptionDetails", {})
                text = exc.get("text", "")[:400]
                url = exc.get("url", "")
                line = exc.get("lineNumber", 0)
                js_exceptions.append(f"{text} @ {url}:{line}")

        # --- Evaluate page ---
        print("[3] 提取页面数据...")
        await cmd(ws, "Runtime.evaluate", {
            "expression": "document.title", "returnByValue": True
        })
        await cmd(ws, "Runtime.evaluate", {
            "expression": """
            JSON.stringify({
                url: location.href,
                readyState: document.readyState,
                links: document.querySelectorAll('a').length,
                images: document.querySelectorAll('img').length,
                buttons: document.querySelectorAll('button').length,
                inputs: document.querySelectorAll('input').length,
                forms: document.querySelectorAll('form').length,
                scripts: document.querySelectorAll('script').length,
                brokenImgs: Array.from(document.querySelectorAll('img')).filter(i => !i.complete || i.naturalWidth === 0).length,
                bodyLen: document.body ? document.body.innerText.length : 0,
                vw: window.innerWidth,
                vh: window.innerHeight
            })
            """,
            "returnByValue": True
        })
        # Check for specific issues
        await cmd(ws, "Runtime.evaluate", {
            "expression": """
            (function() {
                var issues = [];
                // 1. Check overflow
                if (document.documentElement.scrollWidth > window.innerWidth) {
                    issues.push('横向溢出: scrollWidth=' + document.documentElement.scrollWidth + ' > vw=' + window.innerWidth);
                }
                // 2. Check for console errors from page
                // 3. Check for unstyled/empty elements
                var all = document.querySelectorAll('button, a, input, textarea, select');
                var noText = 0;
                all.forEach(function(el) {
                    var text = (el.textContent || el.value || '').trim();
                    var aria = el.getAttribute('aria-label') || '';
                    if (!text && !aria && el.tagName !== 'INPUT') noText++;
                });
                if (noText > 0) issues.push('无文本标签的交互元素: ' + noText + ' 个');
                // 4. Check img alt
                var imgs = document.querySelectorAll('img');
                var noAlt = 0;
                imgs.forEach(function(i) { if (!i.getAttribute('alt')) noAlt++; });
                if (noAlt > 0) issues.push('缺少alt属性的图片: ' + noAlt + ' 张');
                // 5. Check viewport meta
                var vp = document.querySelector('meta[name="viewport"]');
                if (!vp) issues.push('缺少viewport meta标签 (移动端适配)');
                // 6. Check heading hierarchy
                var h1s = document.querySelectorAll('h1');
                if (h1s.length === 0) issues.push('缺少h1标签 (SEO)');
                else if (h1s.length > 1) issues.push('多个h1标签: ' + h1s.length + ' 个 (SEO)');
                return JSON.stringify(issues);
            })()
            """,
            "returnByValue": True
        })
        # Get full page text
        await cmd(ws, "Runtime.evaluate", {
            "expression": "document.body ? document.body.innerText.substring(0, 8000) : 'NO_BODY'",
            "returnByValue": True
        })

        await asyncio.sleep(2)
        eval_results = await recv_all(ws, timeout=3)

        title = "N/A"
        body_text = "N/A"
        dom_stats = {}
        seo_issues = []

        for evt in eval_results:
            if "result" in evt:
                val = evt.get("result", {}).get("result", {}).get("value", "")
                if not val:
                    continue
                if isinstance(val, str):
                    if val.startswith("{") and "links" in val:
                        dom_stats = json.loads(val)
                    elif val.startswith("["):
                        seo_issues = json.loads(val)
                    elif title == "N/A" and len(val) < 300 and "http" not in val:
                        title = val
                    elif body_text == "N/A" and len(val) > 10:
                        body_text = val
                elif isinstance(val, list):
                    seo_issues = val

        # --- Screenshot ---
        print("[4] 截图...")
        await cmd(ws, "Page.captureScreenshot", {"format": "png", "fromSurface": True})
        await asyncio.sleep(2)
        ss_events = await recv_all(ws, timeout=3)

        for evt in ss_events:
            if "result" in evt and "data" in evt.get("result", {}):
                img_data = base64.b64decode(evt["result"]["data"])
                screenshot_path = r"e:\claude code files\site_screenshot.png"
                with open(screenshot_path, "wb") as f:
                    f.write(img_data)
                print(f"   已保存 ({len(img_data)} bytes)")

        # --- Test interactive elements ---
        print("[5] 测试交互元素...")
        # Find clickable elements
        await cmd(ws, "Runtime.evaluate", {
            "expression": """
            JSON.stringify(
                Array.from(document.querySelectorAll('a[href], button, input[type="submit"], [onclick]')).slice(0, 30).map(function(el) {
                    return {
                        tag: el.tagName,
                        text: (el.textContent || '').trim().substring(0, 80),
                        href: el.getAttribute('href') || '',
                        type: el.getAttribute('type') || '',
                        id: el.id || '',
                        className: (el.className || '').toString().substring(0, 60)
                    };
                })
            )
            """,
            "returnByValue": True
        })
        await asyncio.sleep(1)
        int_results = await recv_all(ws, timeout=2)

        interactive_elements = []
        for evt in int_results:
            if "result" in evt:
                val = evt.get("result", {}).get("result", {}).get("value", "")
                if val and isinstance(val, str) and val.startswith("["):
                    try:
                        interactive_elements = json.loads(val)
                    except:
                        pass

        # --- Test console errors via window.onerror ---
        print("[6] 注入错误监听...")
        await cmd(ws, "Runtime.evaluate", {
            "expression": """
            window.__caught_errors = [];
            var _onerror = window.onerror;
            window.onerror = function(msg, url, line, col, err) {
                window.__caught_errors.push({msg: String(msg), url: String(url), line: line, col: col});
                if (_onerror) _onerror.apply(this, arguments);
            };
            window.addEventListener('error', function(e) {
                if (e.target !== window) {
                    window.__caught_errors.push({msg: 'Resource error: ' + (e.target.src || e.target.href || 'unknown'), tag: e.target.tagName});
                }
            }, true);
            'listener_installed'
            """,
            "returnByValue": True
        })

        # Click a few things to trigger potential errors
        await asyncio.sleep(0.5)
        # Try to click first button/link
        await cmd(ws, "Runtime.evaluate", {
            "expression": """
            (function() {
                var clicked = [];
                var btns = document.querySelectorAll('button:not([disabled]), a[href]:not([href="#"]), [role="button"]');
                for (var i = 0; i < Math.min(btns.length, 5); i++) {
                    try {
                        var el = btns[i];
                        clicked.push({tag: el.tagName, text: (el.textContent||'').trim().substring(0,50), id: el.id});
                        el.click();
                    } catch(e) {}
                }
                return JSON.stringify(clicked);
            })()
            """,
            "returnByValue": True
        })
        await asyncio.sleep(2)
        # Check caught errors
        await cmd(ws, "Runtime.evaluate", {
            "expression": "JSON.stringify(window.__caught_errors || [])",
            "returnByValue": True
        })
        click_results = await recv_all(ws, timeout=3)

        runtime_errors = []
        clicked_elements = []
        for evt in click_results:
            if "result" in evt:
                val = evt.get("result", {}).get("result", {}).get("value", "")
                if val and isinstance(val, str):
                    try:
                        data = json.loads(val)
                        if isinstance(data, list) and len(data) > 0:
                            item = data[0]
                            if "msg" in item:
                                runtime_errors = data
                            elif "tag" in item:
                                clicked_elements = data
                    except:
                        pass

        # --- REPORT ---
        print(f"\n{'='*60}")
        print(f"=== 📊 网站测试报告 ===")
        print(f"网站: {TARGET_URL}")
        print(f"标题: {title}")
        print(f"URL: {dom_stats.get('url', 'N/A')}")
        print(f"状态: {dom_stats.get('readyState', 'N/A')}")
        print(f"视口: {dom_stats.get('vw', '?')} x {dom_stats.get('vh', '?')}")

        print(f"\n--- DOM 统计 ---")
        for k, v in dom_stats.items():
            print(f"  {k}: {v}")

        print(f"\n--- 交互元素 (前 30 个) ---")
        if interactive_elements:
            for el in interactive_elements[:20]:
                print(f"  <{el['tag']}> \"{el['text'][:60]}\" href={el['href'][:80]}")
        else:
            print("  无")

        print(f"\n--- 点击测试 ---")
        if clicked_elements:
            print(f"  点击了 {len(clicked_elements)} 个元素:")
            for el in clicked_elements:
                print(f"    <{el['tag']}> \"{el['text']}\"")
        else:
            print("  未找到可点击元素")

        print(f"\n--- 运行时错误 ({len(runtime_errors)} 个) ---")
        if runtime_errors:
            for e in runtime_errors:
                print(f"  ❌ {json.dumps(e, ensure_ascii=False)[:300]}")
        else:
            print("  无")

        print(f"\n--- JS 异常 ({len(js_exceptions)} 个) ---")
        for e in js_exceptions:
            print(f"  ❌ {e[:400]}")

        print(f"\n--- 控制台错误/警告 ({len(console_errors)} 个) ---")
        for e in console_errors:
            print(f"  {'❌' if '[error]' in e else '⚠️'} {e[:400]}")

        print(f"\n--- 网络错误 ({len(network_errors)} 个) ---")
        for e in network_errors:
            print(f"  ❌ {e[:400]}")

        print(f"\n--- 加载的资源 ({len(loaded_urls)} 个) ---")
        for status, mime, url in loaded_urls:
            flag = "✅" if status < 300 else ("⚠️" if status < 400 else "❌")
            print(f"  [{status}] {flag} {mime[:30]:30s} {url[:150]}")

        print(f"\n--- SEO / A11y 问题 ---")
        if seo_issues:
            for i in seo_issues:
                print(f"  ⚠️ {i}")
        else:
            print("  无")

        print(f"\n--- 所有日志 (最近 30 条) ---")
        for entry in log_entries[-30:]:
            print(f"  {entry[:300]}")

        print(f"\n--- 页面文本 (前 5000 字符) ---")
        print((body_text or "无法获取")[:5000])

        # --- BUG REPORT ---
        print(f"\n{'='*60}")
        print(f"=== 🐛 BUG 汇总 ===")
        bugs = []

        if not title or title == "N/A":
            bugs.append("❌ 页面缺少 <title> 标签")
        else:
            print(f"  ✅ 标题: {title}")

        if dom_stats.get('bodyLen', 0) == 0:
            bugs.append("❌ 页面内容为空 (body 无文本)")
        else:
            print(f"  ✅ 页面文本: {dom_stats['bodyLen']} 字符")

        if js_exceptions:
            bugs.append(f"❌ JS 运行时异常: {len(js_exceptions)} 个")
        else:
            print(f"  ✅ JS 异常: 0")

        if console_errors:
            bugs.append(f"❌ 控制台错误: {len(console_errors)} 个")
        else:
            print(f"  ✅ 控制台错误: 0")

        if network_errors:
            bugs.append(f"❌ 网络请求失败: {len(network_errors)} 个")
        else:
            print(f"  ✅ 网络错误: 0")

        broken = dom_stats.get('brokenImgs', 0)
        if broken > 0:
            bugs.append(f"❌ 图片加载失败: {broken} 张")
        else:
            print(f"  ✅ 破损图片: 0")

        if runtime_errors:
            bugs.append(f"❌ 运行时/点击后错误: {len(runtime_errors)} 个")
        else:
            print(f"  ✅ 交互后错误: 0")

        if seo_issues:
            for i in seo_issues:
                bugs.append(f"⚠️ {i}")

        if dom_stats.get('links', 0) == 0 and dom_stats.get('buttons', 0) == 0:
            bugs.append("💡 无可交互元素 (链接/按钮)")

        if not bugs:
            print("  🎉 未发现重大问题!")

        print()
        for b in bugs:
            print(f"  {b}")

        return bugs

if __name__ == "__main__":
    asyncio.run(test_site())
