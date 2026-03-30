import streamlit as st
import serial
import time
import pandas as pd
import io
import qrcode
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak
)
from reportlab.lib.utils import ImageReader

# ══════════════════════════════════════════════════════════════════════════════
# LAND UNIT CONVERSION  (Jharkhand standard)
# ══════════════════════════════════════════════════════════════════════════════
BIGHA_PER_ACRE  = 1.613
KATTHA_PER_ACRE = 32.26

def to_acres(value, unit):
    if unit == "Bigha":  return value / BIGHA_PER_ACRE
    if unit == "Kattha": return value / KATTHA_PER_ACRE
    return value

def acres_display(a):
    return (f"{a:.2f} Acres  |  "
            f"{a * BIGHA_PER_ACRE:.2f} Bigha  |  "
            f"{a * KATTHA_PER_ACRE:.2f} Kattha")

# ══════════════════════════════════════════════════════════════════════════════
# SEASONAL & RAINFALL  (Jharkhand)
# ══════════════════════════════════════════════════════════════════════════════
SEASON_MAP = {
    1:"Rabi", 2:"Rabi", 3:"Rabi/Zaid", 4:"Zaid", 5:"Zaid",
    6:"Zaid/Kharif", 7:"Kharif", 8:"Kharif", 9:"Kharif",
    10:"Kharif", 11:"Rabi", 12:"Rabi"
}
MONTH_NAMES = {
    1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",
    7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"
}
# Jharkhand avg rainfall mm/month
JH_RAIN = {
    1:15, 2:20, 3:25, 4:30, 5:50, 6:150,
    7:280, 8:300, 9:200, 10:80, 11:20, 12:10
}
# Sowing months for calendar strip
SOWING_MONTHS = {
    "Kharif":    [6,7,8],
    "Rabi":      [10,11,12],
    "Zaid":      [3,4,5],
    "Year-round":[1,2,3,4,5,6,7,8,9,10,11,12],
}

def is_in_season(crop_seasons, month):
    cur = SEASON_MAP[month]
    for s in crop_seasons:
        if s == "Year-round" or s in cur or cur in s:
            return True
    return False

# ══════════════════════════════════════════════════════════════════════════════
# MSP TREND & MANDI
# ══════════════════════════════════════════════════════════════════════════════
MSP_TREND = {
    "Maize (Makka)":"Up","Paddy (Dhan)":"Up","Wheat (Gehun)":"Up",
    "Mustard (Sarso)":"Up","Arhar / Tur Dal":"Up","Chana (Gram)":"Up",
    "Tomato (Tamatar)":"Stable","Potato (Aloo)":"Down","Onion (Pyaz)":"Stable",
    "Brinjal (Baingan)":"Stable","Cauliflower (Gobhi)":"Stable",
    "Cabbage (Band Gobhi)":"Stable","Okra / Bhindi":"Up",
    "Bitter Gourd (Karela)":"Up","Pumpkin (Kaddu)":"Stable",
    "Spinach (Palak)":"Stable","Mango (Aam)":"Up","Banana (Kela)":"Stable",
    "Papaya (Papita)":"Stable","Guava (Amrud)":"Up",
    "Litchi (Lychee)":"Up","Jackfruit (Kathal)":"Up",
}
MANDI_MAP = {
    "Grain":     "Ranchi APMC Mandi, Namkum",
    "Oilseed":   "Dhanbad Krishi Upaj Mandi",
    "Pulse":     "Ranchi APMC Mandi, Namkum",
    "Vegetable": "Bargain Sabzi Mandi, Ranchi",
    "Fruit":     "Hinoo Fruit Market, Ranchi",
}

