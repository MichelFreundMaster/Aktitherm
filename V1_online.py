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
    [
        "Ton",
        "Lehm",
        "Kies",
        "Grundwasser",
        "Beispiel Hüllhorst"
    ]
)

# =====================================================
# BODENPARAMETER
# =====================================================

boden_dict = {
    "Ton": ("Ton.png", 1.0),
    "Lehm": ("Lehm.png", 1.3),
    "Kies": ("Kies.png", 2.0),
    "Grundwasser": ("Grundwasser.png", 2.5),

    # Beispiel Hüllhorst
    "Beispiel Hüllhorst": ("Schichtenverzeichnis Hüllhorst.png", None),
}
img_file, lambda_boden = boden_dict[boden]

# =====================================================
# SCHICHTEN HÜLLHORST (Y-BASIERT)
# =====================================================

huellhorst_schichten = [

    # y_start, y_end, lambda

    (326,  416,  1.2),  # Auffüllung / Lehm
    (416,  564,  1.8),  # Mittelsand tonig
    (564,  671,  2.0),  # Feinsand
    (671,  778,  1.0),  # Ton weich
    (778,  883,  1.3),  # Tonstein verwittert
    (883, 1065,  1.1),  # Ton Schluff
    (1065,1460,  1.4),  # Tonstein Ton
]

def tiefe_to_pixel_huellhorst(z_wert):

    for p1, p2, z1, z2 in huellhorst_tiefen:

        if z1 <= z_wert <= z2:

            anteil = (
                (z_wert - z1)
                / (z2 - z1)
            )

            return (
                p1
                + anteil * (p2 - p1)
            ) * scale_factor

    return y2_outer
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

dT = T_fluid - T_ground

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
# THERMISCH AKTIVE GESAMTLÄNGE
# =====================================================

z_aktiv = sum(
    ende - start
    for start, ende in active_ranges
)

z_geometrisch = z_max - z_min

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
# SCHICHTWEISE λ
# =====================================================

if boden == "Beispiel Hüllhorst":

    lambda_profile = np.ones(img_np.shape[0])

    for y_start_layer, y_end_layer, lambda_layer in huellhorst_schichten:

        y_start_layer = int(y_start_layer * scale_factor)
        y_end_layer = int(y_end_layer * scale_factor)

        y_start_local = max(0, y_start_layer - y1_adj)
        y_end_local = max(0, y_end_layer - y1_adj)

        lambda_profile[
            y_start_local:y_end_local
        ] = lambda_layer

    # weiche Übergänge
    kernel_size = 35

    kernel = np.ones(kernel_size) / kernel_size

    lambda_profile = np.convolve(
        lambda_profile,
        kernel,
        mode="same"
    )

else:

    lambda_profile = np.ones(img_np.shape[0]) * lambda_boden
# =====================================================
# BODENABHÄNGIGE AUSBREITUNG
# =====================================================

