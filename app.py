import streamlit as st
import asyncio
from playwright.async_api import async_playwright
import time
import random
import sys
import xml.etree.ElementTree as ET
import os
import subprocess

# === 雲端環境專用：自動安裝 Chromium 瀏覽器 ===
# 這行代碼會檢查是否在雲端，如果是，就自動安裝瀏覽器
try:
    subprocess.run(["playwright", "install", "chromium"], check=True)
except Exception as e:
    pass
# ===========================================

# === Windows 系統專用修復 ===
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# ===========================
# 1. 爬蟲核心 (V11.5 雲端部屬版)
# ===========================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
]
def get_ua(): return random.choice(USER_AGENTS)

async def fetch_stock_name(stock_code):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=get_ua())
        page = await context.new_page()
        try:
            # 策略 A: HiStock
            await page.goto(f"https://histock.tw/stock/{stock_code}", timeout=10000)
            title = await page.title()
            if "(" in title and ")" in title:
                return title.split("(")[0].strip()

            # 策略 B: Goodinfo
            await page.goto(f"https://goodinfo.tw/tw/StockDetail.jsp?STOCK_ID={stock_code}", timeout=10000)
            g_title = await page.title()
            if "(" in g_title:
                return g_title.split("(")[0].strip()
            return stock_code 
        except: return stock_code
        finally: await browser.close()

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
                clean_title = title.split(" - ")[0]
                if len(clean_title) > 6:
                    data.append({"title": clean_title, "source": source_name})
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
            data = [{"title": t, "source": "鉅亨網"} for t in titles if len(t) > 6 and "股價" not in t][:5]
            return data
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
            titles = await page.locator('#YDC-Stream li h3').all_inner_texts()
            if not titles: titles = await page.locator('#YDC-Stream li a').all_inner_texts()
            data = [{"title": t, "source": "Yahoo"} for t in titles if len(t) > 5 and "廣告" not in t][:5]
            return data
        except: return []
        finally: await browser.close()

async def scrape_udn(stock_code): return await fetch_google_rss(stock_code, "money.udn.com", "經濟日報")
async def scrape_ltn(stock_code): return await fetch_google_rss(stock_code, "ec.ltn.com.tw", "自由財經")
async def scrape_ctee(stock_code): return await fetch_google_rss(stock_code, "ctee.com.tw", "工商時報")
async def scrape_chinatimes(stock_code): return await fetch_google_rss(stock_code, "chinatimes.com", "中時新聞")
async def scrape_ettoday(stock_code): return await fetch_google_rss(stock_code, "ettoday.net", "ETtoday")
async def scrape_tvbs(stock_code): return await fetch_google_rss(stock_code, "news.tvbs.com.tw", "TVBS新聞")
async def scrape_businesstoday(stock_code): return await fetch_google_rss(stock_code, "businesstoday.com.tw", "今周刊")
async def scrape_wealth(stock_code): return await fetch_google_rss(stock_code, "wealth.com.tw", "財訊")
async def scrape_storm(stock_code): return await fetch_google_rss(stock_code, "storm.mg", "風傳媒")

def calculate_score(news_list, source_name):
    if not news_list: return 0, []
    positive = ["上漲", "飆", "創高", "買超", "強勢", "超預期", "取得", "超越", "利多", "成長", "收益", "噴", "漲停", "旺", "攻頂", "受惠", "看好", "翻紅", "驚艷", "AI", "擴產", "先進", "動能", "發威", "領先", "搶單", "季增", "年增", "樂觀", "回溫", "布局", "利潤", "大漲"]
    negative = ["下跌", "賣", "砍", "觀望", "保守", "不如", "重挫", "外資賣", "縮減", "崩", "跌停", "疲軟", "利空", "修正", "調節", "延後", "衰退", "翻黑", "示警", "重殺", "不如預期", "裁員", "虧損", "大跌", "重挫"]
    score = 50
    reasons = []
    for news in news_list:
        title = news['title']
        hit = False
        for w in positive:
            if w in title: score += 12; reasons.append(w); hit = True
        for w in negative:
            if w in title: score -= 12; reasons.append(w); hit = True
        if not hit and len(title) > 5: score += 2
    return max(0, min(100, score)), list(set(reasons))

async def run_analysis(stock_code):
    return await asyncio.gather(scrape_anue(stock_code), scrape_yahoo(stock_code), scrape_udn(stock_code), scrape_ltn(stock_code), scrape_ctee(stock_code), scrape_chinatimes(stock_code), scrape_ettoday(stock_code), scrape_tvbs(stock_code), scrape_businesstoday(stock_code), scrape_wealth(stock_code), scrape_storm(stock_code))

