import streamlit as st
import requests
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import re
import random
import math
import zipfile
import os
import time

# --- Sayfa Ayarları ---
st.set_page_config(page_title="ETP Katalog Oluşturucu", layout="wide", page_icon="📑")

# --- GÜVENLİK / LOGIN SİSTEMİ ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def check_password():
    if st.session_state.pin_input == "5702":
        st.session_state.authenticated = True
    else:
        st.error("Hatalı PIN Kodu! Lütfen tekrar deneyin.")

# Giriş Ekranı
if not st.session_state.authenticated:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔒 ETP Ticaret Güvenli Giriş")
        st.write("Devam etmek için lütfen yetkili PIN kodunu giriniz.")
        
        st.text_input("PIN Kodu", type="password", key="pin_input", on_change=check_password)
        
        if st.button("Giriş Yap"):
            check_password()
            
        st.markdown("---")
        st.markdown("""
            <div style='text-align: center; color: grey; padding-top: 20px;'>
            ETP Ticaret | Tüm Hakları Saklıdır © 2025
            </div>
            """, unsafe_allow_html=True)
    st.stop()

# --- PROGRAM BAŞLANGICI ---

# Yardımcı Fonksiyonlar
@st.cache_data(ttl=600)
def get_xml_data(urls):
    headers = {'User-Agent': 'Mozilla/5.0'}
    urun_havuzu = {}
    
    for url in urls:
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            root = ET.fromstring(resp.content)
            items = root.findall('.//item') or root.findall('.//{*}entry')
            
            for item in items:
                p = {}
                for child in item:
                    tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    val = child.text.strip() if child.text else ""
                    if not val: continue
                    
                    if tag == 'title': p['title'] = val
                    elif tag == 'id': p['id'] = val
                    elif 'image_link' in tag: p['img'] = val
                    elif 'price' in tag and 'price' not in p:
                        try:
                            clean = val.replace('.', '').replace(',', '.')
                            clean = re.sub(r'[^\d.]', '', clean)
                            p['price'] = float(clean)
                        except: p['price'] = 0.0
                    elif 'availability' in tag:
                        p['stock'] = val.lower()
                
                if 'id' in p and 'img' in p and 'price' in p:
                    urun_havuzu[p['id']] = p
        except Exception as e:
            st.error(f"XML Hatası ({url}): {e}")
            
    return list(urun_havuzu.values())

def create_gradient(width, height):
    palettes = [
        ((26, 62, 118), (10, 20, 40)), ((60, 10, 10), (15, 5, 5)),
        ((10, 50, 30), (5, 20, 10)), ((40, 40, 40), (10, 10, 10)),
        ((45, 10, 60), (15, 5, 25))
    ]
    start, end = random.choice(palettes)
    base = Image.new('RGB', (width, height), start)
    top = Image.new('RGB', (width, height), end)
    mask = Image.new('L', (width, height))
    mask_data = []
    for y in range(height): mask_data.extend([int(255 * (y/height))] * width)
    mask.putdata(mask_data)
    base.paste(top, (0,0), mask)
    return base

def wrap_text(text, font, max_width, draw):
    words = text.split()
    lines = []
    curr = []
    for w in words:
        curr.append(w)
        if draw.textbbox((0, 0), " ".join(curr), font=font)[2] > max_width:
            curr.pop()
            lines.append(" ".join(curr))
            curr = [w]
    lines.append(" ".join(curr))
    return lines

def get_logo(max_width):
    if os.path.exists("logo.png"):
        try:
            logo = Image.open("logo.png").convert("RGBA")
            ratio = max_width / logo.width
            new_h = int(logo.height * ratio)
            return logo.resize((max_width, new_h), Image.LANCZOS)
        except: pass
    return None

