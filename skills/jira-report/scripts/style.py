"""Charte graphique — constantes de style partagées par tous les rendus de slide.

Base de maquette 1920 x 1080 px sur une slide 16:9 réelle de
12192000 x 6858000 EMU (13.333 x 7.5 in) : EMU = px * 6350, pt = px / 2.
Aucune valeur de couleur/taille/marge ne doit être écrite en dur ailleurs
dans le skill — tout passe par ce module.
"""
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor

EMU_PER_PX = 6350


def px(n):
    """Convertit un nombre de px de maquette (base 1920x1080) en EMU."""
    return Emu(round(n * EMU_PER_PX))


def pt_from_px(n):
    """Convertit une hauteur de police exprimée en px de maquette en Pt (pt = px/2)."""
    return Pt(n / 2)


SLIDE_W_PX = 1920
SLIDE_H_PX = 1080

# ---------------------------------------------------------------- couleurs
BRAND_PRIMARY = RGBColor(0x1F, 0x4E, 0x79)
BRAND_ACCENT = RGBColor(0xF0, 0x4E, 0x23)
ORANGE_LIGHT = RGBColor(0xF9, 0xA4, 0x8C)

BLUE_FILL_1 = RGBColor(0x7F, 0xB2, 0xCE)
BLUE_FILL_2 = RGBColor(0xA9, 0xC4, 0xD6)
BLUE_FILL_3 = RGBColor(0xCB, 0xD9, 0xE4)
BLUE_FILL_4 = RGBColor(0xE4, 0xEA, 0xF0)
BLUE_FILLS = [BLUE_FILL_1, BLUE_FILL_2, BLUE_FILL_3, BLUE_FILL_4]

CARD_BG = RGBColor(0xF4, 0xF7, 0xFA)
CARD_BORDER = RGBColor(0xDC, 0xE3, 0xEA)
CARD_BORDER_INNER = RGBColor(0xEE, 0xF2, 0xF6)

TEXT_PRIMARY = RGBColor(0x33, 0x47, 0x5B)
TEXT_SECONDARY = RGBColor(0x6B, 0x7C, 0x8C)
TEXT_FOOTER = RGBColor(0x93, 0xA2, 0xB0)
TEXT_WHITE = RGBColor(0xFF, 0xFF, 0xFF)

ALERT_BG = RGBColor(0xFE, 0xF5, 0xF2)
ALERT_BORDER = RGBColor(0xF7, 0xC4, 0xB4)
ALERT_TEXT = RGBColor(0xB9, 0x3A, 0x16)

TREND_OPTIMIST = RGBColor(0x2E, 0x9E, 0x6B)
TREND_MEDIAN = RGBColor(0xF0, 0x4E, 0x23)
TREND_PESSIMIST = RGBColor(0xC0, 0x39, 0x2B)

# {{chart:conso_corrective}} — 4 catégories anomalie/incident/Us/US tech
CORRECTIVE_ANOMALY = RGBColor(0xC0, 0x39, 0x2B)   # rouge
CORRECTIVE_INCIDENT = RGBColor(0x2E, 0x5A, 0x8C)  # bleu
CORRECTIVE_US = RGBColor(0x2E, 0x9E, 0x6B)        # vert
CORRECTIVE_TECH = RGBColor(0xE0, 0xB0, 0x2E)      # or

SYNTH_BG = BRAND_PRIMARY  # slides de synthèse : fond plein bleu
SYNTH_ACCENT = ORANGE_LIGHT
SYNTH_RULE = RGBColor(0xFF, 0xFF, 0xFF)  # filet blanc à 14% d'opacité (alpha géré à l'appel)

# ---------------------------------------------------------------- police
FONT_FAMILY = "Aptos"  # fallback Calibri géré par PowerPoint si Aptos absent

SIZE_SURTITLE = pt_from_px(20)      # 10 pt
SIZE_SLIDE_TITLE = pt_from_px(58)   # 29 pt
SIZE_CARD_LABEL = pt_from_px(20)    # 10 pt
SIZE_KPI_BIG = pt_from_px(86)       # 43 pt
SIZE_CARD_NUMBER = pt_from_px(60)   # 30 pt
SIZE_BODY = pt_from_px(25)          # 12.5 pt
SIZE_TABLE_CELL = pt_from_px(24)    # 12 pt
SIZE_LEGEND = pt_from_px(24)        # 12 pt
SIZE_FOOTER = pt_from_px(19)        # 9.5 pt
MIN_CONTENT_PT = Pt(12)             # plancher absolu pour tout texte de contenu

# ---------------------------------------------------------------- gabarit
MARGIN_X = 109
MARGIN_TOP = 74
MARGIN_BOTTOM = 64

CONTENT_Y = 217
CONTENT_W = 1701
CONTENT_H = 800

CARD_RADIUS_PX = 14
CARD_PADDING_PX = 30

LOGO_WIDTH_PX = 230
