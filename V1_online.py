import streamlit as st

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

uploaded_file = st.file_uploader("Excel-Datei hochladen", type=["xlsx"])

dT_min = st.slider("ΔT_min [K]", 1, 6, 5, step=1)
T_fluid = st.slider("Fluidtemperatur [°C]", 15, 40, 15, step=5)
boden = st.selectbox(
    "Untergrund auswählen",
    ["Ton", "Lehm", "Kies", "Grundwasser"]
)
# -----------------------
# BODENPARAMETER
# -----------------------
boden_dict = {
    "Ton": ("Ton.png", 1.0),
    "Lehm": ("Lehm.png", 1.3),
    "Kies": ("Kies.png", 2.0),
    "Grundwasser": ("Grundwasser.png", 2.5),
}

img_file, lambda_boden = boden_dict[boden]

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

# -----------------------
# DATEIEN
# -----------------------
import os

base_dir = os.path.dirname(__file__)
img_path = os.path.join(base_dir, img_file)
excel_path = "Tiefenprofil.xlsx"

# -----------------------
# KOORDINATEN SONDE
# -----------------------
x1, y1 = 371, 271
x2, y2 = 475, 1241

# -----------------------
# VORLAUF-KOORDINATEN
# -----------------------
x1_vl = 456
y1_vl = 326

x2_vl = 468
y2_vl = 1266

# -----------------------
# DATEN EINLESEN
# -----------------------
if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
else:
    st.info("Bitte Excel-Datei hochladen")
    st.stop()
z = df.iloc[:, 0].values
T_ground = df.iloc[:, 1].values
dT = (T_fluid - T_ground) / lambda_boden

if np.max(dT) < dT_min:
    st.error("Temperaturdifferenz zu klein für einen Temperaturübergang")
    st.stop()

z_min = min(z)
z_max = max(z)

# -----------------------
# AKTIVER BEREICH
# -----------------------
mask = dT >= dT_min

active_ranges = []

in_range = False

for i in range(len(z)):
    if mask[i] and not in_range:
        start = z[i]
        in_range = True

    elif not mask[i] and in_range:
        end = z[i-1]
        active_ranges.append((start, end))
        in_range = False

# falls Bereich bis zum Ende geht
if in_range:
    active_ranges.append((start, z[-1]))

# -----------------------
# BILD LADEN + UPSCALE
# -----------------------
img = Image.open(img_path).convert("RGBA")

scale_factor = 2
img = img.resize((img.width * scale_factor, img.height * scale_factor), Image.LANCZOS)

img_np = np.array(img)

x1 *= scale_factor
x2 *= scale_factor
y1 *= scale_factor
y2 *= scale_factor
x1_vl *= scale_factor
x2_vl *= scale_factor
y1_vl *= scale_factor
y2_vl *= scale_factor
# -----------------------
# INNERE SONDE
# -----------------------
offset = 12
x1_inner = x1 + offset
x2_inner = x2 - offset

# -----------------------
# WÄRMEBILD ERZEUGEN
# -----------------------
height = y2 - y1
top_offset = 110
bottom_offset = 10

y1_adj = y1 + top_offset
y2_adj = y2 - bottom_offset

height = y2_adj - y1_adj

# -----------------------
# BREITE JE NACH BODEN
# -----------------------
boden_breiten = {
    "Ton": 120,
    "Lehm": 180,
    "Kies": 260,
    "Grundwasser": 340
}

heat_radius = int(boden_breiten[boden] * scale_factor)

# -----------------------
# INTERPOLATION
# -----------------------
z_new = np.linspace(z_min, z_max, height)
dT_interp = np.interp(z_new, z, dT)

# -----------------------
# LEERES WÄRMEBILD
# -----------------------
heatmap = np.zeros((height, img_np.shape[1]))

# Mittelpunkt Vorlauf
x_center_vl = int((x1_vl + x2_vl) / 2)

# radialer Verlauf
k = 3.0

for i in range(height):

    for x in range(
        max(0, x_center_vl - heat_radius),
        min(img_np.shape[1], x_center_vl + heat_radius)
    ):

        r = abs(x - x_center_vl) / heat_radius

        value = dT_interp[i] * np.exp(-k * r)

        heatmap[i, x] = value

# -----------------------
# FARBEN
# -----------------------
vmin = 0
vmax = 20

norm = np.clip((heatmap - vmin) / (vmax - vmin), 0, 1)

gamma = 0.7
norm = norm**gamma

cmap = plt.get_cmap("turbo")

heat_rgba = (cmap(norm) * 255).astype(np.uint8)

# Transparenz nur dort, wo Wärme vorhanden
heat_rgba[..., 3] = np.where(
    heatmap > 0.05,
    180,
    0
)

