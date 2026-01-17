import streamlit as st
import asyncio
from playwright.async_api import async_playwright
import time
import random
import sys
import xml.etree.ElementTree as ET
import os
import subprocess
import re
import json

# ===========================
# 🛠️ 自動安裝 requests (如果沒有的話)
# ===========================
try:
    import requests
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    import requests

# ===========================
# 0. 環境準備
# ===========================
try:
    subprocess.run(["playwright", "install", "chromium"], check=True)
except Exception:
    pass

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# ===========================
# 🔐 資安核心：讀取金鑰
# ===========================
SYSTEM_API_KEY = st.secrets.get("GEMINI_API_KEY", None)

# ===========================
# 1. 股票資料庫 (Top 100)
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
    "群益台灣精選高息": "00919", "元大美債20年": "00679B", "統一台灣高息動能": "00939", "元大台灣價值高息": "00940"
}

# ===========================
# 2. 爬蟲模組
# ===========================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
]
def get_ua(): return random.choice(USER_AGENTS)

async def sync_market_data():
    full_stock_dict = BASE_STOCKS.copy()
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=get_ua())
            # 使用 requests 替代 playwright 做簡單 API 請求，更穩定
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
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page(user_agent=get_ua())
            encoded = requests.utils.quote(clean_input) # 使用 requests 的工具
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

async def fetch_google_rss(stock_code, site_domain, source_name):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=get_ua())
        page = await context.new_page()
        try:
            rss_url = f"https://news.google.com/rss/search?q={stock_code}+site:{site_domain}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            response = await page.goto(rss_url, timeout=20000, wait_until="commit")
            xml_content = await response.text()
            root = ET.fromstring(xml_content)
            data = []
            for item in root.findall('.//item'):
                title = item.find('title').text
                desc_html = item.find('description').text if item.find('description') is not None else ""
                desc_clean = re.sub(r'<[^>]+>', '', desc_html)
                clean_title = title.split(" - ")[0]
                if len(clean_title) > 4: 
                    data.append({"title": clean_title, "snippet": desc_clean[:200], "source": source_name})
            return data[:5]
        except: return []
        finally: await browser.close()

async def scrape_anue(stock_code):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=get_ua())
        page = await context.new_page()
        try:
            await page.goto(f"https://www.cnyes.com/search/news?q={stock_code}", timeout=15000, wait_until="commit")
            await page.wait_for_timeout(1500)
            titles = await page.locator('h3, h2').all_inner_texts()
            return [{"title": t, "snippet": t, "source": "鉅亨網"} for t in titles if len(t) > 6][:5]
        except: return []
        finally: await browser.close()

async def scrape_yahoo(stock_code):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=get_ua())
        page = await context.new_page()
        try:
            await page.goto(f"https://tw.stock.yahoo.com/quote/{stock_code}.TW/news", timeout=20000, wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)
            items = await page.locator('#YDC-Stream li').all()
            data = []
            for item in items[:5]:
                try:
                    t_el = item.locator('h3')
                    if await t_el.count() > 0:
                        title = await t_el.inner_text()
                        desc_el = item.locator('p')
                        snippet = await desc_el.inner_text() if await desc_el.count() > 0 else title
                        data.append({"title": title, "snippet": snippet, "source": "Yahoo"})
                except: pass
            return data
        except: return []
        finally: await browser.close()

async def scrape_udn(c): return await fetch_google_rss(c, "money.udn.com", "經濟日報")
async def scrape_ltn(c): return await fetch_google_rss(c, "ec.ltn.com.tw", "自由財經")
async def scrape_ctee(c): return await fetch_google_rss(c, "ctee.com.tw", "工商時報")
async def scrape_chinatimes(c): return await fetch_google_rss(c, "chinatimes.com", "中時新聞")
async def scrape_ettoday(c): return await fetch_google_rss(c, "ettoday.net", "ETtoday")
async def scrape_tvbs(c): return await fetch_google_rss(c, "news.tvbs.com.tw", "TVBS新聞")
async def scrape_businesstoday(c): return await fetch_google_rss(c, "businesstoday.com.tw", "今周刊")
async def scrape_wealth(c): return await fetch_google_rss(c, "wealth.com.tw", "財訊")
async def scrape_storm(c): return await fetch_google_rss(c, "storm.mg", "風傳媒")

