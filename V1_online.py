import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
import os

# =====================================================
# UI
# =====================================================

st.markdown("""
    <style>
    html, body, [class*="css"]  {
        font-size: 18px !important;
    }
    </style>
""", unsafe_allow_html=True)

PASSWORD = "Master"

pwd = st.text_input("Passwort eingeben", type="password")

if pwd != PASSWORD:
    st.stop()

st.title("Visualisierung thermischer Aktivität")

uploaded_file = st.file_uploader(
    "Excel-Datei hochladen",
    type=["xlsx"]
)

dT_min = st.slider(
    "ΔT_min [K]",
    1, 6, 5,
    step=1
)

T_fluid = st.slider(
    "Fluidtemperatur [°C]",
    15, 40, 15,
    step=5
)

boden = st.selectbox(
    "Untergrund auswählen",
    ["Ton", "Lehm", "Kies", "Grundwasser"]
)

# =====================================================
# BODENPARAMETER
# =====================================================

boden_dict = {
    "Ton": ("Ton.png", 1.0),
    "Lehm": ("Lehm.png", 1.3),
    "Kies": ("Kies.png", 2.0),
    "Grundwasser": ("Grundwasser.png", 2.5),
}

img_file, lambda_boden = boden_dict[boden]

# =====================================================
# DATEIEN
# =====================================================

base_dir = os.path.dirname(__file__)

img_path = os.path.join(base_dir, img_file)
font_path = os.path.join(base_dir, "DejaVuSans.ttf")

# =====================================================
# KOORDINATEN
# =====================================================

# Sonde gesamt
x1, y1 = 371, 271
x2, y2 = 475, 1325

# Äußerer Bentonit
x1_outer = 416
y1_outer = 323

x2_outer = 581
y2_outer = 1348

# Innerer Ausschlussbereich
x1_inner_cut = 443
y1_inner_cut = 323

x2_inner_cut = 554
y2_inner_cut = 1321

# =====================================================
# DATEN EINLESEN
# =====================================================

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)

else:
    st.info("Bitte Excel-Datei hochladen")
    st.stop()

z = df.iloc[:, 0].values
T_ground = df.iloc[:, 1].values

# =====================================================
# THERMISCHE DIFFERENZ
# =====================================================

dT = (T_fluid - T_ground) / lambda_boden

if np.max(dT) < dT_min:
    st.error(
        "Temperaturdifferenz zu klein für einen Temperaturübergang"
    )
    st.stop()

z_min = min(z)
z_max = max(z)

# =====================================================
# AKTIVE BEREICHE
# =====================================================

mask = dT >= dT_min

active_ranges = []

in_range = False

for i in range(len(z)):

    if mask[i] and not in_range:
        start = z[i]
        in_range = True

    elif not mask[i] and in_range:
        end = z[i - 1]
        active_ranges.append((start, end))
        in_range = False

if in_range:
    active_ranges.append((start, z[-1]))

# =====================================================
# BILD LADEN
# =====================================================

img = Image.open(img_path).convert("RGBA")

scale_factor = 2

img = img.resize(
    (
        img.width * scale_factor,
        img.height * scale_factor
    ),
    Image.LANCZOS
)

img_np = np.array(img)

# =====================================================
# SKALIERUNG
# =====================================================

x1 *= scale_factor
x2 *= scale_factor
y1 *= scale_factor
y2 *= scale_factor

x1_outer *= scale_factor
y1_outer *= scale_factor
x2_outer *= scale_factor
y2_outer *= scale_factor

x1_inner_cut *= scale_factor
y1_inner_cut *= scale_factor
x2_inner_cut *= scale_factor
y2_inner_cut *= scale_factor

# =====================================================
# VERTIKALER OFFSET
# =====================================================

top_offset = 110
bottom_offset = 10

y1_adj = y1 + top_offset
y2_adj = y2 - bottom_offset

height = y2_adj - y1_adj

# =====================================================
# INTERPOLATION
# =====================================================

# ursprüngliche Höhe der Sonde
height_base = y2_adj - y1_adj

# zusätzliche Höhe für Halbkreis
height = height_base

# Interpolation nur entlang der Sonde
z_new = np.linspace(z_min, z_max, height_base)

dT_interp = np.interp(
    z_new,
    z,
    dT
)

# =====================================================
# WÄRMEFELD
# =====================================================

heatmap = np.zeros(
    (height, img_np.shape[1]),
    dtype=np.float32
)

# =====================================================
# BODENABHÄNGIGE AUSBREITUNG
# =====================================================

boden_breiten = {
    "Ton": 120,
    "Lehm": 180,
    "Kies": 260,
    "Grundwasser": 340
}

