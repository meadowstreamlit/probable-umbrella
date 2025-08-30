import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import os, re, requests, random, zipfile
from rembg import remove
from io import BytesIO
from bs4 import BeautifulSoup

# -------------------- SETTINGS --------------------
script_dir = os.path.dirname(os.path.realpath(__file__))
image_dark = os.path.join(script_dir, "Base2.JPEG")
image_light = os.path.join(script_dir, "Base3.jpg")
font_path = os.path.join(script_dir, "Arial.ttf")
overlay_box = (0, 0, 828, 1088)  # background overlay size

blocks_config = {
    "Block 1": {"x": 20, "y": 1240, "height": 40, "color": "#dbdfde", "underline": False},
    "Item Size": {"x": 20, "y": 1290, "height": 38, "color": "#99a2a1", "underline": False},
    "Item Price": {"x": 20, "y": 1365, "height": 33, "color": "#99a2a1", "underline": False},
    "Buyer Fee": {"x": 20, "y": 1408, "height": 38, "color": "#648a93", "underline": False},
}

# ------------------- HELPERS -------------------
def remove_emojis(text):
    return re.sub(r"[^\w\s\-/&]", "", text)

def draw_text_block(draw, text, x, y, h, color, underline=False, is_currency=False):
    if not text: return 0
    font_size = 10
    font = ImageFont.truetype(font_path, font_size)
    while font.getmetrics()[0]+font.getmetrics()[1] < h:
        font_size += 1
        font = ImageFont.truetype(font_path, font_size)

    # Split text into lines
    lines = []
    if len(text) <= 50:
        lines = [text]
    else:
        last_space = text[:50].rfind(" ")
        if last_space == -1:
            lines = [text[:50], text[50:]]
        else:
            lines = [text[:last_space], text[last_space+1:]]

    # Apply extra offset if 2 lines
    extra_offset = 20 if len(lines) > 1 else 0

    if len(lines) > 1:
        font_size -= 3
        font = ImageFont.truetype(font_path, font_size)

    for i, line in enumerate(lines):
        y_offset = y - (font.getmetrics()[0]+font.getmetrics()[1])//2 - (len(lines)-1-i)*h + extra_offset
        if is_currency and line.startswith("£"):
            number_text = line[1:]
            draw.text((x, y_offset), "£", fill=color, font=font)
            draw.text((x + draw.textlength("£", font=font), y_offset), number_text, fill=color, font=font)
        else:
            draw.text((x, y_offset), line, fill=color, font=font)

        if underline:
            bbox = draw.textbbox((x, y_offset), line, font=font)
            y_line = bbox[3]
            draw.line((bbox[0], y_line, bbox[2], y_line), fill=color, width=2)

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

    if mode_theme == "Light Mode":
        text_color = "#606b6c"
        brand_color = "#648a93"
    else:
        text_color = "#99a2a1"
        brand_color = "#648a93"

    if size:
        draw.text((cur_x, y_offset), size, fill=text_color, font=font)
        cur_x += draw.textlength(size, font=font) + spacing

    draw.text((cur_x, y_offset), "·", fill=text_color, font=font)
    cur_x += draw.textlength("·", font=font) + spacing

    if condition:
        draw.text((cur_x, y_offset), condition, fill=text_color, font=font)
        cur_x += draw.textlength(condition, font=font) + spacing

    draw.text((cur_x, y_offset), "·", fill=text_color, font=font)
    cur_x += draw.textlength("·", font=font) + spacing

    if brand:
        draw.text((cur_x, y_offset), brand, fill=brand_color, font=font)
        bbox = draw.textbbox((cur_x, y_offset), brand, font=font)
        y_line = bbox[3]
        draw.line((bbox[0], y_line, bbox[2], y_line), fill=brand_color, width=2)