# -----------------------
# OVERLAY
# -----------------------
alpha_map = heat_rgba[..., 3:4] / 255.0

img_np[y1_adj:y2_adj, :] = (
    heat_rgba[..., :4] * alpha_map
    + img_np[y1_adj:y2_adj, :] * (1 - alpha_map)
).astype(np.uint8)

result = Image.fromarray(img_np)

# Grenzen für Schraffur
x_left = x_center_vl - heat_radius
x_right = x_center_vl + heat_radius

# -----------------------
# ZEICHNEN
# -----------------------
draw = ImageDraw.Draw(result)

import os

font_path = os.path.join(os.path.dirname(__file__), "DejaVuSans.ttf")

font = ImageFont.truetype(font_path, int(20 * scale_factor))
font_big = ImageFont.truetype(font_path, int(20 * scale_factor))
# -----------------------
# TIEFENSKALA
# -----------------------
x_scale = x1 - 80

ticks = np.linspace(z_min, z_max, 6)

for t in ticks:
    y = y1_adj + (t - z_min) / (z_max - z_min) * (y2_adj - y1_adj)
    draw.line((x_scale, y, x_scale + 15, y), fill="black", width=3)
    draw.text((x_scale - 90, y - 15), f"{int(t)}", fill="black", font=font)

y_center_scale = (y1_adj + y2_adj) / 2

draw.text(
    (x_scale - 300, int(y_center_scale - 20)),
    "Tiefe [m]",
    fill="black",
    font=font
)

# -----------------------
# FARBSKALA
# -----------------------
cb_total_height = y2_adj - y1_adj
cb_height = int(cb_total_height * 0.7)
cb_width = 50

y_cb = int(y1_adj + (cb_total_height - cb_height) / 2)

cb = np.linspace(vmin, vmax, cb_height)
cb_img = np.tile(cb[:, np.newaxis], (1, cb_width))

norm_cb = np.clip((cb_img - vmin) / (vmax - vmin), 0, 1)
norm_cb = norm_cb**gamma

cb_rgba = (cmap(norm_cb) * 255).astype(np.uint8)

cb_pil = Image.fromarray(cb_rgba)

x_cb = x2 + 280
result.paste(cb_pil, (x_cb, y_cb))

draw = ImageDraw.Draw(result)

ticks = np.linspace(vmin, vmax, 5)

for t in ticks:
    y = y_cb + (t - vmin) / (vmax - vmin) * cb_height
    draw.text((x_cb + 70, y - 15), f"{t:.0f}", fill="black", font=font)

draw.text((x_cb, y_cb - 60), "ΔT [K]", fill="black", font=font)

# -----------------------
# AKTIVER BEREICH
# -----------------------
for i, (z_start, z_ende) in enumerate(active_ranges):

    # ---- Umrechnung in Pixel ----
    y_start = y1_adj + (z_start - z_min) / (z_max - z_min) * (y2_adj - y1_adj)
    y_ende  = y1_adj + (z_ende  - z_min) / (z_max - z_min) * (y2_adj - y1_adj)
    # ---- Linien ----
    draw.line((x_left, y_start, x_right, y_start), fill="black", width=4)
    draw.line((x_left, y_ende,  x_right, y_ende),  fill="black", width=4)

    # ---- SCHRAFFUR ----
    spacing = 20
    color = (0, 0, 0, 255)

    overlay = Image.new("RGBA", result.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    dx = x_right - x_left

    for y in range(int(y_start - dx), int(y_ende), spacing):

        x0 = x_left
        y0 = y

        x1_line = x_right
        y1_line = y + dx

        # clipping unten
        if y1_line > y_ende:
            diff = y1_line - y_ende
            x1_line -= diff
            y1_line = y_ende

        # clipping oben
        if y0 < y_start:
            diff = y_start - y0
            x0 += diff
            y0 = y_start

        overlay_draw.line(
            [(x0, y0), (x1_line, y1_line)],
            fill=color,
            width=1
        )

    result = Image.alpha_composite(result.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(result)

    # ---- BESCHRIFTUNG ----
    text = f"aktiver Bereich {i+1}"

    bbox = font_big.getbbox(text)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    pad = 40

    txt_img = Image.new("RGBA", (text_width + pad, text_height + pad), (0,0,0,0))
    txt_draw = ImageDraw.Draw(txt_img)

    txt_draw.text((pad//2, pad//2), text, fill="black", font=font_big)

    txt_img = txt_img.rotate(90, expand=True)

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
# -----------------------
# SPEICHERN
# -----------------------
result.save("thermische_Aktivität_T15_Ort.png", dpi=(300,300))

st.image(result, caption="Thermische Aktivität")
