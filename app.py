import streamlit as st
import pandas as pd
import re
import time
import os
import subprocess
import sys
import base64
import json

# ۱. تنظیمات صفحه
st.set_page_config(
    page_title="سامانه هوشمند استعلام اتحادیه",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# تابع تبدیل تصویر به Base64
def get_image_base64(path):
    if os.path.exists(path):
        with open(path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode()
            return f"data:image/png;base64,{encoded}"
    return ""

# تابع تبدیل فایل فونت محلی به Base64
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

# پیدا کردن فایل فونت محلی
font_file_name = None
for f in ["Rey.woff2", "Rey.ttf", "Rey.woff", "rey.ttf", "rey.woff2"]:
    if os.path.exists(f):
        font_file_name = f
        break

font_base64 = get_font_base64(font_file_name) if font_file_name else ""

font_css = ""
if font_base64:
    font_css = f"""
    @font-face {{
        font-family: 'ReyFont';
        src: url('{font_base64}') format('truetype');
        font-weight: normal;
        font-style: normal;
    }}
    """
else:
    font_css = """
    @import url('https://v1.fontapi.ir/css/Rey');
    """

# ۲. استایل‌های CSS
st.markdown(f"""
<style>
    {font_css}

    html, body, [class*="css"], .stApp, button, input, textarea, select, div, span, p, h1, h2, h3, h4, h5, h6, table, th, td, label, .stMarkdown {{
        font-family: 'ReyFont', 'Rey', 'Vazirmatn', sans-serif !important;
    }}

    #MainMenu, footer, header, [data-testid="stHeader"] {{ visibility: hidden !important; display: none !important; }}
    
    .stApp {{
        background-color: #ffffff;
        direction: rtl;
    }}

    .block-container {{
        padding: 0 !important;
        max-width: 100% !important;
    }}

    [data-testid="stHorizontalBlock"] {{
        min-height: 100vh;
        align-items: center;
    }}

    [data-testid="column"] {{
        padding: 0 !important;
    }}

    .left-side-panel {{
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
        min-height: 100vh;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        padding: 40px 20px;
        color: #ffffff;
        text-align: center;
        box-sizing: border-box;
    }}

    .brand-title {{
        font-size: 24px;
        font-weight: bold;
        color: #f8fafc;
        margin-top: 15px;
    }}

    .brand-sub {{
        font-size: 15px;
        color: #38bdf8;
        margin-top: 8px;
    }}

    .right-side-panel {{
        max-width: 520px;
        margin: 0 auto;
        padding: 40px 20px;
    }}

    [data-testid="stFileUploader"] label {{
        text-align: center !important;
        display: block !important;
        width: 100% !important;
    }}

    .stButton>button {{
        width: 100%;
        background: #0ea5e9 !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 14px !important;
        font-size: 16px !important;
        font-weight: bold !important;
        box-shadow: 0 4px 14px rgba(14, 165, 233, 0.3) !important;
        margin-top: 10px !important;
    }}

    .stButton>button:hover {{
        background: #0284c7 !important;
        color: white !important;
    }}

    .stDownloadButton>button {{
        width: 100%;
        background: #FFB03B !important;
        color: #1e293b !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 14px !important;
        font-size: 16px !important;
        font-weight: bold !important;
        box-shadow: 0 4px 14px rgba(255, 176, 59, 0.4) !important;
        margin-top: 20px !important;
    }}

    .stDownloadButton>button:hover {{
        background: #e59b2b !important;
        color: #0f172a !important;
    }}

    [data-testid="stFileUploadDropzone"] {{
        border: 2px dashed #cbd5e1;
        border-radius: 14px;
        background-color: #f8fafc;
        padding: 25px;
    }}
    
    .stProgress > div > div > div > div {{
        background-color: #0ea5e9;
    }}
</style>
""", unsafe_allow_html=True)

# اسکریپت پردازش با قابلیت Resume خودکار
def create_runner_script(input_excel_path, output_excel_path, progress_json_path, log_file_path):
    input_p = input_excel_path.replace('\\', '/')
    output_p = output_excel_path.replace('\\', '/')
    prog_p = progress_json_path.replace('\\', '/')
    log_p = log_file_path.replace('\\', '/')

    script_code = f"""import pandas as pd
import re
import time
import json
import os
import traceback
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

def update_progress(current, total, status_text=""):
    try:
        with open("{prog_p}", "w", encoding="utf-8") as f:
            json.dump({{"current": current, "total": total, "status": status_text}}, f, ensure_ascii=False)
    except Exception:
        pass

def clean_domain(url):
    if not isinstance(url, str) or not url.strip():
        return ""
    url = url.strip().lower()
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path
    if domain.startswith('www.'):
        domain = domain[4:]
    return domain.split('/')[0]

def check_ecunion_modal(page, site_url):
    domain = clean_domain(site_url)
    if not domain:
        return "آدرس نامعتبر"

    try:
        page.goto("https://ecunion.ir/", wait_until="domcontentloaded", timeout=30000)
        time.sleep(1.0)

        modal_button = page.locator("text=استعلام مجوز").first
        modal_button.scroll_into_view_if_needed()
        modal_button.click()

        search_input_selector = ".modal-body input, #myModal input, input[type='text']"
        page.wait_for_selector(search_input_selector, timeout=8000, state="visible")
        
        search_input = page.locator(search_input_selector).first
        search_input.click()
        search_input.fill("")
        search_input.type(domain, delay=60)
        time.sleep(2.0)  # فرصت برای ظاهر شدن لیست پیشنهادها

        # انتخاب و کلیک روی پیشنهاد کشویی با دقت بیشتر
        dropdown_selector = "ul.ui-autocomplete li, .ui-menu-item, .select2-results li, .dropdown-menu li, div[class*='result']"
        dropdown_item = page.locator(dropdown_selector).first
        
        if dropdown_item.is_visible(timeout=3000):
            dropdown_item.click()
            time.sleep(0.5)
        else:
            # اگر منوی پیشنهادی ظاهر نشد کلید پایین و اینتر زده شود
            page.keyboard.press("ArrowDown")
            time.sleep(0.2)
            page.keyboard.press("Enter")
            time.sleep(0.5)

        search_btn = page.locator(".modal-body button:has-text('جستجو'), .modal button:has-text('جستجو'), button.btn-success").first
        if search_btn.is_visible():
            search_btn.click()
        else:
            page.keyboard.press("Enter")

        time.sleep(3.5)

        popup = page.locator(".modal-body, .modal-content").first
        popup_text = popup.inner_text()

        # بررسی کلمات کلیدی عدم وجود مجوز یا خطا در انتخاب
        if any(msg in popup_text for msg in ["یافت نشد", "نتیجه‌ای یافت نشد", "موردی انتخاب", "انتخاب موردی"]):
            return "مجوزی در اتحادیه ثبت نشده"

        if "اعتبار" in popup_text:
            for line in popup_text.split('\\n'):
                if "اعتبار" in line or "انقضا" in line or "تا تاریخ" in line:
                    line_clean = line.replace("مدت اعتبار:", "").replace("مدت اعتبار", "").strip()
                    if line_clean.startswith(":"):
                        line_clean = line_clean[1:].strip()
                    if len(line_clean) > 3:
                        return line_clean

        date_match = re.search(r'(از تاریخ|تاریخ|اعتبار|تا)\\s*(1[34]\\d{{2}}[/-]\\d{{1,2}}[/-]\\d{{1,2}})\\s*(به مدت|تا)?\\s*([^\\n]*)', popup_text)
        if date_match:
            return f"از {{date_match.group(2)}} {{date_match.group(4)}}".strip()

        dates = re.findall(r'1[34]\\d{{2}}[/-]\\d{{1,2}}[/-]\\d{{1,2}}', popup_text)
        if dates:
            return "تاریخ یافت‌شده: " + " - ".join(dates)

        if len(popup_text.strip()) > 10 and "موردی انتخاب" not in popup_text:
            clean_text = ' '.join(popup_text.split())[:60]
            return f"اطلاعات پیدا شد: {{clean_text}}"

        return "مجوزی در اتحادیه ثبت نشده"

    except Exception:
        return "خطا در پردازش آدرس"

try:
    # بررسی وجود خروجی قبلی برای Resume
    if os.path.exists("{output_p}"):
        df = pd.read_excel("{output_p}")
    else:
        df = pd.read_excel("{input_p}")

    url_col = None
    for col in df.columns:
        if str(col).lower() in ['url', 'urls', 'website', 'آدرس', 'لینک']:
            url_col = col
            break

    if url_col:
        if 'تاریخ اعتبار اتحادیه' not in df.columns:
            df['تاریخ اعتبار اتحادیه'] = None

        total_rows = len(df)
        update_progress(0, total_rows, "شروع مرورگر...")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            for index, row in df.iterrows():
                site_url = str(row[url_col]).strip()
                current_val = str(row['تاریخ اعتبار اتحادیه']).strip()

                # اگر قبلاً انجام شده یا حاوی پیغام "موردی انتخاب" بوده، مجدداً استعلام شود
                if pd.notna(row['تاریخ اعتبار اتحادیه']) and current_val != "" and current_val != "None" and "موردی انتخاب" not in current_val and current_val != "خطا در برقراری ارتباط" and current_val != "خطا در پردازش آدرس":
                    update_progress(index + 1, total_rows, f"قبلاً انجام شده: {{site_url}}")
                    continue

                update_progress(index, total_rows, f"در حال استعلام: {{site_url}}")
                
                try:
                    expiry_date = check_ecunion_modal(page, site_url)
                except Exception:
                    expiry_date = "خطا در برقراری ارتباط"
                    try:
                        page.close()
                        page = browser.new_page()
                    except Exception:
                        pass

                df.at[index, 'تاریخ اعتبار اتحادیه'] = expiry_date

                # آزادسازی حافظه RAM هر ۳۰ رکورد
                if (index + 1) % 30 == 0:
                    page.close()
                    page = browser.new_page()

                # ذخیره لحظه‌ای خروجی هر ۵ رکورد
                if (index + 1) % 5 == 0 or (index + 1) == total_rows:
                    df.to_excel("{output_p}", index=False)

                update_progress(index + 1, total_rows, f"استعلام {{site_url}} انجام شد")

            browser.close()

        df.to_excel("{output_p}", index=False)
        update_progress(total_rows, total_rows, "پایان")
    else:
        with open("{log_p}", "w", encoding="utf-8") as f:
            f.write("ستون آدرس یا URL در فایل اکسل پیدا نشد.")

except Exception as err:
    with open("{log_p}", "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
"""
    temp_script_path = "temp_runner.py"
    with open(temp_script_path, "w", encoding="utf-8") as f:
        f.write(script_code)
    return temp_script_path

# ۳. بخش ۵۰ / ۵۰
col_right, col_left = st.columns([1, 1])

with col_left:
    img_iran_html = f'<img src="{logo_iran}" width="480" style="filter: brightness(0) invert(1); margin-bottom: 5px; max-width: 90%; height: auto;">' if logo_iran else ''
    img_union_html = f'<img src="{logo_union}" width="360" style="margin-bottom: 15px; max-width: 80%; height: auto;">' if logo_union else ''

    st.markdown(f"""
    <div class="left-side-panel">
        <div style="margin-bottom: 10px;">
            {img_iran_html}
        </div>
        <hr style="border: 0; border-top: 1px solid #334155; width: 60%; margin: 20px 0;">
        <div style="margin-top: 10px;">
            {img_union_html}
            <div class="brand-title">اتحادیه کشوری کسب‌وکارهای مجازی</div>
            <div class="brand-sub">سامانه استعلام آنلاین و هوشمند مجوزها</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_right:
    st.markdown('<div class="right-side-panel">', unsafe_allow_html=True)
    
    st.markdown("""
    <div style="margin-bottom: 25px; text-align: center;">
        <h2 style="color: #0f172a; font-size: 26px; font-weight: bold; margin: 0;">پردازش فایل اکسل</h2>
        <p style="color: #64748b; font-size: 14px; margin-top: 10px;">لطفاً فایل اکسل حاوی لیست آدرس‌های اینترنتی را جهت استعلام وارد کنید.</p>
    </div>
    """, unsafe_allow_html=True)

    output_temp = os.path.abspath("temp_output.xlsx")

    # اگر خروجی قبلی وجود دارد
    if os.path.exists(output_temp):
        st.info("💡 **یک پردازش نیمه‌کاره یا قبلی پیدا شد.** می‌توانید پردازش را ادامه دهید یا از صفر شروع کنید.")
        if st.button("🗑️ پاکسازی نتایج قبلی (شروع مجدد از صفر)"):
            try:
                os.remove(output_temp)
                st.success("نتایج قبلی پاک شد. حالا می‌توانید فایل جدید را آپلود و پردازش کنید.")
                st.rerun()
            except Exception as e:
                st.error("خطا در پاکسازی فایل قبلی.")

    uploaded_file = st.file_uploader("انتخاب فایل اکسل (.xlsx)", type=["xlsx"])

    if uploaded_file is not None:
        df_input = pd.read_excel(uploaded_file)
        st.success(f"فایل با موفقیت بارگذاری شد ({len(df_input)} رکورد)")
        
        with st.expander("👁️ پیش‌نمایش فایل اکسل", expanded=False):
            st.dataframe(df_input.head(), use_container_width=True)

        btn_label = "▶️ ادامه پردازش (از جایی که قطع شده بود)" if os.path.exists(output_temp) else "شروع استعلام و پردازش"

        if st.button(btn_label):
            input_temp = os.path.abspath("temp_input.xlsx")
            progress_temp = os.path.abspath("progress.json")
            log_temp = os.path.abspath("error_log.txt")

            for f_clean in [progress_temp, log_temp]:
                if os.path.exists(f_clean):
                    try:
                        os.remove(f_clean)
                    except:
                        pass

            df_input.to_excel(input_temp, index=False)
            script_path = create_runner_script(input_temp, output_temp, progress_temp, log_temp)

            progress_bar = st.progress(0)
            status_text = st.empty()
            percent_text = st.empty()
            time_text = st.empty()

            start_time = time.time()
            process = subprocess.Popen([sys.executable, script_path])

            total_items = len(df_input)
            while process.poll() is None:
                if os.path.exists(progress_temp):
                    try:
                        with open(progress_temp, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            current = data.get("current", 0)
                            total = data.get("total", total_items)
                            status = data.get("status", "")

                            percent = int((current / total) * 100) if total > 0 else 0
                            progress_bar.progress(percent)
                            
                            elapsed_time = time.time() - start_time
                            if current > 0:
                                avg_time_per_item = elapsed_time / current
                                remaining_items = total - current
                                remaining_seconds = remaining_items * avg_time_per_item
                                remaining_minutes = round(remaining_seconds / 60, 1)
                                
                                if remaining_minutes < 1:
                                    rem_str = "کمتر از ۱ دقیقه"
                                else:
                                    rem_str = f"حدود {remaining_minutes} دقیقه"
                                
                                time_text.markdown(f"⏱️ **زمان باقی‌مانده:** {rem_str}")
                            else:
                                time_text.markdown("⏱️ **زمان باقی‌مانده:** در حال محاسبه...")

                            percent_text.markdown(f"**پیشرفت: {percent}%** ({current} از {total})")
                            status_text.caption(f"🔄 {status}")
                    except Exception:
                        pass
                time.sleep(0.5)

            progress_bar.progress(100)
            percent_text.markdown("**پیشرفت: ۱۰۰% (تکمیل شد)**")
            time_text.empty()
            status_text.empty()

            try:
                if os.path.exists(output_temp):
                    df_result = pd.read_excel(output_temp)
                    st.success("استعلام تمامی رکوردها با موفقیت انجام شد.")
                    st.dataframe(df_result, use_container_width=True)

                    with open(output_temp, "rb") as f:
                        st.download_button(
                            label="📥 دانلود فایل اکسل خروجی",
                            data=f,
                            file_name="نتایج_استعلام_اتحادیه.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                else:
                    st.error("فایل خروجی ساخته نشد. جزییات خطا را در زیر بررسی کنید:")
                    if os.path.exists(log_temp):
                        with open(log_temp, "r", encoding="utf-8") as f_err:
                            st.code(f_err.read(), language="python")
            except Exception as e:
                st.error(f"خطا در دریافت نتایج: {str(e)}")
            finally:
                for temp_file in [input_temp, progress_temp, script_path]:
                    if os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                        except:
                            pass

    st.markdown('</div>', unsafe_allow_html=True)