heat_radius = int(
    boden_breiten[boden] * scale_factor
)
# zusätzlicher Platz für Halbkreis
height_total = height + heat_radius

# Heatmap jetzt auf neue Höhe erweitern
new_heatmap = np.zeros(
    (height_total, img_np.shape[1]),
    dtype=np.float32
)

new_heatmap[:height, :] = heatmap

heatmap = new_heatmap
# Abklingkonstante
k = 3.0

# Temperatur im äußeren Bentonit konstant
dT_bentonit = np.max(dT_interp)

# =====================================================
# WÄRMEFELD IM ÄUSSEREN BENTONIT
# =====================================================

for i in range(height_total):

    y_global = y1_adj + i

    # -------------------------------------------------
    # VERTIKALER BEREICH
    # -------------------------------------------------

    if y1_outer <= y_global <= y2_outer + heat_radius:

        for x in range(
            max(0, x1_outer - heat_radius),
            min(img_np.shape[1], x2_outer + heat_radius)
        ):

            # -----------------------------------------
            # INNEREN BEREICH AUSSCHNEIDEN
            # -----------------------------------------

            if (
                x1_inner_cut <= x <= x2_inner_cut
                and
                y1_inner_cut <= y_global <= y2_inner_cut
            ):
                continue

            # -----------------------------------------
            # OBERHALB DES SONDENFUSSES
            # -> vertikale Ausbreitung
            # -----------------------------------------

            if y_global <= y2_outer:

                if x < x1_outer:
                    dist = x1_outer - x

                elif x > x2_outer:
                    dist = x - x2_outer

                else:
                    dist = 0

            # -----------------------------------------
            # UNTERHALB DES SONDENFUSSES
            # -> radial / halbrund
            # -----------------------------------------

            else:

                dx_circle = x - ((x1_outer + x2_outer) / 2)
                dy_circle = y_global - y2_outer

                dist = np.sqrt(
                    dx_circle**2 + dy_circle**2
                )

            # -----------------------------------------
            # TEMPERATURFELD
            # -----------------------------------------

            r_norm = dist / heat_radius

            if dist == 0:

                value = dT_bentonit

            else:

                value = dT_bentonit * np.exp(
                    -k * r_norm
                )

            heatmap[i, x] = value
# =====================================================
# ZUSÄTZLICHER HALBKREIS UNTEN
# =====================================================

x_center_circle = int((x1_outer + x2_outer) / 2)

y_center_circle = y2_outer - y1_adj

circle_radius = (x2_outer - x1_outer) // 2 + heat_radius

for y in range(height_total):

    for x in range(
        max(0, x_center_circle - circle_radius),
        min(img_np.shape[1], x_center_circle + circle_radius)
    ):

        dx = x - x_center_circle
        dy = y - y_center_circle

        r = np.sqrt(dx**2 + dy**2)

        # nur untere Hälfte
        if r <= circle_radius and y >= y_center_circle:

            value = dT_bentonit * np.exp(
                -2.2 * r / circle_radius
            )

            heatmap[y, x] = max(
                heatmap[y, x],
                value
            )                     
# =====================================================
# FARBMAPPING
# =====================================================

vmin = 0
vmax = 20

norm = np.clip(
    (heatmap - vmin) / (vmax - vmin),
    0,
    1
)

gamma = 0.7
norm = norm ** gamma

cmap = plt.get_cmap("turbo")

heat_rgba = (
    cmap(norm) * 255
).astype(np.uint8)

# =====================================================
# TRANSPARENZ
# =====================================================

alpha_strength = (norm * 220).astype(np.uint8)

heat_rgba[..., 3] = np.where(
    heatmap > 0.03,
    alpha_strength,
    0
)
# =====================================================
# OVERLAY
# =====================================================

alpha_map = heat_rgba[..., 3:4] / 255.0

y_end_overlay = min(
    y1_adj + height_total,
    img_np.shape[0]
)

overlay_height = y_end_overlay - y1_adj

img_np[y1_adj:y_end_overlay, :] = (
    heat_rgba[:overlay_height, :, :4]
    * alpha_map[:overlay_height]
    + img_np[y1_adj:y_end_overlay, :]
    * (1 - alpha_map[:overlay_height])
).astype(np.uint8)

result = Image.fromarray(img_np)

# =====================================================
# GRENZEN AKTIVER BEREICH
# =====================================================

x_left = x1_outer - heat_radius
x_right = x2_outer + heat_radius

# =====================================================
# ZEICHNEN
# =====================================================

draw = ImageDraw.Draw(result)

font = ImageFont.truetype(
    font_path,
    int(20 * scale_factor)
)

font_big = ImageFont.truetype(
    font_path,
    int(20 * scale_factor)
)