# ------------------- VINTED SCRAPER -------------------
def fetch_vinted(url):
    headers = {"User-Agent":"Mozilla/5.0"}
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")

    title_tag = soup.select_one("h1.web_ui__Text__title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    title = remove_emojis(title)

    price_tag = soup.select_one("p.web_ui__Text__subtitle")
    price_text = price_tag.get_text(strip=True) if price_tag else ""
    price_val = float(re.sub(r"[^0-9.]", "", price_text) or 0)
    buyer_fee = round(price_val * 1.06, 2)

    image = None
    for img in soup.find_all("img"):
        src = img.get("src")
        if src and src.startswith("https://images1.vinted.net/"):
            image = src
            break

    size = ""
    size_button = soup.select_one('button[aria-label="Size information"], button[title="Size information"]')
    if size_button and size_button.parent:
        candidate = size_button.parent.find(text=True, recursive=False)
        if candidate:
            size = candidate.strip()

    valid_conditions = ["New with tags","New without tags","Very good","Good","Satisfactory"]
    condition = ""
    for span in soup.select('span.web_ui__Text__bold'):
        text = span.get_text(strip=True) if span else ""
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

# ------------------- SESSION STATE -------------------
if "cache" not in st.session_state:
    st.session_state.cache = {}

# ------------------- GENERATE IMAGE FUNCTION -------------------
def generate_image(info, product_img, bg_color, base_img_path, mode_theme, is_uploaded=False):
    all_texts = {
        "Block 1": info.get("title","") if info else "",
        "Item Price": info.get("price","") if info else "",
        "Buyer Fee": info.get("buyer_fee","") if info else ""
    }

    base_img = Image.open(base_img_path).convert("RGBA")
    overlay_left, ot, overlay_right, ob = overlay_box
    ow, oh = overlay_right - overlay_left, ob - ot

    bg_rect = Image.new("RGBA", (ow, oh), bg_color)
    background = Image.new("RGBA", base_img.size, (0, 0, 0, 0))

    img_offset = 0 if is_uploaded else (16 if mode_theme=="Light Mode" else 0)
    text_offset = 0 if is_uploaded else (10 if mode_theme=="Light Mode" else 0)

    background.paste(bg_rect, (overlay_left, ot + img_offset))
    img = Image.alpha_composite(base_img, background)

    if product_img:
        img_w, img_h = product_img.size
        scale = max(ow / img_w, oh / img_h)
        new_w = int(img_w * scale)
        new_h = int(img_h * scale)
        resized = product_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        left = (new_w - ow) // 2
        top = (new_h - oh) // 2
        cropped = resized.crop((left, top, left + ow, top + oh))

        paste_y = ot if is_uploaded else ot + img_offset
        img.paste(cropped, (overlay_left, paste_y), cropped)

    draw = ImageDraw.Draw(img)

    if info:
        cfg = blocks_config["Block 1"]
        extra_offset = draw_text_block(draw, info.get("title",""), cfg["x"], cfg["y"] + text_offset, cfg["height"], 
                                       "#15191a" if mode_theme=="Light Mode" else cfg["color"], 
                                       cfg["underline"], is_currency=False)

        draw_item_size_block(
            draw,
            info.get("size",""),
            info.get("condition",""),
            info.get("brand",""),
            blocks_config["Item Size"]["x"],
            blocks_config["Item Size"]["y"] + text_offset + extra_offset,
            blocks_config["Item Size"]["height"],
            mode_theme
        )

        for block, text in all_texts.items():
            cfg = blocks_config[block]
            if block == "Block 1":
                continue
            color = cfg["color"]
            if block == "Item Price" and mode_theme=="Light Mode":
                color = "#606b6c"
            draw_text_block(draw, text, cfg["x"], cfg["y"] + text_offset, cfg["height"], color, cfg["underline"], is_currency=True)

    fw, fh = img.width, int(img.width*16/9)
    if fh > img.height:
        fh = img.height
        fw = int(fh*9/16)
    left, top = (img.width-fw)//2, (img.height-fh)//2
    img_cropped = img.crop((left, top, left+fw, top+fh))
    return img_cropped

# ------------------- APP -------------------
st.title("Vinted Link Image Generator")

mode_theme = st.radio("Select Theme", ["Dark Mode", "Light Mode"], index=0)

bg_colors = {
    "Red": "#b04c5c",
    "Green": "#689E9C",
    "Blue": "#4E6FA4",
    "Rose": "#FE8AB1",
    "Purple": "#948EF2"
}

mode = st.radio("Choose Mode", ["Single URL","Bulk URLs"])

# ------------------- SINGLE URL -------------------
if mode == "Single URL":
    color_name = st.selectbox("Select Background Color", list(bg_colors.keys()), index=0)
    bg_color = bg_colors[color_name]
    url = st.text_input("Paste Vinted URL")

    uploaded_file = st.file_uploader("Optional: Use Your Own Image", type=["png","jpg","jpeg"])
    if uploaded_file:
        product_img = Image.open(uploaded_file).convert("RGBA")
        st.session_state.cache["uploaded_img"] = {"info": None, "img": product_img}

    if url and url not in st.session_state.cache:
        info = fetch_vinted(url)
        product_img_vinted = None
        if info["image"]:
            img_data = requests.get(info["image"]).content
            product_img_vinted = remove(Image.open(BytesIO(img_data)).convert("RGBA"))
        st.session_state.cache[url] = {"info": info, "img": product_img_vinted}

    cache_key = "uploaded_img" if uploaded_file else url

    if st.button("Generate Image") and cache_key in st.session_state.cache:
        data = st.session_state.cache[cache_key]
        info_obj = st.session_state.cache[url]["info"] if url else None
        product_img_obj = data["img"]
        base_img_path = image_dark if mode_theme=="Dark Mode" else image_light
        is_uploaded = uploaded_file is not None
        img_cropped = generate_image(info_obj, product_img_obj, bg_color, base_img_path, mode_theme, is_uploaded=is_uploaded)
        st.image(img_cropped)
        output_path = os.path.join(script_dir,"output.jpeg")
        img_cropped.convert("RGB").save(output_path)

        col1, col2 = st.columns([1,3])
        with col1:
            st.download_button("Download Image", open(output_path,"rb"), "output.jpeg", mime="image/jpeg")
        with col2:
            st.markdown("**Hold Image Above To Save Instead of Download**")

# ------------------- BULK URL -------------------
elif mode == "Bulk URLs":
    urls_text = st.text_area("Paste multiple Vinted URLs (comma or newline separated)")
    urls = [u.strip() for u in re.split(r"[\n,]", urls_text) if u.strip()]

    if st.button("Generate Bulk Images") and urls:
        zip_path = os.path.join(script_dir, "bulk_output.zip")
        with st.spinner("Generating bulk images..."):
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for i, url in enumerate(urls, 1):
                    if url not in st.session_state.cache:
                        info = fetch_vinted(url)
                        product_img = None
                        if info["image"]:
                            img_data = requests.get(info["image"]).content
                            product_img = remove(Image.open(BytesIO(img_data)).convert("RGBA"))
                        st.session_state.cache[url] = {"info": info, "img": product_img}

                    data = st.session_state.cache[url]
                    info_obj, product_img_obj = data["info"], data["img"]
                    bg_color = random.choice(list(bg_colors.values()))
                    base_img_path = image_dark if mode_theme=="Dark Mode" else image_light
                    img_cropped = generate_image(info_obj, product_img_obj, bg_color, base_img_path, mode_theme)

                    out_path = f"bulk_image_{i}.jpeg"
                    img_cropped.convert("RGB").save(out_path)
                    zipf.write(out_path)
                    st.image(img_cropped, caption=f"Image {i}")

        st.download_button("Download All as ZIP", open(zip_path,"rb"), "bulk_output.zip", mime="application/zip")