# ══════════════════════════════════════════════════════════════════════════════
# CROP DATABASE — 22 crops
# ══════════════════════════════════════════════════════════════════════════════
CROP_DATA = [
    # GRAINS
    {"name":"Maize (Makka)",        "category":"Grain",     "emoji":"🌽",
     "N":120,"P":60, "K":40,  "t_min":18,"t_max":35,"m_min":40,"m_max":80,
     "yield":20,  "msp":2090, "seasons":["Kharif","Zaid"],
     "water_req":4500,"days":90,  "seed_cost":3000,"fert_cost":4000,
     "rain_min":80, "rain_max":300,
     "intercrop":"Arhar / Tur Dal",
     "schemes":["PM-KISAN","PMFBY Crop Insurance","Rashtriya Krishi Vikas Yojana"]},
    {"name":"Paddy (Dhan)",         "category":"Grain",     "emoji":"🌾",
     "N":80, "P":40, "K":40,  "t_min":20,"t_max":38,"m_min":60,"m_max":100,
     "yield":15,  "msp":2183, "seasons":["Kharif"],
     "water_req":9000,"days":120, "seed_cost":2500,"fert_cost":3500,
     "rain_min":150,"rain_max":350,
     "intercrop":"Azolla (green manure)",
     "schemes":["PM-KISAN","PMFBY","PM Krishi Sinchai Yojana"]},
    {"name":"Wheat (Gehun)",        "category":"Grain",     "emoji":"🌾",
     "N":100,"P":50, "K":40,  "t_min":10,"t_max":26,"m_min":30,"m_max":60,
     "yield":12,  "msp":2275, "seasons":["Rabi"],
     "water_req":3500,"days":110, "seed_cost":2000,"fert_cost":3000,
     "rain_min":10, "rain_max":60,
     "intercrop":"Mustard (Sarso)",
     "schemes":["PM-KISAN","PMFBY","National Food Security Mission"]},
    # OILSEEDS
    {"name":"Mustard (Sarso)",      "category":"Oilseed",   "emoji":"🌼",
     "N":60, "P":40, "K":40,  "t_min":10,"t_max":25,"m_min":30,"m_max":50,
     "yield":5,   "msp":5650, "seasons":["Rabi"],
     "water_req":2000,"days":90,  "seed_cost":1500,"fert_cost":2500,
     "rain_min":10, "rain_max":40,
     "intercrop":"Wheat (Gehun)",
     "schemes":["PM-KISAN","NMOOP Oilseed Mission","PMFBY"]},
    # PULSES
    {"name":"Arhar / Tur Dal",      "category":"Pulse",     "emoji":"🫘",
     "N":20, "P":50, "K":20,  "t_min":20,"t_max":35,"m_min":30,"m_max":60,
     "yield":4,   "msp":7000, "seasons":["Kharif"],
     "water_req":2500,"days":150, "seed_cost":2000,"fert_cost":1500,
     "rain_min":60, "rain_max":200,
     "intercrop":"Maize (Makka)",
     "schemes":["PM-KISAN","NFS Mission — Pulses","PMFBY"]},
    {"name":"Chana (Gram)",         "category":"Pulse",     "emoji":"🫘",
     "N":20, "P":60, "K":20,  "t_min":10,"t_max":25,"m_min":25,"m_max":50,
     "yield":6,   "msp":5440, "seasons":["Rabi"],
     "water_req":1800,"days":100, "seed_cost":2500,"fert_cost":1500,
     "rain_min":10, "rain_max":40,
     "intercrop":"Wheat (Gehun)",
     "schemes":["PM-KISAN","PMFBY","NFS Mission — Pulses"]},
    # VEGETABLES
    {"name":"Tomato (Tamatar)",     "category":"Vegetable", "emoji":"🍅",
     "N":100,"P":60, "K":80,  "t_min":15,"t_max":32,"m_min":50,"m_max":80,
     "yield":80,  "msp":800,  "seasons":["Rabi","Zaid"],
     "water_req":5000,"days":70,  "seed_cost":4000,"fert_cost":6000,
     "rain_min":20, "rain_max":80,
     "intercrop":"Cabbage (Band Gobhi)",
     "schemes":["PM-KISAN","Horticulture Mission","PMFBY"]},
    {"name":"Potato (Aloo)",        "category":"Vegetable", "emoji":"🥔",
     "N":120,"P":60, "K":100, "t_min":10,"t_max":25,"m_min":50,"m_max":80,
     "yield":100, "msp":600,  "seasons":["Rabi"],
     "water_req":4500,"days":80,  "seed_cost":8000,"fert_cost":5000,
     "rain_min":15, "rain_max":50,
     "intercrop":"Spinach (Palak)",
     "schemes":["PM-KISAN","PMFBY","Sub-Mission on Agri Mechanization"]},
    {"name":"Onion (Pyaz)",         "category":"Vegetable", "emoji":"🧅",
     "N":80, "P":50, "K":60,  "t_min":13,"t_max":30,"m_min":40,"m_max":70,
     "yield":60,  "msp":800,  "seasons":["Rabi","Kharif"],
     "water_req":3500,"days":90,  "seed_cost":5000,"fert_cost":4000,
     "rain_min":20, "rain_max":100,
     "intercrop":"Tomato (Tamatar)",
     "schemes":["PM-KISAN","PMFBY","National Horticulture Mission"]},
    {"name":"Brinjal (Baingan)",    "category":"Vegetable", "emoji":"🍆",
     "N":100,"P":50, "K":50,  "t_min":20,"t_max":38,"m_min":50,"m_max":75,
     "yield":70,  "msp":700,  "seasons":["Kharif","Zaid"],
     "water_req":4000,"days":65,  "seed_cost":3500,"fert_cost":4500,
     "rain_min":60, "rain_max":200,
     "intercrop":"Okra / Bhindi",
     "schemes":["PM-KISAN","PMFBY","National Horticulture Mission"]},
    {"name":"Cauliflower (Gobhi)",  "category":"Vegetable", "emoji":"🥦",
     "N":120,"P":60, "K":60,  "t_min":10,"t_max":22,"m_min":50,"m_max":75,
     "yield":50,  "msp":600,  "seasons":["Rabi"],
     "water_req":4000,"days":70,  "seed_cost":4000,"fert_cost":5000,
     "rain_min":10, "rain_max":50,
     "intercrop":"Cabbage (Band Gobhi)",
     "schemes":["PM-KISAN","PMFBY","National Horticulture Mission"]},
    {"name":"Cabbage (Band Gobhi)", "category":"Vegetable", "emoji":"🥬",
     "N":100,"P":60, "K":60,  "t_min":10,"t_max":22,"m_min":50,"m_max":75,
     "yield":60,  "msp":500,  "seasons":["Rabi"],
     "water_req":3500,"days":75,  "seed_cost":3500,"fert_cost":4500,
     "rain_min":10, "rain_max":50,
     "intercrop":"Cauliflower (Gobhi)",
     "schemes":["PM-KISAN","PMFBY","National Horticulture Mission"]},
    {"name":"Okra / Bhindi",        "category":"Vegetable", "emoji":"🌿",
     "N":80, "P":40, "K":40,  "t_min":22,"t_max":38,"m_min":45,"m_max":75,
     "yield":30,  "msp":1200, "seasons":["Kharif","Zaid"],
     "water_req":3000,"days":55,  "seed_cost":2500,"fert_cost":3000,
     "rain_min":60, "rain_max":200,
     "intercrop":"Brinjal (Baingan)",
     "schemes":["PM-KISAN","PMFBY","National Horticulture Mission"]},
    {"name":"Bitter Gourd (Karela)","category":"Vegetable", "emoji":"🥒",
     "N":60, "P":40, "K":60,  "t_min":25,"t_max":38,"m_min":50,"m_max":80,
     "yield":25,  "msp":1500, "seasons":["Kharif","Zaid"],
     "water_req":3500,"days":60,  "seed_cost":3000,"fert_cost":3000,
     "rain_min":80, "rain_max":250,
     "intercrop":"Pumpkin (Kaddu)",
     "schemes":["PM-KISAN","PMFBY","National Horticulture Mission"]},
    {"name":"Pumpkin (Kaddu)",      "category":"Vegetable", "emoji":"🎃",
     "N":60, "P":40, "K":50,  "t_min":20,"t_max":38,"m_min":50,"m_max":80,
     "yield":80,  "msp":400,  "seasons":["Kharif","Zaid"],
     "water_req":4000,"days":75,  "seed_cost":2000,"fert_cost":2500,
     "rain_min":80, "rain_max":280,
     "intercrop":"Bitter Gourd (Karela)",
     "schemes":["PM-KISAN","PMFBY","National Horticulture Mission"]},
    {"name":"Spinach (Palak)",      "category":"Vegetable", "emoji":"🥬",
     "N":60, "P":30, "K":40,  "t_min":10,"t_max":24,"m_min":40,"m_max":70,
     "yield":40,  "msp":600,  "seasons":["Rabi"],
     "water_req":2500,"days":40,  "seed_cost":1500,"fert_cost":2000,
     "rain_min":10, "rain_max":50,
     "intercrop":"Potato (Aloo)",
     "schemes":["PM-KISAN","PMFBY","National Horticulture Mission"]},
    # FRUITS
    {"name":"Mango (Aam)",          "category":"Fruit",     "emoji":"🥭",
     "N":60, "P":40, "K":80,  "t_min":22,"t_max":40,"m_min":40,"m_max":75,
     "yield":50,  "msp":2500, "seasons":["Zaid","Kharif"],
     "water_req":3500,"days":120, "seed_cost":10000,"fert_cost":5000,
     "rain_min":80, "rain_max":300,
     "intercrop":"Guava (Amrud)",
     "schemes":["PM-KISAN","National Horticulture Mission","Paramparagat Krishi Vikas Yojana"]},
    {"name":"Banana (Kela)",        "category":"Fruit",     "emoji":"🍌",
     "N":200,"P":60, "K":300, "t_min":20,"t_max":38,"m_min":60,"m_max":85,
     "yield":200, "msp":1200, "seasons":["Year-round"],
     "water_req":8000,"days":300, "seed_cost":15000,"fert_cost":8000,
     "rain_min":80, "rain_max":280,
     "intercrop":"Papaya (Papita)",
     "schemes":["PM-KISAN","National Horticulture Mission","PMFBY"]},
    {"name":"Papaya (Papita)",      "category":"Fruit",     "emoji":"🍈",
     "N":100,"P":50, "K":100, "t_min":22,"t_max":38,"m_min":50,"m_max":75,
     "yield":150, "msp":800,  "seasons":["Year-round"],
     "water_req":5000,"days":270, "seed_cost":8000,"fert_cost":6000,
     "rain_min":60, "rain_max":250,
     "intercrop":"Banana (Kela)",
     "schemes":["PM-KISAN","National Horticulture Mission","PMFBY"]},
    {"name":"Guava (Amrud)",        "category":"Fruit",     "emoji":"🍐",
     "N":50, "P":30, "K":50,  "t_min":18,"t_max":38,"m_min":35,"m_max":70,
     "yield":60,  "msp":1500, "seasons":["Year-round"],
     "water_req":3000,"days":180, "seed_cost":8000,"fert_cost":4000,
     "rain_min":50, "rain_max":250,
     "intercrop":"Mango (Aam)",
     "schemes":["PM-KISAN","National Horticulture Mission","PMFBY"]},
    {"name":"Litchi (Lychee)",      "category":"Fruit",     "emoji":"🍒",
     "N":60, "P":30, "K":60,  "t_min":20,"t_max":35,"m_min":50,"m_max":80,
     "yield":30,  "msp":5000, "seasons":["Zaid"],
     "water_req":4000,"days":90,  "seed_cost":12000,"fert_cost":5000,
     "rain_min":60, "rain_max":150,
     "intercrop":"Guava (Amrud)",
     "schemes":["PM-KISAN","National Horticulture Mission","GI Tag — Shahi Litchi"]},
    {"name":"Jackfruit (Kathal)",   "category":"Fruit",     "emoji":"🍈",
     "N":40, "P":20, "K":40,  "t_min":22,"t_max":38,"m_min":50,"m_max":80,
     "yield":80,  "msp":1000, "seasons":["Zaid","Kharif"],
     "water_req":4500,"days":150, "seed_cost":6000,"fert_cost":3000,
     "rain_min":80, "rain_max":300,
     "intercrop":"Banana (Kela)",
     "schemes":["PM-KISAN","National Horticulture Mission","One District One Product — JH"]},
]

