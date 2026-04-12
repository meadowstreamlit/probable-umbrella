import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import os, re, requests, random, zipfile, time
from rembg import remove, new_session
from io import BytesIO
from bs4 import BeautifulSoup

# -------------------- SETTINGS --------------------
script_dir = os.path.dirname(os.path.realpath(__file__))
image_dark = os.path.join(script_dir, "Base2.JPEG")
image_light = os.path.join(script_dir, "Base3.jpg")
font_path = os.path.join(script_dir, "Arial.ttf")
overlay_box = (0, 0, 828, 1088)  

blocks_config = {
    "Block 1": {"x": 20, "y": 1240, "height": 40, "color": "#dbdfde", "underline": False},
    "Item Size": {"x": 20, "y": 1290, "height": 38, "color": "#99a2a1", "underline": False},
    "Item Price": {"x": 20, "y": 1365, "height": 33, "color": "#99a2a1", "underline": False},
    "Buyer Fee": {"x": 20, "y": 1408, "height": 38, "color": "#648a93", "underline": False},
}

# ------------------- SESSION STATE & SINGLETONS -------------------
if "cache" not in st.session_state:
    st.session_state.cache = {}
if "rembg_session" not in st.session_state:
    st.session_state.rembg_session = new_session()

# ------------------- HELPERS -------------------
def remove_emojis(text):
    return re.sub(r"[^\w\s\-/&]", "", text)

def fetch_vinted(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept-Language": "en-GB,en;q=0.9"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        
        title_tag = soup.select_one("h1.web_ui__Text__title")
        title = remove_emojis(title_tag.get_text(strip=True)) if title_tag else "Unknown Item"

        price_tag = soup.select_one("p.web_ui__Text__subtitle")
        price_text = price_tag.get_text(strip=True) if price_tag else "0"
        price_val = float(re.sub(r"[^0-9.]", "", price_text) or 0)
        buyer_fee = round(price_val * 1.06, 2)

        image = None
        for img in soup.find_all("img"):
            src = img.get("src")
            if src and "images1.vinted.net/" in src:
                image = src
                break

        size = ""
        size_button = soup.select_one('button[aria-label*="Size"], button[title*="Size"]')
        if size_button and size_button.parent:
            candidate = size_button.parent.find(string=True, recursive=False)
            size = candidate.strip() if candidate else ""

        valid_conditions = ["New with tags","New without tags","Very good","Good","Satisfactory"]
        condition = ""
        for span in soup.select('span.web_ui__Text__bold'):
            text = span.get_text(strip=True)
            if text in valid_conditions:
                condition = text
                break

        brand_tag = soup.select_one('a[href^="/brand/"] span')
        brand = brand_tag.get_text(strip=True) if brand_tag else ""

        return {
            "title": title, 
            "price": f"£{price_val:.2f}", 
            "buyer_fee": f"£{buyer_fee:.2f}",
            "image": image, 
            "size": size, 
            "condition": condition, 
            "brand": brand
        }
    except Exception as e:
        st.error(f"Error scraping {url}: {e}")
        return None

def draw_text_block(draw, text, x, y, h, color, underline=False, is_currency=False):
    if not text: return 0
    font_size = 10
    font = ImageFont.truetype(font_path, font_size)
    while font.getmetrics()[0]+font.getmetrics()[1] < h:
        font_size += 1
        font = ImageFont.truetype(font_path, font_size)

    # FIXED ROBUST WRAPPING LOGIC
    if len(text) <= 50:
        lines = [text]
    else:
        split_idx = text[:50].rfind(" ")
        if split_idx == -1: split_idx = 50
        lines = [text[:split_idx].strip(), text[split_idx:].strip()]

    extra_offset = 20 if len(lines) > 1 else 0
    if len(lines) > 1:
        font_size -= 3
        font = ImageFont.truetype(font_path, font_size)

    for i, line in enumerate(lines):
        y_offset = y - (font.getmetrics()[0]+font.getmetrics()[1])//2 - (len(lines)-1-i)*h + extra_offset
        if is_currency and line.startswith("£"):
            draw.text((x, y_offset), "£", fill=color, font=font)
            draw.text((x + draw.textlength("£", font=font), y_offset), line[1:], fill=color, font=font)
        else:
            draw.text((x, y_offset), line, fill=color, font=font)
        if underline:
            bbox = draw.textbbox((x, y_offset), line, font=font)
            draw.line((bbox[0], bbox[3], bbox[2], bbox[3]), fill=color, width=2)
    return extra_offset

def draw_item_size_block(draw, size, condition, brand, x, y, h, mode_theme):
    spacing = 6
    cur_x = x
    font_size = 10
    font = ImageFont.truetype(font_path, font_size)
    while font.getmetrics()[0]+font.getmetrics()[1] < h:
        font_size += 1
        font = ImageFont.truetype(font_path, font_size)
    y_offset = y-(font.getmetrics()[0]+font.getmetrics()[1])//2
    text_color = "#606b6c" if mode_theme == "Light Mode" else "#99a2a1"
    brand_color = "#648a93"

    for val in [size, "·", condition, "·"]:
        if val:
            draw.text((cur_x, y_offset), val, fill=text_color, font=font)
            cur_x += draw.textlength(val, font=font) + spacing
    if brand:
        draw.text((cur_x, y_offset), brand, fill=brand_color, font=font)
        bbox = draw.textbbox((cur_x, y_offset), brand, font=font)
        draw.line((bbox[0], bbox[3], bbox[2], bbox[3]), fill=brand_color, width=2)

def generate_image(info, product_img, bg_color, base_img_path, mode_theme, remove_bg):
    base_img = Image.open(base_img_path).convert("RGBA")
    overlay_left, ot, overlay_right, ob = overlay_box
    ow, oh = overlay_right - overlay_left, ob - ot
    img_offset, text_offset = (16, 10) if mode_theme == "Light Mode" else (0, 0)

    bg_rect = Image.new("RGBA", (ow, oh), bg_color)
    background = Image.new("RGBA", base_img.size, (0,0,0,0))
    if mode_theme == "Light Mode":
        background.paste(Image.new("RGBA", (ow, img_offset), bg_color), (overlay_left, ot))
    background.paste(bg_rect, (overlay_left, ot + img_offset))
    img = Image.alpha_composite(base_img, background)

    if product_img:
        eff_box = (overlay_left, (ot + img_offset) - 16, overlay_right, ob + 16) if mode_theme == "Light Mode" else (overlay_left, ot, overlay_right, ob)
        eff_w, eff_h = eff_box[2]-eff_box[0], eff_box[3]-eff_box[1]
        pw, ph = product_img.size
        scale = min(eff_w/pw, eff_h/ph) if remove_bg else max(eff_w/pw, eff_h/ph)
        nw, nh = int(pw*scale), int(ph*scale)
        resized = product