# ===========================
# 3. AI 評分核心 (Requests 版)
# ===========================
def get_available_model(api_key):
    """先查詢 Google，看這把 Key 能用哪些模型"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        # 使用 requests.get 自動處理 headers 和編碼
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            models = data.get('models', [])
            
            priority_list = [
                'models/gemini-1.5-flash',
                'models/gemini-1.5-pro',
                'models/gemini-1.0-pro',
                'models/gemini-pro'
            ]
            
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

def analyze_with_gemini_requests(api_key, stock_name, news_data):
    # 1. 自動偵測
    model_name = get_available_model(api_key)
    if not model_name:
        model_name = "models/gemini-pro"
        
    news_text = ""
    for i, news in enumerate(news_data):
        news_text += f"{i+1}. [{news['source']}] {news['title']}\n   摘要: {news['snippet']}\n"

    prompt = f"""
    你是一位專業的華爾街股票分析師。請閱讀以下關於「{stock_name}」的台灣財經新聞摘要，並進行綜合情緒分析。
    
    新聞列表：
    {news_text}

    請輸出以下格式的報告 (請用繁體中文)：
    1. **情緒分數 (0-100)**: (0是極度恐慌/利空，50是中立，100是極度樂觀/利多)。請直接給出一個數字。
    2. **市場氣氛**: (例如：偏多、觀望、主力出貨、利多出盡等)。
    3. **關鍵摘要**: 請總結這幾則新聞的核心重點，不要逐條列出，請融會貫通。
    4. **多空分析**: 簡單列出利多因素與利空因素。

    輸出範例格式：
    SCORE: 75
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
        
        # 使用 requests.post，它會自動處理 UTF-8 編碼，解決 Windows 問題
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                content = result['candidates'][0]['content']['parts'][0]['text']
                score_match = re.search(r"SCORE:\s*(\d+)", content)
                score = int(score_match.group(1)) if score_match else 50
                return score, content, model_name
        else:
            return None, f"Error {response.status_code}: {response.text}", model_name

    except Exception as e:
        return None, str(e), model_name

    return None, "未知錯誤", model_name

def calculate_score_keyword(news_list, source_name):
    if not news_list: return 0, []
    positive = ["上漲", "飆", "創高", "買超", "強勢", "超預期", "取得", "超越", "利多", "成長", "收益", "噴", "漲停", "旺", "攻頂", "受惠", "看好", "翻紅", "驚艷", "AI", "擴產", "先進", "動能", "發威", "領先", "搶單", "季增", "年增", "樂觀", "回溫", "布局", "利潤", "大漲", "完勝"]
    negative = ["下跌", "賣", "砍", "觀望", "保守", "不如", "重挫", "外資賣", "縮減", "崩", "跌停", "疲軟", "利空", "修正", "調節", "延後", "衰退", "翻黑", "示警", "重殺", "不如預期", "裁員", "虧損", "大跌", "重挫", "隱憂", "利空"]
    score = 50; reasons = []
    for news in news_list:
        content = news['title'] + " " + news.get('snippet', "")
        hit = False
        for w in positive: 
            if w in content: score += 12; reasons.append(w); hit = True
        for w in negative: 
            if w in content: score -= 12; reasons.append(w); hit = True
        if not hit and len(content) > 10: score += 2
    return max(0, min(100, score)), list(set(reasons))

async def run_analysis(stock_code):
    return await asyncio.gather(
        scrape_anue(stock_code), scrape_yahoo(stock_code), scrape_udn(stock_code),
        scrape_ltn(stock_code), scrape_ctee(stock_code), scrape_chinatimes(stock_code),
        scrape_ettoday(stock_code), scrape_tvbs(stock_code), scrape_businesstoday(stock_code),
        scrape_wealth(stock_code), scrape_storm(stock_code)
    )

# ===========================
# 4. Streamlit 介面 (V14.8)
# ===========================
st.set_page_config(page_title="V14.8 AI 投資顧問 (Requests版)", page_icon="🛡️", layout="wide")
st.markdown("""<style>.source-tag { padding: 3px 6px; border-radius: 4px; font-size: 11px; margin-right: 5px; color: white; display: inline-block; }.news-row { margin-bottom: 8px; padding: 4px; border-bottom: 1px solid #333; font-size: 14px; }.stock-check { background-color: #262730; padding: 10px; border-radius: 5px; border: 1px solid #4b4b4b; text-align: center; margin-bottom: 15px; }.stock-name-text { font-size: 24px; font-weight: bold; color: #4CAF50; }</style>""", unsafe_allow_html=True)

st.title("🛡️ V14.8 股市全視角熱度儀 (Requests 編碼修復版)")

# 自動同步
if 'stock_dict' not in st.session_state:
    with st.spinner("🚀 正在啟動天網：同步 2026 全市場股票清單..."):
        stock_dict, count = asyncio.run(sync_market_data())
        st.session_state.stock_dict = stock_dict
        st.success(f"✅ 資料庫就緒：{count} 檔股票")
        time.sleep(1) 