CATEGORIES = ["All","Grain","Pulse","Oilseed","Vegetable","Fruit"]

# ══════════════════════════════════════════════════════════════════════════════
# SCORING ENGINE
# ══════════════════════════════════════════════════════════════════════════════
def score_crop(crop, n_val, p_val, k_val, final_temp, final_moist, current_month):
    in_season = is_in_season(crop["seasons"], current_month)
    rain_now  = JH_RAIN[current_month]
    rain_ok   = crop["rain_min"] <= rain_now <= crop["rain_max"]

    npk_diff  = ((crop['N']-n_val)**2+(crop['P']-p_val)**2+(crop['K']-k_val)**2)**0.5
    npk_score = max(0, 100 - npk_diff)

    if crop['t_min'] <= final_temp <= crop['t_max']:
        t_score = 100
    else:
        t_pen   = min(abs(final_temp-crop['t_min']), abs(final_temp-crop['t_max'])) * 5
        t_score = max(0, 100 - t_pen)

    if crop['m_min'] <= final_moist <= crop['m_max']:
        m_score = 100
    else:
        m_pen   = min(abs(final_moist-crop['m_min']), abs(final_moist-crop['m_max'])) * 2
        m_score = max(0, 100 - m_pen)

    overall = (npk_score*0.40) + (t_score*0.30) + (m_score*0.30)
    if not in_season: overall = max(0, overall - 25)
    if not rain_ok:   overall = max(0, overall - 10)

    risk = "Low" if overall >= 75 else ("Medium" if overall >= 50 else "High")

    if rain_now < crop["rain_min"]:   rain_status = "Too Dry"
    elif rain_now > crop["rain_max"]: rain_status = "Too Wet"
    else:                              rain_status = "Suitable"

    return {
        "npk_score":  round(npk_score, 1),
        "t_score":    round(t_score, 1),
        "m_score":    round(m_score, 1),
        "env_score":  round((t_score + m_score) / 2, 1),
        "overall":    round(overall, 1),
        "in_season":  in_season,
        "rain_status":rain_status,
        "risk":       risk,
        "n_gap":      max(0, crop['N'] - n_val),
        "p_gap":      max(0, crop['P'] - p_val),
        "k_gap":      max(0, crop['K'] - k_val),
    }

def build_results(crop_list, n_val, p_val, k_val,
                  final_temp, final_moist, land_acres, current_month):
    rows = []
    for crop in crop_list:
        sc          = score_crop(crop, n_val, p_val, k_val, final_temp, final_moist, current_month)
        total_yield = crop['yield'] * land_acres
        revenue     = total_yield * crop['msp']
        input_cost  = (crop['seed_cost'] + crop['fert_cost']) * land_acres
        net_profit  = revenue - input_cost
        trend       = MSP_TREND.get(crop['name'], "Stable")
        trend_emoji = {"Up":"↑ Up","Stable":"→ Stable","Down":"↓ Down"}.get(trend, trend)
        rows.append({
            "Crop":                    f"{crop['emoji']} {crop['name']}",
            "Category":                crop['category'],
            "Season":                  "In Season" if sc['in_season'] else "Off Season",
            "Rainfall":                sc['rain_status'],
            "Overall Match (%)":       sc['overall'],
            "NPK Health":              f"{sc['npk_score']}%",
            "Env Health":              f"{sc['env_score']}%",
            "Risk":                    sc['risk'],
            "Water (L/Acre/Day)":      crop['water_req'],
            "Days to Harvest":         crop['days'],
            "Total Yield (Quintals)":  round(total_yield, 1),
            "Est Revenue (INR)":       f"Rs.{revenue:,.0f}",
            "Input Cost (INR)":        f"Rs.{input_cost:,.0f}",
            "Net Profit (INR)":        f"Rs.{net_profit:,.0f}",
            "MSP Trend":               trend_emoji,
            "Intercrop":               crop['intercrop'],
            "_overall":                sc['overall'],
            "_npk":                    sc['npk_score'],
            "_env":                    sc['env_score'],
            "_n_gap":                  sc['n_gap'],
            "_p_gap":                  sc['p_gap'],
            "_k_gap":                  sc['k_gap'],
            "_name":                   crop['name'],
            "_schemes":                crop['schemes'],
            "_mandi":                  MANDI_MAP.get(crop['category'], "Ranchi APMC"),
            "_seasons":                crop['seasons'],
            "_net_profit_raw":         net_profit,
        })
    df = (pd.DataFrame(rows)
            .sort_values("_overall", ascending=False)
            .reset_index(drop=True))
    return df

# ══════════════════════════════════════════════════════════════════════════════
# QR CODE
# ══════════════════════════════════════════════════════════════════════════════
def make_qr_bytes(url="https://kvk.icar.gov.in/"):
    qr  = qrcode.QRCode(version=1, box_size=4, border=2)
    qr.add_data(url); qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
    return buf.read()