st.set_page_config(page_title="V11.5 雲端股票熱度儀", page_icon="📈", layout="wide")
st.markdown("""<style>.source-tag { padding: 3px 6px; border-radius: 4px; font-size: 11px; margin-right: 5px; color: white; display: inline-block; }.news-row { margin-bottom: 8px; padding: 4px; border-bottom: 1px solid #333; font-size: 14px; }.stock-check { background-color: #262730; padding: 10px; border-radius: 5px; border: 1px solid #4b4b4b; text-align: center; margin-bottom: 15px; }.stock-name-text { font-size: 24px; font-weight: bold; color: #4CAF50; }</style>""", unsafe_allow_html=True)

st.title("📈 V11.5 股市全視角熱度監測 (雲端版)")
st.markdown("整合 **11 大權威媒體**，支援手機/電腦跨平台使用。")

with st.sidebar:
    st.header("⚙️ 股票設定")
    stock_input = st.text_input("輸入股票代碼 (按 Enter 確認)", value="2330")
    if stock_input:
        if 'last_stock' not in st.session_state or st.session_state.last_stock != stock_input:
            with st.spinner(f"正在確認 {stock_input} ..."):
                stock_name = asyncio.run(fetch_stock_name(stock_input))
                st.session_state.stock_name_display = stock_name
                st.session_state.last_stock = stock_input
        if st.session_state.get('stock_name_display'):
            st.markdown(f"<div class='stock-check'><div style='font-size: 12px; color: #aaa;'>確認目標</div><div class='stock-name-text'>{st.session_state.stock_name_display}</div><div style='font-size: 12px; color: #888;'>({stock_input})</div></div>", unsafe_allow_html=True)
        else: st.markdown(f"<div class='stock-check' style='color:#ff4757'>⚠️ 查無此代號</div>", unsafe_allow_html=True)
    run_btn = st.button("🚀 啟動雲端掃描", type="primary")

if run_btn and stock_input:
    status = st.empty(); bar = st.progress(0)
    status.text(f"🔍 雲端主機正在連線 11 大數據源...")
    bar.progress(10)
    results = asyncio.run(run_analysis(stock_input))
    bar.progress(85)
    status.text("🧠 正在計算情緒...")
    source_names = ["鉅亨網", "Yahoo", "經濟日報", "自由財經", "工商時報", "中時新聞", "ETtoday", "TVBS新聞", "今周刊", "財訊", "風傳媒"]
    data_map = {name: res for name, res in zip(source_names, results)}
    scores = {}; all_signals = []; all_news = []; valid_count = 0; total_score = 0
    for name, data in data_map.items():
        s, r = calculate_score(data, name)
        scores[name] = s; all_signals.extend(r); all_news.extend(data)
        if len(data) > 0: total_score += s; valid_count += 1
    final_score = round(total_score / valid_count, 1) if valid_count > 0 else 0
    bar.progress(100); time.sleep(0.5); status.empty(); bar.empty()

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1: st.metric("全市場熱度", f"{final_score} 分", f"{len(all_news)} 則新聞")
    with col2:
        if final_score >= 75: l, c = "🔥🔥🔥 沸騰", "#ff4757"
        elif final_score >= 60: l, c = "🔥 加溫", "#ffa502"
        elif final_score <= 35: l, c = "🧊 冰凍", "#5352ed"
        else: l, c = "⚖️ 溫和", "#747d8c"
        st.markdown(f"<h2 style='color:{c}'>{l}</h2>", unsafe_allow_html=True)
    with col3: st.write(", ".join(list(set(all_signals))[:15]) if all_signals else "無訊號")
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        keys = list(data_map.keys())
        for name in keys[:6]: 
            s = scores[name]; cnt = len(data_map[name])
            if cnt: st.write(f"**{name}**: {s}"); st.progress(s)
            else: st.caption(f"{name}: ⚠️")
    with c2:
        for name in keys[6:]:
            s = scores[name]; cnt = len(data_map[name])
            if cnt: st.write(f"**{name}**: {s}"); st.progress(s)
            else: st.caption(f"{name}: ⚠️")
    st.divider()
    if all_news:
        cmap = {"鉅亨網": "#0984e3", "Yahoo": "#6c5ce7", "經濟日報": "#e17055", "自由財經": "#d63031", "工商時報": "#00b894", "中時新聞": "#e84393", "ETtoday": "#fdcb6e", "TVBS新聞": "#2d3436", "今周刊": "#00cec9", "財訊": "#fab1a0", "風傳媒": "#636e72"}
        for n in all_news[:30]:
            bg = cmap.get(n['source'], "#999")
            st.markdown(f"<div class='news-row'><span class='source-tag' style='background-color:{bg}'>{n['source']}</span><a href='https://www.google.com/search?q={n['title']}' target='_blank' style='text-decoration:none; color:inherit'>{n['title']}</a></div>", unsafe_allow_html=True)
    else: st.info("無新聞")