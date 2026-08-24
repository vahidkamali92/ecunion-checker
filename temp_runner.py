import pandas as pd
import re
import time
import json
import os
import traceback
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

def update_progress(current, total, status_text=""):
    try:
        with open("C:/Users/1/Desktop/codding/excel-scraper/progress.json", "w", encoding="utf-8") as f:
            json.dump({"current": current, "total": total, "status": status_text}, f, ensure_ascii=False)
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
            for line in popup_text.split('\n'):
                if "اعتبار" in line or "انقضا" in line or "تا تاریخ" in line:
                    line_clean = line.replace("مدت اعتبار:", "").replace("مدت اعتبار", "").strip()
                    if line_clean.startswith(":"):
                        line_clean = line_clean[1:].strip()
                    if len(line_clean) > 3:
                        return line_clean

        date_match = re.search(r'(از تاریخ|تاریخ|اعتبار|تا)\s*(1[34]\d{2}[/-]\d{1,2}[/-]\d{1,2})\s*(به مدت|تا)?\s*([^\n]*)', popup_text)
        if date_match:
            return f"از {date_match.group(2)} {date_match.group(4)}".strip()

        dates = re.findall(r'1[34]\d{2}[/-]\d{1,2}[/-]\d{1,2}', popup_text)
        if dates:
            return "تاریخ یافت‌شده: " + " - ".join(dates)

        if len(popup_text.strip()) > 10 and "موردی انتخاب" not in popup_text:
            clean_text = ' '.join(popup_text.split())[:60]
            return f"اطلاعات پیدا شد: {clean_text}"

        return "مجوزی در اتحادیه ثبت نشده"

    except Exception:
        return "خطا در پردازش آدرس"

try:
    # بررسی وجود خروجی قبلی برای Resume
    if os.path.exists("C:/Users/1/Desktop/codding/excel-scraper/temp_output.xlsx"):
        df = pd.read_excel("C:/Users/1/Desktop/codding/excel-scraper/temp_output.xlsx")
    else:
        df = pd.read_excel("C:/Users/1/Desktop/codding/excel-scraper/temp_input.xlsx")

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
                    update_progress(index + 1, total_rows, f"قبلاً انجام شده: {site_url}")
                    continue

                update_progress(index, total_rows, f"در حال استعلام: {site_url}")
                
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
                    df.to_excel("C:/Users/1/Desktop/codding/excel-scraper/temp_output.xlsx", index=False)

                update_progress(index + 1, total_rows, f"استعلام {site_url} انجام شد")

            browser.close()

        df.to_excel("C:/Users/1/Desktop/codding/excel-scraper/temp_output.xlsx", index=False)
        update_progress(total_rows, total_rows, "پایان")
    else:
        with open("C:/Users/1/Desktop/codding/excel-scraper/error_log.txt", "w", encoding="utf-8") as f:
            f.write("ستون آدرس یا URL در فایل اکسل پیدا نشد.")

except Exception as err:
    with open("C:/Users/1/Desktop/codding/excel-scraper/error_log.txt", "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