# ══════════════════════════════════════════════════════════════════════════════
# PDF GENERATOR
# ══════════════════════════════════════════════════════════════════════════════
def generate_pdf(df, land_acres, land_input, land_unit,
                 n_val, p_val, k_val, final_temp, final_hum, final_moist, final_sun,
                 current_month, season_label, farmer_name, farmer_village, farmer_district):

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=1.8*cm, leftMargin=1.8*cm,
                            topMargin=1.8*cm, bottomMargin=1.8*cm)

    DG = colors.HexColor("#166534"); MG = colors.HexColor("#16a34a")
    LG = colors.HexColor("#dcfce7"); DB = colors.HexColor("#0f172a")
    SL = colors.HexColor("#334155"); W  = colors.white
    AM = colors.HexColor("#d97706"); RE = colors.HexColor("#dc2626")
    OR = colors.HexColor("#f59e0b"); PU = colors.HexColor("#7e22ce")

    base = getSampleStyleSheet()
    def ps(n, **kw): return ParagraphStyle(n, parent=base["Normal"], **kw)
    sec  = ps("S",  fontSize=11, textColor=DG, spaceBefore=10, spaceAfter=5, fontName="Helvetica-Bold")
    disc = ps("D",  fontSize=7.5, textColor=colors.HexColor("#64748b"), fontName="Helvetica-Oblique", leading=11)
    norm = ps("NR", fontSize=8.5, textColor=SL, fontName="Helvetica", leading=13)

    story = []; now = datetime.now()
    bigha_eq  = land_acres * BIGHA_PER_ACRE
    kattha_eq = land_acres * KATTHA_PER_ACRE
    rain_now  = JH_RAIN[current_month]

    def grid_style(header_bg=DG):
        return [
            ("BACKGROUND",    (0,0),(-1,0),  header_bg),
            ("TEXTCOLOR",     (0,0),(-1,0),  W),
            ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0,0),(-1,-1), 8),
            ("FONTNAME",      (0,1),(-1,-1), "Helvetica"),
            ("TEXTCOLOR",     (0,1),(-1,-1), SL),
            ("ROWBACKGROUNDS",(0,1),(-1,-1), [W, colors.HexColor("#f8fafc")]),
            ("ALIGN",         (0,0),(-1,-1), "CENTER"),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
            ("GRID",          (0,0),(-1,-1), 0.4, colors.HexColor("#cbd5e1")),
            ("TOPPADDING",    (0,0),(-1,-1), 5),
            ("BOTTOMPADDING", (0,0),(-1,-1), 5),
            ("LEFTPADDING",   (0,0),(-1,-1), 6),
            ("RIGHTPADDING",  (0,0),(-1,-1), 6),
        ]

    # ── HEADER ────────────────────────────────────────────────────────────────
    hdr = [[
        Paragraph("<b>AGRI-ADVISOR</b><br/><font size=9>Smart Crop Advisory — Jharkhand</font>",
                  ps("HB", fontSize=18, textColor=W, fontName="Helvetica-Bold",
                     alignment=TA_LEFT, leading=22)),
        Paragraph(f"<b>Farmer Soil Report</b><br/>"
                  f"<font size=8>Date: {now.strftime('%d %B %Y, %I:%M %p')}</font><br/>"
                  f"<font size=8>Season: {season_label} | {MONTH_NAMES[current_month]}</font><br/>"
                  f"<font size=8>ID: AA-{now.strftime('%Y%m%d%H%M')}</font>",
                  ps("HR", fontSize=10, textColor=LG, fontName="Helvetica",
                     alignment=TA_RIGHT, leading=13))
    ]]
    ht = Table(hdr, colWidths=[10*cm, 7.2*cm])
    ht.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),DG),("LEFTPADDING",(0,0),(-1,-1),12),
                             ("RIGHTPADDING",(0,0),(-1,-1),12),("TOPPADDING",(0,0),(-1,-1),10),
                             ("BOTTOMPADDING",(0,0),(-1,-1),10),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.append(ht); story.append(Spacer(1, 0.25*cm))

    # ── FARMER BANNER ─────────────────────────────────────────────────────────
    fi = [[
        Paragraph(f"<b>Farmer:</b> {farmer_name}",
                  ps("FA", fontSize=9, textColor=W, fontName="Helvetica-Bold")),
        Paragraph(f"<b>Village:</b> {farmer_village}",
                  ps("FB", fontSize=9, textColor=LG, fontName="Helvetica")),
        Paragraph(f"<b>District:</b> {farmer_district}",
                  ps("FC", fontSize=9, textColor=LG, fontName="Helvetica")),
        Paragraph(f"<b>Land:</b> {land_input:.1f} {land_unit} = {land_acres:.2f} Ac / {bigha_eq:.1f} Bigha",
                  ps("FD", fontSize=9, textColor=LG, fontName="Helvetica")),
    ]]
    fib = Table(fi, colWidths=[4.3*cm, 4.3*cm, 3.5*cm, 5.1*cm])
    fib.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),DB),("LEFTPADDING",(0,0),(-1,-1),10),
                              ("RIGHTPADDING",(0,0),(-1,-1),10),("TOPPADDING",(0,0),(-1,-1),8),
                              ("BOTTOMPADDING",(0,0),(-1,-1),8),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                              ("LINEAFTER",(0,0),(2,0),0.5,colors.HexColor("#1e293b"))]))
    story.append(fib); story.append(Spacer(1, 0.25*cm))

    # ── TOP CROP BANNER ───────────────────────────────────────────────────────
    best = df.iloc[0]
    bn = [[
        Paragraph(f"<b>TOP RECOMMENDATION</b><br/><font size=13>{best['Crop']}</font>",
                  ps("BC",fontSize=9,textColor=W,fontName="Helvetica-Bold",alignment=TA_CENTER,leading=18)),
        Paragraph(f"<b>Match</b><br/><font size=15 color='#4ade80'>{best['Overall Match (%)']}%</font>",
                  ps("BM",fontSize=9,textColor=LG,fontName="Helvetica-Bold",alignment=TA_CENTER,leading=19)),
        Paragraph(f"<b>Risk</b><br/><font size=12>{best['Risk']}</font>",
                  ps("BRK",fontSize=9,textColor=LG,fontName="Helvetica-Bold",alignment=TA_CENTER,leading=17)),
        Paragraph(f"<b>Net Profit</b><br/><font size=10 color='#fbbf24'>{best['Net Profit (INR)']}</font>",
                  ps("BNP",fontSize=9,textColor=LG,fontName="Helvetica-Bold",alignment=TA_CENTER,leading=15)),
        Paragraph(f"<b>Days to Harvest</b><br/><font size=11>{best['Days to Harvest']}</font>",
                  ps("BDH",fontSize=9,textColor=LG,fontName="Helvetica-Bold",alignment=TA_CENTER,leading=17)),
        Paragraph(f"<b>Intercrop</b><br/><font size=8>{best['Intercrop']}</font>",
                  ps("BIC",fontSize=9,textColor=LG,fontName="Helvetica-Bold",alignment=TA_CENTER,leading=13)),
    ]]
    bnt = Table(bn, colWidths=[3.5*cm,2.7*cm,2.2*cm,3.4*cm,2.7*cm,2.7*cm])
    bnt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),DB),("BACKGROUND",(0,0),(0,0),MG),
                              ("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),
                              ("TOPPADDING",(0,0),(-1,-1),9),("BOTTOMPADDING",(0,0),(-1,-1),9),
                              ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                              ("LINEAFTER",(0,0),(4,0),0.5,colors.HexColor("#1e293b"))]))
    story.append(bnt); story.append(Spacer(1, 0.25*cm))

    # ── SEC 1 — INPUT PARAMETERS ──────────────────────────────────────────────
    story.append(Paragraph("1. Input Parameters & Soil Profile", sec))
    story.append(HRFlowable(width="100%", thickness=1.5, color=MG, spaceAfter=6))
    pd1 = [
        ["SOIL NUTRIENTS","","ENVIRONMENT & LOCATION",""],
        ["Parameter","Value","Parameter","Value"],
        ["Nitrogen (N)",    f"{n_val} kg/ha",    "Temperature",   f"{final_temp:.1f} C"],
        ["Phosphorus (P)",  f"{p_val} kg/ha",    "Humidity",      f"{final_hum:.1f} %"],
        ["Potassium (K)",   f"{k_val} kg/ha",    "Soil Moisture", f"{final_moist:.1f} %"],
        ["Land (Acres)",    f"{land_acres:.2f}", "Sunlight",      f"{final_sun:.1f} hrs/day"],
        ["Land (Bigha)",    f"{bigha_eq:.2f}",   "Rainfall Now",  f"{rain_now} mm/month"],
        ["Land (Kattha)",   f"{kattha_eq:.2f}",  "Season",        season_label],
    ]
    p1t = Table(pd1, colWidths=[3.9*cm,3.3*cm,4.5*cm,5.5*cm])
    p1t.setStyle(TableStyle([
        ("SPAN",(0,0),(1,0)),("SPAN",(2,0),(3,0)),
        ("BACKGROUND",(0,0),(1,0),DG),("BACKGROUND",(2,0),(3,0),colors.HexColor("#15803d")),
        ("TEXTCOLOR",(0,0),(-1,0),W),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,0),8.5),("ALIGN",(0,0),(-1,0),"CENTER"),
        ("BACKGROUND",(0,1),(-1,1),LG),("TEXTCOLOR",(0,1),(-1,1),DG),
        ("FONTNAME",(0,1),(-1,1),"Helvetica-Bold"),("FONTSIZE",(0,1),(-1,1),8),
        ("ALIGN",(0,1),(-1,1),"CENTER"),
        ("FONTNAME",(0,2),(-1,-1),"Helvetica"),("FONTSIZE",(0,2),(-1,-1),8.5),
        ("TEXTCOLOR",(0,2),(-1,-1),SL),
        ("ROWBACKGROUNDS",(0,2),(-1,-1),[W,colors.HexColor("#f8fafc")]),
        ("FONTNAME",(0,2),(0,-1),"Helvetica-Bold"),("FONTNAME",(2,2),(2,-1),"Helvetica-Bold"),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#cbd5e1")),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0),(-1,-1),8),
        ("ALIGN",(1,2),(1,-1),"CENTER"),("ALIGN",(3,2),(3,-1),"CENTER"),
    ]))
    story.append(p1t); story.append(Spacer(1,0.25*cm))

    # ── SEC 2 — SOIL HEALTH ───────────────────────────────────────────────────
    story.append(Paragraph("2. Soil Health Summary", sec))
    story.append(HRFlowable(width="100%", thickness=1.5, color=MG, spaceAfter=6))
    def npk_status(val, low, high):
        if val < low:   return "Deficient", "#dc2626"
        if val > high:  return "Excess",    "#d97706"
        return "Ideal", "#16a34a"
    n_st, n_col = npk_status(n_val, 40, 120)
    p_st, p_col = npk_status(p_val, 20, 80)
    k_st, k_col = npk_status(k_val, 20, 80)
    sh = [
        ["Nutrient","Your Level","Status","Ideal Range","Advice"],
        ["Nitrogen (N)", f"{n_val} kg/ha",
         Paragraph(f"<font color='{n_col}'><b>{n_st}</b></font>", ps("NS",fontSize=8,fontName="Helvetica-Bold")),
         "40–120 kg/ha", "Add Urea if Deficient; reduce if Excess"],
        ["Phosphorus (P)", f"{p_val} kg/ha",
         Paragraph(f"<font color='{p_col}'><b>{p_st}</b></font>", ps("PS",fontSize=8,fontName="Helvetica-Bold")),
         "20–80 kg/ha",  "Add DAP if Deficient"],
        ["Potassium (K)", f"{k_val} kg/ha",
         Paragraph(f"<font color='{k_col}'><b>{k_st}</b></font>", ps("KS",fontSize=8,fontName="Helvetica-Bold")),
         "20–80 kg/ha",  "Add MOP/SOP if Deficient"],
    ]
    sht = Table(sh, colWidths=[3*cm,2.5*cm,2.5*cm,3*cm,6.2*cm])
    sht.setStyle(TableStyle(grid_style(SL) + [("ALIGN",(0,1),(0,-1),"LEFT")]))
    story.append(sht); story.append(Spacer(1,0.25*cm))

    # ── SEC 3 — FERTILIZER RECOMMENDATION ────────────────────────────────────
    story.append(Paragraph("3. Fertilizer Recommendation for Top Crop", sec))
    story.append(HRFlowable(width="100%", thickness=1.5, color=MG, spaceAfter=6))
    best_raw = next((c for c in CROP_DATA if c['name'] in best['Crop']), None)
    if best_raw:
        n_gap = max(0, best_raw['N']-n_val); p_gap = max(0, best_raw['P']-p_val); k_gap = max(0, best_raw['K']-k_val)
        n_kg  = round(n_gap*0.4047*land_acres,1); p_kg = round(p_gap*0.4047*land_acres,1); k_kg = round(k_gap*0.4047*land_acres,1)
        fd = [
            ["Nutrient","Soil Level","Ideal Level","Gap (kg/ha)","Add for Your Land","Status"],
            ["Nitrogen (N)",  f"{n_val}",f"{best_raw['N']}",f"{n_gap}",f"{n_kg} kg","Deficient" if n_gap>0 else "Sufficient"],
            ["Phosphorus (P)",f"{p_val}",f"{best_raw['P']}",f"{p_gap}",f"{p_kg} kg","Deficient" if p_gap>0 else "Sufficient"],
            ["Potassium (K)", f"{k_val}",f"{best_raw['K']}",f"{k_gap}",f"{k_kg} kg","Deficient" if k_gap>0 else "Sufficient"],
        ]
        fdt = Table(fd, colWidths=[3.2*cm,2.5*cm,2.5*cm,2.5*cm,3.5*cm,3*cm])
        fdt.setStyle(TableStyle(grid_style(SL)))
        story.append(fdt)
    story.append(Spacer(1,0.25*cm))

    # ── SEC 4 — CATEGORY BEST CROP ────────────────────────────────────────────
    story.append(Paragraph("4. Best Crop by Category (Your Soil & Current Season)", sec))
    story.append(HRFlowable(width="100%", thickness=1.5, color=MG, spaceAfter=6))
    cat_rows = [["Category","Best Crop","Match (%)","Risk","Net Profit","Days","Nearest Mandi"]]
    for cat in ["Grain","Pulse","Oilseed","Vegetable","Fruit"]:
        cat_df = df[df["Category"]==cat]
        if len(cat_df):
            r = cat_df.iloc[0]
            cat_rows.append([cat, r["Crop"], str(r["Overall Match (%)"]), r["Risk"],
                             r["Net Profit (INR)"], str(r["Days to Harvest"]),
                             MANDI_MAP.get(cat,"Ranchi APMC")])
        else:
            cat_rows.append([cat,"No data","—","—","—","—","—"])
    crt = Table(cat_rows, colWidths=[2.2*cm,3.8*cm,2*cm,1.8*cm,3*cm,1.6*cm,2.8*cm])
    crt.setStyle(TableStyle(grid_style() + [
        ("BACKGROUND",(0,1),(0,-1),LG),("FONTNAME",(0,1),(0,-1),"Helvetica-Bold"),
        ("TEXTCOLOR",(0,1),(0,-1),DG),("ALIGN",(1,1),(1,-1),"LEFT"),
    ]))
    story.append(crt); story.append(Spacer(1,0.25*cm))

    # ── SEC 5 — GOVT SCHEMES ──────────────────────────────────────────────────
    story.append(Paragraph("5. Government Schemes for Top Crop", sec))
    story.append(HRFlowable(width="100%", thickness=1.5, color=MG, spaceAfter=6))
    best_raw2 = next((c for c in CROP_DATA if c['name'] in best['Crop']), None)
    if best_raw2:
        sch_data = [["Scheme Name","Benefit"]]
        scheme_benefits = {
            "PM-KISAN":                  "Rs.6,000/year direct income support",
            "PMFBY Crop Insurance":      "Crop insurance at subsidised premium",
            "PMFBY":                     "Crop insurance at subsidised premium",
            "Rashtriya Krishi Vikas Yojana":"Infrastructure & tech support grants",
            "PM Krishi Sinchai Yojana":  "Subsidised drip/sprinkler irrigation",
            "National Food Security Mission":"Seed & input subsidy for food crops",
            "NMOOP Oilseed Mission":     "Subsidised seeds & training for oilseeds",
            "NFS Mission — Pulses":      "Seed minikits & demo plots for pulses",
            "National Horticulture Mission":"50% subsidy on hort infrastructure",
            "Horticulture Mission":      "50% subsidy on hort infrastructure",
            "Paramparagat Krishi Vikas Yojana":"Organic farming support Rs.50,000/cluster",
            "Sub-Mission on Agri Mechanization":"Subsidised farm equipment",
            "GI Tag — Shahi Litchi":     "Premium market access via GI certification",
            "One District One Product — JH":"Market linkage & branding support",
        }
        for s in best_raw2['schemes']:
            sch_data.append([s, scheme_benefits.get(s, "Contact local KVK for details")])
        scht = Table(sch_data, colWidths=[6*cm,11.2*cm])
        scht.setStyle(TableStyle(grid_style(MG) + [("ALIGN",(0,1),(0,-1),"LEFT"),("ALIGN",(1,1),(1,-1),"LEFT")]))
        story.append(scht)
    story.append(Spacer(1,0.25*cm))

    # ── SEC 6 — SOWING CALENDAR ───────────────────────────────────────────────
    story.append(Paragraph("6. Sowing Calendar for Top Crop", sec))
    story.append(HRFlowable(width="100%", thickness=1.5, color=MG, spaceAfter=6))
    month_abbr = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    best_raw3 = next((c for c in CROP_DATA if c['name'] in best['Crop']), None)
    sow_months = set()
    harv_months = set()
    if best_raw3:
        for s in best_raw3['seasons']:
            sow = SOWING_MONTHS.get(s, [])
            for m in sow:
                sow_months.add(m)
                harv_months.add(((m - 1 + best_raw3['days']//30) % 12) + 1)

    cal_header = month_abbr
    sow_row    = []
    harv_row   = []
    cur_row    = []
    for i in range(1,13):
        if i in sow_months:         sow_row.append("SOW")
        else:                       sow_row.append("")
        if i in harv_months:        harv_row.append("HARVEST")
        else:                       harv_row.append("")
        if i == current_month:      cur_row.append("NOW")
        else:                       cur_row.append("")

    cal_data = [
        [""] + cal_header,
        ["Sowing"]   + sow_row,
        ["Harvest"]  + harv_row,
        ["Current"]  + cur_row,
    ]
    cw_cal = [1.8*cm] + [1.37*cm]*12
    calt   = Table(cal_data, colWidths=cw_cal)
    cal_styles = [
        ("BACKGROUND",(0,0),(-1,0), SL),("TEXTCOLOR",(0,0),(-1,0), W),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),7),
        ("FONTNAME",(0,1),(-1,-1),"Helvetica"),("TEXTCOLOR",(0,1),(-1,-1),SL),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#cbd5e1")),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("BACKGROUND",(0,1),(0,-1), LG),("FONTNAME",(0,1),(0,-1),"Helvetica-Bold"),
        ("TEXTCOLOR",(0,1),(0,-1), DG),
    ]
    for col in range(1,13):
        if sow_row[col-1]  == "SOW":     cal_styles.append(("BACKGROUND",(col,1),(col,1), colors.HexColor("#bbf7d0")))
        if harv_row[col-1] == "HARVEST": cal_styles.append(("BACKGROUND",(col,2),(col,2), colors.HexColor("#fef08a")))
        if cur_row[col-1]  == "NOW":
            cal_styles.append(("BACKGROUND",(col,3),(col,3), MG))
            cal_styles.append(("TEXTCOLOR",(col,3),(col,3),  W))
    calt.setStyle(TableStyle(cal_styles))
    story.append(calt); story.append(Spacer(1,0.25*cm))

    # ── SEC 7 — FULL RANKED TABLE ─────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("7. Full Crop Suitability Ranking", sec))
    story.append(HRFlowable(width="100%", thickness=1.5, color=MG, spaceAfter=6))
    th = ["Rank","Crop","Cat","Season","Rain","Match\n(%)","Risk",
          "Water\nL/Ac/D","Days","Net Profit","Trend"]
    td = [th]
    for idx, (_, row) in enumerate(df.iterrows(), start=1):
        medal = {1:"1st",2:"2nd",3:"3rd"}.get(idx, f"{idx}th")
        td.append([medal, str(row["Crop"]), str(row["Category"])[:4],
                   "IN" if row["Season"]=="In Season" else "OFF",
                   str(row["Rainfall"])[:7],
                   str(row["Overall Match (%)"]),
                   str(row["Risk"]),
                   str(row["Water (L/Acre/Day)"]),
                   str(row["Days to Harvest"]),
                   str(row["Net Profit (INR)"]),
                   str(row["MSP Trend"]),])
    cw2 = [1.2*cm,3.7*cm,1.4*cm,1.3*cm,1.8*cm,1.5*cm,1.5*cm,1.7*cm,1.3*cm,3*cm,1.8*cm]
    rkt = Table(td, colWidths=cw2, repeatRows=1)
    rkt.setStyle(TableStyle(grid_style() + [
        ("BACKGROUND",(0,1),(-1,1), LG),("FONTNAME",(0,1),(-1,1),"Helvetica-Bold"),
        ("TEXTCOLOR",(0,1),(-1,1), DG),
        ("ROWBACKGROUNDS",(0,2),(-1,-1),[W,colors.HexColor("#f8fafc")]),
        ("ALIGN",(1,1),(1,-1),"LEFT"),
    ]))
    story.append(rkt); story.append(Spacer(1,0.3*cm))

    # ── SEASONAL CALENDAR ─────────────────────────────────────────────────────
    story.append(Paragraph("8. Jharkhand Seasonal Farming Calendar", sec))
    story.append(HRFlowable(width="100%", thickness=1.5, color=MG, spaceAfter=6))
    sc_data = [
        ["Season","Months","Key Crops"],
        ["Kharif","June – October","Paddy, Maize, Arhar, Okra, Brinjal, Bitter Gourd, Pumpkin, Onion"],
        ["Rabi","November – March","Wheat, Mustard, Chana, Potato, Cauliflower, Cabbage, Spinach, Tomato"],
        ["Zaid","March – June","Maize, Okra, Brinjal, Tomato, Mango, Litchi, Jackfruit"],
        ["Year-round","All months","Banana, Papaya, Guava"],
    ]
    sct = Table(sc_data, colWidths=[2.8*cm,4*cm,10.4*cm])
    sct.setStyle(TableStyle(grid_style() + [("ALIGN",(0,1),(1,-1),"LEFT"),("ALIGN",(2,1),(2,-1),"LEFT")]))
    story.append(sct); story.append(Spacer(1,0.3*cm))

    # ── DISCLAIMER + QR FOOTER ────────────────────────────────────────────────
    story.append(HRFlowable(width="100%",thickness=0.5,color=colors.HexColor("#94a3b8"),spaceAfter=7))
    try:
        qr_bytes  = make_qr_bytes()
        qr_img    = ImageReader(io.BytesIO(qr_bytes))
        qr_para   = Paragraph(
            "<b>Scan for KVK Support</b><br/>"
            "<font size=7>kvk.icar.gov.in</font>",
            ps("QT", fontSize=8, textColor=SL, fontName="Helvetica", alignment=TA_CENTER))
        footer_data = [[
            Paragraph("<b>Disclaimer:</b> This report is generated by the Agri-Advisor Smart Dashboard "
                      "using IoT sensor data and scientific crop-matching algorithms. Revenue estimates "
                      "use Government MSP rates and typical yield assumptions. Actual results may vary. "
                      "Consult your local Krishi Vigyan Kendra (KVK) before major farming decisions.", disc),
            [qr_para]
        ]]
        ftab = Table(footer_data, colWidths=[14*cm, 3.2*cm])
        ftab.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),0),
                                   ("RIGHTPADDING",(0,0),(-1,-1),0)]))
        story.append(ftab)
        # QR image inline
        from reportlab.platypus import Image as RLImage
        story.append(Spacer(1,0.1*cm))
    except Exception:
        story.append(Paragraph("<b>Disclaimer:</b> Consult local KVK before major farming decisions. kvk.icar.gov.in", disc))

    green_footer = [[
        Paragraph("Agri-Advisor | Jharkhand Agricultural Intelligence System",
                  ps("GFL", fontSize=7.5, textColor=W, fontName="Helvetica", alignment=TA_LEFT)),
        Paragraph(f"Report ID: AA-{now.strftime('%Y%m%d%H%M')} | Confidential",
                  ps("GFR", fontSize=7.5, textColor=LG, fontName="Helvetica", alignment=TA_RIGHT)),
    ]]
    gft = Table(green_footer, colWidths=[10*cm, 7.2*cm])
    gft.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),DG),("LEFTPADDING",(0,0),(-1,-1),12),
                              ("RIGHTPADDING",(0,0),(-1,-1),12),("TOPPADDING",(0,0),(-1,-1),7),
                              ("BOTTOMPADDING",(0,0),(-1,-1),7),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.append(gft)
    doc.build(story)
    buf.seek(0)
    return buf