with st.sidebar:
    st.header("⚙️ 設定")
    user_input = st.text_input("輸入股票 (如 2330 或 緯創)", value="2330")
    
    st.markdown("---")
    st.subheader("🧠 AI 大腦")
    
    active_key = None
    if SYSTEM_API_KEY:
        st.success("✅ 系統金鑰已載入 (隱藏保護中)")
        active_key = SYSTEM_API_KEY
    else:
        user_key = st.text_input("Gemini API Key", type="password", placeholder="未檢測到系統 Key，請手動輸入")
        if user_key: active_key = user_key
        else: st.caption("⚠️ 使用備用關鍵字算法")
    
    if user_input:
        if 'last_input' not in st.session_state or st.session_state.last_input != user_input:
            code, name = asyncio.run(resolve_stock_info(user_input, st.session_state.stock_dict))
            if code:
                st.session_state.target_code = code
                st.session_state.target_name = name
                st.session_state.last_input = user_input
            else:
                st.session_state.target_code = None; st.session_state.target_name = None

        if st.session_state.get('target_code'):
            st.markdown(f"<div class='stock-check'><div class='stock-name-text'>{st.session_state.target_name}</div><div>({st.session_state.target_code})</div></div>", unsafe_allow_html=True)
        else: st.markdown(f"<div class='stock-check' style='color:#ff4757'>⚠️ 找不到目標</div>", unsafe_allow_html=True)
    
    run_btn = st.button("🚀 啟動 AI 分析", type="primary", disabled=not st.session_state.get('target_code'))

if run_btn:
    target_code = st.session_state.get('target_code')
    target_name = st.session_state.get('target_name')
    
    status = st.empty(); bar = st.progress(0)
    status.text(f"🔍 爬蟲出動：正在搜集 {target_name} 的全網新聞摘要...")
    bar.progress(10)
    
    results = asyncio.run(run_analysis(target_code))
    bar.progress(60)
    
    all_news = []
    source_names = ["鉅亨網", "Yahoo", "經濟日報", "自由財經", "工商時報", "中時新聞", "ETtoday", "TVBS新聞", "今周刊", "財訊", "風傳媒"]
    data_map = {name: res for name, res in zip(source_names, results)}
    for name, data in data_map.items():
        all_news.extend(data)
    
    final_score = 0
    ai_report = ""
    used_model = "None"
    
    if active_key and all_news:
        status.text("🧠 AI 正在掃描可用模型並撰寫報告...")
        bar.progress(80)
        # 使用 Requests 版函數
        ai_score, ai_report, used_model = analyze_with_gemini_requests(active_key, target_name, all_news)
        
        if ai_score:
            final_score = ai_score
        else:
            st.warning(f"AI 連線失敗 ({ai_report})，轉為備用算法")
            total = 0; count = 0
            for name, data in data_map.items():
                s, _ = calculate_score_keyword(data, name)
                if data: total += s; count += 1
            final_score = round(total/count, 1) if count else 0
            
    else:
        status.text("⚡ 正在進行關鍵字+摘要權重計算...")
        bar.progress(80)
        total = 0; count = 0
        all_signals = []
        for name, data in data_map.items():
            s, r = calculate_score_keyword(data, name)
            all_signals.extend(r)
            if data: total += s; count += 1
        final_score = round(total/count, 1) if count else 0
        ai_report = f"### 關鍵字訊號\n{', '.join(list(set(all_signals))[:15])}"

    bar.progress(100); time.sleep(0.5); status.empty(); bar.empty()

    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.metric("綜合評分", f"{final_score} 分", f"{len(all_news)} 則新聞")
        if final_score >= 75: l, c = "🔥🔥🔥 極度樂觀", "#ff4757"
        elif final_score >= 60: l, c = "🔥 偏多看待", "#ffa502"
        elif final_score <= 40: l, c = "🧊 偏空保守", "#5352ed"
        else: l, c = "⚖️ 中立震盪", "#747d8c"
        st.markdown(f"<h2 style='color:{c}'>{l}</h2>", unsafe_allow_html=True)
        if used_model != "None":
            st.caption(f"🤖 使用模型: {used_model}")
        
        st.divider()
        st.subheader("新聞來源分布")
        for name, data in data_map.items():
            if data: st.caption(f"{name}: {len(data)} 則")

    with col2:
        if active_key and "SCORE:" in ai_report:
            st.subheader("🤖 AI 投資分析報告")
            clean_report = ai_report.replace("SCORE:", "").strip()
            st.info(clean_report)
        else:
            st.subheader("📊 關鍵字分析結果")
            st.write(ai_report)
            
        st.divider()
        st.subheader("📰 精選新聞摘要")
        if all_news:
            for n in all_news[:15]:
                snippet = n.get('snippet', '無摘要')
                if len(snippet) > 50: snippet = snippet[:50] + "..."
                st.markdown(f"""
                <div class='news-row'>
                    <b>[{n['source']}]</b> <a href='https://www.google.com/search?q={n['title']}' target='_blank'>{n['title']}</a><br>
                    <small style='color:#aaa'>{snippet}</small>
                </div>
                """, unsafe_allow_html=True)
        else: st.info("無新聞資料")