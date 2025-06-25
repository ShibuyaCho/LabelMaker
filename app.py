import streamlit as st
import pandas as pd
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import Color, black
from reportlab.lib.utils import ImageReader
import qrcode
import re

# Constants for Avery 8463 labels
LABEL_W = 4 * inch
LABEL_H = 2 * inch
COLS, ROWS = 2, 5
LEFT_MARGIN = 0.1875 * inch
TOP_MARGIN = 0.5 * inch
H_GAP = 0.125 * inch
QR_SIZE = 50
QR_GAP = 5
STR_FONT = ("Helvetica-Bold", 22)
STR_LINE_GAP = 6
Y_SHIFT = 35
THC_FONT = ("Helvetica-Bold", 18)
THC_MARGIN = 4
PRICE_FONT = ("Helvetica-Bold", 20)
FARM_FONT = ("Helvetica-Bold", 14)
PRICE_COLORS = {"Sativa": Color(1,0,0), "Indica": Color(0.5,0,0.5), "Hybrid": Color(0,0.5,0)}

def get_suffix(s):
    if "Gram" in s: return "/g"
    if "Ounce" in s: return "/oz"
    return ""

def wrap_text(text, max_w, font, size, c):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if c.stringWidth(test, font, size) <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines

def generate_pdf(df: pd.DataFrame) -> bytes:
    # Sort and duplicate for pairs
    df = df.sort_values("Product Name").reset_index(drop=True)
    df2 = pd.concat([df, df], ignore_index=True)
    order = [i for pair in [(i, i+len(df)) for i in range(len(df))] for i in pair]
    df_final = df2.iloc[order].reset_index(drop=True)

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    for idx, row in df_final.iterrows():
        col = idx % COLS
        rn = (idx // COLS) % ROWS
        if idx and idx % (COLS*ROWS) == 0:
            c.showPage()
        x0 = LEFT_MARGIN + col*(LABEL_W + H_GAP)
        y0 = letter[1] - TOP_MARGIN - rn*LABEL_H
        cx, cy = x0 + LABEL_W/2, y0 - LABEL_H/2

        name = row["Product Name"]
        thc_text = f"THC: {row['% THC']}%"
        price_raw = row["Price Profile Name"]
        num = re.sub(r"\D","", price_raw)
        price_num = f"{int(num):.2f}" if num else ""
        suffix = get_suffix(price_raw)
        is_deal = "Deal" in price_raw
        farm = row.get("Farm", row.get("Supplier Name", ""))
        variant = row["Variant Type"]
        price_color = PRICE_COLORS.get(variant, black)
        sku = row["SKU"]

        c.saveState()
        c.translate(cx, cy)
        c.rotate(90)

        # Vertical anchors
        top_y = LABEL_H/2 - 10
        bottom_y = -LABEL_W/2 + QR_SIZE + QR_GAP

        # Strain
        lines = wrap_text(name, LABEL_H - 20, STR_FONT[0], STR_FONT[1], c)
        y = top_y + Y_SHIFT
        c.setFont(*STR_FONT)
        for line in lines:
            c.drawCentredString(0, y, line)
            y -= STR_FONT[1] + STR_LINE_GAP

        # THC
        y_thc = y - THC_MARGIN
        c.setFont(*THC_FONT)
        c.drawCentredString(0, y_thc, thc_text)

        # Price / Deal
        avail = y_thc - bottom_y
        gap = avail / 3
        y_price = y_thc - gap
        c.setFont(*PRICE_FONT)
        if is_deal:
            w2 = c.stringWidth("2 OZ", *PRICE_FONT)
            wD = c.stringWidth("Deal", *PRICE_FONT)
            sx = -(w2 + wD + 5)/2
            c.setFillColor(price_color); c.drawString(sx, y_price, "2 OZ")
            c.setFillColor(black);       c.drawString(sx+w2+5, y_price, "Deal")
        else:
            wd = c.stringWidth("$", *PRICE_FONT)
            wn = c.stringWidth(price_num, *PRICE_FONT)
            ws = c.stringWidth(suffix, *PRICE_FONT)
            sx = -(wd + wn + ws)/2
            c.setFillColor(black);       c.drawString(sx, y_price, "$")
            c.setFillColor(price_color); c.drawString(sx+wd, y_price, price_num)
            c.setFillColor(black);       c.drawString(sx+wd+wn, y_price, suffix)

        # Farm
        y_farm = y_price - gap
        c.setFont(*FARM_FONT)
        for fl in wrap_text(farm, LABEL_H - 20, FARM_FONT[0], FARM_FONT[1], c)[:2]:
            c.drawCentredString(0, y_farm, fl)
            y_farm -= FARM_FONT[1] + 2

        # QR
        qr_buf = BytesIO()
        qrcode.make(sku).save(qr_buf, format="PNG")
        qr_buf.seek(0)
        qr_x = -QR_SIZE/2
        qr_y = y_farm - QR_SIZE - QR_GAP
        c.drawImage(ImageReader(qr_buf), qr_x, qr_y, QR_SIZE, QR_SIZE)

        c.restoreState()

    c.save()
    buffer.seek(0)
    return buffer.getvalue()

st.title("Avery 8463 Label Generator")
uploaded = st.file_uploader("Upload inventory CSV", type=["csv"])
if uploaded:
    df = pd.read_csv(uploaded)
    pdf_bytes = generate_pdf(df)
    st.download_button("Download Labels PDF", data=pdf_bytes, file_name="labels.pdf", mime="application/pdf")