# ══════════════════════════════════════════════════════════════════════════════
# STREAMLIT UI
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Agri-Advisor Dashboard", layout="wide")
st.markdown("""
<style>
.main{background-color:#020617;color:white;}
div[data-testid="stMetricValue"]{color:#4ade80;font-size:2rem;}
.stMetric{background-color:#0f172a;padding:20px;border-radius:10px;border:1px solid #1e293b;}
.season-banner{background:linear-gradient(135deg,#0f172a,#1e293b);border-left:4px solid #4ade80;
    border-radius:8px;padding:12px 18px;margin-bottom:10px;}
.soil-card{background:#0f172a;border:1px solid #1e293b;border-radius:10px;padding:16px;margin:4px 0;}
.download-banner{background:linear-gradient(135deg,#166534,#15803d);border:2px solid #4ade80;
    border-radius:12px;padding:20px 28px;margin-top:24px;text-align:center;}
.scheme-box{background:#0f172a;border-left:3px solid #4ade80;border-radius:6px;
    padding:10px 14px;margin:6px 0;}
stProgress .st-bo{background-color:#4ade80;}
</style>
""", unsafe_allow_html=True)

# ── SESSION STATE ──────────────────────────────────────────────────────────────
for k, v in {
    "locked_temp":25.0,"locked_hum":50.0,"locked_moist":50.0,"locked_sun":8.0,
    "manual_mode":False,"analysis_done":False,"report_df":None,"report_params":None,
    "selected_cat":"All",
}.items():
    if k not in st.session_state: st.session_state[k] = v