# =====================================================
# TIEFENSKALA
# =====================================================

x_scale = x1 - 80

ticks = np.linspace(z_min, z_max, 6)

for t in ticks:

    y = y1_adj + (
        (t - z_min)
        / (z_max - z_min)
        * (y2_adj - y1_adj)
    )

    draw.line(
        (x_scale, y, x_scale + 15, y),
        fill="black",
        width=3
    )

    draw.text(
        (x_scale - 90, y - 15),
        f"{int(t)}",
        fill="black",
        font=font
    )

# =====================================================
# LABEL TIEFE
# =====================================================

y_center_scale = (y1_adj + y2_adj) / 2

draw.text(
    (x_scale - 300, int(y_center_scale - 20)),
    "Tiefe [m]",
    fill="black",
    font=font
)

# =====================================================
# FARBSKALA
# =====================================================

cb_total_height = height_total

cb_height = int(cb_total_height * 0.7)
cb_width = 50

y_cb = int(
    y1_adj + (cb_total_height - cb_height) / 2
)

cb = np.linspace(vmin, vmax, cb_height)

cb_img = np.tile(
    cb[:, np.newaxis],
    (1, cb_width)
)

norm_cb = np.clip(
    (cb_img - vmin) / (vmax - vmin),
    0,
    1
)

norm_cb = norm_cb ** gamma

cb_rgba = (
    cmap(norm_cb) * 255
).astype(np.uint8)

cb_pil = Image.fromarray(cb_rgba)

x_cb = x2 + 280

result.paste(
    cb_pil,
    (x_cb, y_cb)
)

ticks = np.linspace(vmin, vmax, 5)

for t in ticks:

    y = y_cb + (
        (t - vmin)
        / (vmax - vmin)
        * cb_height
    )

    draw.text(
        (x_cb + 70, y - 15),
        f"{t:.0f}",
        fill="black",
        font=font
    )

draw.text(
    (x_cb, y_cb - 60),
    "ΔT [K]",
    fill="black",
    font=font
)

# =====================================================
# AKTIVE BEREICHE
# =====================================================

for i, (z_start, z_ende) in enumerate(active_ranges):

    y_start = y1_adj + (
        (z_start - z_min)
        / (z_max - z_min)
        * (y2_adj - y1_adj)
    )

    y_ende = y1_adj + (
        (z_ende - z_min)
        / (z_max - z_min)
        * (y2_adj - y1_adj)
    )

    # Linien
    draw.line(
        (x_left, y_start, x_right, y_start),
        fill="black",
        width=4
    )

    draw.line(
        (x_left, y_ende, x_right, y_ende),
        fill="black",
        width=4
    )

    # Schraffur
    spacing = 20
    color = (0, 0, 0, 255)

    overlay = Image.new(
        "RGBA",
        result.size,
        (0, 0, 0, 0)
    )

    overlay_draw = ImageDraw.Draw(overlay)

    dx = x_right - x_left

    for y in range(
        int(y_start - dx),
        int(y_ende),
        spacing
    ):

        x0 = x_left
        y0 = y

        x1_line = x_right
        y1_line = y + dx

        if y1_line > y_ende:

            diff = y1_line - y_ende

            x1_line -= diff
            y1_line = y_ende

        if y0 < y_start:

            diff = y_start - y0

            x0 += diff
            y0 = y_start

        overlay_draw.line(
            [(x0, y0), (x1_line, y1_line)],
            fill=color,
            width=1
        )

    result = Image.alpha_composite(
        result.convert("RGBA"),
        overlay
    )

    draw = ImageDraw.Draw(result)

    # Beschriftung
    text = f"aktiver Bereich {i+1}"

    bbox = font_big.getbbox(text)

    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    pad = 40

    txt_img = Image.new(
        "RGBA",
        (text_width + pad, text_height + pad),
        (0, 0, 0, 0)
    )

    txt_draw = ImageDraw.Draw(txt_img)

    txt_draw.text(
        (pad // 2, pad // 2),
        text,
        fill="black",
        font=font_big
    )

    txt_img = txt_img.rotate(
        90,
        expand=True
    )

    y_center = (y_start + y_ende) / 2

    x_text = x_right - 100

    result.paste(
        txt_img,
        (
            int(x_text - txt_img.width / 2),
            int(y_center - txt_img.height / 2)
        ),
        txt_img
    )

# =====================================================
# SPEICHERN
# =====================================================

result.save(
    "thermische_Aktivität_T15_Ort.png",
    dpi=(300, 300)
)

# =====================================================
# AUSGABE
# =====================================================

st.image(
    result,
    caption="Thermische Aktivität"
)
