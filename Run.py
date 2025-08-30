# ... keep all imports and helpers the same ...

def generate_image(info, product_img, bg_color, base_img_path, mode_theme):
    all_texts = {
        "Block 1": info.get("title","") if info else "",
        "Item Price": info.get("price","") if info else "",
        "Buyer Fee": info.get("buyer_fee","") if info else ""
    }

    base_img = Image.open(base_img_path).convert("RGBA")
    overlay_left,ot,overlay_right,ob = overlay_box
    ow,oh = overlay_right-overlay_left, ob-ot

    bg_rect = Image.new("RGBA",(ow,oh),bg_color)
    background = Image.new("RGBA", base_img.size, (0,0,0,0))

    img_offset = 0
    text_offset = 0
    if mode_theme == "Light Mode":
        img_offset = 16
        text_offset = 10
        fill_band = Image.new("RGBA", (ow, img_offset), bg_color)
        background.paste(fill_band, (overlay_left, ot))

    background.paste(bg_rect, (overlay_left, ot+img_offset))
    img = Image.alpha_composite(base_img, background)

    if product_img:
        # Resize to fill overlay area while keeping aspect ratio
        img_w, img_h = product_img.size
        scale_w = ow / img_w
        scale_h = oh / img_h
        scale = max(scale_w, scale_h)  # cover the whole overlay
        new_w = int(img_w * scale)
        new_h = int(img_h * scale)
        product_img_resized = product_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Crop center to fit overlay
        left = (new_w - ow) // 2
        top = (new_h - oh) // 2
        cropped = product_img_resized.crop((left, top, left + ow, top + oh))

        # Paste into overlay
        img.paste(cropped, (overlay_left, ot + img_offset), cropped)

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

    # Crop final image to 16:9
    fw, fh = img.width, int(img.width*16/9)
    if fh>img.height: fh=img.height; fw=int(fh*9/16)
    left, top = (img.width-fw)//2, (img.height-fh)//2
    img_cropped = img.crop((left, top, left+fw, top+fh))
    return img_cropped

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
        # Always use info from URL if available, else None
        info = st.session_state.cache[url]["info"] if url else None
        product_img = data["img"]
        base_img_path = image_dark if mode_theme=="Dark Mode" else image_light
        img_cropped = generate_image(info, product_img, bg_color, base_img_path, mode_theme)
        st.image(img_cropped)
        output_path = os.path.join(script_dir,"output.jpeg")
        img_cropped.convert("RGB").save(output_path)

        col1, col2 = st.columns([1,3])
        with col1:
            st.download_button("Download Image", open(output_path,"rb"), "output.jpeg", mime="image/jpeg")
        with col2:
            st.markdown("**Hold Image Above To Save Instead of Download**")
