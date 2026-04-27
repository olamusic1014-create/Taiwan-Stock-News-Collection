import streamlit as st
import asyncio
from playwright.async_api import async_playwright
import requests
import time
import random
import sys
import xml.etree.ElementTree as ET
import os
import re
import json
import email.utils

from browser_support import detect_browser_status, get_launch_kwargs
from market_data import merge_market_scan_data
from news_relevance import build_google_rss_url, is_relevant_news_text
from time_window import DEFAULT_DAY_RANGE, clamp_day_range, is_within_recent_days
from ui_helpers import build_report_markup, build_source_sections
from ui_config import get_mobile_search_panel_config, resolve_active_api_key

# ===========================
# 0. 環境準備
# ===========================
BROWSER_STATUS = detect_browser_status()

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# ===========================
# 🔐 資安核心
# ===========================
SYSTEM_API_KEY = st.secrets.get("GEMINI_API_KEY", None)


def browser_runtime_warning(action_name):
    return (
        f"瀏覽器執行環境不可用，{action_name} 會跳過。"
        f" {BROWSER_STATUS.message}"
    )


async def launch_browser(playwright_instance):
    return await playwright_instance.chromium.launch(**get_launch_kwargs(BROWSER_STATUS))

# ===========================
# 1. 股票資料庫
# ===========================
BASE_STOCKS = {
    "台積電": "2330", "聯電": "2303", "鴻海": "2317", "聯發科": "2454", "長榮": "2603",
    "陽明": "2609", "萬海": "2615", "中鋼": "2002", "中鴻": "2014", "台塑": "1301",
    "南亞": "1303", "台化": "1326", "台塑化": "6505", "國泰金": "2882", "富邦金": "2881",
    "中信金": "2891", "玉山金": "2884", "元大金": "2885", "兆豐金": "2886", "台泥": "1101",
    "緯創": "3231", "廣達": "2382", "英業達": "2356", "仁寶": "2324", "和碩": "4938",
    "技嘉": "2376", "微星": "2377", "華碩": "2357", "宏碁": "2353", "光寶科": "2301",
    "群創": "3481", "友達": "2409", "彩晶": "6116", "聯詠": "3034", "瑞昱": "2379",
    "台達電": "2308", "日月光": "3711", "力積電": "6770", "世界": "5347", "元太": "8069",
    "智原": "3035", "創意": "3443", "世芯": "3661", "愛普": "6531", "祥碩": "5269",
    "長榮航": "2618", "華航": "2610", "高鐵": "2633", "裕隆": "2201", "和泰車": "2207",
    "統一超": "2912", "全家": "5903", "中華電": "2412", "台灣大": "3045", "遠傳": "4904",
    "開發金": "2883", "新光金": "2888", "永豐金": "2890", "台新金": "2887", "合庫金": "5880",
    "第一金": "2892", "華南金": "2880", "彰銀": "2801", "臺企銀": "2834", "上海商銀": "5876",
    "元大台灣50": "0050", "元大高股息": "0056", "國泰永續高股息": "00878", "復華台灣科技優息": "00929",
    "群益台灣精選高息": "00919", "元大美債20年": "00679B", "統一台灣高息動能": "00939", "元大台灣價值高息": "00940",
    "力積電": "6770"
}

# ===========================
# 2. 爬蟲模組 (維持 V15.6 的精兵策略)
# ===========================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
]
def get_ua(): return random.choice(USER_AGENTS)

