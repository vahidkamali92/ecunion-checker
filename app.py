import sys
import asyncio
import io
import os
import subprocess

# ۱. نصب و آماده‌سازی Playwright و مرورگر برای سرور ابری
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright"])
    from playwright.sync_api import sync_playwright

os.system("playwright install chromium")

# ۲. تنظیم حلقه رویدادهای ویندوز
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import streamlit as st
import pandas as pd
import re
import time
import base64
from urllib.parse import urlparse

# ۳. پیکربندی اولیه صفحه Streamlit
st.set_page_config(
    page_title="سامانه هوشمند استعلام اتحادیه",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# توابع تبدیل عکس و فونت به Base64
def get_image_base64(path):
    if os.path.exists(path):
        with open(path, "rb") as image_file:
            return f"data:image/png;base64,{base64.b64encode(image_file.read()).decode()}"
    return ""

def get_font_base64(font_path):
    if os.path.exists(font_path):
        with open(font_path, "rb") as font_file:
            encoded = base64.b64encode(font_file.read()).decode()
            ext = font_path.split('.')[-1].lower()
            font_format = "woff2" if ext == "woff2" else ("woff" if ext == "woff" else "truetype")
            return f"data:font/{font_format};charset=utf-8;base64,{encoded}"
    return ""

logo_iran = get_image_base64("iran.png")
logo_union = get_image_base64("union.png")

font_file_name = None
for f in ["Rey.woff2", "Rey.ttf", "Rey.woff", "rey.ttf", "rey.woff2"]:
    if os.path.exists(f):
        font_file_name = f
        break

font_base64 = get_font_base64(font_file_name) if font_file_name else ""
font_css = f"""
@font-face {{
    font-family: 'ReyFont';
    src: url('{font_base64}') format('truetype');
}}
""" if font_base64 else "@import url('https://v1.fontapi.ir/css/Rey');"

# ۴. استایل کامل CSS - اصلاح دکمه آپلود و چیدمان
st.markdown(f"""
<style>
    {font_css}
    * {{ font-family: 'ReyFont', 'Rey', 'Vazirmatn', sans-serif; }}
    #MainMenu, footer, header, [data-testid="stHeader"] {{ visibility: hidden !important; display: none !important; }}
    .stApp {{ background-color: #ffffff; direction: rtl; }}
    .block-container {{ padding: 0 !important; max-width: 100% !important; }}

    /* اصلاح کامل دکمه آپلود Streamlit برای جلوگیری از هم‌پوشانی متنی */
    [data-testid="stFileUploader"] {{
        direction: rtl !important;
    }}
    [data-testid="stFileUploader"] section {{
        padding: 20px !important;
        border-radius: 12px !important;
    }}
    [data-testid="stFileUploader"] section > div {{
        direction: rtl !important;
    }}
    [data-testid="stFileUploader"] button {{
        font-family: inherit !important;
        margin: 0 auto !important;
    }}

    /* خنثی‌سازی اثر مات شدن صفحه */
    html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stVerticalBlock"], div {{
        opacity: 1 !important;
        filter: none !important;
        -webkit-filter: none !important;
    }}

    .left-side-container {{
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%) !important;
        min-height: 100vh;
        width: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        padding: 40px 20px;
        color: #ffffff;
        text-align: center;
        box-sizing: border-box;
    }}

    .brand-title {{ font-size: 24px; font-weight: bold; color: #f8fafc; margin-top: 15px; }}
    .brand-sub {{ font-size: 15px; color: #38bdf8; margin-top: 8px; }}
    .right-side-container {{ max-width: 550px; margin: 0 auto; padding: 50px 20px; direction: rtl; }}
    
    div[data-testid="column"]:nth-child(1) .stButton>button {{ background-color: #0ea5e9 !important; color: white !important; border: none !important; border-radius: 10px !important; padding: 12px !important; font-size: 15px !important; font-weight: bold !important; width: 100%; }}
    div[data-testid="column"]:nth-child(2) .stButton>button {{ background-color: #ef4444 !important; color: white !important; border: none !important; border-radius: 10px !important; padding: 12px !important; font-size: 15px !important; font-weight: bold !important; width: 100%; }}
    .stDownloadButton>button {{ width: 100%; background-color: #10b981 !important; color: white !important; border-radius: 10px !important; padding: 12px !important; font-weight: bold !important; border: none !important; }}
</style>
""", unsafe_allow_html=True)

def format_time(seconds):
    if seconds <= 0: return "کمتر از یک ثانیه"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0: return f"{h} ساعت و {m} دقیقه"
    if m > 0: return f"{m} دقیقه و {s} ثانیه"
    return f"{s} ثانیه"

def clean_domain(url):
    if not isinstance(url, str) or not url.strip(): return ""
    url = url.strip().lower()
    if not url.startswith(('http://', 'https://')): url = 'http://' + url
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path
    if domain.startswith('www.'): domain = domain[4:]
    return domain.split('/')[0]

# ۵. تابع مقاوم‌سازی‌شده استعلام برای سرور ابری
def check_ecunion_modal(page, site_url):
    domain = clean_domain(site_url)
    if not domain: 
        return "آدرس نامعتبر"
    
    try:
        # لود اولیه صفحه
        response = page.goto("https://ecunion.ir/", wait_until="commit", timeout=35000)
        time.sleep(3.0)
        
        # تلاش برای یافتن دکمه استعلام با انتخابگرهای متعدد
        btn = page.locator("text=استعلام مجوز, a:has-text('استعلام'), button:has-text('استعلام')").first
        if btn.is_visible(): 
            btn.click()
        else:
            page.evaluate("() => { const el = document.querySelector(\"a[href*='modal'], button[data-toggle='modal']\"); if(el) el.click(); }")
            
        time.sleep(2.0)
        
        # یافتن اینپوت و تایپ دامنه
        search_input = page.locator("input[type='text'], .modal-body input").first
        search_input.wait_for(state="visible", timeout=10000)
        search_input.click()
        search_input.fill("")
        search_input.type(domain, delay=70)
        time.sleep(1.0)
        
        # ارسال فرم
        page.keyboard.press("Enter")
        time.sleep(4.0)
        
        # دریافت پاسخ
        popup_text = page.locator("body").inner_text()
        
        if any(msg in popup_text for msg in ["یافت نشد", "نتیجه‌ای یافت نشد", "موردی انتخاب", "اطلاعاتی موجود نیست"]):
            return "مجوزی در اتحادیه ثبت نشده"
            
        date_match = re.search(r'(1[34]\d{2}[/-]\d{1,2}[/-]\d{1,2})', popup_text)
        if date_match: 
            return f"معتبر تا {date_match.group(1)}"
            
        if "اعتبار" in popup_text or "تاریخ" in popup_text:
            for line in popup_text.split('\n'):
                if any(kw in line for kw in ["اعتبار", "انقضا", "تاریخ"]):
                    return line.strip()
                    
        return "مجوزی در اتحادیه ثبت نشده"
        
    except Exception as e:
        return f"خطا در پردازش آدرس"

if 'stop_processing' not in st.session_state:
    st.session_state['stop_processing'] = False

# ۶. چیدمان ستون‌ها
col_right, col_left = st.columns([1, 1])

# ستون سمت چپ (بنر برند سرمه‌ای)
with col_left:
    img_iran_html = f'<img src="{logo_iran}" width="480" style="filter: brightness(0) invert(1); margin-bottom: 5px; max-width: 90%; height: auto;">' if logo_iran else ''
    img_union_html = f'<img src="{logo_union}" width="360" style="margin-bottom: 15px; max-width: 80%; height: auto;">' if logo_union else ''

    st.markdown(f"""
    <div class="left-side-container">
        <div>{img_iran_html}</div>
        <hr style="border: 0; border-top: 1px solid #334155; width: 60%; margin: 20px 0;">
        <div>
            {img_union_html}
            <div class="brand-title">اتحادیه کشوری کسب‌وکارهای مجازی</div>
            <div class="brand-sub">سامانه استعلام آنلاین و هوشمند مجوزها</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ستون سمت راست (فرم آپلود و دکمه‌ها)
with col_right:
    st.markdown('<div class="right-side-container">', unsafe_allow_html=True)
    st.markdown("""
    <div style="margin-bottom: 25px; text-align: center;">
        <h2 style="color: #0f172a; font-size: 26px; font-weight: bold; margin: 0;">پردازش فایل اکسل</h2>
        <p style="color: #64748b; font-size: 14px; margin-top: 10px;">فایل اکسل لیست سایت‌ها را جهت استعلام آپلود کنید.</p>
    </div>
    """, unsafe_allow_html=True)

    uploaded_file = st.file_uploader("انتخاب فایل اکسل (.xlsx)", type=["xlsx"])

    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file)
        st.success(f"فایل با موفقیت بارگذاری شد ({len(df)} رکورد)")

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            start_btn = st.button("▶️ شروع پردازش")
        with col_btn2:
            stop_btn = st.button("⛔ توقف پردازش")

        if stop_btn:
            st.session_state['stop_processing'] = True

        if start_btn:
            st.session_state['stop_processing'] = False
            url_col = None
            for col in df.columns:
                if str(col).lower() in ['url', 'urls', 'website', 'آدرس', 'لینک']:
                    url_col = col
                    break

            if not url_col:
                st.error("❌ ستون آدرس یا URL در فایل اکسل پیدا نشد!")
            else:
                if 'تاریخ اعتبار اتحادیه' not in df.columns:
                    df['تاریخ اعتبار اتحادیه'] = None

                progress_bar = st.progress(0)
                status_box = st.empty()

                total_rows = len(df)
                start_time = time.time()
                processed_count = 0
                
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=True,
                        args=[
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-gpu"
                        ]
                    )
                    # تنظیم هویت مرورگر واقعی تا توسط سرور بلاک نشود
                    context = browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                    page = context.new_page()

                    for index, row in df.iterrows():
                        if st.session_state.get('stop_processing', False):
                            status_box.error("⛔ پردازش توسط کاربر متوقف شد.")
                            break

                        site_url = str(row[url_col]).strip()
                        current_val = str(row['تاریخ اعتبار اتحادیه']).strip()

                        pct = int(((index + 1) / total_rows) * 100)
                        progress_bar.progress(pct)

                        if processed_count > 0:
                            elapsed = time.time() - start_time
                            avg_time = elapsed / processed_count
                            remaining_items = total_rows - (index + 1)
                            eta_seconds = remaining_items * avg_time
                            time_str = f" | ⏳ زمان باقیمانده: {format_time(eta_seconds)}"
                        else:
                            time_str = " | ⏳ زمان باقیمانده: در حال محاسبه..."

                        if pd.notna(row['تاریخ اعتبار اتحادیه']) and current_val not in ["", "None", "nan", "خطا در پردازش آدرس"]:
                            status_box.info(f"⏭️ قبلاً انجام شده ({pct}% | {index + 1} از {total_rows}){time_str}: {site_url}")
                            continue

                        status_box.warning(f"🔍 در حال استعلام ({pct}% | {index + 1} از {total_rows}){time_str}: {site_url}")

                        res = check_ecunion_modal(page, site_url)
                        df.at[index, 'تاریخ اعتبار اتحادیه'] = res
                        processed_count += 1

                    browser.close()

                if not st.session_state.get('stop_processing', False):
                    status_box.success("✅ پردازش فایل با موفقیت کامل شد!")
                
                st.session_state['processed_df'] = df

        if 'processed_df' in st.session_state:
            st.divider()
            df_out = st.session_state['processed_df']
            st.write("📋 **پیش‌نمایش نتایج:**")
            st.dataframe(df_out, use_container_width=True)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_out.to_excel(writer, index=False)
            buffer.seek(0)

            st.download_button(
                label="📥 دانلود فایل خروجی اکسل",
                data=buffer,
                file_name="نتایج_استعلام_اتحادیه.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    st.markdown('</div>', unsafe_allow_html=True)