# ── TITLE + SEASON BANNER ──────────────────────────────────────────────────────
st.title("📋 Smart Crop Advisory Dashboard")
current_month = datetime.now().month
season_label  = SEASON_MAP[current_month]
month_name    = MONTH_NAMES[current_month]
rain_now      = JH_RAIN[current_month]

st.markdown(f"""
<div class="season-banner">
  <span style="color:#4ade80;font-size:18px;font-weight:bold;">
    🗓️ Current Season: {season_label}
  </span>&nbsp;&nbsp;|&nbsp;&nbsp;
  <span style="color:#94a3b8;font-size:14px;">
    Month: {month_name} &nbsp;|&nbsp;
    Avg Rainfall: {rain_now} mm/month &nbsp;|&nbsp;
    In-season crops ranked higher. Off-season = 25pt penalty.
  </span>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION A — FARMER DETAILS
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("👨‍🌾 Farmer Details")
fa, fb, fc = st.columns(3)
with fa: farmer_name    = st.text_input("Farmer Name",    placeholder="Enter farmer name", value="")
with fb: farmer_village = st.text_input("Village",        placeholder="Enter village name", value="")
with fc: farmer_district= st.text_input("District",       placeholder="Enter district", value="")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION B — FARMING PARAMETERS
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("🌱 Farming Parameters")
if st.button("🎚 Toggle Manual Override"):
    st.session_state.manual_mode = not st.session_state.manual_mode

# Land area
st.write("📐 **Land Area**")
lc1, lc2, lc3 = st.columns([1,1,2])
with lc1:
    land_unit = st.selectbox("Unit",["Acres","Bigha","Kattha"],
                             help="Jharkhand: 1 Acre = 1.613 Bigha = 32.26 Kattha")
with lc2:
    defaults = {"Acres":10.0,"Bigha":16.0,"Kattha":322.0}
    steps    = {"Acres":0.5,"Bigha":1.0,"Kattha":5.0}
    land_input = st.number_input(f"Land Area ({land_unit})",
                                  value=defaults[land_unit], min_value=0.1, step=steps[land_unit])
with lc3:
    land_acres = to_acres(land_input, land_unit)
    st.info(f"📏 **{acres_display(land_acres)}**")

# NPK
st.write("")
nc1, nc2, nc3 = st.columns(3)
with nc1: n_val = st.number_input("Nitrogen (N) kg/ha",   value=35)
with nc2: p_val = st.number_input("Phosphorus (P) kg/ha", value=60)
with nc3: k_val = st.number_input("Potassium (K) kg/ha",  value=40)

# Soil health summary card
st.write("")
st.write("🧪 **Soil Health Summary**")
def npk_badge(val, low, high):
    if val < low:  return "🔴 Deficient"
    if val > high: return "🟠 Excess"
    return "🟢 Ideal"

sh1, sh2, sh3 = st.columns(3)
sh1.metric("Nitrogen (N)",   f"{n_val} kg/ha",  npk_badge(n_val, 40, 120))
sh2.metric("Phosphorus (P)", f"{p_val} kg/ha",  npk_badge(p_val, 20, 80))
sh3.metric("Potassium (K)",  f"{k_val} kg/ha",  npk_badge(k_val, 20, 80))

# Live sensor
st.divider()
st.write("📡 **Live Environment Readings**")
m1, m2, m3, m4 = st.columns(4)
if st.session_state.manual_mode:
    final_moist = m1.slider("Soil Moisture (%)",  0, 100, int(st.session_state.locked_moist))
    final_sun   = m2.slider("Sunlight (hrs)",     0, 12,  int(st.session_state.locked_sun))
    final_temp  = m3.slider("Temperature (°C)",  10, 45,  int(st.session_state.locked_temp))
    final_hum   = m4.slider("Humidity (%)",       0, 100, int(st.session_state.locked_hum))
else:
    m1.metric("Soil Moisture", f"{st.session_state.locked_moist:.1f} %")
    m2.metric("Sunlight",      f"{st.session_state.locked_sun:.1f} hrs")
    m3.metric("Temperature",   f"{st.session_state.locked_temp:.1f} °C")
    m4.metric("Humidity",      f"{st.session_state.locked_hum:.1f} %")
    final_moist = st.session_state.locked_moist; final_sun = st.session_state.locked_sun
    final_temp  = st.session_state.locked_temp;  final_hum = st.session_state.locked_hum

# ══════════════════════════════════════════════════════════════════════════════
# SECTION C — HARDWARE FETCH
# ══════════════════════════════════════════════════════════════════════════════
st.divider()
st.write("⏱️ **Data Collection Settings**")
col_btn, col_time = st.columns([1,2])
with col_time:
    collect_time = st.number_input("Duration to observe environment (Seconds)",
                                    min_value=1, max_value=60, value=10)
    st.caption("💡 Longer duration filters sensor noise for accurate readings.")
with col_btn:
    if st.button("📡 Fetch & Average Data"):
        try:
            ser = serial.Serial('COM8', 9600, timeout=1)
            time.sleep(2); ser.reset_input_buffer()
            t_list,h_list,m_list,s_list = [],[],[],[]
            pb = st.progress(0); st_txt = st.empty(); t0 = time.time()
            while (time.time()-t0) < collect_time:
                e = time.time()-t0
                pb.progress(min(e/collect_time,1.0))
                st_txt.text(f"Collecting... {int(e)}s / {collect_time}s")
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8',errors='ignore').strip()
                    if line and ',' in line:
                        parts = line.split(',')
                        if len(parts) >= 5:
                            try:
                                t_list.append(float(parts[0])); h_list.append(float(parts[1]))
                                m_list.append(max(0,min(100,(1-float(parts[2])/1023)*100)))
                                s_list.append(float(parts[4]))
                            except ValueError: pass
            ser.close()
            if t_list:
                st.session_state.locked_temp  = sum(t_list)/len(t_list)
                st.session_state.locked_hum   = sum(h_list)/len(h_list)
                st.session_state.locked_moist = sum(m_list)/len(m_list)
                st.session_state.locked_sun   = sum(s_list)/len(s_list)
                st.toast(f"Averaged {len(t_list)} data points!", icon="✅")
            else: st.error("No valid data from sensors.")
            st.rerun()
        except Exception as e:
            st.error(f"Hardware error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION D — CATEGORY FILTER (outside button so it persists)
# ══════════════════════════════════════════════════════════════════════════════
st.divider()
st.write("🔍 **Filter by Crop Category**")
cat_cols = st.columns(len(CATEGORIES))
for i, cat in enumerate(CATEGORIES):
    with cat_cols[i]:
        if st.button(cat, key=f"cat_{cat}",
                     type="primary" if st.session_state.selected_cat == cat else "secondary",
                     use_container_width=True):
            st.session_state.selected_cat = cat
            st.rerun()

chosen_cat = st.session_state.selected_cat
st.caption(f"Showing: **{chosen_cat}** crops")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION E — ANALYSIS BUTTON
# ══════════════════════════════════════════════════════════════════════════════
if st.button("🚀 Start Soil & Weather Analysis", type="primary"):
    # Filter crop list
    if chosen_cat == "All":
        crop_list = CROP_DATA
    else:
        crop_list = [c for c in CROP_DATA if c["category"] == chosen_cat]

    df_all = build_results(CROP_DATA, n_val, p_val, k_val,
                           final_temp, final_moist, land_acres, current_month)
    df_show = build_results(crop_list, n_val, p_val, k_val,
                            final_temp, final_moist, land_acres, current_month)

    st.subheader(f"📊 Results — {chosen_cat} Crops")

    # Score bars for top 5
    st.write("**Top 5 Crop Match Scores**")
    for _, row in df_show.head(5).iterrows():
        c1, c2, c3, c4 = st.columns([3,2,2,2])
        c1.write(f"**{row['Crop']}**")
        c2.progress(int(row["Overall Match (%)"])/100, text=f"Overall {row['Overall Match (%)']}%")
        npk_val = float(str(row["NPK Health"]).replace("%",""))/100
        c3.progress(npk_val, text=f"NPK {row['NPK Health']}")
        env_val = float(str(row["Env Health"]).replace("%",""))/100
        c4.progress(env_val, text=f"Env {row['Env Health']}")

    st.write("")

    # Full table with styling
    display_cols = ["Crop","Category","Season","Rainfall","Overall Match (%)","NPK Health",
                    "Env Health","Risk","Water (L/Acre/Day)","Days to Harvest",
                    "Total Yield (Quintals)","Est Revenue (INR)","Input Cost (INR)",
                    "Net Profit (INR)","MSP Trend","Intercrop"]
    df_display = df_show[display_cols].copy()

    def highlight_rows(row):
        if row["Season"] == "Off Season":
            return ["background-color:#1c0a0a;color:#fca5a5"] * len(row)
        if row["Risk"] == "High":
            return ["background-color:#1c0505;color:#fca5a5"] * len(row)
        if row.name == 0:
            return ["background-color:#052e16;color:#4ade80;font-weight:bold"] * len(row)
        return [""] * len(row)

    st.dataframe(df_display.style.apply(highlight_rows, axis=1),
                 use_container_width=True,
                 height=min(60+len(df_display)*38, 650))

    # Best crop summary
    best     = df_show.iloc[0]
    best_raw = next((c for c in CROP_DATA if c['name'] in best['Crop']), None)

    note = " *(check sowing window)*" if best["Season"] == "Off Season" else ""
    st.success(
        f"✅ Best {chosen_cat} crop for **{land_input:.1f} {land_unit}** "
        f"({land_acres:.2f} Acres) in **{month_name}** [{season_label}] → "
        f"**{best['Crop']}**{note}"
    )

    # Season summary
    in_s  = df_show[df_show["Season"]=="In Season"]
    out_s = df_show[df_show["Season"]=="Off Season"]
    sc1, sc2 = st.columns(2)
    sc1.info(f"🟢 **{len(in_s)} crops** In Season for {month_name}")
    sc2.warning(f"🔴 **{len(out_s)} crops** Off Season (25-pt penalty applied)")

    # Fertilizer recommendation
    if best_raw:
        st.write("")
        st.write("### 🧪 Fertilizer Recommendation")
        n_gap = max(0, best_raw['N']-n_val)
        p_gap = max(0, best_raw['P']-p_val)
        k_gap = max(0, best_raw['K']-k_val)
        n_kg  = round(n_gap*0.4047*land_acres, 1)
        p_kg  = round(p_gap*0.4047*land_acres, 1)
        k_kg  = round(k_gap*0.4047*land_acres, 1)
        f1,f2,f3 = st.columns(3)
        f1.metric("Nitrogen to Add",   f"{n_kg} kg", f"Gap: {n_gap} kg/ha")
        f2.metric("Phosphorus to Add", f"{p_kg} kg", f"Gap: {p_gap} kg/ha")
        f3.metric("Potassium to Add",  f"{k_kg} kg", f"Gap: {k_gap} kg/ha")

    # Intercropping & schemes
    if best_raw:
        st.write("")
        ic1, ic2 = st.columns(2)
        with ic1:
            st.write("### 🌿 Intercropping Suggestion")
            st.info(f"**Grow alongside:** {best_raw['intercrop']}\n\n"
                    f"Intercropping increases income per acre and improves soil health.")
        with ic2:
            st.write("### 🏛️ Government Schemes")
            for scheme in best_raw['schemes']:
                st.markdown(f'<div class="scheme-box">✅ {scheme}</div>', unsafe_allow_html=True)

    # Nearest mandi
    st.write("")
    st.write("### 🏪 Nearest Mandi")
    mandi = MANDI_MAP.get(best["Category"], "Ranchi APMC Mandi")
    st.info(f"📍 **{mandi}** — Sell your {best['Crop']} here for best MSP price")

    # Rainfall warning
    st.write("")
    if best["Rainfall"] != "Suitable":
        st.warning(f"🌧️ **Rainfall Warning:** Current rainfall ({rain_now} mm/month) is "
                   f"**{best['Rainfall']}** for {best['Crop']}. Plan irrigation accordingly.")
    else:
        st.success(f"🌧️ **Rainfall:** Current rainfall ({rain_now} mm/month) is suitable for {best['Crop']}.")

    # Save to session
    st.session_state.analysis_done  = True
    st.session_state.report_df      = df_all   # always full df for PDF
    st.session_state.report_params  = dict(
        land_acres=land_acres, land_input=land_input, land_unit=land_unit,
        n_val=n_val, p_val=p_val, k_val=k_val,
        final_temp=final_temp, final_hum=final_hum,
        final_moist=final_moist, final_sun=final_sun,
        current_month=current_month, season_label=season_label,
        farmer_name=farmer_name, farmer_village=farmer_village,
        farmer_district=farmer_district,
    )

# ══════════════════════════════════════════════════════════════════════════════
# SECTION F — DOWNLOAD REPORT
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.analysis_done and st.session_state.report_df is not None:
    st.divider()
    st.markdown("""
    <div class="download-banner">
        <h2 style="color:#4ade80;margin:0 0 6px 0;">📄 Your Soil Report is Ready!</h2>
        <p style="color:#d1fae5;margin:0;font-size:15px;">
            Download a fully formatted PDF — crop rankings, seasonal guide, fertilizer plan,
            govt schemes, sowing calendar, land conversions & revenue projections.
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.write("")

    p = st.session_state.report_params
    try:
        pdf_buf = generate_pdf(
            df=st.session_state.report_df,
            land_acres=p["land_acres"], land_input=p["land_input"], land_unit=p["land_unit"],
            n_val=p["n_val"], p_val=p["p_val"], k_val=p["k_val"],
            final_temp=p["final_temp"], final_hum=p["final_hum"],
            final_moist=p["final_moist"], final_sun=p["final_sun"],
            current_month=p["current_month"], season_label=p["season_label"],
            farmer_name=p["farmer_name"], farmer_village=p["farmer_village"],
            farmer_district=p["farmer_district"],
        )
        fname = (f"AgriAdvisor_{p['farmer_name'].replace(' ','_')}_"
                 f"{p['season_label'].replace('/','_')}_"
                 f"{datetime.now().strftime('%d%b%Y_%H%M')}.pdf")

        col_l, col_c, col_r = st.columns([1.5,2,1.5])
        with col_c:
            st.download_button(
                label="⬇️  Download Full Soil Report (PDF)",
                data=pdf_buf, file_name=fname, mime="application/pdf",
                use_container_width=True, type="primary",
            )
            st.caption(f"📁 `{fname}`  •  22 crops  •  Seasonal filter  •  Fertilizer plan  •  Govt schemes")
    except Exception as e:
        st.error(f"PDF generation error: {e}")