async def sync_market_data():
    full_stock_dict = BASE_STOCKS.copy()
    try:
        api_url = "https://scanner.tradingview.com/taiwan/scan"
        payload = {
            "columns": ["name", "description", "volume"],
            "ignore_unknown_fields": False,
            "options": {"lang": "zh_TW"},
            "range": [0, 5000],
            "sort": {"sortBy": "volume", "sortOrder": "desc"},
            "symbols": {"query": {"types": []}, "tickers": []},
            "filter": [{"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}]
        }
        resp = await asyncio.to_thread(
            requests.post,
            api_url,
            json=payload,
            timeout=5,
            headers={"User-Agent": get_ua()},
        )
        if resp.status_code == 200:
            full_stock_dict = merge_market_scan_data(full_stock_dict, resp.json())
    except Exception:
        pass
    return full_stock_dict, len(full_stock_dict)

async def resolve_stock_info(user_input, stock_dict):
    clean_input = user_input.strip().upper()
    for name, code in stock_dict.items():
        if clean_input == name or clean_input == code: return code, name
    for name, code in stock_dict.items():
        if clean_input in name: return code, name

    if not BROWSER_STATUS.available:
        return None, None

    async with async_playwright() as p:
        browser = await launch_browser(p)
        try:
            page = await browser.new_page(user_agent=get_ua())
            encoded = requests.utils.quote(clean_input)
            await page.goto(f"https://tw.stock.yahoo.com/search?p={encoded}", timeout=8000)
            link = page.locator("a[href*='/quote/']").first
            if await link.count() > 0:
                text = await link.inner_text()
                href = await link.get_attribute("href")
                match = re.search(r"(\d{4,6})", href)
                if match:
                    code = match.group(1)
                    name = text.split("\n")[0].strip()
                    if name == code or not name: name = clean_input
                    return code, name
        except: pass
        finally: await browser.close()
    return None, None

async def fetch_google_rss(stock_code, stock_name, site_domain, source_name, day_range):
    try:
        rss_url = build_google_rss_url(stock_code, stock_name, site_domain)
        response = await asyncio.to_thread(
            requests.get,
            rss_url,
            timeout=10,
            headers={"User-Agent": get_ua()},
        )
        if response.status_code != 200:
            return []

        root = ET.fromstring(response.text)
        data = []

        for item in root.findall('.//item'):
            title = item.find('title').text if item.find('title') is not None else ""
            link = item.find('link').text if item.find('link') is not None else None
            pub_date_str = item.find('pubDate').text if item.find('pubDate') is not None else None

            is_fresh = True
            if pub_date_str:
                try:
                    pub_date = email.utils.parsedate_to_datetime(pub_date_str)
                    if not is_within_recent_days(pub_date, day_range):
                        is_fresh = False
                except Exception:
                    pass

            if not is_fresh:
                continue

            desc_html = item.find('description').text if item.find('description') is not None else ""
            desc_clean = re.sub(r'<[^>]+>', '', desc_html)
            clean_title = title.split(" - ")[0].strip()
            combined_text = f"{clean_title} {desc_clean}".strip()

            if len(clean_title) > 4 and is_relevant_news_text(combined_text, stock_code, stock_name):
                data.append({
                    "title": clean_title,
                    "snippet": desc_clean[:200],
                    "source": source_name,
                    "link": link
                })

        return data[:3]
    except Exception:
        return []


async def scrape_anue(stock_code, stock_name, day_range):
    try:
        current_time = int(time.time())
        url = f"https://ess.api.cnyes.com/ess/api/v1/news/keyword?q={requests.utils.quote(stock_name)}&limit=10&page=1"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.cnyes.com/"
        }
        response = await asyncio.to_thread(requests.get, url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('data', {}).get('items', [])
            result = []
            
            earliest_allowed_ts = current_time - (clamp_day_range(day_range) * 86400)
            
            for item in items:
                publish_at = item.get('publishAt', 0)
                if publish_at < earliest_allowed_ts:
                    continue
                
                title = item.get('title', '')
                summary = item.get('summary')
                if summary is None: summary = ""
                
                news_id = item.get('newsId')
                link = f"https://news.cnyes.com/news/id/{news_id}" if news_id else None
                combined_text = f"{title} {summary}".strip()
                
                if title and is_relevant_news_text(combined_text, stock_code, stock_name):
                    result.append({
                        "title": title,
                        "snippet": summary,
                        "source": "鉅亨網",
                        "link": link
                    })
            
            return result[:3]
    except Exception:
        pass
    return []

async def scrape_yahoo(stock_code):
    if not BROWSER_STATUS.available:
        return []

    async with async_playwright() as p:
        browser = await launch_browser(p)
        context = await browser.new_context(user_agent=get_ua())
        page = await context.new_page()
        try:
            await page.goto(f"https://tw.stock.yahoo.com/quote/{stock_code}.TW/news", timeout=20000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
            
            data = []
            elements = await page.locator('#main-2-QuoteNews-Proxy a[href*="/news/"]').all()
            seen_titles = set()
            
            for el in elements[:3]: 
                try:
                    text = await el.inner_text()
                    href = await el.get_attribute("href")
                    
                    lines = text.split('\n')
                    title = max(lines, key=len) if lines else ""
                    
                    if len(title) > 5 and title not in seen_titles:
                        seen_titles.add(title)
                        data.append({
                            "title": title, 
                            "snippet": "Yahoo 焦點新聞 (最新)", 
                            "source": "Yahoo",
                            "link": href
                        })
                except: pass
                
            return data
        except: return []
        finally: await browser.close()

async def scrape_udn(c, n, d): return await fetch_google_rss(c, n, "money.udn.com", "經濟日報", d)
async def scrape_ltn(c, n, d): return await fetch_google_rss(c, n, "ec.ltn.com.tw", "自由財經", d)
async def scrape_ctee(c, n, d): return await fetch_google_rss(c, n, "ctee.com.tw", "工商時報", d)
async def scrape_chinatimes(c, n, d): return await fetch_google_rss(c, n, "chinatimes.com", "中時新聞", d)
async def scrape_ettoday(c, n, d): return await fetch_google_rss(c, n, "ettoday.net", "ETtoday", d)
async def scrape_tvbs(c, n, d): return await fetch_google_rss(c, n, "news.tvbs.com.tw", "TVBS新聞", d)
async def scrape_businesstoday(c, n, d): return await fetch_google_rss(c, n, "businesstoday.com.tw", "今周刊", d)
async def scrape_wealth(c, n, d): return await fetch_google_rss(c, n, "wealth.com.tw", "財訊", d)
async def scrape_storm(c, n, d): return await fetch_google_rss(c, n, "storm.mg", "風傳媒", d)

# ===========================
# 3. AI 評分核心 (完全依賴 AI)
# ===========================
def get_available_model(api_key):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            models = data.get('models', [])
            priority_list = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-1.0-pro', 'models/gemini-pro']
            
            for p_model in priority_list:
                for m in models:
                    if m['name'] == p_model and 'generateContent' in m['supportedGenerationMethods']:
                        return m['name']
            
            for m in models:
                if 'generateContent' in m['supportedGenerationMethods']:
                    return m['name']
    except Exception:
        pass
    return None

def analyze_with_gemini_requests(api_key, stock_name, news_data, day_range):
    model_name = get_available_model(api_key)
    if not model_name: model_name = "models/gemini-pro"
        
    news_text = ""
    for i, news in enumerate(news_data):
        safe_snippet = news.get('snippet', '')
        if safe_snippet is None: safe_snippet = ""
        news_text += f"{i+1}. [{news['source']}] {news['title']}\n   摘要: {safe_snippet}\n"

    # 🚀 AI 裁判提示詞 (強制要求 AI 打分)
    prompt = f"""
    你現在是一位權威的華爾街資深分析師。請仔細閱讀以下關於「{stock_name}」的最新新聞內容（包含標題與摘要）。

    任務：
    請不要依賴簡單的關鍵字，而是要「理解」新聞的語氣、具體數據（如營收、EPS、訂單量）以及市場預期，來給出一個綜合情緒分數。

    新聞列表 (只包含最近 {clamp_day_range(day_range)} 天的重點新聞)：
    {news_text}

    請輸出嚴格符合以下格式的報告 (請用繁體中文)：
    請純粹基於語氣、具體數據和市場預期進行質性分析，並輸出嚴格符合以下格式的報告 (請用繁體中文)：
    1. **LEVEL**: (例如：偏多、觀望、主力出貨、利多出盡)。
    2. **SUMMARY**: 請綜合分析這些新聞的核心影響。
    3. **ANALYSIS**: 詳細列出你看多的理由與看空的理由。

    範例輸出：
    LEVEL: 樂觀偏多
    SUMMARY: ...
    ANALYSIS: ...
    """

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={api_key}"
        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                content = result['candidates'][0]['content']['parts'][0]['text']
                return None, content, model_name
        else:
            return None, f"Error {response.status_code}: {response.text}", model_name

    except Exception as e:
        return None, str(e), model_name



async def run_analysis(stock_code, stock_name, day_range):
    safe_day_range = clamp_day_range(day_range)
    return await asyncio.gather(
        scrape_anue(stock_code, stock_name, safe_day_range), scrape_yahoo(stock_code), scrape_udn(stock_code, stock_name, safe_day_range),
        scrape_ltn(stock_code, stock_name, safe_day_range), scrape_ctee(stock_code, stock_name, safe_day_range), scrape_chinatimes(stock_code, stock_name, safe_day_range),
        scrape_ettoday(stock_code, stock_name, safe_day_range), scrape_tvbs(stock_code, stock_name, safe_day_range), scrape_businesstoday(stock_code, stock_name, safe_day_range),
        scrape_wealth(stock_code, stock_name, safe_day_range), scrape_storm(stock_code, stock_name, safe_day_range)
    )

# ===========================
# 3b. 今日股市焦點模組（共用個股爬蟲架構）
# ===========================

async def scrape_anue_market() -> list:
    """鉅亨網台股分類新聞 API（市場焦點專用，不需關鍵字）"""
    try:
        url = "https://ess.api.cnyes.com/ess/api/v1/news/category/tw_stock?limit=20&page=1"
        headers = {"User-Agent": get_ua(), "Referer": "https://www.cnyes.com/"}
        resp = await asyncio.to_thread(requests.get, url, headers=headers, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('data', {}).get('items', [])
            cutoff = int(time.time()) - 86400  # 最近 24 小時
            result = []
            for item in items:
                if item.get('publishAt', 0) < cutoff:
                    continue
                title = item.get('title', '').strip()
                summary = item.get('summary') or ''
                news_id = item.get('newsId')
                link = f"https://news.cnyes.com/news/id/{news_id}" if news_id else None
                if title:
                    result.append({
                        'title': title,
                        'snippet': summary[:150],
                        'source': '鉅亨網',
                        'link': link
                    })
            return result[:5]
    except Exception:
        pass
    return []


async def fetch_google_rss_market(site_domain: str, source_name: str) -> list:
    """共用 RSS 爬蟲：與個股分析同一套架構，關鍵字改為「台股 股市」（不過濾個股）"""
    try:
        query = requests.utils.quote(f'"台股" OR "股市" site:{site_domain}')
        rss_url = f"https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        response = await asyncio.to_thread(
            requests.get, rss_url, timeout=10, headers={"User-Agent": get_ua()}
        )
        if response.status_code != 200:
            return []
        root = ET.fromstring(response.text)
        data = []
        cutoff_ts = int(time.time()) - 86400  # 最近 24 小時
        for item in root.findall('.//item'):
            title_el = item.find('title')
            link_el = item.find('link')
            pub_el = item.find('pubDate')
            title = title_el.text.split(' - ')[0].strip() if title_el is not None and title_el.text else ''
            link = link_el.text if link_el is not None else None
            # 時效過濾
            is_fresh = True
            if pub_el is not None and pub_el.text:
                try:
                    pub_dt = email.utils.parsedate_to_datetime(pub_el.text)
                    if not is_within_recent_days(pub_dt, 1):
                        is_fresh = False
                except Exception:
                    pass
            if not is_fresh or len(title) <= 5:
                continue
            desc_el = item.find('description')
            snippet = re.sub(r'<[^>]+>', '', desc_el.text or '') if desc_el is not None else ''
            data.append({
                'title': title,
                'snippet': snippet[:150],
                'source': source_name,
                'link': link
            })
        return data[:3]
    except Exception:
        return []


async def fetch_market_headlines_today() -> list:
    """抓取當日台股市場頭條新聞。
    
    共用個股分析的相同媒體來源（共 10 路），
    以 asyncio.gather 全部並行，比序列快 3-5 倍。
    """
    # 10 路並行：鉅亨網分類 API + 9 家 Google News RSS（與個股分析同一批媒體）
    results = await asyncio.gather(
        scrape_anue_market(),
        fetch_google_rss_market("money.udn.com",         "經濟日報"),
        fetch_google_rss_market("ec.ltn.com.tw",         "自由財經"),
        fetch_google_rss_market("ctee.com.tw",           "工商時報"),
        fetch_google_rss_market("chinatimes.com",        "中時新聞"),
        fetch_google_rss_market("ettoday.net",           "ETtoday"),
        fetch_google_rss_market("news.tvbs.com.tw",      "TVBS新聞"),
        fetch_google_rss_market("businesstoday.com.tw",  "今周刊"),
        fetch_google_rss_market("wealth.com.tw",         "財訊"),
        fetch_google_rss_market("storm.mg",              "風傳媒"),
    )

    # 合併所有結果並去重（依標題前 30 字）
    headlines = [h for batch in results for h in batch]
    seen, unique = set(), []
    for h in headlines:
        key = h['title'][:30]
        if key not in seen:
            seen.add(key)
            unique.append(h)

    return unique[:30]  # 最多 30 則給 AI


def summarize_market_with_gemini(api_key: str, headlines: list) -> str:
    """呼叫 Gemini AI 總結今日台股市場焦點"""
    model_name = get_available_model(api_key)
    if not model_name:
        model_name = "models/gemini-pro"

    news_text = ""
    for i, h in enumerate(headlines, 1):
        snippet = h.get('snippet') or ''
        news_text += f"{i}. [{h['source']}] {h['title']}\n   摘要: {snippet}\n"

    today_str = time.strftime('%Y年%m月%d日', time.localtime())
    prompt = f"""
你是一位資深的台灣股市分析師。今天是 {today_str}。
以下是今日台灣股市的多來源頭條新聞（包含標題與摘要）：

{news_text}

請依據上述新聞，以繁體中文輸出一份「今日台股市場焦點摘要」，格式如下：

📊 **今日大盤氛圍**：（用 2-3 句描述今日整體市場多空氣氛）

🔥 **三大核心焦點**：
1. （焦點一：最重要的市場事件，含影響分析）
2. （焦點二：法人動態或資金流向）
3. （焦點三：產業/個股值得注意的訊號）

⚠️ **潛在風險提示**：（列出 1-2 個今日需注意的下行風險）

💡 **投資人關注重點**：（給散戶的一句話操作建議）

請保持客觀、不誇大，以數據和事實為主。
    """

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        resp = requests.post(url, headers={'Content-Type': 'application/json'}, json=payload, timeout=60)
        if resp.status_code == 200:
            result = resp.json()
            if 'candidates' in result and result['candidates']:
                return result['candidates'][0]['content']['parts'][0]['text']
        return f"AI 回應錯誤 ({resp.status_code})：{resp.text[:200]}"
    except Exception as e:
        return f"AI 請求失敗：{e}"


# ===========================
# 4. 背景分析引擎
# ===========================
import threading
from streamlit.runtime.scriptrunner import add_script_run_ctx

def background_task_runner(task_id):
    import asyncio
    task_data = st.session_state.tasks[task_id]
    
    async def _run():
        try:
            target_code = task_data['stock_code']
            target_name = task_data['stock_name']
            selected_day_range = task_data['day_range']
            
            task_data['progress'] = 10
            await asyncio.sleep(0.1)
            
            async def progress_updater():
                for p in range(11, 60, 2):
                    if task_data.get('progress', 0) >= 60: break
                    task_data['progress'] = p
                    await asyncio.sleep(1.0)
            
            updater_task = asyncio.create_task(progress_updater())
            results = await run_analysis(target_code, target_name, selected_day_range)
            updater_task.cancel()
            
            task_data['progress'] = 60
            
            all_news = []
            source_names = ["鉅亨網", "Yahoo", "經濟日報", "自由財經", "工商時報", "中時新聞", "ETtoday", "TVBS新聞", "今周刊", "財訊", "風傳媒"]
            data_map = {name: res for name, res in zip(source_names, results)}
            source_sections = build_source_sections(data_map)
            for name, data in data_map.items():
                all_news.extend(data)
            
            task_data['progress'] = 80
            
            ai_report = ""
            
            if SYSTEM_API_KEY and all_news:
                _, ai_report_text, used_model = analyze_with_gemini_requests(
                    resolve_active_api_key(SYSTEM_API_KEY), target_name, all_news, selected_day_range
                )
                if ai_report_text:
                    ai_report = ai_report_text
                else:
                    ai_report = "### AI 無法生成報告，僅提供新聞摘要"
            else:
                ai_report = "### 系統未配置 AI 金鑰，無法進行分析，僅提供新聞摘要"

            task_data['progress'] = 100
            task_data['result'] = {
                "all_news": all_news,
                "source_sections": source_sections,
                "ai_report": ai_report,
                "selected_day_range": selected_day_range
            }
            task_data['status'] = 'done'
        except Exception as e:
            task_data['status'] = 'error'
            task_data['error'] = str(e)
            
    asyncio.run(_run())

# ===========================
# 5. Streamlit 介面 (V15.7)
# ===========================
st.set_page_config(page_title="V15.7 AI 投資顧問 (AI裁判版)", page_icon="🛡️", layout="wide")
st.markdown(
    """<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');

    /* UI Pro Max: Financial Dashboard Palette & Premium Sans */
    :root {
        --bg-color: #020617;
        --surface-color: #0F172A;
        --surface-border: #1E293B;
        --cta-color: #22C55E;
        --cta-hover: #16a34a;
        --text-main: #F8FAFC;
        --text-muted: #94A3B8;
        --accent-blue: #3B82F6;
    }

    /* Apply font-family safely */
    .stApp {
        font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
    }
    
    /* Ensure Material Symbols are preserved */
    .material-symbols-rounded, .stIcon, [data-testid="stIconMaterial"], [class*="icon"] {
        font-family: "Material Symbols Rounded" !important;
    }

    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { 
        background: var(--bg-color); 
        color: var(--text-main); 
    }
    .block-container { 
        max-width: 720px; 
        padding-top: 1.5rem; 
        padding-bottom: 3rem; 
    }
    [data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none; }
    
    .news-row { 
        margin-bottom: 12px; 
        padding: 16px; 
        border-radius: 16px;
        background: var(--surface-color);
        border: 1px solid var(--surface-border); 
        font-size: 14px; 
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .news-row:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        border-color: #334155;
    }

    .stock-check { 
        background-color: var(--surface-color); 
        padding: 16px; 
        border-radius: 16px; 
        border: 1px solid var(--surface-border); 
        text-align: center; 
        margin: 14px 0 20px 0; 
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .stock-name-text { font-size: 26px; font-weight: 700; color: var(--cta-color); letter-spacing: -0.5px; }
    
    .mobile-hero { text-align: center; padding: 1rem 0 1.5rem 0; }
    .mobile-hero h1 { font-size: 2.2rem; margin-bottom: 0.5rem; font-weight: 700; letter-spacing: -1px; color: var(--text-main); }
    .mobile-hero p { color: var(--text-muted); margin-bottom: 0; font-size: 16px; }
    
    div[data-testid="stForm"] { 
        background: var(--surface-color); 
        border: 1px solid var(--surface-border); 
        border-radius: 16px; 
        padding: 1.25rem; 
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    div[data-testid="stForm"] input { 
        background: #020617; 
        color: var(--text-main); 
        border-radius: 16px; 
        border: 1px solid var(--surface-border);
        padding: 12px 16px;
    }
    div[data-testid="stForm"] input:focus {
        border-color: var(--accent-blue);
        box-shadow: 0 0 0 1px var(--accent-blue);
    }

    div[data-testid="stForm"] button { 
        border-radius: 16px; 
        min-height: 3rem; 
        font-weight: 700; 
        background-color: var(--accent-blue); 
        border: none; 
        color: #ffffff; 
        transition: background-color 0.2s;
    }
    div[data-testid="stForm"] button:hover {
        background-color: #2563EB; 
    }
    
    .done-btn-wrapper div[data-testid="stButton"] button { 
        background-color: #10B981 !important; 
        border: 1px solid #059669 !important; 
        border-radius: 16px !important; 
    }
    .done-btn-wrapper div[data-testid="stButton"] button p {
        color: #ffffff !important; 
        font-weight: 700 !important;
    }
    .done-btn-wrapper div[data-testid="stButton"] button:hover {
        background-color: #059669 !important; 
        border-color: #047857 !important; 
    }
    .done-btn-wrapper div[data-testid="stButton"] button p {
        color: #ffffff !important; 
        font-weight: 700 !important;
    }
    .done-btn-wrapper div[data-testid="stButton"] button:hover {
        background-color: #059669 !important; 
        border-color: #047857 !important; 
    }

    .error-btn-wrapper div[data-testid="stButton"] button { 
        background-color: #EF4444 !important; 
        border: 1px solid #B91C1C !important; 
        border-radius: 16px !important; 
    }
    .error-btn-wrapper div[data-testid="stButton"] button p {
        color: #ffffff !important; 
        font-weight: 700 !important;
    }
    .error-btn-wrapper div[data-testid="stButton"] button p {
        color: #ffffff !important; 
        font-weight: 700 !important;
    }
    
    /* Task slots 欄位間距 24px */
    [data-testid="column"] {
        padding-left: 0 !important;
        padding-right: 0 !important;
    }
    div[data-testid="stHorizontalBlock"] {
        gap: 24px !important; 
    }

    /* 今日股市焦點按鈕 */
    .focus-btn-wrapper div[data-testid="stButton"] button {
        background: linear-gradient(135deg, #F59E0B 0%, #EF4444 100%) !important;
        border: none !important;
        border-radius: 16px !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 15px !important;
        letter-spacing: 0.3px;
        transition: opacity 0.2s ease !important;
        box-shadow: 0 4px 14px rgba(245,158,11,0.35) !important;
    }
    .focus-btn-wrapper div[data-testid="stButton"] button:hover {
        opacity: 0.88 !important;
    }
    .focus-btn-wrapper div[data-testid="stButton"] button p {
        color: #ffffff !important;
        font-weight: 700 !important;
    }

    /* 今日焦點卡片 */
    .focus-card {
        background: linear-gradient(135deg, rgba(245,158,11,0.08) 0%, rgba(239,68,68,0.05) 100%);
        border: 1px solid rgba(245,158,11,0.25);
        border-radius: 20px;
        padding: 24px 28px;
        margin: 16px 0;
    }
    .focus-headline-row {
        margin-bottom: 10px;
        padding: 12px 16px;
        border-radius: 12px;
        background: var(--surface-color);
        border: 1px solid var(--surface-border);
        font-size: 13.5px;
        transition: transform 0.18s ease, box-shadow 0.18s ease;
    }
    .focus-headline-row:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        border-color: rgba(245,158,11,0.4);
    }

    /* Expander UI Fixes */
    [data-testid="stExpander"] {
        background: var(--surface-color);
        border: 1px solid var(--surface-border);
        border-radius: 16px !important;
        overflow: hidden;
    }
    
    /* Progress bar pill fix */
    .progress-pill {
        padding: 12px; 
        border-radius: 16px; 
        text-align: center; 
        color: white; 
        font-weight: 600; 
        border: 1px solid var(--surface-border); 
        white-space: nowrap; 
        overflow: hidden; 
        text-overflow: ellipsis; 
        font-size: 14px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    @media (max-width: 640px) {
        .block-container { padding-top: 1rem; padding-left: 1rem; padding-right: 1rem; }
        .mobile-hero h1 { font-size: 1.75rem; }
    }
    </style>""",
    unsafe_allow_html=True,
)

if 'tasks' not in st.session_state:
    st.session_state.tasks = {}
if 'tasks_slots' not in st.session_state:
    st.session_state.tasks_slots = [None, None, None]
if 'current_slot_idx' not in st.session_state:
    st.session_state.current_slot_idx = 0
if 'current_view' not in st.session_state:
    st.session_state.current_view = None
# 今日股市焦點狀態
if 'market_focus' not in st.session_state:
    st.session_state.market_focus = {
        'status': 'idle',   # idle | running | done | error
        'headlines': [],
        'summary': '',
        'error': '',
        'fetched_date': ''
    }

search_panel = get_mobile_search_panel_config()
active_key = resolve_active_api_key(SYSTEM_API_KEY)

st.markdown(
    """
    <div class="mobile-hero">
        <h1>🛡️ 股市全視角熱度儀</h1>
        <p>輸入股票代號或名稱，直接從手機啟動分析。</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# 自動同步
if 'stock_dict' not in st.session_state:
    with st.spinner("🚀 正在啟動天網：同步 2026 全市場股票清單..."):
        stock_dict, count = asyncio.run(sync_market_data())
        st.session_state.stock_dict = stock_dict
        st.success(f"✅ 資料庫就緒：{count} 檔股票")
        time.sleep(1) 

if not active_key:
    st.caption("⚠️ 未偵測到系統 AI 金鑰，將使用備用關鍵字算法。")

default_input = st.session_state.get("last_input", "2330")
default_day_range = clamp_day_range(st.session_state.get("selected_day_range", DEFAULT_DAY_RANGE))
with st.form("mobile_search_form"):
    user_input = st.text_input(
        search_panel.title,
        value=default_input,
        placeholder=search_panel.placeholder,
        label_visibility="collapsed",
    )
    selected_day_range = st.select_slider(
        search_panel.day_range_label,
        options=[1, 2, 3, 5, 7, 10, 14],
        value=default_day_range,
        help="可選擇最近 1 到 14 天的新聞",
    )
    run_btn = st.form_submit_button(
        f"🚀 {search_panel.button_label}",
        type="primary",
        use_container_width=True,
    )

if run_btn:
    normalized_input = user_input.strip()
    st.session_state.selected_day_range = clamp_day_range(selected_day_range)
    if normalized_input:
        code, name = asyncio.run(resolve_stock_info(normalized_input, st.session_state.stock_dict))
        if code:
            st.session_state.target_code = code
            st.session_state.target_name = name
            st.session_state.last_input = normalized_input
        else:
            st.session_state.target_code = None
            st.session_state.target_name = None
            st.session_state.last_input = normalized_input
    else:
        st.session_state.target_code = None
        st.session_state.target_name = None

if st.session_state.get('target_code'):
    st.markdown(
        f"<div class='stock-check'><div class='stock-name-text'>{st.session_state.target_name}</div><div>({st.session_state.target_code})</div></div>",
        unsafe_allow_html=True,
    )
elif st.session_state.get("last_input"):
    st.markdown(
        "<div class='stock-check' style='color:#ff4757'>⚠️ 找不到目標</div>",
        unsafe_allow_html=True,
    )

if run_btn:
    target_code = st.session_state.get('target_code')
    target_name = st.session_state.get('target_name')
    selected_day_range = clamp_day_range(st.session_state.get("selected_day_range", DEFAULT_DAY_RANGE))
    
    if not target_code:
        st.error("找不到目標股票，無法啟動分析。")
    else:
        slot_idx = st.session_state.current_slot_idx
        task_id = f"task_{target_code}_{int(time.time())}"
        
        # 覆蓋指定 slot 的舊任務 (如果有的話)
        st.session_state.tasks_slots[slot_idx] = task_id
        
        st.session_state.tasks[task_id] = {
            "task_id": task_id,
            "stock_code": target_code,
            "stock_name": target_name,
            "day_range": selected_day_range,
            "progress": 0,
            "status": "running",
            "result": None
        }
        
        # 移動指標到下一個 slot (0 -> 1 -> 2 -> 0)
        st.session_state.current_slot_idx = (slot_idx + 1) % 3
        st.session_state.current_view = task_id
        
        # 啟動背景執行緒
        import threading
        from streamlit.runtime.scriptrunner import add_script_run_ctx
        import time
        t = threading.Thread(target=background_task_runner, args=(task_id,))
        add_script_run_ctx(t)
        t.start()

# 繪製 Task Slots 按鈕列
st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
cols = st.columns(3)
for i in range(3):
    t_id = st.session_state.tasks_slots[i]
    with cols[i]:
        if t_id and t_id in st.session_state.tasks:
            task = st.session_state.tasks[t_id]
            if task['status'] == 'running':
                pct = task['progress']
                code = task['stock_code']
                name = task['stock_name']
                # 進度條按鈕樣式
                st.markdown(f"""
                <div class="progress-pill" style="background: linear-gradient(to right, var(--accent-blue) {pct}%, var(--surface-color) {pct}%);">
                    {code}{name} {pct}%
                </div>
                """, unsafe_allow_html=True)
            elif task['status'] == 'done':
                st.markdown('<div class="done-btn-wrapper">', unsafe_allow_html=True)
                if st.button(f"✅ {task['stock_name']}分析完成", key=f"btn_{t_id}", use_container_width=True):
                    st.session_state.current_view = t_id
                st.markdown('</div>', unsafe_allow_html=True)
            elif task['status'] == 'error':
                st.markdown('<div class="error-btn-wrapper">', unsafe_allow_html=True)
                if st.button(f"❌ {task['stock_name']}失敗", key=f"btn_{t_id}", use_container_width=True):
                    st.session_state.current_view = t_id
                st.markdown('</div>', unsafe_allow_html=True)


# 顯示目前選取的報告
if st.session_state.current_view and st.session_state.current_view in st.session_state.tasks:
    task = st.session_state.tasks[st.session_state.current_view]
    
    st.markdown(f"### 🔍 {task['stock_name']} ({task['stock_code']}) 分析報告")
    
    if task['status'] == 'running':
        st.info(f"🚀 正在為您篩選與分析中... 目前進度 {task['progress']}%")
    elif task['status'] == 'error':
        st.error(f"分析發生錯誤: {task['error']}")
    elif task['status'] == 'done':
        res = task['result']
        all_news = res['all_news']
        source_sections = res['source_sections']
        ai_report = res['ai_report']
        selected_day_range = res['selected_day_range']
        
        # ─── AI 分析報告（全版，最優先）───
        st.subheader("🤖 AI 投資分析報告")
        if not all_news:
            # 沒有新聞時，引導用戶延長搜尋天數
            st.markdown(f"""
            <div style='
                background: rgba(59, 130, 246, 0.08);
                border: 1px solid rgba(59, 130, 246, 0.25);
                border-radius: 16px;
                padding: 20px 24px;
                text-align: center;
            '>
                <div style='font-size: 32px; margin-bottom: 12px;'>🔍</div>
                <div style='font-size: 16px; font-weight: 600; color: #F8FAFC; margin-bottom: 8px;'>
                    近 {selected_day_range} 天內沒有找到相關新聞
                </div>
                <div style='font-size: 14px; color: #94A3B8; line-height: 1.6;'>
                    這支股票可能是較冷門的小型股。<br>
                    請回到上方，將「抓取天數」拉長至 <b style='color: #3B82F6;'>7 天或 14 天</b>，再重新分析。
                </div>
            </div>
            """, unsafe_allow_html=True)
        elif active_key and ai_report and "### 系統未配置" not in ai_report and "### AI 無法" not in ai_report:
            import re
            from ui_helpers import build_report_markup
            clean_report = ai_report.replace("SCORE:", "").strip()
            clean_report = re.sub(r"SCORE: \d+\n?", "", clean_report)
            st.markdown(build_report_markup(clean_report), unsafe_allow_html=True)
        else:
            st.info(ai_report)
        
        st.divider()
        
        # ─── 新聞來源分布 + 精選頭條（下方兩欄）───
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("📰 新聞來源分布")
            for section in source_sections:
                with st.expander(f"{section['source']}: {section['count']} 則"):
                    for link_item in section["links"]:
                        st.markdown(
                            f"- [{link_item['title']}]({link_item['link']})"
                        )
        
        with col2:
            st.subheader(f"🗞️ 精選頭條 (近 {selected_day_range} 日)")
            if all_news:
                for n in all_news:
                    snippet = n.get('snippet')
                    if snippet is None: snippet = "無摘要"
                    
                    link = n.get('link')
                    if not link:
                        link = f"https://www.google.com/search?q={n['title']}"

                    if len(snippet) > 50: snippet = snippet[:50] + "..."
                    
                    st.markdown(f"""
                    <div class='news-row'>
                        <b>[{n['source']}]</b> <a href='{link}' target='_blank' style='text-decoration:none; font-weight:600; color: #3B82F6;'>{n['title']}</a><br>
                        <small style='color:#94A3B8'>{snippet}</small>
                    </div>
                    """, unsafe_allow_html=True)
            else: 
                st.info(f"無新聞資料 (最近 {selected_day_range} 天無重要新聞)")

# ===========================
# 今日股市焦點 區塊
# ===========================
st.markdown("---")
st.markdown(
    """
    <div style='text-align:center; padding: 8px 0 4px 0;'>
        <span style='color:#94A3B8; font-size:13px;'>⬇️ 不分個股，掃描整體台股市場</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# 今日股市焦點按鈕
col_focus_l, col_focus_c, col_focus_r = st.columns([1, 3, 1])
with col_focus_c:
    st.markdown('<div class="focus-btn-wrapper">', unsafe_allow_html=True)
    focus_btn = st.button(
        "📡 今日股市焦點　掃描 & AI 總結",
        key="market_focus_btn",
        use_container_width=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)

if focus_btn:
    # 每日只抓一次，若已有當日資料則直接顯示
    today_key = time.strftime('%Y-%m-%d')
    mf = st.session_state.market_focus
    if mf['status'] == 'done' and mf.get('fetched_date') == today_key:
        st.toast("✅ 已顯示今日最新焦點（快取中）")
    else:
        st.session_state.market_focus = {
            'status': 'running',
            'headlines': [],
            'summary': '',
            'error': '',
            'fetched_date': today_key
        }
        st.rerun()

# 執行抓取（同步在主線程完成，避免 thread 衝突）
mf = st.session_state.market_focus
if mf['status'] == 'running':
    with st.spinner("📡 正在掃描今日台股市場頭條新聞，請稍候..."):
        try:
            today_headlines = asyncio.run(fetch_market_headlines_today())
            ai_summary = ""
            if active_key and today_headlines:
                ai_summary = summarize_market_with_gemini(
                    resolve_active_api_key(SYSTEM_API_KEY), today_headlines
                )
            elif not active_key:
                ai_summary = "⚠️ 未設定 AI 金鑰，無法進行 AI 總結，僅顯示頭條新聞。"
            elif not today_headlines:
                ai_summary = "⚠️ 今日暫無抓取到市場頭條，請稍後再試。"

            st.session_state.market_focus = {
                'status': 'done',
                'headlines': today_headlines,
                'summary': ai_summary,
                'error': '',
                'fetched_date': time.strftime('%Y-%m-%d')
            }
        except Exception as e:
            st.session_state.market_focus['status'] = 'error'
            st.session_state.market_focus['error'] = str(e)
    st.rerun()

# 顯示結果
mf = st.session_state.market_focus
if mf['status'] == 'done':
    today_str = time.strftime('%Y年%m月%d日')
    st.markdown(
        f"""
        <div class='focus-card'>
            <div style='font-size:18px; font-weight:700; color:#F59E0B; margin-bottom:6px;'>
                📡 今日股市焦點 &nbsp;<span style='font-size:13px; color:#94A3B8; font-weight:400;'>({today_str} · {len(mf['headlines'])} 則頭條)</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # AI 總結
    if mf['summary']:
        st.subheader("🤖 AI 市場總結")
        st.markdown(mf['summary'])
        st.divider()

    # 頭條新聞列表
    if mf['headlines']:
        st.subheader(f"📰 今日頭條 ({len(mf['headlines'])} 則)")
        for h in mf['headlines']:
            snippet = (h.get('snippet') or '')[:60]
            if len(h.get('snippet') or '') > 60:
                snippet += '...'
            link = h.get('link') or f"https://www.google.com/search?q={h['title']}"
            st.markdown(
                f"""
                <div class='focus-headline-row'>
                    <b style='color:#F59E0B;'>[{h['source']}]</b>
                    <a href='{link}' target='_blank' style='text-decoration:none; font-weight:600; color:#F8FAFC;'>{h['title']}</a><br>
                    <small style='color:#94A3B8;'>{snippet}</small>
                </div>
                """,
                unsafe_allow_html=True,
            )
elif mf['status'] == 'error':
    st.error(f"❌ 抓取今日焦點失敗：{mf['error']}")

# 定期更新檢查
if any(t['status'] == 'running' for t in st.session_state.tasks.values()):
    import time
    time.sleep(1)
    st.rerun()
