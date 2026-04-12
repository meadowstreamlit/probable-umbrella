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
    # Added robust headers and timeout to prevent hanging
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
            candidate = size_button.parent.find(text=True, recursive=False)
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
            "title": title, "price": f"£{price_val:.2f}", "buyer_fee": f"£{buyer_fee:.2f}",
            "image": image, "size": size, "condition": condition, "brand": brand
        }
    except Exception as e:
        st.error(f"Error scraping {url}: {e}")
        return None

# ------------------- GENERATION LOGIC -------------------
# (Your generate_image, draw_text_block, and draw_item_size_block logic preserved exactly as designed)
def draw_text_block(draw, text, x, y, h, color, underline=False, is_currency=False):
    if not text: return 0
    font_size = 10
    font = ImageFont.truetype(font_path, font_size)
    while font.getmetrics()[0]+font.getmetrics()[1] < h:
        font_size += 1
        font = ImageFont.truetype(font_path, font_size)

    lines = [text] if len(text) <= 50 else [text[:text[:50].rfind(" ") if text[:50].rfind(" ") != -1 else 50], text[len(text[:50].rfind(" ") if text[:50].rfind(" ") != -1 else 50):].strip()]
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
        resized = product_img.resize((nw, nh), Image.Resampling.LANCZOS)
        if remove_bg:
            img.paste(resized, (eff_box[0] + (eff_w - nw)//2, eff_box[1] + (eff_h - nh)//2), resized)
        else:
            img.paste(resized.crop(((nw-eff_w)//2, (nh-eff_h)//2, (nw-eff_w)//2+eff_w, (nh-eff_h)//2+eff_h)), (eff_box[0], eff_box[1]))

    draw = ImageDraw.Draw(img)
    cfg1 = blocks_config["Block 1"]
    extra = draw_text_block(draw, info.get("title",""), cfg1["x"], cfg1["y"] + text_offset, cfg1["height"], "#15191a" if mode_theme=="Light Mode" else cfg1["color"])
    
    draw_item_size_block(draw, info.get("size",""), info.get("condition",""), info.get("brand",""), blocks_config["Item Size"]["x"], blocks_config["Item Size"]["y"] + text_offset + extra, blocks_config["Item Size"]["height"], mode_theme)

    for block in ["Item Price", "Buyer Fee"]:
        cfg = blocks_config[block]
        color = "#606b6c" if block == "Item Price" and mode_theme == "Light Mode" else cfg["color"]
        draw_text_block(draw, info.get(block.lower().replace(" ","_"),""), cfg["x"], cfg["y"] + text_offset, cfg["height"], color, is_currency=True)

    fw, fh = img.width, int(img.width*16/9)
    if fh>img.height: fh=img.height; fw=int(fh*9/16)
    return img.crop(((img.width-fw)//2, (img.height-fh)//2, (img.width-fw)//2+fw, (img.height-fh)//2+fh))

# ------------------- APP UI -------------------
st.title("Vinted Link Image Generator")
mode_theme = st.radio("Select Theme", ["Dark Mode", "Light Mode"])
bg_colors = {"Red": "#b04c5c","Green": "#689E9C","Blue": "#4E6FA4","Rose": "#FE8AB1","Purple": "#948EF2"}
remove_bg = st.toggle("Remove Background", value=True)
mode = st.radio("Choose Mode", ["Single URL","Bulk URLs"])

if mode == "Single URL":
    color_name = st.selectbox("Select Background Color", list(bg_colors.keys()))
    url = st.text_input("Paste Vinted URL")

    if st.button("Generate Image") and url:
        with st.spinner("Processing..."):
            if url not in st.session_state.cache:
                info = fetch_vinted(url)
                if info and info["image"]:
                    img_data = requests.get(info["image"]).content
                    pil_img = Image.open(BytesIO(img_data)).convert("RGBA")
                    # Using singleton session for speed
                    product_img = remove(pil_img, session=st.session_state.rembg_session) if remove_bg else pil_img
                    st.session_state.cache[url] = {"info": info, "img": product_img}
            
            if url in st.session_state.cache:
                data = st.session_state.cache[url]
                final_img = generate_image(data["info"], data["img"], bg_colors[color_name], image_dark if mode_theme=="Dark Mode" else image_light, mode_theme, remove_bg)
                st.image(final_img)
                
                # Optimized Byte Handling
                buf = BytesIO()
                final_img.convert("RGB").save(buf, format="JPEG")
                st.download_button("Download Image", buf.getvalue(), "output.jpeg", "image/jpeg")

elif mode == "Bulk URLs":
    urls_text = st.text_area("Paste multiple Vinted URLs")
    urls = [u.strip() for u in re.split(r"[\n,]", urls_text) if u.strip()]

    if st.button("Generate Bulk Images") and urls:
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zipf:
            for i, url in enumerate(urls, 1):
                if url not in st.session_state.cache:
                    # Defensive Scraping: small random pause
                    time.sleep(random.uniform(0.5, 1.5))
                    info = fetch_vinted(url)
                    if info:
                        img_data = requests.get(info["image"]).content
                        pil_img = Image.open(BytesIO(img_data)).convert("RGBA")
                        product_img = remove(pil_img, session=st.session_state.rembg_session) if remove_bg else pil_img
                        st.session_state.cache[url] = {"info": info, "img": product_img}
                
                if url in st.session_state.cache:
                    data = st.session_state.cache[url]
                    bg_color = random.choice(list(bg_colors.values()))
                    img_out = generate_image(data["info"], data["img"], bg_color, image_dark if mode_theme=="Dark Mode" else image_light, mode_theme, remove_bg)
                    
                    img_buf = BytesIO()
                    img_out.convert("RGB").save(img_buf, format="JPEG")
                    zipf.writestr(f"item_{i}.jpeg", img_buf.getvalue())
                    st.image(img_out, caption=f"Item {i}")

        st.download_button("Download All as ZIP", zip_buffer.getvalue(), "bulk_output.zip", "application/zip")