boden_breiten = {
    "Ton": 120,
    "Lehm": 180,
    "Kies": 260,
    "Grundwasser": 340,

    # Hüllhorst
    "Beispiel Hüllhorst": 220
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
            # lokale Wärmeausbreitung je Schicht
            local_radius = (
                heat_radius
                * lambda_profile[
                    min(i, len(lambda_profile)-1)
                ]
                / 1.5
            )

            # Mindestwert gegen Kollaps
            local_radius = max(local_radius, 60)

            r_norm = dist / local_radius
            if dist == 0:

                value = dT_bentonit

            else:

                value = dT_bentonit * np.exp(
                    -k * r_norm
                )

            heatmap[i, x] = value
# =====================================================
# BREITER WÄRMEBEREICH AM SONDENFUSS
# =====================================================

# tatsächliche Breite des U-Bogens
x_left_bottom = x1_outer
x_right_bottom = x2_outer

# Mittelpunkt unten
x_center_bottom = int((x_left_bottom + x_right_bottom) / 2)

# Höhe Sondenfuß
y_bottom = y2_outer

# zusätzliche Ausbreitung
bottom_radius = int(heat_radius * 0.65)

for y in range(height_total):

    y_global = y1_adj + y

    # nur unterhalb des Sondenfußes
    if y_global >= y_bottom:

        for x in range(
            max(0, x_left_bottom - bottom_radius),
            min(img_np.shape[1], x_right_bottom + bottom_radius)
        ):

            # -------------------------------------------------
            # INNERHALB DER U-BREITE
            # -> volle Temperatur
            # -------------------------------------------------

            if x_left_bottom <= x <= x_right_bottom:

                dist = y_global - y_bottom

            # -------------------------------------------------
            # LINKS AUSSERHALB
            # -------------------------------------------------

            elif x < x_left_bottom:

                dx = x_left_bottom - x
                dy = y_global - y_bottom

                dist = np.sqrt(dx**2 + dy**2)

            # -------------------------------------------------
            # RECHTS AUSSERHALB
            # -------------------------------------------------

            else:

                dx = x - x_right_bottom
                dy = y_global - y_bottom

                dist = np.sqrt(dx**2 + dy**2)

            # -------------------------------------------------
            # TEMPERATUR
            # -------------------------------------------------

            local_bottom_radius = (
                bottom_radius
                * lambda_profile[
                    min(y, len(lambda_profile)-1)
                ]
                / 1.2
            )

            local_bottom_radius = max(
                local_bottom_radius,
                60
            )

            r_norm = dist / local_bottom_radius

            value = dT_bentonit * np.exp(
                -2.2 * r_norm
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
    int(28 * scale_factor)
)

font_big = ImageFont.truetype(
    font_path,
    int(28 * scale_factor)
)

# =====================================================
# TIEFENSKALA
# =====================================================

x_scale = x1 - 80

ticks = np.linspace(z_min, z_max, 6)

if boden != "Beispiel Hüllhorst":
    
    for t in ticks:

        if boden == "Beispiel Hüllhorst":

    y = tiefe_to_pixel_huellhorst(t)

else:

    y = y1_adj + (
        (t - z_min)
        / (z_max - z_min)
        * (y2_adj - y1_adj)
    )

        draw.line(
            (x_scale, y, x_scale + 15, y),
            fill="white",
            width=3
        )

        draw.text(
            (x_scale - 90, y - 15),
            f"{int(t)}",
            fill="white",
            font=font
        )

# =====================================================
# LABEL TIEFE
# =====================================================

if boden != "Beispiel Hüllhorst":

    y_center_scale = (y1_adj + y2_adj) / 2

    draw.text(
        (x_scale - 300, int(y_center_scale - 20)),
        "Tiefe [m]",
        fill="white",
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

x_cb = x2 + 970

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
        fill="white",
        font=font
    )

draw.text(
    (x_cb, y_cb - 60),
    "ΔT [K]",
    fill="white",
    font=font
)

# =====================================================
# LÄNGENANGABEN
# =====================================================

y_info = y2_outer + 100

draw.text(
    (100, y_info),
    f"Geometrische Länge: {z_geometrisch:.1f} m",
    fill="white",
    font=font
)

draw.text(
    (1100, y_info),
    f"Thermisch aktive Länge: {z_aktiv:.1f} m",
    fill="white",
    font=font
)

# =====================================================
# AKTIVE BEREICHE
# =====================================================

for i, (z_start, z_ende) in enumerate(active_ranges):

    if boden == "Beispiel Hüllhorst":

    y_start = tiefe_to_pixel_huellhorst(
        z_start
    )

    y_ende = tiefe_to_pixel_huellhorst(
        z_ende
    )

else:

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
        fill="white",
        width=4
    )

    draw.line(
        (x_left, y_ende, x_right, y_ende),
        fill="white",
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

    # =====================================================
    # TECHNISCHE BEMASSUNG
    # =====================================================

    # Maßlinie rechts
    x_dim = x_right + 120

    # Pfeilgröße
    arrow_size = 18

    # obere Pfeilspitze
    draw.line(
        [(x_dim, y_start), (x_dim, y_ende)],
        fill="white",
        width=3
    )

    # Pfeil oben
    draw.line(
        [(x_dim, y_start),
         (x_dim - arrow_size, y_start + arrow_size)],
        fill="white",
        width=3
    )

    draw.line(
        [(x_dim, y_start),
         (x_dim + arrow_size, y_start + arrow_size)],
        fill="white",
        width=3
    )

    # Pfeil unten
    draw.line(
        [(x_dim, y_ende),
         (x_dim - arrow_size, y_ende - arrow_size)],
        fill="white",
        width=3
    )

    draw.line(
        [(x_dim, y_ende),
         (x_dim + arrow_size, y_ende - arrow_size)],
        fill="white",
        width=3
    )

    # horizontale Anschlusslinien
    draw.line(
        [(x_right, y_start), (x_dim, y_start)],
        fill="white",
        width=2
    )

    draw.line(
        [(x_right, y_ende), (x_dim, y_ende)],
        fill="white",
        width=2
    )

    # tatsächliche Mächtigkeit
    thickness = abs(z_ende - z_start)

    text = f"{thickness:.1f} m"

    bbox = font_big.getbbox(text)

    text_width = bbox[2] - bbox[0]

    y_text = (y_start + y_ende) / 2

    draw.text(
        (
            x_dim - text_width / 2,
            y_text - 20
        ),
        text,
        fill="white",
        font=font_big
    )

    # =====================================================
    # GEDREHTER TEXT
    # =====================================================

    label_text = f"aktiver Bereich {i+1}"

    bbox = font_big.getbbox(label_text)

    label_width = bbox[2] - bbox[0]
    label_height = bbox[3] - bbox[1]

    pad = 40

    txt_img = Image.new(
        "RGBA",
        (label_width + pad, label_height + pad),
        (0, 0, 0, 0)
    )

    txt_draw = ImageDraw.Draw(txt_img)

    txt_draw.text(
        (pad // 2, pad // 2),
        label_text,
        fill="white",
        font=font_big
    )

    txt_img = txt_img.rotate(
        90,
        expand=True
    )

    result.paste(
        txt_img,
        (
            int(x_dim - 250),
            int(y_text - txt_img.height / 2)
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
