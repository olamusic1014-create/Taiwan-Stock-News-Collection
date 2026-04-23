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
    if not BROWSER_STATUS.available:
        return full_stock_dict, len(full_stock_dict)

    try:
        async with async_playwright() as p:
            browser = await launch_browser(p)
            context = await browser.new_context(user_agent=get_ua())
            try:
                api_url = "https://scanner.tradingview.com/taiwan/scan"
                payload = {
                    "columns": ["name", "description", "volume"],
                    "ignore_unknown_fields": False,
                    "options": {"lang": "zh_TW"},
                    "range": [0, 1500],
                    "sort": {"sortBy": "volume", "sortOrder": "desc"},
                    "symbols": {"query": {"types": []}, "tickers": []},
                    "filter": [{"left": "type", "operation": "in_range", "right": ["stock", "dr", "fund"]}]
                }
                resp = requests.post(api_url, json=payload, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get('data', []):
                        code = item['d'][0]
                        name = item['d'][1].replace("KY", "").strip()
                        full_stock_dict[name] = code
            except: pass
            await browser.close()
    except Exception: pass
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
        response = requests.get(
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
        response = requests.get(url, headers=headers, timeout=5)
        
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
    1. **SCORE: [分數]** -> 請填入 0 到 100 的整數。
       - 0-20: 極度恐慌 / 重大利空 (如跌停、虧損擴大、掉單)
       - 40-60: 中立 / 觀望 / 多空交戰
       - 80-100: 極度樂觀 / 重大利多 (如漲停、獲利創新高、接到大單)
    2. **LEVEL**: (例如：偏多、觀望、主力出貨、利多出盡)。
    3. **SUMMARY**: 請綜合分析這些新聞的核心影響。
    4. **ANALYSIS**: 詳細列出你看多的理由與看空的理由。

    範例輸出：
    SCORE: 78
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
                # 嚴格解析 AI 的分數
                score_match = re.search(r"SCORE:\s*(\d+)", content, re.IGNORECASE)
                score = int(score_match.group(1)) if score_match else None
                return score, content, model_name
        else:
            return None, f"Error {response.status_code}: {response.text}", model_name

    except Exception as e:
        return None, str(e), model_name

# 備用關鍵字算法 (只有在 AI 掛掉時才用)
def calculate_score_keyword_fallback(news_list):
    if not news_list: return 0
    
    positive = ["上漲", "飆", "創高", "買超", "強勢", "超預期", "取得", "超越", "利多", "成長", "收益", "噴", "漲停", "旺", "攻頂", "受惠", "看好", "翻紅", "驚艷", "AI", "擴產", "先進", "動能", "發威", "領先", "搶單", "季增", "年增", "樂觀", "回溫", "布局", "利潤", "大漲", "完勝", "收購", "賣廠", "百億"]
    negative = ["下跌", "賣", "砍", "觀望", "保守", "不如", "重挫", "外資賣", "縮減", "崩", "跌停", "疲軟", "利空", "修正", "調節", "延後", "衰退", "翻黑", "示警", "重殺", "不如預期", "裁員", "虧損", "大跌", "重挫", "隱憂", "利空"]
    
    base_score = 50
    for news in news_list:
        snippet = news.get('snippet', '') or ""
        content = news['title'] + " " + snippet
        for w in positive: 
            if w in content: base_score += 5
        for w in negative: 
            if w in content: base_score -= 5
            
    return max(0, min(100, base_score))

async def run_analysis(stock_code, stock_name, day_range):
    safe_day_range = clamp_day_range(day_range)
    return await asyncio.gather(
        scrape_anue(stock_code, stock_name, safe_day_range), scrape_yahoo(stock_code), scrape_udn(stock_code, stock_name, safe_day_range),
        scrape_ltn(stock_code, stock_name, safe_day_range), scrape_ctee(stock_code, stock_name, safe_day_range), scrape_chinatimes(stock_code, stock_name, safe_day_range),
        scrape_ettoday(stock_code, stock_name, safe_day_range), scrape_tvbs(stock_code, stock_name, safe_day_range), scrape_businesstoday(stock_code, stock_name, safe_day_range),
        scrape_wealth(stock_code, stock_name, safe_day_range), scrape_storm(stock_code, stock_name, safe_day_range)
    )

# ===========================
# 4. Streamlit 介面 (V15.7)
# ===========================
st.set_page_config(page_title="V15.7 AI 投資顧問 (AI裁判版)", page_icon="🛡️", layout="wide")
st.markdown(
    """<style>
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background: #000000; color: #f5f5f5; }
    .block-container { max-width: 720px; padding-top: 1.5rem; padding-bottom: 3rem; }
    [data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none; }
    .source-tag { padding: 3px 6px; border-radius: 4px; font-size: 11px; margin-right: 5px; color: white; display: inline-block; }
    .news-row { margin-bottom: 8px; padding: 10px 0; border-bottom: 1px solid #202020; font-size: 14px; }
    .stock-check { background-color: #111111; padding: 14px; border-radius: 16px; border: 1px solid #2d2d2d; text-align: center; margin: 14px 0 18px 0; }
    .stock-name-text { font-size: 24px; font-weight: bold; color: #4CAF50; }
    .mobile-hero { text-align: center; padding: 0.5rem 0 1rem 0; }
    .mobile-hero h1 { font-size: 1.9rem; margin-bottom: 0.4rem; }
    .mobile-hero p { color: #bbbbbb; margin-bottom: 0; }
    div[data-testid="stForm"] { background: #0a0a0a; border: 1px solid #1f1f1f; border-radius: 18px; padding: 0.75rem 0.75rem 0.25rem 0.75rem; }
    div[data-testid="stForm"] input { background: #151515; color: #ffffff; border-radius: 12px; }
    div[data-testid="stForm"] button { border-radius: 999px; min-height: 3rem; font-weight: 700; }
    @media (max-width: 640px) {
        .block-container { padding-top: 1rem; padding-left: 1rem; padding-right: 1rem; }
        .mobile-hero h1 { font-size: 1.55rem; }
    }
    </style>""",
    unsafe_allow_html=True,
)

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
        options=[1, 2, 3, 4, 5],
        value=default_day_range,
        help="可選擇最近 1 到 5 天的新聞",
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
    
    status = st.empty(); bar = st.progress(0)
    status.text(f"🔍 爬蟲出動：正在為您篩選 {target_name} 最近 {selected_day_range} 天的頭條新聞...")
    bar.progress(10)
    
    results = asyncio.run(run_analysis(target_code, target_name, selected_day_range))
    bar.progress(60)
    
    all_news = []
    source_names = ["鉅亨網", "Yahoo", "經濟日報", "自由財經", "工商時報", "中時新聞", "ETtoday", "TVBS新聞", "今周刊", "財訊", "風傳媒"]
    data_map = {name: res for name, res in zip(source_names, results)}
    source_sections = build_source_sections(data_map)
    for name, data in data_map.items():
        all_news.extend(data)
    
    final_score = 0
    ai_report = ""
    score_source = "AI" # 標記分數來源
    
    if active_key and all_news:
        status.text("🧠 AI 正在閱讀內容並進行深度評分...")
        bar.progress(80)
        ai_score, ai_report, used_model = analyze_with_gemini_requests(active_key, target_name, all_news, selected_day_range)
        
        if ai_score is not None:
            final_score = ai_score
            score_source = "AI" # 確認是 AI 打的分
        else:
            # AI 失敗時的備用方案
            st.warning(f"AI 連線或解析失敗，轉為備用算法")
            final_score = calculate_score_keyword_fallback(all_news)
            score_source = "Fallback"
            ai_report = "### AI 無法生成報告，僅提供新聞摘要"
            
    else:
        status.text("⚡ 正在進行關鍵字計算...")
        bar.progress(80)
        final_score = calculate_score_keyword_fallback(all_news)
        score_source = "Fallback"

    bar.progress(100); time.sleep(0.5); status.empty(); bar.empty()

    col1, col2 = st.columns([1, 2])
    
    with col1:
        # 顯示分數來源標籤
        score_label = "🧠 AI 深度評分" if score_source == "AI" else "📊 備用關鍵字評分"
        st.caption(score_label)
        
        st.metric("綜合評分", f"{final_score} 分", f"{len(all_news)} 則精選新聞")
        if final_score >= 75: l, c = "🔥🔥🔥 極度樂觀", "#ff4757"
        elif final_score >= 60: l, c = "🔥 偏多看待", "#ffa502"
        elif final_score <= 40: l, c = "🧊 偏空保守", "#5352ed"
        else: l, c = "⚖️ 中立震盪", "#747d8c"
        st.markdown(f"<h2 style='color:{c}'>{l}</h2>", unsafe_allow_html=True)
        
        st.divider()
        st.subheader("新聞來源分布")
        for section in source_sections:
            with st.expander(f"{section['source']}: {section['count']} 則"):
                for link_item in section["links"]:
                    st.markdown(
                        f"- [{link_item['title']}]({link_item['link']})"
                    )

    with col2:
        if active_key and "SCORE:" in ai_report:
            st.subheader("🤖 AI 投資分析報告")
            clean_report = ai_report.replace("SCORE:", "").strip()
            # 移除 score 行以免重複顯示
            clean_report = re.sub(r"SCORE: \d+\n?", "", clean_report)
            st.markdown(build_report_markup(clean_report), unsafe_allow_html=True)
        else:
            st.subheader("📊 分析結果")
            st.markdown(build_report_markup(ai_report), unsafe_allow_html=True)
            
        st.divider()
        st.subheader(f"📰 精選頭條 (近{selected_day_range}日 Top 3)")
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
                    <b>[{n['source']}]</b> <a href='{link}' target='_blank' style='text-decoration:none; font-weight:bold; color: #4DA6FF;'>{n['title']}</a><br>
                    <small style='color:#aaa'>{snippet}</small>
                </div>
                """, unsafe_allow_html=True)
        else: st.info(f"無新聞資料 (最近 {selected_day_range} 天無重要新聞)")