# --- FONT YÜKLEME FONKSİYONU (YENİ) ---
def load_fonts(mode="single"):
    # Roboto fontlarını klasörden yüklemeye çalışır
    # mode: "single" (tekli görsel) veya "catalog" (katalog sayfası)
    
    font_reg = "Roboto-Regular.ttf"
    font_bold = "Roboto-Bold.ttf"
    
    try:
        if mode == "single":
            # Tekli görsel boyutları
            f_head = ImageFont.truetype(font_reg, 40)
            f_title = ImageFont.truetype(font_reg, 60)
            f_price = ImageFont.truetype(font_bold, 120)
            return f_head, f_title, f_price
        else:
            # Katalog boyutları
            kf_title = ImageFont.truetype(font_reg, 40)
            kf_price = ImageFont.truetype(font_bold, 60)
            kf_head = ImageFont.truetype(font_bold, 80)
            return kf_title, kf_price, kf_head
            
    except OSError:
        # Eğer font dosyaları GitHub'a yüklenmemişse yine default'a döner (ama yükleyince düzelecek)
        if mode == "single":
            return ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default()
        else:
            return ImageFont.load_default(), ImageFont.load_default(), ImageFont.load_default()


# --- GÖRSEL OLUŞTURUCULAR ---
def generate_single_image(urun):
    try:
        # YENİ FONT YÜKLEME SİSTEMİ
        f_head, f_title, f_price = load_fonts(mode="single")

        W, H = 1080, 1920
        canvas = create_gradient(W, H)
        draw = ImageDraw.Draw(canvas, "RGBA")

        head_txt = "ETP Ticaret | Ürün Fiyatları"
        bbox = draw.textbbox((0, 0), head_txt, font=f_head)
        draw.text(((W - (bbox[2]-bbox[0])) / 2, 80), head_txt, font=f_head, fill="#d1d1d1")

        resp = requests.get(urun['img'], timeout=10)
        img_data = Image.open(BytesIO(resp.content)).convert("RGBA")
        img_data.thumbnail((900, 900), Image.LANCZOS)
        canvas.paste(img_data, ((W - img_data.width) // 2, 200), img_data)

        lines = wrap_text(urun['title'], f_title, 900, draw)
        text_start_y = 200 + img_data.height + 100
        total_h = len(lines) * 80
        draw.rectangle([(50, text_start_y - 20), (W-50, text_start_y + total_h + 30)], fill=(0, 0, 0, 180))

        ty = text_start_y
        for line in lines:
            lw = draw.textbbox((0, 0), line, font=f_title)[2]
            draw.text(((W - lw) / 2, ty), line, font=f_title, fill="white")
            ty += 80

        p_str = f"{int(urun['price']):,}".replace(',', '.') + " ₺"
        pw = draw.textbbox((0, 0), p_str, font=f_price)[2]
        draw.text(((W - pw) / 2, ty + 60), p_str, font=f_price, fill="#FFD700")
        
        logo = get_logo(300)
        if logo:
            lx = (W - logo.width) // 2
            ly = H - logo.height - 100
            canvas.paste(logo, (lx, ly), logo)

        return canvas
    except Exception as e:
        return None

def generate_catalog_pages(urunler):
    A4_W, A4_H = 2480, 3508
    COLS, ROWS = 3, 4
    items_per_page = COLS * ROWS
    
    # YENİ FONT YÜKLEME SİSTEMİ
    kf_title, kf_price, kf_head = load_fonts(mode="catalog")

    logo_img = get_logo(400)
    total_pages = math.ceil(len(urunler) / items_per_page)
    pages = []

    for page_num in range(total_pages):
        canvas = Image.new("RGB", (A4_W, A4_H), "white")
        draw = ImageDraw.Draw(canvas)
        
        header_text = f"ETP Ticaret Ürün Kataloğu - Sayfa {page_num+1}"
        draw.text((100, 50), header_text, font=kf_head, fill="#1a3e76")
        if logo_img:
            canvas.paste(logo_img, (A4_W - logo_img.width - 50, 30), logo_img)
        
        draw.line([(50, 150), (A4_W-50, 150)], fill="#1a3e76", width=5)

        start_idx = page_num * items_per_page
        end_idx = min(start_idx + items_per_page, len(urunler))
        page_items = urunler[start_idx:end_idx]

        margin_x, margin_y = 100, 200
        usable_w = A4_W - (2 * margin_x)
        usable_h = A4_H - margin_y - 100
        cell_w, cell_h = usable_w // COLS, usable_h // ROWS

        for i, urun in enumerate(page_items):
            row, col = i // COLS, i % COLS
            x = margin_x + (col * cell_w)
            y = margin_y + (row * cell_h)
            center_x = x + (cell_w // 2)
            
            try:
                resp = requests.get(urun['img'], timeout=10)
                img = Image.open(BytesIO(resp.content)).convert("RGBA")
                target_h = int(cell_h * 0.55)
                img.thumbnail((cell_w - 40, target_h), Image.LANCZOS)
                img_x = center_x - (img.width // 2)
                img_y = y + 20
                canvas.paste(img, (img_x, img_y), img)
                current_y = img_y + img.height + 20
            except: current_y = y + 100

            lines = wrap_text(urun['title'], kf_title, cell_w - 20, draw)
            if len(lines) > 2: lines = lines[:2]
            for line in lines:
                w = draw.textbbox((0, 0), line, font=kf_title)[2]
                draw.text((center_x - w//2, current_y), line, font=kf_title, fill="black")
                current_y += 45
            
            p_str = f"{int(urun['price']):,}".replace(',', '.') + " ₺"
            pw = draw.textbbox((0, 0), p_str, font=kf_price)[2]
            draw.text((center_x - pw//2, current_y + 10), p_str, font=kf_price, fill="#b30000")

        pages.append((f"Katalog_Sayfa_{page_num+1}.png", canvas))
        
    return pages

# --- ARAYÜZ ---
if st.sidebar.button("🔒 Çıkış Yap"):
    st.session_state.authenticated = False
    st.rerun()

st.title("📱 ETP Ticaret Fiyatlı Katalog Oluşturucu")

# Yan Menü
st.sidebar.header("⚙️ Ayarlar & Filtreler")
default_urls = [
    "https://www.etpticaret.com/merchant-1.xml",
    "https://www.etpticaret.com/merchant-2.xml",
    "https://www.etpticaret.com/merchant-3.xml"
]
xml_urls = st.sidebar.text_area("XML Linkleri", value="\n".join(default_urls), height=100).split('\n')
xml_urls = [u.strip() for u in xml_urls if u.strip()]

output_mode = st.sidebar.radio("Çıktı Modu", ["Tekli Görsel (Sosyal Medya)", "Toplu Katalog (A4)"])

search_query = st.sidebar.text_input("🔍 Ürün Adı (Virgülle çoklu)", placeholder="şampuan, krem")
stock_option = st.sidebar.selectbox("📦 Stok Durumu", ["Tümü", "Sadece Stokta Olanlar"])
min_price = st.sidebar.number_input("Min Fiyat", min_value=0, value=0)
max_price = st.sidebar.number_input("Max Fiyat", min_value=0, value=99999)
sort_option = st.sidebar.selectbox("Sıralama", ["XML Sırası", "Fiyat Artan", "Fiyat Azalan"])

if st.sidebar.button("🚀 Verileri Getir", type="primary"):
    st.session_state['filtered_products'] = []
    with st.spinner("Veriler çekiliyor..."):
        all_products = get_xml_data(xml_urls)
        filtered = []
        for p in all_products:
            if not (min_price <= p['price'] <= max_price): continue
            if stock_option == "Sadece Stokta Olanlar" and p.get('stock') != 'in stock': continue
            if search_query:
                keywords = [k.strip().lower() for k in search_query.split(',') if k.strip()]
                if not any(k in p['title'].lower() for k in keywords): continue
            filtered.append(p)
            
        if sort_option == "Fiyat Artan": filtered.sort(key=lambda x: x['price'])
        elif sort_option == "Fiyat Azalan": filtered.sort(key=lambda x: x['price'], reverse=True)
            
        st.session_state['filtered_products'] = filtered
        if filtered:
            st.success(f"{len(filtered)} ürün bulundu! İşlem yapmaya hazır.")
        else:
            st.warning("Kriterlere uygun ürün bulunamadı.")

# --- SONUÇLAR ---
if 'filtered_products' in st.session_state and st.session_state['filtered_products']:
    products = st.session_state['filtered_products']
    count = len(products)
    
    st.divider()
    
    # MOD 1: TEKLİ GÖRSELLER
    if output_mode == "Tekli Görsel (Sosyal Medya)":
        st.subheader(f"📸 Tekli Mod: {count} Ürün")
        
        # ZIP İndirme
        if st.button(f"📦 TÜMÜNÜ ZIP OLARAK İNDİR ({count} Adet)", type="primary"):
            progress_bar = st.progress(0)
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for i, prod in enumerate(products):
                    img = generate_single_image(prod)
                    if img:
                        buf = BytesIO()
                        img.save(buf, format="PNG")
                        safe_name = re.sub(r'[\\/*?:"<>|]', "", prod['id'])
                        zf.writestr(f"{safe_name}.png", buf.getvalue())
                    progress_bar.progress((i + 1) / count)
            st.download_button("✅ ZIP DOSYASINI İNDİR", data=zip_buffer.getvalue(), file_name="sosyal_medya_gorselleri.zip", mime="application/zip")

        st.markdown("---")
        st.info("👇 Aşağıdan görselleri tek tek görüp indirebilirsiniz:")
        
        for prod in products[:50]:
            with st.container():
                c1, c2 = st.columns([1, 2])
                with c1:
                    if st.button(f"Görseli Oluştur: {prod['id']}", key=f"btn_{prod['id']}"):
                        st.session_state[f"img_{prod['id']}"] = generate_single_image(prod)
                    
                    if f"img_{prod['id']}" in st.session_state and st.session_state[f"img_{prod['id']}"]:
                        img_preview = st.session_state[f"img_{prod['id']}"]
                        st.image(img_preview, use_container_width=True)
                        
                        buf = BytesIO()
                        img_preview.save(buf, format="PNG")
                        st.download_button(
                            label="⬇️ Görseli İndir",
                            data=buf.getvalue(),
                            file_name=f"{prod['id']}.png",
                            mime="image/png",
                            key=f"dl_{prod['id']}"
                        )

                with c2:
                    st.write(f"**{prod['title']}**")
                    st.write(f"💰 {int(prod['price']):,} ₺".replace(',', '.'))
                    st.write(f"Stok Kodu: {prod['id']}")
                st.divider()

    # MOD 2: KATALOG
    else:
        st.subheader(f"📑 Katalog Modu: {count} Ürün")
        
        if st.button("📑 KATALOGU OLUŞTUR", type="primary"):
            with st.spinner("Katalog sayfaları hazırlanıyor..."):
                st.session_state['catalog_pages'] = generate_catalog_pages(products)
        
        if 'catalog_pages' in st.session_state and st.session_state['catalog_pages']:
            pages = st.session_state['catalog_pages']
            
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for filename, img_obj in pages:
                    buf = BytesIO()
                    img_obj.save(buf, format="PNG")
                    zf.writestr(filename, buf.getvalue())
            
            st.download_button("📦 HEPSİNİ ZIP OLARAK İNDİR", data=zip_buffer.getvalue(), file_name="etp_katalog.zip", mime="application/zip")
            st.divider()
            
            st.write(f"Toplam {len(pages)} sayfa oluşturuldu. Aşağıdan tek tek indirebilirsiniz:")
            
            for i, (filename, img_obj) in enumerate(pages):
                with st.container():
                    st.write(f"#### 📄 Sayfa {i+1}")
                    st.image(img_obj, caption=f"Katalog Sayfa {i+1}", use_container_width=True)
                    
                    buf = BytesIO()
                    img_obj.save(buf, format="PNG")
                    st.download_button(
                        label=f"⬇️ Sayfa {i+1} İndir",
                        data=buf.getvalue(),
                        file_name=filename,
                        mime="image/png",
                        key=f"dl_page_{i}"
                    )
                    st.divider()
