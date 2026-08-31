"""Rendus de slide « design agile » — un module par famille de
placeholder, orchestré par build_ppt.py. Pilote : {{chart:burnup}}.

Toutes les positions sont exprimées en px de maquette (base 1920x1080) et
converties en EMU via style.px() — jamais de valeur brute EMU/Inches ici.
"""
import math
import re
from datetime import datetime, timezone

from lxml import etree
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import (XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION,
                              XL_MARKER_STYLE, XL_TICK_LABEL_POSITION)
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_SHAPE, PP_PLACEHOLDER
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Pt

import shapes as SH
import style as S

MOIS_FR = ["JANVIER", "FÉVRIER", "MARS", "AVRIL", "MAI", "JUIN", "JUILLET",
           "AOÛT", "SEPTEMBRE", "OCTOBRE", "NOVEMBRE", "DÉCEMBRE"]

CHART_W = 1330
RAIL_GAP = 31
RAIL_X = S.MARGIN_X + CHART_W + RAIL_GAP
RAIL_W = S.CONTENT_W - CHART_W - RAIL_GAP


def _parse_iso(iso):
    if not iso:
        return None
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None


def _mois_annee(dt):
    return f"{MOIS_FR[dt.month - 1]} {dt.year}"


def _ddmm(dt):
    return dt.strftime("%d/%m") if dt else ""


def _ddmmyyyy(dt):
    return dt.strftime("%d/%m/%Y") if dt else ""


def _fr_num(x, decimals=1):
    """Nombre au format FR (virgule décimale)."""
    return f"{x:,.{decimals}f}".replace(",", " ").replace(".", ",")


def _fr_num_compact(x):
    """Comme _fr_num, mais sans décimale inutile (5,0 -> 5) — les valeurs SP
    entières ne doivent pas être plus longues à l'affichage que leur
    équivalent US, sous peine de forcer un retour à la ligne dans les
    cartes du rail droit."""
    return _fr_num(x, 0) if float(x).is_integer() else _fr_num(x, 1)


def _estimate_text_height_px(text, width_px, font_size_px, line_height_mult=1.32):
    """Hauteur estimée (en px de maquette) qu'occupera `text` une fois wrappé
    sur `width_px` à `font_size_px` — python-pptx ne mesure pas le texte
    réel, donc heuristique (largeur moyenne de caractère ≈ 0.52 * la taille
    de police, valable pour une police proportionnelle sans-serif en
    français). Sert à dimensionner un bloc/une carte sur son besoin réel
    plutôt qu'une proportion fixe qui peut chevaucher le bloc suivant ou
    déborder de sa propre carte si le texte est plus long que prévu."""
    if not text:
        return 0
    avg_char_w = font_size_px * 0.52
    chars_per_line = max(int(width_px / avg_char_w), 1)
    lines = sum(max(math.ceil(len(p) / chars_per_line), 1) for p in text.split("\n"))
    return lines * font_size_px * line_height_mult


def _total_us(status_counts_us):
    return sum(status_counts_us.values())


def _waiting_us(status_counts_us):
    """US en attente/blocage externe — heuristique sur le libellé du statut."""
    return {k: v for k, v in status_counts_us.items() if "attente" in k.lower()}


def _set_manual_plot_area(chart, x_frac, y_frac, w_frac, h_frac):
    """Fige la zone de tracé à des fractions connues du cadre du graphique,
    indispensable pour positionner ensuite la bande de projection en overlay
    (python-pptx n'expose pas la zone de tracé réellement calculée par
    PowerPoint, donc on la fixe nous-mêmes)."""
    plot_area = chart._chartSpace.find(qn("c:chart")).find(qn("c:plotArea"))
    layout_xml = f'''<c:layout xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart">
  <c:manualLayout>
    <c:layoutTarget val="inner"/>
    <c:xMode val="edge"/><c:yMode val="edge"/>
    <c:x val="{x_frac}"/><c:y val="{y_frac}"/>
    <c:w val="{w_frac}"/><c:h val="{h_frac}"/>
  </c:manualLayout>
</c:layout>'''
    new_layout = etree.fromstring(layout_xml.encode("utf-8"))
    old_layout = plot_area.find(qn("c:layout"))
    if old_layout is not None:
        plot_area.remove(old_layout)
    plot_area.insert(0, new_layout)


def _delete_legend_entries(chart, indices):
    legend = chart._chartSpace.find(qn("c:chart")).find(qn("c:legend"))
    if legend is None:
        return
    ns = "http://schemas.openxmlformats.org/drawingml/2006/chart"
    for idx in indices:
        entry = etree.fromstring(
            f'<c:legendEntry xmlns:c="{ns}"><c:idx val="{idx}"/><c:delete val="1"/></c:legendEntry>'.encode("utf-8")
        )
        legend.insert(0, entry)


C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _first_plot_element(chart):
    plot_area = chart._chartSpace.find(qn("c:chart")).find(qn("c:plotArea"))
    for tag in ("c:areaChart", "c:barChart", "c:lineChart"):
        el = plot_area.find(qn(tag))
        if el is not None:
            return el, plot_area
    return None, plot_area


def _add_combo_area(chart, name, categories, values, color, opacity_pct, series_idx=40):
    """Ajoute un <c:areaChart> translucide en sœur du plot principal, inséré
    AVANT lui pour dessiner le remplissage derrière la ligne (ex. aire sous
    la courbe « Réel » du burndown, sans les marqueurs qu'une AreaSeries ne
    supporte pas nativement dans python-pptx)."""
    base_el, plot_area = _first_plot_element(chart)
    ax_ids = [e.get("val") for e in base_el.findall(qn("c:axId"))]
    cat_pts = "".join(f'<c:pt idx="{i}"><c:v>{c}</c:v></c:pt>' for i, c in enumerate(categories))
    val_pts = "".join(
        f'<c:pt idx="{i}"><c:v>{v}</c:v></c:pt>' for i, v in enumerate(values) if v is not None
    )
    alpha = round((100 - opacity_pct) * 1000)
    area_xml = f'''<c:areaChart xmlns:c="{C_NS}" xmlns:a="{A_NS}">
  <c:grouping val="standard"/><c:varyColors val="0"/>
  <c:ser>
    <c:idx val="{series_idx}"/><c:order val="{series_idx}"/>
    <c:tx><c:strRef><c:f></c:f><c:strCache><c:ptCount val="1"/>
      <c:pt idx="0"><c:v>{name}</c:v></c:pt></c:strCache></c:strRef></c:tx>
    <c:spPr>
      <a:solidFill><a:srgbClr val="{color}"><a:alpha val="{alpha}"/></a:srgbClr></a:solidFill>
      <a:ln><a:noFill/></a:ln>
    </c:spPr>
    <c:cat><c:strRef><c:f></c:f><c:strCache><c:ptCount val="{len(categories)}"/>
      {cat_pts}</c:strCache></c:strRef></c:cat>
    <c:val><c:numRef><c:f></c:f><c:numCache><c:formatCode>General</c:formatCode>
      <c:ptCount val="{len(values)}"/>{val_pts}</c:numCache></c:numRef></c:val>
  </c:ser>
  <c:axId val="{ax_ids[0]}"/><c:axId val="{ax_ids[1]}"/>
</c:areaChart>'''
    base_el.addprevious(etree.fromstring(area_xml.encode("utf-8")))
    return series_idx


def _add_combo_line(chart, name, categories, values, color, weight_pt, dash=None,
                     series_idx=50):
    """Ajoute un <c:lineChart> en sœur du plot principal (aire/barres), avec
    ses propres axId — combo natif, cf. la même technique que la ligne
    médiane du chart:velocity."""
    base_el, plot_area = _first_plot_element(chart)
    ax_ids = [e.get("val") for e in base_el.findall(qn("c:axId"))]
    cat_pts = "".join(f'<c:pt idx="{i}"><c:v>{c}</c:v></c:pt>' for i, c in enumerate(categories))
    val_pts = "".join(
        f'<c:pt idx="{i}"><c:v>{v}</c:v></c:pt>' for i, v in enumerate(values) if v is not None
    )
    dash_xml = f'<a:prstDash val="{dash}"/>' if dash else ""
    line_xml = f'''<c:lineChart xmlns:c="{C_NS}" xmlns:a="{A_NS}">
  <c:grouping val="standard"/><c:varyColors val="0"/>
  <c:ser>
    <c:idx val="{series_idx}"/><c:order val="{series_idx}"/>
    <c:tx><c:strRef><c:f></c:f><c:strCache><c:ptCount val="1"/>
      <c:pt idx="0"><c:v>{name}</c:v></c:pt></c:strCache></c:strRef></c:tx>
    <c:spPr><a:ln w="{round(weight_pt * 12700)}" cap="rnd">
      <a:solidFill><a:srgbClr val="{color}"/></a:solidFill>{dash_xml}
    </a:ln></c:spPr>
    <c:marker><c:symbol val="none"/></c:marker>
    <c:cat><c:strRef><c:f></c:f><c:strCache><c:ptCount val="{len(categories)}"/>
      {cat_pts}</c:strCache></c:strRef></c:cat>
    <c:val><c:numRef><c:f></c:f><c:numCache><c:formatCode>General</c:formatCode>
      <c:ptCount val="{len(values)}"/>{val_pts}</c:numCache></c:numRef></c:val>
    <c:smooth val="0"/>
  </c:ser>
  <c:marker val="1"/>
  <c:axId val="{ax_ids[0]}"/><c:axId val="{ax_ids[1]}"/>
</c:lineChart>'''
    base_el.addnext(etree.fromstring(line_xml.encode("utf-8")))


def _style_line_series(series, color, weight_pt, dash=None, smooth=False):
    series.smooth = smooth
    line = series.format.line
    line.color.rgb = color
    line.width = Pt(weight_pt)
    if dash:
        line.dash_style = dash
    series.marker.style = XL_MARKER_STYLE.NONE


def _mark_arrival_point(series, idx, color):
    """Marqueur plein uniquement sur le point d'arrivée (là où la tendance
    atteint le périmètre), les autres points de la série restent sans
    marqueur — géré au niveau du point, pas de la série entière."""
    pt = series.points[idx]
    pt.marker.style = XL_MARKER_STYLE.CIRCLE
    pt.marker.size = 9
    pt.marker.format.fill.solid()
    pt.marker.format.fill.fore_color.rgb = color
    pt.marker.format.line.color.rgb = color


def _first_arrival_index(trend, target, start_idx):
    for i in range(start_idx, len(trend)):
        if trend[i] is not None and trend[i] >= target:
            return i
    return len(trend) - 1


# axId sentinels pour l'axe secondaire (Story Points) — distincts des axId
# que python-pptx attribue par défaut à l'axe primaire (toujours les mêmes
# deux valeurs, ex. 2118791784/2140495176, quel que soit le chart).
SEC_CAT_AX_ID = 900000001
SEC_VAL_AX_ID = 900000002


def _add_secondary_axis(chart, categories, series_specs, number_format="General"):
    """Ajoute un groupe de séries sur un second axe de valeurs (échelle
    différente de l'axe primaire — ex. Story Points à côté d'un comptage de
    US), affiché à droite. `series_specs` : liste de (name, values, color,
    weight_pt, dash). Contrairement à _add_combo_line/_add_combo_area (même
    échelle que le plot de base, mêmes axId réutilisés), ce groupe a ses
    propres axId : un nouvel axe de valeurs (à droite) et un axe de
    catégories jumeau caché — requis par le schéma OOXML pour tout groupe de
    séries sur un axe secondaire, même quand les catégories sont identiques
    à celles de l'axe primaire."""
    base_el, plot_area = _first_plot_element(chart)
    cat_pts = "".join(f'<c:pt idx="{i}"><c:v>{c}</c:v></c:pt>' for i, c in enumerate(categories))

    sers_xml = []
    for series_idx, (name, values, color, weight_pt, dash) in enumerate(series_specs, start=60):
        val_pts = "".join(
            f'<c:pt idx="{i}"><c:v>{v}</c:v></c:pt>' for i, v in enumerate(values) if v is not None
        )
        dash_xml = f'<a:prstDash val="{dash}"/>' if dash else ""
        sers_xml.append(f'''<c:ser>
    <c:idx val="{series_idx}"/><c:order val="{series_idx}"/>
    <c:tx><c:strRef><c:f></c:f><c:strCache><c:ptCount val="1"/>
      <c:pt idx="0"><c:v>{name}</c:v></c:pt></c:strCache></c:strRef></c:tx>
    <c:spPr><a:ln w="{round(weight_pt * 12700)}" cap="rnd">
      <a:solidFill><a:srgbClr val="{color}"/></a:solidFill>{dash_xml}
    </a:ln></c:spPr>
    <c:marker><c:symbol val="none"/></c:marker>
    <c:cat><c:strRef><c:f></c:f><c:strCache><c:ptCount val="{len(categories)}"/>
      {cat_pts}</c:strCache></c:strRef></c:cat>
    <c:val><c:numRef><c:f></c:f><c:numCache><c:formatCode>General</c:formatCode>
      <c:ptCount val="{len(values)}"/>{val_pts}</c:numCache></c:numRef></c:val>
    <c:smooth val="0"/>
  </c:ser>''')

    group_xml = f'''<c:lineChart xmlns:c="{C_NS}" xmlns:a="{A_NS}">
  <c:grouping val="standard"/><c:varyColors val="0"/>
  {"".join(sers_xml)}
  <c:marker val="1"/>
  <c:axId val="{SEC_CAT_AX_ID}"/><c:axId val="{SEC_VAL_AX_ID}"/>
</c:lineChart>'''
    base_el.addnext(etree.fromstring(group_xml.encode("utf-8")))

    val_ax_xml = f'''<c:valAx xmlns:c="{C_NS}">
  <c:axId val="{SEC_VAL_AX_ID}"/>
  <c:scaling><c:orientation val="minMax"/></c:scaling>
  <c:delete val="0"/>
  <c:axPos val="r"/>
  <c:numFmt formatCode="{number_format}" sourceLinked="0"/>
  <c:majorTickMark val="out"/><c:minorTickMark val="none"/>
  <c:tickLblPos val="nextTo"/>
  <c:crossAx val="{SEC_CAT_AX_ID}"/>
  <c:crosses val="max"/>
</c:valAx>'''
    cat_ax_xml = f'''<c:catAx xmlns:c="{C_NS}">
  <c:axId val="{SEC_CAT_AX_ID}"/>
  <c:scaling><c:orientation val="minMax"/></c:scaling>
  <c:delete val="1"/>
  <c:axPos val="b"/>
  <c:majorTickMark val="none"/><c:minorTickMark val="none"/>
  <c:tickLblPos val="none"/>
  <c:crossAx val="{SEC_VAL_AX_ID}"/>
</c:catAx>'''
    existing_axes = plot_area.findall(qn("c:valAx")) + plot_area.findall(qn("c:catAx"))
    anchor = existing_axes[-1] if existing_axes else base_el
    anchor.addnext(etree.fromstring(val_ax_xml.encode("utf-8")))
    anchor.addnext(etree.fromstring(cat_ax_xml.encode("utf-8")))


def render_burnup(slide, placeholder_shape, data, template_path, page_num, total_pages):
    m = data["metrics"]
    br = m.get("burnup_release")
    project_name = data["project_name"].strip()
    SH.clear_legacy_chrome(slide)
    SH.clear_placeholder(placeholder_shape)

    burnup = m["burnup"]
    anchor_idx = br["anchor_index"] if br else len(burnup) - 1
    first_real_start = _parse_iso(burnup[1]["start"]) if len(burnup) > 1 else _parse_iso(burnup[0]["end"])
    last_real_end = _parse_iso(burnup[anchor_idx]["end"]) or _parse_iso(burnup[anchor_idx]["start"])
    last_num = burnup[anchor_idx]["num"]
    if first_real_start and last_real_end:
        surtitre = f"S0 → S{last_num} · {_mois_annee(first_real_start)} À {_mois_annee(last_real_end)}".upper()
    else:
        surtitre = f"S0 → S{last_num}"
    SH.add_header(slide, surtitre, "Burnup release", template_path)

    categories = br["categories"] if br else []
    if not br:
        SH.add_text(slide, S.MARGIN_X, S.CONTENT_Y + 40, S.CONTENT_W, 60,
                    "Pas assez de données pour tracer un burnup release.",
                    size=S.SIZE_BODY, color=S.TEXT_SECONDARY)
        SH.add_footer(slide, project_name, page_num, total_pages)
        return

    scope = br["scope_cumul_us"]
    done = br["done_cumul_us"]
    target = scope[anchor_idx]
    start_done = done[anchor_idx]
    has_trend = bool(br.get("trend_pessimist"))

    # ---------------------------------------------------------- graphique
    cd = CategoryChartData()
    cd.categories = categories
    cd.add_series("Périmètre cumulé (US)", scope)
    cd.add_series("Terminé cumulé (US)", done)
    if has_trend:
        cd.add_series("Tendance pessimiste", br["trend_pessimist"])
        cd.add_series("Tendance médiane", br["trend_median"])
        cd.add_series("Tendance optimiste", br["trend_optimist"])

    gf = slide.shapes.add_chart(XL_CHART_TYPE.LINE, S.px(S.MARGIN_X), S.px(S.CONTENT_Y),
                                 S.px(CHART_W), S.px(S.CONTENT_H), cd)
    chart = gf.chart
    chart.has_title = False
    plots = chart.plots[0]
    plots.gap_width = 0

    x_frac, y_frac, w_frac, h_frac = 0.02, 0.03, 0.96, 0.80
    _set_manual_plot_area(chart, x_frac, y_frac, w_frac, h_frac)

    series = plots.series
    _style_line_series(series[0], S.BRAND_PRIMARY, 4)
    _style_line_series(series[1], S.BRAND_ACCENT, 4)
    if has_trend:
        _style_line_series(series[2], S.TREND_PESSIMIST, 2, dash=MSO_LINE_DASH_STYLE.DASH)
        _style_line_series(series[3], S.TREND_MEDIAN, 2, dash=MSO_LINE_DASH_STYLE.DASH)
        _style_line_series(series[4], S.TREND_OPTIMIST, 2, dash=MSO_LINE_DASH_STYLE.DASH)
        _mark_arrival_point(series[2], _first_arrival_index(br["trend_pessimist"], target, anchor_idx), S.TREND_PESSIMIST)
        _mark_arrival_point(series[3], _first_arrival_index(br["trend_median"], target, anchor_idx), S.TREND_MEDIAN)
        _mark_arrival_point(series[4], _first_arrival_index(br["trend_optimist"], target, anchor_idx), S.TREND_OPTIMIST)
        _delete_legend_entries(chart, [2, 3, 4])

    _add_secondary_axis(chart, categories, [
        ("Périmètre cumulé (SP)", br["scope_cumul_sp"], "7FB2CE", 3, "dash"),
        ("Terminé cumulé (SP)", br["done_cumul_sp"], "F9A48C", 3, "dash"),
    ])

    chart.has_legend = True
    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.legend.include_in_layout = False
    chart.legend.font.size = S.SIZE_LEGEND
    chart.legend.font.color.rgb = S.TEXT_PRIMARY

    cat_ax = chart.category_axis
    cat_ax.format.line.color.rgb = S.CARD_BORDER
    cat_ax.tick_labels.font.size = Pt(9.5)  # labels d'axe : exception autorisée sous 12 pt
    cat_ax.tick_labels.font.color.rgb = S.TEXT_FOOTER
    skip = max(1, round(len(categories) / 12))
    ax_el = cat_ax._element
    tls = ax_el.find(qn("c:tickLblSkip"))
    if tls is None:
        tls = ax_el.makeelement(qn("c:tickLblSkip"), {})
        ax_el.append(tls)
    tls.set("val", str(skip))

    val_ax = chart.value_axis
    val_ax.has_major_gridlines = True
    val_ax.major_gridlines.format.line.color.rgb = S.CARD_BORDER_INNER
    val_ax.tick_labels.font.size = Pt(9.5)
    val_ax.tick_labels.font.color.rgb = S.TEXT_FOOTER
    val_ax.format.line.fill.background()

    # -------------------------------------------------- bande de projection
    if has_trend:
        n = len(categories)
        plot_x0 = S.MARGIN_X + CHART_W * x_frac
        plot_w = CHART_W * w_frac
        plot_y0 = S.CONTENT_Y + S.CONTENT_H * y_frac
        plot_h = S.CONTENT_H * h_frac
        anchor_x = plot_x0 + plot_w * (anchor_idx / (n - 1))
        band_x = anchor_x
        band_w = plot_x0 + plot_w - anchor_x
        band = SH.add_rect(slide, band_x, plot_y0, band_w, plot_h, fill=S.BRAND_PRIMARY, line_color=None)
        SH.set_transparency(band, 96.5)  # 3.5 % d'opacité
        line = SH.add_rect(slide, anchor_x, plot_y0, 1.5, plot_h, fill=S.BRAND_PRIMARY, line_color=None)
        SH.add_text(slide, anchor_x + 10, plot_y0 + 8, band_w - 20, 30,
                    f"Projection depuis S{last_num}", size=Pt(9.5), color=S.BRAND_PRIMARY, bold=True)

    # ------------------------------------------------------------ rail droit
    y = S.CONTENT_Y
    avancement = round(100 * start_done / target) if target else 0
    _card_stat(slide, RAIL_X, y, RAIL_W, 174, "AVANCEMENT", f"{avancement} %",
               f"{start_done} US sur {target}")
    y += 174 + 20

    if has_trend:
        v = br["velocity_us"]
        remaining = target - start_done
        scenarios = [
            ("OPTIMISTE", S.TREND_OPTIMIST, v["optimist"], br["trend_optimist"]),
            ("MÉDIANE", S.TREND_MEDIAN, v["median"], br["trend_median"]),
            ("PESSIMISTE", S.TREND_PESSIMIST, v["pessimist"], br["trend_pessimist"]),
        ]
        card_h = (S.CONTENT_H - 174 - 20 * 3) / 3
        for label, color, throughput, trend in scenarios:
            arrival = _first_arrival_index(trend, target, anchor_idx)
            label_sprint = f"S{last_num + (arrival - anchor_idx)}" if arrival >= anchor_idx else f"S{last_num}"
            date_line = _ddmmyyyy(_parse_iso(br["category_dates"][arrival]))
            _card_scenario(slide, RAIL_X, y, RAIL_W, card_h, label, color,
                            f"{label_sprint}", f"{throughput} US / sprint", date_line)
            y += card_h + 20
    else:
        remaining_h = S.CONTENT_H - 174 - 20
        _card_alert(slide, RAIL_X, y, RAIL_W, remaining_h, "PROJECTION DE FIN",
                    "Non calculable",
                    "Les scénarios pessimiste, médian et optimiste sont absents : "
                    "l'historique de livraison n'est pas assez stable pour projeter une date.")

    SH.add_footer(slide, project_name, page_num, total_pages)


def _render_burnup_single_unit(slide, placeholder_shape, data, template_path, page_num, total_pages, unit):
    """Variante mono-unité de render_burnup — `unit` "us" (nombre de tickets)
    ou "sp" (story points) — un seul axe, pas de superposition. Pour les cas
    où l'axe secondaire nuit à la lisibilité ou où les SP ne sont pas
    systématiquement renseignées. Pas de tendance calculée pour "sp" — voir
    indicators/burnup.py."""
    m = data["metrics"]
    br = m.get("burnup_release")
    project_name = data["project_name"].strip()
    SH.clear_legacy_chrome(slide)
    SH.clear_placeholder(placeholder_shape)

    unit_label = "US" if unit == "us" else "SP"
    numfmt = (lambda v: _fr_num_compact(v)) if unit == "sp" else (lambda v: v)

    burnup = m["burnup"]
    anchor_idx = br["anchor_index"] if br else len(burnup) - 1
    first_real_start = _parse_iso(burnup[1]["start"]) if len(burnup) > 1 else _parse_iso(burnup[0]["end"])
    last_real_end = _parse_iso(burnup[anchor_idx]["end"]) or _parse_iso(burnup[anchor_idx]["start"])
    last_num = burnup[anchor_idx]["num"]
    if first_real_start and last_real_end:
        surtitre = f"S0 → S{last_num} · {_mois_annee(first_real_start)} À {_mois_annee(last_real_end)}".upper()
    else:
        surtitre = f"S0 → S{last_num}"
    SH.add_header(slide, surtitre, f"Burnup release ({unit_label})", template_path)

    categories = br["categories"] if br else []
    if not br:
        SH.add_text(slide, S.MARGIN_X, S.CONTENT_Y + 40, S.CONTENT_W, 60,
                    "Pas assez de données pour tracer un burnup release.",
                    size=S.SIZE_BODY, color=S.TEXT_SECONDARY)
        SH.add_footer(slide, project_name, page_num, total_pages)
        return

    scope = br["scope_cumul_us"] if unit == "us" else br["scope_cumul_sp"]
    done = br["done_cumul_us"] if unit == "us" else br["done_cumul_sp"]
    target = scope[anchor_idx]
    start_done = done[anchor_idx]
    has_trend = unit == "us" and bool(br.get("trend_pessimist"))

    # ---------------------------------------------------------- graphique
    cd = CategoryChartData()
    cd.categories = categories
    cd.add_series(f"Périmètre cumulé ({unit_label})", scope)
    cd.add_series(f"Terminé cumulé ({unit_label})", done)
    if has_trend:
        cd.add_series("Tendance pessimiste", br["trend_pessimist"])
        cd.add_series("Tendance médiane", br["trend_median"])
        cd.add_series("Tendance optimiste", br["trend_optimist"])

    gf = slide.shapes.add_chart(XL_CHART_TYPE.LINE, S.px(S.MARGIN_X), S.px(S.CONTENT_Y),
                                 S.px(CHART_W), S.px(S.CONTENT_H), cd)
    chart = gf.chart
    chart.has_title = False
    plots = chart.plots[0]
    plots.gap_width = 0

    x_frac, y_frac, w_frac, h_frac = 0.02, 0.03, 0.96, 0.80
    _set_manual_plot_area(chart, x_frac, y_frac, w_frac, h_frac)

    series = plots.series
    _style_line_series(series[0], S.BRAND_PRIMARY, 4)
    _style_line_series(series[1], S.BRAND_ACCENT, 4)
    if has_trend:
        _style_line_series(series[2], S.TREND_PESSIMIST, 2, dash=MSO_LINE_DASH_STYLE.DASH)
        _style_line_series(series[3], S.TREND_MEDIAN, 2, dash=MSO_LINE_DASH_STYLE.DASH)
        _style_line_series(series[4], S.TREND_OPTIMIST, 2, dash=MSO_LINE_DASH_STYLE.DASH)
        _mark_arrival_point(series[2], _first_arrival_index(br["trend_pessimist"], target, anchor_idx), S.TREND_PESSIMIST)
        _mark_arrival_point(series[3], _first_arrival_index(br["trend_median"], target, anchor_idx), S.TREND_MEDIAN)
        _mark_arrival_point(series[4], _first_arrival_index(br["trend_optimist"], target, anchor_idx), S.TREND_OPTIMIST)
        _delete_legend_entries(chart, [2, 3, 4])

    chart.has_legend = True
    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.legend.include_in_layout = False
    chart.legend.font.size = S.SIZE_LEGEND
    chart.legend.font.color.rgb = S.TEXT_PRIMARY

    cat_ax = chart.category_axis
    cat_ax.format.line.color.rgb = S.CARD_BORDER
    cat_ax.tick_labels.font.size = Pt(9.5)
    cat_ax.tick_labels.font.color.rgb = S.TEXT_FOOTER
    skip = max(1, round(len(categories) / 12))
    ax_el = cat_ax._element
    tls = ax_el.find(qn("c:tickLblSkip"))
    if tls is None:
        tls = ax_el.makeelement(qn("c:tickLblSkip"), {})
        ax_el.append(tls)
    tls.set("val", str(skip))

    val_ax = chart.value_axis
    val_ax.has_major_gridlines = True
    val_ax.major_gridlines.format.line.color.rgb = S.CARD_BORDER_INNER
    val_ax.tick_labels.font.size = Pt(9.5)
    val_ax.tick_labels.font.color.rgb = S.TEXT_FOOTER
    val_ax.format.line.fill.background()

    # -------------------------------------------------- bande de projection
    if has_trend:
        n = len(categories)
        plot_x0 = S.MARGIN_X + CHART_W * x_frac
        plot_w = CHART_W * w_frac
        plot_y0 = S.CONTENT_Y + S.CONTENT_H * y_frac
        plot_h = S.CONTENT_H * h_frac
        anchor_x = plot_x0 + plot_w * (anchor_idx / (n - 1))
        band_x = anchor_x
        band_w = plot_x0 + plot_w - anchor_x
        band = SH.add_rect(slide, band_x, plot_y0, band_w, plot_h, fill=S.BRAND_PRIMARY, line_color=None)
        SH.set_transparency(band, 96.5)
        SH.add_rect(slide, anchor_x, plot_y0, 1.5, plot_h, fill=S.BRAND_PRIMARY, line_color=None)
        SH.add_text(slide, anchor_x + 10, plot_y0 + 8, band_w - 20, 30,
                    f"Projection depuis S{last_num}", size=Pt(9.5), color=S.BRAND_PRIMARY, bold=True)

    # ------------------------------------------------------------ rail droit
    y = S.CONTENT_Y
    avancement = round(100 * start_done / target) if target else 0
    _card_stat(slide, RAIL_X, y, RAIL_W, 174, "AVANCEMENT", f"{avancement} %",
               f"{numfmt(start_done)} {unit_label} sur {numfmt(target)}")
    y += 174 + 20

    if has_trend:
        v = br["velocity_us"]
        scenarios = [
            ("OPTIMISTE", S.TREND_OPTIMIST, v["optimist"], br["trend_optimist"]),
            ("MÉDIANE", S.TREND_MEDIAN, v["median"], br["trend_median"]),
            ("PESSIMISTE", S.TREND_PESSIMIST, v["pessimist"], br["trend_pessimist"]),
        ]
        card_h = (S.CONTENT_H - 174 - 20 * 3) / 3
        for label, color, throughput, trend in scenarios:
            arrival = _first_arrival_index(trend, target, anchor_idx)
            label_sprint = f"S{last_num + (arrival - anchor_idx)}" if arrival >= anchor_idx else f"S{last_num}"
            date_line = _ddmmyyyy(_parse_iso(br["category_dates"][arrival]))
            _card_scenario(slide, RAIL_X, y, RAIL_W, card_h, label, color,
                            f"{label_sprint}", f"{throughput} US / sprint", date_line)
            y += card_h + 20
    else:
        remaining_h = S.CONTENT_H - 174 - 20
        msg = (
            "Les scénarios pessimiste, médian et optimiste sont absents : "
            "l'historique de livraison n'est pas assez stable pour projeter une date."
            if unit == "us" else
            "Pas de tendance calculée en story points pour l'instant — voir la "
            "slide Burnup release (US) pour la projection en tickets."
        )
        _card_alert(slide, RAIL_X, y, RAIL_W, remaining_h, "PROJECTION DE FIN", "Non calculable", msg)

    SH.add_footer(slide, project_name, page_num, total_pages)


def render_burnup_nb(slide, placeholder_shape, data, template_path, page_num, total_pages):
    _render_burnup_single_unit(slide, placeholder_shape, data, template_path, page_num, total_pages, "us")


def render_burnup_sp(slide, placeholder_shape, data, template_path, page_num, total_pages):
    _render_burnup_single_unit(slide, placeholder_shape, data, template_path, page_num, total_pages, "sp")


# ================================================================= burndown
def render_burndown(slide, placeholder_shape, data, template_path, page_num, total_pages):
    m = data["metrics"]
    bd = m.get("burndown_sprint")
    project_name = data["project_name"].strip()
    SH.clear_legacy_chrome(slide)
    SH.clear_placeholder(placeholder_shape)

    if not bd:
        SH.add_header(slide, "AUCUN SPRINT ACTIF", "Burndown du sprint", template_path)
        SH.add_text(slide, S.MARGIN_X, S.CONTENT_Y + 40, S.CONTENT_W, 60,
                    "Aucun sprint en cours pour calculer un burndown.",
                    size=S.SIZE_BODY, color=S.TEXT_SECONDARY)
        SH.add_footer(slide, project_name, page_num, total_pages)
        return

    real_known = [v for v in bd["real"] if v is not None]
    surtitre = f"SPRINT {bd['sprint'].split()[-1]} · {bd['categories'][0]} → {bd['categories'][-1]}".upper()
    SH.add_header(slide, surtitre, "Burndown du sprint", template_path)

    scope = bd["scope"]
    remaining_now = real_known[-1] if real_known else scope

    if len(real_known) <= 1:
        # Le sprint vient de démarrer : un seul point connu, pas de courbe.
        cx = S.MARGIN_X + CHART_W / 2
        cy = S.CONTENT_Y + S.CONTENT_H / 2
        SH.add_rounded_rect(slide, S.MARGIN_X, S.CONTENT_Y, CHART_W, S.CONTENT_H)
        SH.add_rect(slide, cx - 10, cy - 10, 20, 20, fill=S.BRAND_ACCENT, line_color=None)
        SH.add_text(slide, S.MARGIN_X, cy + 30, CHART_W, 40,
                    f"{scope} US engagées, 0 terminée au {bd['categories'][0]}",
                    size=S.SIZE_BODY, color=S.TEXT_PRIMARY, align=PP_ALIGN.CENTER)
    else:
        cd = CategoryChartData()
        cd.categories = bd["categories"]
        cd.add_series("Reste à faire (US)", bd["real"])
        gf = slide.shapes.add_chart(XL_CHART_TYPE.LINE, S.px(S.MARGIN_X), S.px(S.CONTENT_Y),
                                     S.px(CHART_W), S.px(S.CONTENT_H), cd)
        chart = gf.chart
        chart.has_title = False
        x_frac, y_frac, w_frac, h_frac = 0.02, 0.03, 0.96, 0.80
        _set_manual_plot_area(chart, x_frac, y_frac, w_frac, h_frac)

        series = chart.plots[0].series[0]
        series.smooth = False
        series.format.line.color.rgb = S.BRAND_ACCENT
        series.format.line.width = Pt(4)
        series.marker.style = XL_MARKER_STYLE.CIRCLE
        series.marker.size = 6
        series.marker.format.fill.solid()
        series.marker.format.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        series.marker.format.line.color.rgb = S.BRAND_ACCENT

        last_idx = max(i for i, v in enumerate(bd["real"]) if v is not None)
        last_pt = series.points[last_idx]
        last_pt.marker.size = 12
        last_pt.data_label.has_text_frame = True
        last_pt.data_label.text_frame.text = f"{remaining_now} US restantes"
        last_pt.data_label.text_frame.paragraphs[0].runs[0].font.size = Pt(11)
        last_pt.data_label.text_frame.paragraphs[0].runs[0].font.bold = True
        last_pt.data_label.text_frame.paragraphs[0].runs[0].font.color.rgb = S.BRAND_ACCENT

        # Aire sous la courbe « Réel » à 9 % d'opacité (combo, derrière la ligne)
        area_idx = _add_combo_area(chart, "Reste à faire (US)", bd["categories"], bd["real"],
                                    "F04E23", 9)
        _delete_legend_entries(chart, [area_idx])

        _add_combo_line(chart, "Droite idéale", bd["categories"], bd["ideal"],
                         "1F4E79", 2.25, dash="dash")

        _add_secondary_axis(chart, bd["categories"], [
            ("Reste à faire (SP)", bd["real_sp"], "F9A48C", 3, None),
            ("Droite idéale (SP)", bd["ideal_sp"], "7FB2CE", 2.25, "dash"),
        ])

        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        chart.legend.font.size = S.SIZE_LEGEND
        chart.legend.font.color.rgb = S.TEXT_PRIMARY

        cat_ax = chart.category_axis
        cat_ax.format.line.color.rgb = S.CARD_BORDER
        cat_ax.tick_labels.font.size = Pt(9.5)
        cat_ax.tick_labels.font.color.rgb = S.TEXT_FOOTER
        val_ax = chart.value_axis
        val_ax.has_major_gridlines = True
        val_ax.major_gridlines.format.line.color.rgb = S.CARD_BORDER_INNER
        val_ax.tick_labels.font.size = Pt(9.5)
        val_ax.tick_labels.font.color.rgb = S.TEXT_FOOTER
        val_ax.format.line.fill.background()

    # ------------------------------------------------------------ rail droit
    y = S.CONTENT_Y
    _card_stat(slide, RAIL_X, y, RAIL_W, 174, "PÉRIMÈTRE DU SPRINT", f"{scope} US", "reports inclus")
    y += 174 + 20

    alert = remaining_now > 0
    reste_h = 220
    if alert:
        _card_alert(slide, RAIL_X, y, RAIL_W, reste_h, "RESTE À FAIRE", f"{remaining_now} US",
                    "cible théorique : 0")
    else:
        _card_stat(slide, RAIL_X, y, RAIL_W, reste_h, "RESTE À FAIRE", f"{remaining_now} US",
                   "cible théorique : 0")
    y += reste_h + 20

    lecture = (data.get("coaching") or {}).get("burndown_lecture", "")
    _card_lecture(slide, RAIL_X, y, RAIL_W, S.CONTENT_H - 174 - reste_h - 40, lecture)

    SH.add_footer(slide, project_name, page_num, total_pages)


def _render_burndown_single_unit(slide, placeholder_shape, data, template_path, page_num, total_pages, unit):
    """Variante mono-unité de render_burndown — `unit` "us" ou "sp"."""
    m = data["metrics"]
    bd = m.get("burndown_sprint")
    project_name = data["project_name"].strip()
    SH.clear_legacy_chrome(slide)
    SH.clear_placeholder(placeholder_shape)

    unit_label = "US" if unit == "us" else "SP"
    numfmt = (lambda v: _fr_num_compact(v)) if unit == "sp" else (lambda v: v)
    scope_key = "scope" if unit == "us" else "scope_sp"
    real_key = "real" if unit == "us" else "real_sp"
    ideal_key = "ideal" if unit == "us" else "ideal_sp"

    if not bd:
        SH.add_header(slide, "AUCUN SPRINT ACTIF", f"Burndown du sprint ({unit_label})", template_path)
        SH.add_text(slide, S.MARGIN_X, S.CONTENT_Y + 40, S.CONTENT_W, 60,
                    "Aucun sprint en cours pour calculer un burndown.",
                    size=S.SIZE_BODY, color=S.TEXT_SECONDARY)
        SH.add_footer(slide, project_name, page_num, total_pages)
        return

    real_known = [v for v in bd[real_key] if v is not None]
    surtitre = f"SPRINT {bd['sprint'].split()[-1]} · {bd['categories'][0]} → {bd['categories'][-1]}".upper()
    SH.add_header(slide, surtitre, f"Burndown du sprint ({unit_label})", template_path)

    scope = bd[scope_key]
    remaining_now = real_known[-1] if real_known else scope

    if len(real_known) <= 1:
        # Le sprint vient de démarrer : un seul point connu, pas de courbe.
        cx = S.MARGIN_X + CHART_W / 2
        cy = S.CONTENT_Y + S.CONTENT_H / 2
        SH.add_rounded_rect(slide, S.MARGIN_X, S.CONTENT_Y, CHART_W, S.CONTENT_H)
        SH.add_rect(slide, cx - 10, cy - 10, 20, 20, fill=S.BRAND_ACCENT, line_color=None)
        SH.add_text(slide, S.MARGIN_X, cy + 30, CHART_W, 40,
                    f"{numfmt(scope)} {unit_label} engagé(e)s, 0 terminé(e) au {bd['categories'][0]}",
                    size=S.SIZE_BODY, color=S.TEXT_PRIMARY, align=PP_ALIGN.CENTER)
    else:
        cd = CategoryChartData()
        cd.categories = bd["categories"]
        cd.add_series(f"Reste à faire ({unit_label})", bd[real_key])
        gf = slide.shapes.add_chart(XL_CHART_TYPE.LINE, S.px(S.MARGIN_X), S.px(S.CONTENT_Y),
                                     S.px(CHART_W), S.px(S.CONTENT_H), cd)
        chart = gf.chart
        chart.has_title = False
        x_frac, y_frac, w_frac, h_frac = 0.02, 0.03, 0.96, 0.80
        _set_manual_plot_area(chart, x_frac, y_frac, w_frac, h_frac)

        series = chart.plots[0].series[0]
        series.smooth = False
        series.format.line.color.rgb = S.BRAND_ACCENT
        series.format.line.width = Pt(4)
        series.marker.style = XL_MARKER_STYLE.CIRCLE
        series.marker.size = 6
        series.marker.format.fill.solid()
        series.marker.format.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        series.marker.format.line.color.rgb = S.BRAND_ACCENT

        last_idx = max(i for i, v in enumerate(bd[real_key]) if v is not None)
        last_pt = series.points[last_idx]
        last_pt.marker.size = 12
        last_pt.data_label.has_text_frame = True
        last_pt.data_label.text_frame.text = f"{numfmt(remaining_now)} {unit_label} restant(e)s"
        last_pt.data_label.text_frame.paragraphs[0].runs[0].font.size = Pt(11)
        last_pt.data_label.text_frame.paragraphs[0].runs[0].font.bold = True
        last_pt.data_label.text_frame.paragraphs[0].runs[0].font.color.rgb = S.BRAND_ACCENT

        # Aire sous la courbe « Réel » à 9 % d'opacité (combo, derrière la ligne)
        area_idx = _add_combo_area(chart, f"Reste à faire ({unit_label})", bd["categories"], bd[real_key],
                                    "F04E23", 9)
        _delete_legend_entries(chart, [area_idx])

        _add_combo_line(chart, "Droite idéale", bd["categories"], bd[ideal_key],
                         "1F4E79", 2.25, dash="dash")

        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        chart.legend.font.size = S.SIZE_LEGEND
        chart.legend.font.color.rgb = S.TEXT_PRIMARY

        cat_ax = chart.category_axis
        cat_ax.format.line.color.rgb = S.CARD_BORDER
        cat_ax.tick_labels.font.size = Pt(9.5)
        cat_ax.tick_labels.font.color.rgb = S.TEXT_FOOTER
        val_ax = chart.value_axis
        val_ax.has_major_gridlines = True
        val_ax.major_gridlines.format.line.color.rgb = S.CARD_BORDER_INNER
        val_ax.tick_labels.font.size = Pt(9.5)
        val_ax.tick_labels.font.color.rgb = S.TEXT_FOOTER
        val_ax.format.line.fill.background()

    # ------------------------------------------------------------ rail droit
    y = S.CONTENT_Y
    _card_stat(slide, RAIL_X, y, RAIL_W, 174, "PÉRIMÈTRE DU SPRINT", f"{numfmt(scope)} {unit_label}",
               "reports inclus")
    y += 174 + 20

    alert = remaining_now > 0
    reste_h = 220
    if alert:
        _card_alert(slide, RAIL_X, y, RAIL_W, reste_h, "RESTE À FAIRE", f"{numfmt(remaining_now)} {unit_label}",
                    "cible théorique : 0")
    else:
        _card_stat(slide, RAIL_X, y, RAIL_W, reste_h, "RESTE À FAIRE", f"{numfmt(remaining_now)} {unit_label}",
                   "cible théorique : 0")
    y += reste_h + 20

    lecture = (data.get("coaching") or {}).get("burndown_lecture", "")
    _card_lecture(slide, RAIL_X, y, RAIL_W, S.CONTENT_H - 174 - reste_h - 40, lecture)

    SH.add_footer(slide, project_name, page_num, total_pages)


def render_burndown_nb(slide, placeholder_shape, data, template_path, page_num, total_pages):
    _render_burndown_single_unit(slide, placeholder_shape, data, template_path, page_num, total_pages, "us")


def render_burndown_sp(slide, placeholder_shape, data, template_path, page_num, total_pages):
    _render_burndown_single_unit(slide, placeholder_shape, data, template_path, page_num, total_pages, "sp")


# ================================================================= velocity
def render_velocity(slide, placeholder_shape, data, template_path, page_num, total_pages):
    m = data["metrics"]
    project_name = data["project_name"].strip()
    SH.clear_legacy_chrome(slide)
    SH.clear_placeholder(placeholder_shape)
    SH.add_header(slide, "ENGAGEMENT VS RÉALISÉ", "Vélocité par sprint", template_path)

    vel = [v for v in m["velocity"] if v["engaged"] or v["done"]]
    if not vel:
        SH.add_text(slide, S.MARGIN_X, S.CONTENT_Y + 40, S.CONTENT_W, 60,
                    "Pas encore de sprint avec engagement ou clôture d'US.",
                    size=S.SIZE_BODY, color=S.TEXT_SECONDARY)
        SH.add_footer(slide, project_name, page_num, total_pages)
        return

    state_by_sprint = {b["sprint"]: b["state"] for b in m["burnup"]}
    cats = [short_label(v["sprint"]) for v in vel]
    engaged_vals = [v["engaged"] for v in vel]
    done_vals = [v["done"] for v in vel]
    sp_engaged_vals = [v["sp_engaged"] for v in vel]
    sp_done_vals = [v["sp_done"] for v in vel]
    current_idx = next((i for i, v in enumerate(vel) if state_by_sprint.get(v["sprint"]) == "active"), None)

    cd = CategoryChartData()
    cd.categories = cats
    cd.add_series("Engagé", engaged_vals)
    cd.add_series("Terminé", done_vals)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, S.px(S.MARGIN_X), S.px(S.CONTENT_Y),
                                 S.px(CHART_W), S.px(S.CONTENT_H), cd)
    chart = gf.chart
    chart.has_title = False
    plot = chart.plots[0]
    plot.gap_width = 60
    plot.overlap = -10

    engaged_s, done_s = plot.series[0], plot.series[1]
    engaged_s.format.fill.solid()
    engaged_s.format.fill.fore_color.rgb = S.BLUE_FILL_3
    engaged_s.format.line.fill.background()
    done_s.format.fill.solid()
    done_s.format.fill.fore_color.rgb = S.BRAND_PRIMARY
    done_s.format.line.fill.background()
    if current_idx is not None:
        for ser in (engaged_s, done_s):
            pt = ser.points[current_idx]
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = S.BRAND_ACCENT

    show_labels = len(vel) <= 8
    x_frac, y_frac, w_frac, h_frac = 0.02, 0.03, 0.96, 0.78
    _set_manual_plot_area(chart, x_frac, y_frac, w_frac, h_frac)

    if show_labels:
        plot.has_data_labels = True
        dls = plot.data_labels
        dls.font.size = Pt(12)
        dls.font.bold = True
        dls.font.color.rgb = S.TEXT_PRIMARY
        dls.position = XL_LABEL_POSITION.OUTSIDE_END
        ymax = None
    else:
        ymax = max(5, math.ceil(max(engaged_vals + done_vals) / 5) * 5)

    val_ax = chart.value_axis
    val_ax.has_major_gridlines = not show_labels
    if val_ax.has_major_gridlines:
        val_ax.major_gridlines.format.line.color.rgb = S.CARD_BORDER_INNER
    if ymax:
        val_ax.maximum_scale = ymax
        val_ax.minimum_scale = 0
    val_ax.tick_labels.font.size = Pt(9.5)
    val_ax.tick_labels.font.color.rgb = S.TEXT_FOOTER
    val_ax.visible = not show_labels
    val_ax.format.line.fill.background()

    cat_ax = chart.category_axis
    cat_ax.format.line.color.rgb = S.CARD_BORDER
    cat_ax.tick_labels.font.size = Pt(9.5)
    cat_ax.tick_labels.font.color.rgb = S.TEXT_FOOTER

    _add_secondary_axis(chart, cats, [
        ("Engagé (SP)", sp_engaged_vals, "7FB2CE", 2.5, "dash"),
        ("Terminé (SP)", sp_done_vals, "F9A48C", 2.5, None),
    ])

    median = m["median_velocity_us"]
    if median and ymax:
        _add_combo_line(chart, "Médiane", cats, [median] * len(cats), "1F4E79", 1.5, dash="dash")
        _delete_legend_entries(chart, [50])
        plot_y0 = S.CONTENT_Y + S.CONTENT_H * y_frac
        plot_h = S.CONTENT_H * h_frac
        label_y = plot_y0 + plot_h * (1 - min(median / ymax, 1)) - 24
        SH.add_text(slide, S.MARGIN_X + CHART_W - 220, max(label_y, S.CONTENT_Y), 200, 24,
                    f"Médiane {median:g} US", size=Pt(10.5), color=S.BRAND_PRIMARY, bold=True,
                    align=PP_ALIGN.RIGHT)

    chart.has_legend = True
    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.legend.include_in_layout = False
    chart.legend.font.size = S.SIZE_LEGEND
    chart.legend.font.color.rgb = S.TEXT_PRIMARY

    # ------------------------------------------------------------ rail droit
    y = S.CONTENT_Y
    _card_stat(slide, RAIL_X, y, RAIL_W, 174, "VÉLOCITÉ MÉDIANE", f"{median:g} US",
               "sprints à 0 terminé exclus")
    y += 174 + 20

    positive_done = [v["done"] for v in vel if v["done"] > 0]
    fourchette = f"{min(positive_done)} – {max(positive_done)} US" if positive_done else "n/a"
    _card_stat(slide, RAIL_X, y, RAIL_W, 174, "FOURCHETTE", fourchette, "US terminées / sprint")
    y += 174 + 20

    lecture = (data.get("coaching") or {}).get("velocity_lecture", "")
    _card_lecture(slide, RAIL_X, y, RAIL_W, S.CONTENT_H - 2 * (174 + 20), lecture)

    SH.add_footer(slide, project_name, page_num, total_pages)


def _render_velocity_single_unit(slide, placeholder_shape, data, template_path, page_num, total_pages, unit):
    """Variante mono-unité de render_velocity — `unit` "us" ou "sp"."""
    m = data["metrics"]
    project_name = data["project_name"].strip()
    SH.clear_legacy_chrome(slide)
    SH.clear_placeholder(placeholder_shape)

    unit_label = "US" if unit == "us" else "SP"
    numfmt = (lambda v: _fr_num_compact(v)) if unit == "sp" else (lambda v: f"{v:g}")
    SH.add_header(slide, "ENGAGEMENT VS RÉALISÉ", f"Vélocité par sprint ({unit_label})", template_path)

    vel = [v for v in m["velocity"] if v["engaged"] or v["done"]]
    if not vel:
        SH.add_text(slide, S.MARGIN_X, S.CONTENT_Y + 40, S.CONTENT_W, 60,
                    "Pas encore de sprint avec engagement ou clôture d'US.",
                    size=S.SIZE_BODY, color=S.TEXT_SECONDARY)
        SH.add_footer(slide, project_name, page_num, total_pages)
        return

    engaged_key = "engaged" if unit == "us" else "sp_engaged"
    done_key = "done" if unit == "us" else "sp_done"

    state_by_sprint = {b["sprint"]: b["state"] for b in m["burnup"]}
    cats = [short_label(v["sprint"]) for v in vel]
    engaged_vals = [v[engaged_key] for v in vel]
    done_vals = [v[done_key] for v in vel]
    current_idx = next((i for i, v in enumerate(vel) if state_by_sprint.get(v["sprint"]) == "active"), None)

    cd = CategoryChartData()
    cd.categories = cats
    cd.add_series(f"Engagé ({unit_label})", engaged_vals)
    cd.add_series(f"Terminé ({unit_label})", done_vals)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, S.px(S.MARGIN_X), S.px(S.CONTENT_Y),
                                 S.px(CHART_W), S.px(S.CONTENT_H), cd)
    chart = gf.chart
    chart.has_title = False
    plot = chart.plots[0]
    plot.gap_width = 60
    plot.overlap = -10

    engaged_s, done_s = plot.series[0], plot.series[1]
    engaged_s.format.fill.solid()
    engaged_s.format.fill.fore_color.rgb = S.BLUE_FILL_3
    engaged_s.format.line.fill.background()
    done_s.format.fill.solid()
    done_s.format.fill.fore_color.rgb = S.BRAND_PRIMARY
    done_s.format.line.fill.background()
    if current_idx is not None:
        for ser in (engaged_s, done_s):
            pt = ser.points[current_idx]
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = S.BRAND_ACCENT

    show_labels = len(vel) <= 8
    x_frac, y_frac, w_frac, h_frac = 0.02, 0.03, 0.96, 0.78
    _set_manual_plot_area(chart, x_frac, y_frac, w_frac, h_frac)

    if show_labels:
        plot.has_data_labels = True
        dls = plot.data_labels
        dls.font.size = Pt(12)
        dls.font.bold = True
        dls.font.color.rgb = S.TEXT_PRIMARY
        dls.position = XL_LABEL_POSITION.OUTSIDE_END
        ymax = None
    else:
        ymax = max(5, math.ceil(max(engaged_vals + done_vals) / 5) * 5)

    val_ax = chart.value_axis
    val_ax.has_major_gridlines = not show_labels
    if val_ax.has_major_gridlines:
        val_ax.major_gridlines.format.line.color.rgb = S.CARD_BORDER_INNER
    if ymax:
        val_ax.maximum_scale = ymax
        val_ax.minimum_scale = 0
    val_ax.tick_labels.font.size = Pt(9.5)
    val_ax.tick_labels.font.color.rgb = S.TEXT_FOOTER
    val_ax.visible = not show_labels
    val_ax.format.line.fill.background()

    cat_ax = chart.category_axis
    cat_ax.format.line.color.rgb = S.CARD_BORDER
    cat_ax.tick_labels.font.size = Pt(9.5)
    cat_ax.tick_labels.font.color.rgb = S.TEXT_FOOTER

    median = m["median_velocity_us"] if unit == "us" else m["median_velocity_sp"]
    if median and ymax:
        _add_combo_line(chart, "Médiane", cats, [median] * len(cats), "1F4E79", 1.5, dash="dash")
        _delete_legend_entries(chart, [50])
        plot_y0 = S.CONTENT_Y + S.CONTENT_H * y_frac
        plot_h = S.CONTENT_H * h_frac
        label_y = plot_y0 + plot_h * (1 - min(median / ymax, 1)) - 24
        SH.add_text(slide, S.MARGIN_X + CHART_W - 220, max(label_y, S.CONTENT_Y), 200, 24,
                    f"Médiane {numfmt(median)} {unit_label}", size=Pt(10.5), color=S.BRAND_PRIMARY, bold=True,
                    align=PP_ALIGN.RIGHT)

    chart.has_legend = True
    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.legend.include_in_layout = False
    chart.legend.font.size = S.SIZE_LEGEND
    chart.legend.font.color.rgb = S.TEXT_PRIMARY

    # ------------------------------------------------------------ rail droit
    y = S.CONTENT_Y
    _card_stat(slide, RAIL_X, y, RAIL_W, 174, "VÉLOCITÉ MÉDIANE", f"{numfmt(median)} {unit_label}",
               "sprints à 0 terminé exclus")
    y += 174 + 20

    positive_done = [v[done_key] for v in vel if v["done"] > 0]
    fourchette = (f"{numfmt(min(positive_done))} – {numfmt(max(positive_done))} {unit_label}"
                  if positive_done else "n/a")
    _card_stat(slide, RAIL_X, y, RAIL_W, 174, "FOURCHETTE", fourchette, f"{unit_label} terminées / sprint")
    y += 174 + 20

    lecture = (data.get("coaching") or {}).get("velocity_lecture", "")
    _card_lecture(slide, RAIL_X, y, RAIL_W, S.CONTENT_H - 2 * (174 + 20), lecture)

    SH.add_footer(slide, project_name, page_num, total_pages)


def render_velocity_nb(slide, placeholder_shape, data, template_path, page_num, total_pages):
    _render_velocity_single_unit(slide, placeholder_shape, data, template_path, page_num, total_pages, "us")


def render_velocity_sp(slide, placeholder_shape, data, template_path, page_num, total_pages):
    _render_velocity_single_unit(slide, placeholder_shape, data, template_path, page_num, total_pages, "sp")


def short_label(sprint_name):
    match = re.search(r"(\d+)\s*$", sprint_name or "")
    return f"S{match.group(1)}" if match else (sprint_name or "")[:6]


# =================================================================== status
def _status_colors(items, waiting_names, done_names):
    """Dégradé clair (1er statut) -> foncé, dans l'ordre déjà trié (workflow
    configuré si présent, sinon fréquence) — un dégradé continu ne se répète
    jamais, contrairement à l'ancienne palette à 5 couleurs cycliques qui
    pouvait donner la même couleur au premier et au dernier statut d'un
    workflow à 6+ étapes. Statuts "terminé" (`done_statuses_us`, calculé par
    status_flow.py à partir de `done_statuses` de project.yaml — jamais
    deviné) forcés en vert ; statuts "en attente" forcés en orange, comme
    avant."""
    n = len(items)
    gradient = [_lerp_color(S.BLUE_FILL_4, S.BRAND_PRIMARY, i / max(n - 1, 1)) for i in range(n)]
    colors = {}
    for (name, _), base in zip(items, gradient):
        if name in waiting_names:
            colors[name] = S.BRAND_ACCENT
        elif name in done_names:
            colors[name] = S.TREND_OPTIMIST
        else:
            colors[name] = base
    return colors


def _contrast_text_color(rgb):
    luminance = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    return S.TEXT_WHITE if luminance < 150 else S.BRAND_PRIMARY


# SH.add_text plancherait de toute façon Pt(11)/Pt(9.5) à Pt(12) (MIN_CONTENT_PT)
# — la largeur estimée doit se baser sur la taille réellement rendue, pas sur
# celle demandée, sous peine de sous-estimer l'espace nécessaire et de faire
# tenir un libellé long ("Attente validation PO 3") sur un segment trop
# étroit, qui le retourne à la ligne en accordéon illisible.
_STATUS_LABEL_FONT_PX = 24  # Pt(12) -> px (pt_from_px : px = pt * 2)


def _text_w_px(text, font_px=_STATUS_LABEL_FONT_PX):
    """Largeur estimée (px maquette), même heuristique que
    _estimate_text_height_px (police proportionnelle sans-serif, ~0.52 fois
    la taille de police par caractère)."""
    return len(text) * font_px * 0.52


def render_status(slide, placeholder_shape, data, template_path, page_num, total_pages):
    m = data["metrics"]
    project_name = data["project_name"].strip()
    SH.clear_legacy_chrome(slide)
    SH.clear_placeholder(placeholder_shape)

    counts = m["status_counts_us"]
    total = _total_us(counts)
    if not total:
        SH.add_header(slide, "0 US AU PÉRIMÈTRE", "Répartition par statut", template_path)
        SH.add_text(slide, S.MARGIN_X, S.CONTENT_Y + 40, S.CONTENT_W, 60,
                    "Aucune US au périmètre à ce jour.", size=S.SIZE_BODY, color=S.TEXT_SECONDARY)
        SH.add_footer(slide, project_name, page_num, total_pages)
        return
    SH.add_header(slide, f"{total} US AU PÉRIMÈTRE", "Répartition par statut", template_path)

    # Déjà ordonné par status_flow.py::compute() — workflow configuré
    # (bac à sable -> terminé) si disponible, sinon fréquence décroissante.
    items = list(counts.items())
    waiting_names = set(_waiting_us(counts))
    done_names = set(m.get("done_statuses_us") or [])
    colors = _status_colors(items, waiting_names, done_names)

    # -------------------------------------------------------- barre empilée
    # Espace réservé au-dessus et en dessous de la barre pour les libellés
    # des segments trop étroits pour leur texte à l'intérieur (voir plus
    # bas) — un statut avec peu de tickets ne doit jamais rester sans
    # étiquette visible.
    ABOVE_H, GAP_BELOW = 40, 46
    bar_y, bar_h = S.CONTENT_Y + ABOVE_H, 78

    segments, x = [], S.MARGIN_X
    for name, count in items:
        seg_w = S.CONTENT_W * count / total
        segments.append((name, count, x, seg_w))
        x += seg_w

    for name, count, seg_x, seg_w in segments:
        SH.add_rect(slide, seg_x, bar_y, max(seg_w, 1), bar_h, fill=colors[name], line_color=None)

    # Segments assez larges : libellé centré à l'intérieur. Segments trop
    # étroits : libellé externe avec une amorce, au-dessus ou en dessous de
    # la barre — deux statuts étroits consécutifs alternent de côté pour ne
    # pas superposer leurs libellés.
    tick_len, label_h = 10, 24
    above_next = True
    for name, count, seg_x, seg_w in segments:
        color = colors[name]
        label = f"{name} {count}"
        if seg_w - 24 >= _text_w_px(label):
            SH.add_text(slide, seg_x + 12, bar_y + bar_h / 2 - 20, seg_w - 24, 40,
                        label, size=Pt(11), color=_contrast_text_color(color), bold=True,
                        anchor=MSO_ANCHOR.MIDDLE)
            above_next = True  # une rupture de série redémarre au-dessus
            continue

        cx = seg_x + seg_w / 2
        label_w = _text_w_px(label) + 16
        if above_next:
            SH.add_rect(slide, cx - 1, bar_y - tick_len, 2, tick_len, fill=color, line_color=None)
            SH.add_text(slide, cx - label_w / 2, bar_y - tick_len - label_h, label_w, label_h,
                        label, size=Pt(9.5), color=S.TEXT_PRIMARY, bold=True,
                        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.BOTTOM)
        else:
            SH.add_rect(slide, cx - 1, bar_y + bar_h, 2, tick_len, fill=color, line_color=None)
            SH.add_text(slide, cx - label_w / 2, bar_y + bar_h + tick_len, label_w, label_h,
                        label, size=Pt(9.5), color=S.TEXT_PRIMARY, bold=True,
                        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.TOP)
        above_next = not above_next

    # ------------------------------------------------------------- cartes
    grid_y = bar_y + bar_h + GAP_BELOW
    cols = 4
    gap = 24
    card_w = (S.CONTENT_W - gap * (cols - 1)) / cols
    rows = math.ceil(len(items) / cols)
    card_h = min(300, (S.CONTENT_H - ABOVE_H - bar_h - GAP_BELOW - gap * (rows - 1)) / rows)

    for i, (name, count) in enumerate(items):
        r, c = divmod(i, cols)
        cx = S.MARGIN_X + c * (card_w + gap)
        cy = grid_y + r * (card_h + gap)
        is_waiting = name in waiting_names
        is_done = name in done_names
        pct = round(100 * count / total)
        if is_waiting:
            SH.add_rounded_rect(slide, cx, cy, card_w, card_h, fill=S.ALERT_BG, line_color=S.ALERT_BORDER)
            num_color, sub_color = S.BRAND_ACCENT, S.ALERT_TEXT
        else:
            SH.add_rounded_rect(slide, cx, cy, card_w, card_h)
            num_color = S.TREND_OPTIMIST if is_done else S.BRAND_PRIMARY
            sub_color = S.TEXT_SECONDARY
        pad = S.CARD_PADDING_PX
        SH.add_rect(slide, cx + pad, cy + pad + 4, 16, 16, fill=colors[name], line_color=None)
        SH.add_text(slide, cx + pad + 26, cy + pad, card_w - pad - 26, 30, name,
                    size=Pt(12), color=S.BRAND_PRIMARY, bold=True)
        SH.add_text(slide, cx + pad, cy + pad + 40, card_w - 2 * pad, 60, str(count),
                    size=S.SIZE_CARD_NUMBER, color=num_color, bold=True)
        SH.add_text(slide, cx + pad, cy + card_h - pad - 26, card_w - 2 * pad, 26,
                    f"{pct} % du périmètre", size=S.SIZE_CARD_LABEL, color=sub_color)

    SH.add_footer(slide, project_name, page_num, total_pages)


# =============================================================== sprint_spread
def render_sprint_spread(slide, placeholder_shape, data, template_path, page_num, total_pages):
    m = data["metrics"]
    project_name = data["project_name"].strip()
    SH.clear_legacy_chrome(slide)
    SH.clear_placeholder(placeholder_shape)

    counts = m["sprint_spread"]
    total = sum(counts.values())
    if not total:
        SH.add_header(slide, "0 US MESURÉE", "Répartition par nombre de sprints", template_path)
        SH.add_text(slide, S.MARGIN_X, S.CONTENT_Y + 40, S.CONTENT_W, 60,
                    "Aucune US terminée avec un sprint renseigné.",
                    size=S.SIZE_BODY, color=S.TEXT_SECONDARY)
        SH.add_footer(slide, project_name, page_num, total_pages)
        return
    SH.add_header(slide, f"{total} US MESURÉES", "Répartition par nombre de sprints", template_path)

    # Les clés numériques deviennent des chaînes après l'aller-retour JSON
    # (data.json) — reconverties ici, avec un tri de sécurité (déjà croissant
    # côté sprint_spread.py::compute(), mais l'ordre d'un dict JSON n'est pas
    # une garantie à faire porter sur l'affichage).
    items = sorted((int(nb), count) for nb, count in counts.items())
    n = len(items)
    gradient = [_lerp_color(S.BLUE_FILL_4, S.BRAND_PRIMARY, i / max(n - 1, 1)) for i in range(n)]
    colors = {nb: color for (nb, _), color in zip(items, gradient)}

    # -------------------------------------------------------- barre empilée
    # Même construction que {{chart:status}} : espace réservé au-dessus et
    # en dessous de la barre pour les libellés des segments trop étroits.
    ABOVE_H, GAP_BELOW = 40, 46
    bar_y, bar_h = S.CONTENT_Y + ABOVE_H, 78

    segments, x = [], S.MARGIN_X
    for nb, count in items:
        seg_w = S.CONTENT_W * count / total
        segments.append((nb, count, x, seg_w))
        x += seg_w

    for nb, count, seg_x, seg_w in segments:
        SH.add_rect(slide, seg_x, bar_y, max(seg_w, 1), bar_h, fill=colors[nb], line_color=None)

    # Contrairement à {{chart:status}}, pas d'étiquette externe (amorce
    # au-dessus/en dessous) pour les segments trop étroits : une répartition
    # par nombre de sprints a régulièrement une longue traîne de plusieurs
    # segments étroits consécutifs (7, 8, 9, 10 sprints...), où l'alternance
    # au-dessus/en dessous de {{chart:status}} finit par superposer deux
    # étiquettes. Un segment trop étroit reste donc juste sans étiquette dans
    # la barre — le compte exact reste lisible dans les cartes ci-dessous.
    for nb, count, seg_x, seg_w in segments:
        color = colors[nb]
        label = f"{nb} sprint{'s' if nb > 1 else ''} · {count}"
        if seg_w - 24 >= _text_w_px(label):
            SH.add_text(slide, seg_x + 12, bar_y + bar_h / 2 - 20, seg_w - 24, 40,
                        label, size=Pt(11), color=_contrast_text_color(color), bold=True,
                        anchor=MSO_ANCHOR.MIDDLE)

    # ------------------------------------------------------------- cartes
    grid_y = bar_y + bar_h + GAP_BELOW
    cols = 4
    gap = 24
    card_w = (S.CONTENT_W - gap * (cols - 1)) / cols
    rows = math.ceil(len(items) / cols)
    card_h = min(300, (S.CONTENT_H - ABOVE_H - bar_h - GAP_BELOW - gap * (rows - 1)) / rows)

    for i, (nb, count) in enumerate(items):
        r, c = divmod(i, cols)
        cx = S.MARGIN_X + c * (card_w + gap)
        cy = grid_y + r * (card_h + gap)
        pct = round(100 * count / total)
        SH.add_rounded_rect(slide, cx, cy, card_w, card_h)
        pad = S.CARD_PADDING_PX
        SH.add_rect(slide, cx + pad, cy + pad + 4, 16, 16, fill=colors[nb], line_color=None)
        SH.add_text(slide, cx + pad + 26, cy + pad, card_w - pad - 26, 30,
                    f"{nb} sprint{'s' if nb > 1 else ''}", size=Pt(12), color=S.BRAND_PRIMARY, bold=True)
        SH.add_text(slide, cx + pad, cy + pad + 40, card_w - 2 * pad, 60, str(count),
                    size=S.SIZE_CARD_NUMBER, color=S.BRAND_PRIMARY, bold=True)
        SH.add_text(slide, cx + pad, cy + card_h - pad - 26, card_w - 2 * pad, 26,
                    f"{pct} % des US mesurées", size=S.SIZE_CARD_LABEL, color=S.TEXT_SECONDARY)

    SH.add_footer(slide, project_name, page_num, total_pages)


# ===================================================================== CFD
def _lerp_color(c1, c2, t):
    return RGBColor(*(round(c1[k] + (c2[k] - c1[k]) * t) for k in range(3)))


def _cfd_palette(n_stages):
    """Dégradé clair (1re étape) -> foncé (avant-dernière étape), puis vert
    de succès pour la dernière étape (Terminé) — cohérent avec SUCCESS_GREEN
    utilisé ailleurs (tableau des epics) pour signaler l'achèvement."""
    n_mid = max(n_stages - 1, 1)
    mid = [_lerp_color(S.BLUE_FILL_4, S.BRAND_PRIMARY, i / max(n_mid - 1, 1)) for i in range(n_mid)]
    return (mid if n_stages > 1 else []) + [S.TREND_OPTIMIST]


def render_cfd(slide, placeholder_shape, data, template_path, page_num, total_pages):
    m = data["metrics"]
    project_name = data["project_name"].strip()
    SH.clear_legacy_chrome(slide)
    SH.clear_placeholder(placeholder_shape)

    cfd = m.get("cfd")
    if not cfd:
        SH.add_header(slide, "CONFIGURATION MANQUANTE", "Cumulative Flow Diagram", template_path)
        SH.add_text(slide, S.MARGIN_X, S.CONTENT_Y + 40, S.CONTENT_W, 100,
                    "Le workflow (project.yaml, champ `workflow`) doit être configuré, dans "
                    "l'ordre réel de progression, pour tracer le CFD — voir SKILL.md.",
                    size=S.SIZE_BODY, color=S.TEXT_SECONDARY)
        SH.add_footer(slide, project_name, page_num, total_pages)
        return

    categories = cfd["categories"]
    workflow = cfd["workflow"]
    reached = cfd["reached"]
    totals = cfd["totals"]
    n = len(workflow)
    surtitre = f"{categories[0]} → {categories[-1]}".upper()
    SH.add_header(slide, surtitre, "Cumulative Flow Diagram", template_path)

    cd = CategoryChartData()
    cd.categories = categories
    # Empilé du bas (dernière étape, Terminé) vers le haut (1re étape) : la
    # 1re série ajoutée forme la base de la pile dans un chart empilé.
    for i in range(n - 1, -1, -1):
        upper = reached[i + 1] if i + 1 < n else [0] * len(categories)
        band = [r - u for r, u in zip(reached[i], upper)]
        cd.add_series(workflow[i], band)

    gf = slide.shapes.add_chart(XL_CHART_TYPE.AREA_STACKED, S.px(S.MARGIN_X), S.px(S.CONTENT_Y),
                                 S.px(CHART_W), S.px(S.CONTENT_H), cd)
    chart = gf.chart
    chart.has_title = False
    x_frac, y_frac, w_frac, h_frac = 0.02, 0.03, 0.96, 0.80
    _set_manual_plot_area(chart, x_frac, y_frac, w_frac, h_frac)

    colors = _cfd_palette(n)
    for k, ser in enumerate(chart.plots[0].series):
        stage_i = n - 1 - k
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = colors[stage_i]
        ser.format.line.fill.background()

    chart.has_legend = True
    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.legend.include_in_layout = False
    chart.legend.font.size = S.SIZE_LEGEND
    chart.legend.font.color.rgb = S.TEXT_PRIMARY

    cat_ax = chart.category_axis
    cat_ax.format.line.color.rgb = S.CARD_BORDER
    cat_ax.tick_labels.font.size = Pt(9.5)
    cat_ax.tick_labels.font.color.rgb = S.TEXT_FOOTER
    skip = max(1, round(len(categories) / 12))
    ax_el = cat_ax._element
    tls = ax_el.find(qn("c:tickLblSkip"))
    if tls is None:
        tls = ax_el.makeelement(qn("c:tickLblSkip"), {})
        ax_el.append(tls)
    tls.set("val", str(skip))

    val_ax = chart.value_axis
    val_ax.has_major_gridlines = True
    val_ax.major_gridlines.format.line.color.rgb = S.CARD_BORDER_INNER
    val_ax.tick_labels.font.size = Pt(9.5)
    val_ax.tick_labels.font.color.rgb = S.TEXT_FOOTER
    val_ax.format.line.fill.background()

    # ------------------------------------------------------------ rail droit
    y = S.CONTENT_Y
    _card_stat(slide, RAIL_X, y, RAIL_W, 174, "PÉRIMÈTRE SUIVI", f"{totals['scope']} US", "")
    y += 174 + 20
    done_pct = round(100 * totals["done"] / totals["scope"]) if totals["scope"] else 0
    _card_stat(slide, RAIL_X, y, RAIL_W, 174, "TERMINÉ", f"{totals['done']} US", f"{done_pct} % du périmètre")
    y += 174 + 20
    _card_stat(slide, RAIL_X, y, RAIL_W, S.CONTENT_H - 174 * 2 - 40, "EN COURS",
               f"{totals['in_progress']} US", "")

    SH.add_footer(slide, project_name, page_num, total_pages)


# ==================================================================== epics
EPIC_TABLE_HEADERS = ["ID", "Libellé", "Statut", "Estim.", "Conso", "RAF théo",
                      "US term.", "US restantes", "% avanc."]
EPIC_TABLE_COL_FRACS = [0.09, 0.27, 0.11, 0.10, 0.10, 0.10, 0.08, 0.08, 0.07]
# PowerPoint peut augmenter automatiquement la hauteur des lignes lorsque les
# libellés d'EPIC sont longs. Garder sept lignes détaillées plus la synthèse
# évite que le tableau ne déborde sur le bandeau et le pied de page.
MAX_EPIC_ROWS = 8
SUCCESS_GREEN = S.TREND_OPTIMIST  # 2E9E6B, réutilisé comme vert de succès


def _card_mini(slide, x, y, w, h, label, big, sub, fill=S.CARD_BG, border=S.CARD_BORDER,
               label_color=S.TEXT_SECONDARY, big_color=S.BRAND_PRIMARY, sub_color=S.TEXT_SECONDARY):
    SH.add_rounded_rect(slide, x, y, w, h, fill=fill, line_color=border)
    pad = 20
    SH.add_text(slide, x + pad, y + pad - 4, w - 2 * pad, 24, label, size=Pt(10.5),
                color=label_color, bold=True, all_caps=True)
    SH.add_text(slide, x + pad, y + pad + 26, w - 2 * pad, 56, big, size=Pt(26),
                color=big_color, bold=True)
    if sub:
        SH.add_text(slide, x + pad, y + h - pad - 22, w - 2 * pad, 22, sub, size=Pt(10.5),
                    color=sub_color)


def render_epics(slide, placeholder_shape, data, template_path, page_num, total_pages):
    m = data["metrics"]
    project_name = data["project_name"].strip()
    SH.clear_legacy_chrome(slide)
    SH.clear_placeholder(placeholder_shape)

    ep = m.get("epics")
    if not ep or not ep["items"]:
        SH.add_header(slide, "PÉRIMÈTRE EPIC", "Avancement par EPIC", template_path)
        SH.add_text(slide, S.MARGIN_X, S.CONTENT_Y + 40, S.CONTENT_W, 60,
                    "Aucune EPIC détectée (champ parent non renseigné sur les tickets).",
                    size=S.SIZE_BODY, color=S.TEXT_SECONDARY)
        SH.add_footer(slide, project_name, page_num, total_pages)
        return

    SH.add_header(slide, f"PÉRIMÈTRE EPIC · {ep['us_done_total']} US TERMINÉES",
                  "Avancement par EPIC", template_path)

    # ---------------------------------------------------------------- cartes
    gap = 20
    card_w = (S.CONTENT_W - 4 * gap) / 5
    card_h = 150
    cx = S.MARGIN_X
    _card_mini(slide, cx, S.CONTENT_Y, card_w, card_h, "ESTIMATION", f"{_fr_num(ep['total_estimate_jh'])} jh", "")
    cx += card_w + gap
    conso_alert = ep["total_conso_jh"] > ep["total_estimate_jh"]
    _card_mini(slide, cx, S.CONTENT_Y, card_w, card_h, "CONSOMMÉ", f"{_fr_num(ep['total_conso_jh'])} jh", "",
               fill=S.ALERT_BG if conso_alert else S.CARD_BG, border=S.ALERT_BORDER if conso_alert else S.CARD_BORDER,
               label_color=S.ALERT_TEXT if conso_alert else S.TEXT_SECONDARY,
               big_color=S.BRAND_ACCENT if conso_alert else S.BRAND_PRIMARY)
    cx += card_w + gap
    raf_alert = ep["total_raf_theo_jh"] < 0
    raf_txt = f"{'−' if ep['total_raf_theo_jh'] < 0 else ''}{_fr_num(abs(ep['total_raf_theo_jh']))} jh"
    _card_mini(slide, cx, S.CONTENT_Y, card_w, card_h, "RAF THÉORIQUE", raf_txt, "",
               fill=S.ALERT_BG if raf_alert else S.CARD_BG, border=S.ALERT_BORDER if raf_alert else S.CARD_BORDER,
               label_color=S.ALERT_TEXT if raf_alert else S.TEXT_SECONDARY,
               big_color=S.BRAND_ACCENT if raf_alert else S.BRAND_PRIMARY)
    cx += card_w + gap
    _card_mini(slide, cx, S.CONTENT_Y, card_w, card_h, "AVANCEMENT", f"{_fr_num(ep['avancement_pct'], 0)} %", "",
               fill=S.BRAND_PRIMARY, border=None, label_color=S.TEXT_WHITE, big_color=S.TEXT_WHITE)
    cx += card_w + gap
    if ep["projection_theorique_jh"] is not None:
        prev = ep["previsibilite_pct"]
        if prev is not None:
            sign = "+" if prev >= 0 else ""
            sub = f"{sign}{_fr_num(prev, 0)} % vs estimé"
        else:
            sub = "estimation totale nulle"
        _card_mini(slide, cx, S.CONTENT_Y, card_w, card_h, "PROJECTION THÉORIQUE",
                   f"{_fr_num(ep['projection_theorique_jh'])} jh", sub)
    else:
        _card_mini(slide, cx, S.CONTENT_Y, card_w, card_h, "PROJECTION THÉORIQUE", "—",
                   "aucune US terminée")

    # --------------------------------------------------------------- tableau
    table_y = S.CONTENT_Y + card_h + gap
    table_h = S.CONTENT_H - card_h - gap

    items = ep["items"]
    truncated = len(items) > MAX_EPIC_ROWS
    shown = items[:MAX_EPIC_ROWS - 1] if truncated else items
    rest = items[MAX_EPIC_ROWS - 1:] if truncated else []

    n_rows = len(shown) + 1 + (1 if rest else 0)
    header_h = 46
    row_h = max((table_h - header_h) / (n_rows - 1), 36)

    tbl_shape = slide.shapes.add_table(n_rows, len(EPIC_TABLE_HEADERS),
                                        S.px(S.MARGIN_X), S.px(table_y),
                                        S.px(S.CONTENT_W), S.px(header_h + row_h * (n_rows - 1)))
    table = tbl_shape.table
    table.first_row = False
    table.horz_banding = False
    for c, frac in enumerate(EPIC_TABLE_COL_FRACS):
        table.columns[c].width = S.px(round(S.CONTENT_W * frac))
    table.rows[0].height = S.px(header_h)
    for r in range(1, n_rows):
        table.rows[r].height = S.px(row_h)

    def set_cell(r, c, text, bold=False, color=S.TEXT_PRIMARY, fill=None, align=PP_ALIGN.LEFT,
                 size=Pt(11)):
        cell = table.cell(r, c)
        cell.margin_left = S.px(14)
        cell.margin_right = S.px(14)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        if fill is None:
            cell.fill.background()
        else:
            cell.fill.solid()
            cell.fill.fore_color.rgb = fill
        cell.text_frame.clear()
        cell.text_frame.word_wrap = True
        p = cell.text_frame.paragraphs[0]
        p.alignment = align
        run = p.add_run()
        run.text = text
        run.font.size = size
        run.font.bold = bold
        run.font.name = S.FONT_FAMILY
        run.font.color.rgb = color

    for c, h in enumerate(EPIC_TABLE_HEADERS):
        align = PP_ALIGN.LEFT if c < 3 else PP_ALIGN.RIGHT
        set_cell(0, c, h, bold=True, color=S.BRAND_PRIMARY, fill=S.CARD_BG, align=align)

    for i, e in enumerate(shown):
        r = i + 1
        row_fill = RGBColor(0xFF, 0xFF, 0xFF) if i % 2 == 0 else RGBColor(0xFA, 0xFC, 0xFD)
        pct = e["avancement_pct"]
        pct_color = SUCCESS_GREEN if pct >= 90 else S.TEXT_PRIMARY
        raf_color = S.BRAND_ACCENT if e["raf_theo_jh"] < 0 else S.TEXT_PRIMARY
        set_cell(r, 0, e["key"], bold=True, color=S.BRAND_PRIMARY, fill=row_fill)
        set_cell(r, 1, e["name"], color=S.TEXT_PRIMARY, fill=row_fill)
        set_cell(r, 2, e["status"], color=S.TEXT_SECONDARY, fill=row_fill)
        set_cell(r, 3, _fr_num(e["estimate_jh"]), color=S.TEXT_PRIMARY, fill=row_fill, align=PP_ALIGN.RIGHT)
        set_cell(r, 4, _fr_num(e["conso_jh"]), color=S.TEXT_PRIMARY, fill=row_fill, align=PP_ALIGN.RIGHT)
        set_cell(r, 5, _fr_num(e["raf_theo_jh"]), color=raf_color, fill=row_fill, align=PP_ALIGN.RIGHT, bold=e["raf_theo_jh"] < 0)
        set_cell(r, 6, str(e["us_done"]), color=S.TEXT_PRIMARY, fill=row_fill, align=PP_ALIGN.RIGHT)
        set_cell(r, 7, str(e["us_remaining"]), color=S.TEXT_PRIMARY, fill=row_fill, align=PP_ALIGN.RIGHT)
        set_cell(r, 8, f"{_fr_num(pct, 0)} %", color=pct_color, fill=row_fill, align=PP_ALIGN.RIGHT, bold=pct >= 90)

    if rest:
        r = len(shown) + 1
        statuses = []
        for e in rest:
            if e["status"] not in statuses:
                statuses.append(e["status"])
        preview = ", ".join(s.lower() for s in statuses[:3]) + ("…" if len(statuses) > 3 else "")
        rest_done = sum(e["us_done"] for e in rest)
        rest_remaining = sum(e["us_remaining"] for e in rest)
        rest_total = rest_done + rest_remaining
        rest_pct = round(100 * rest_done / rest_total, 1) if rest_total else 0.0
        row_fill = RGBColor(0xF4, 0xF7, 0xFA)
        set_cell(r, 0, "—", color=S.TEXT_FOOTER, fill=row_fill)
        set_cell(r, 1, f"{len(rest)} autres EPICs ({preview})", color=S.TEXT_SECONDARY, fill=row_fill)
        for c in (2, 3, 4, 5):
            set_cell(r, c, "—", color=S.TEXT_FOOTER, fill=row_fill, align=PP_ALIGN.RIGHT if c >= 3 else PP_ALIGN.LEFT)
        set_cell(r, 6, str(rest_done), color=S.TEXT_SECONDARY, fill=row_fill, align=PP_ALIGN.RIGHT)
        set_cell(r, 7, str(rest_remaining), color=S.TEXT_SECONDARY, fill=row_fill, align=PP_ALIGN.RIGHT)
        set_cell(r, 8, f"{_fr_num(rest_pct, 0)} %", color=S.TEXT_SECONDARY, fill=row_fill, align=PP_ALIGN.RIGHT)

    SH.add_footer(slide, project_name, page_num, total_pages)


# ==================================================================== types
def _bar_rows(slide, x, y, w, h, items, value_fmt, bar_color_fn, unit=""):
    """Lignes de barres horizontales réparties sur la hauteur disponible
    (label 280px, piste F4F7FA, barre pleine, valeur alignée à droite)."""
    label_w = 280
    value_w = 130
    track_x = x + label_w + 16
    track_w = w - label_w - 16 - value_w - 16
    max_val = max((v for _, v in items), default=1) * 1.06 or 1
    row_h = h / len(items)
    for i, (name, val) in enumerate(items):
        ry = y + i * row_h
        SH.add_text(slide, x, ry, label_w, row_h, name, size=Pt(12.5), color=S.BRAND_PRIMARY,
                    bold=True, anchor=MSO_ANCHOR.MIDDLE)
        track_h = min(31, row_h * 0.5)
        track_y = ry + (row_h - track_h) / 2
        SH.add_rounded_rect(slide, track_x, track_y, track_w, track_h, fill=S.CARD_BG,
                             line_color=None, radius_px=8)
        bar_w = track_w * val / max_val
        if bar_w > 0:
            SH.add_rounded_rect(slide, track_x, track_y, max(bar_w, 8), track_h,
                                 fill=bar_color_fn(i), line_color=None, radius_px=8)
        SH.add_text(slide, track_x + track_w + 16, ry, value_w, row_h, value_fmt(val),
                    size=Pt(16), color=S.BRAND_PRIMARY, bold=True, anchor=MSO_ANCHOR.MIDDLE,
                    align=PP_ALIGN.RIGHT)


def render_types(slide, placeholder_shape, data, template_path, page_num, total_pages):
    m = data["metrics"]
    project_name = data["project_name"].strip()
    SH.clear_legacy_chrome(slide)
    SH.clear_placeholder(placeholder_shape)

    total = sum(m["type_counts"].values())
    SH.add_header(slide, f"VOLUME · {total} TICKETS", "Types de tickets", template_path)
    items = sorted(m["type_counts"].items(), key=lambda kv: -kv[1])

    SH.add_rounded_rect(slide, S.MARGIN_X, S.CONTENT_Y, S.CONTENT_W, S.CONTENT_H)
    pad = S.CARD_PADDING_PX
    lecture = (data.get("coaching") or {}).get("types_lecture", "")
    lecture_h = 70 if lecture else 20
    rows_h = S.CONTENT_H - 2 * pad - lecture_h
    _bar_rows(slide, S.MARGIN_X + pad, S.CONTENT_Y + pad, S.CONTENT_W - 2 * pad, rows_h,
              items, lambda v: str(int(v)), lambda i: S.BRAND_PRIMARY)

    if lecture:
        sep_y = S.CONTENT_Y + pad + rows_h + 14
        SH.add_rect(slide, S.MARGIN_X + pad, sep_y, S.CONTENT_W - 2 * pad, 1.5, fill=S.CARD_BORDER, line_color=None)
        SH.add_text(slide, S.MARGIN_X + pad, sep_y + 14, S.CONTENT_W - 2 * pad, lecture_h - 14,
                    lecture, size=S.SIZE_BODY, color=S.TEXT_SECONDARY)

    SH.add_footer(slide, project_name, page_num, total_pages)


# ============================================================== types_conso
def render_types_conso(slide, placeholder_shape, data, template_path, page_num, total_pages):
    m = data["metrics"]
    project_name = data["project_name"].strip()
    SH.clear_legacy_chrome(slide)
    SH.clear_placeholder(placeholder_shape)

    conso = m["type_conso_jh"]
    total_jh = sum(conso.values())
    SH.add_header(slide, f"CONSOMMATION · {_fr_num(total_jh)} JH", "Charge par type de ticket", template_path)
    items = sorted(conso.items(), key=lambda kv: -kv[1])

    left_w = (S.CONTENT_W - 40) / 2
    right_x = S.MARGIN_X + left_w + 40
    right_w = left_w

    SH.add_rounded_rect(slide, S.MARGIN_X, S.CONTENT_Y, left_w, S.CONTENT_H)
    pad = S.CARD_PADDING_PX
    SH.add_text(slide, S.MARGIN_X + pad, S.CONTENT_Y + pad - 6, left_w - 2 * pad, 26,
                "JOURS-HOMME CONSOMMÉS", size=S.SIZE_CARD_LABEL, color=S.TEXT_SECONDARY,
                bold=True, all_caps=True)
    lecture = (data.get("coaching") or {}).get("types_conso_lecture", "")
    lecture_h = 60 if lecture else 20
    rows_h = S.CONTENT_H - 2 * pad - 40 - lecture_h
    _bar_rows(slide, S.MARGIN_X + pad, S.CONTENT_Y + pad + 40, left_w - 2 * pad, rows_h,
              items, lambda v: f"{_fr_num(v)}",
              lambda i: S.BRAND_ACCENT if i == 0 else S.BRAND_PRIMARY)
    if lecture:
        sep_y = S.CONTENT_Y + pad + 40 + rows_h + 14
        SH.add_rect(slide, S.MARGIN_X + pad, sep_y, left_w - 2 * pad, 1.5, fill=S.CARD_BORDER, line_color=None)
        SH.add_text(slide, S.MARGIN_X + pad, sep_y + 14, left_w - 2 * pad, lecture_h - 14,
                    lecture, size=S.SIZE_BODY, color=S.TEXT_SECONDARY)

    dominant_name, dominant_jh = items[0] if items else ("", 0)
    dominant_pct = 100 * dominant_jh / total_jh if total_jh else 0
    card_h = (S.CONTENT_H - 40) / 2
    _card_stat(slide, right_x, S.CONTENT_Y, right_w, card_h, "TYPE DOMINANT",
               f"{_fr_num(dominant_pct, 1)} %",
               f"{dominant_name} · {_fr_num(dominant_jh)} jh sur {_fr_num(total_jh)} consommés")

    scope_jh = m["burnup"][-1]["scope_cumul_us_jh"] if m["burnup"] else 0
    conso_us_jh = m["burnup"][-1]["conso_cumul_us_jh"] if m["burnup"] else 0
    _card_stat(slide, right_x, S.CONTENT_Y + card_h + 40, right_w, card_h,
               "ESTIMATION DU PÉRIMÈTRE", f"{_fr_num(scope_jh)} jh",
               f"dont {_fr_num(conso_us_jh)} jh consommés sur les US terminées")

    SH.add_footer(slide, project_name, page_num, total_pages)


# ======================================================== conso_corrective
def render_conso_corrective(slide, placeholder_shape, data, template_path, page_num, total_pages):
    m = data["metrics"]
    project_name = data["project_name"].strip()
    SH.clear_legacy_chrome(slide)
    SH.clear_placeholder(placeholder_shape)

    cc = m.get("conso_corrective")
    if not cc:
        SH.add_header(slide, "AUCUNE DONNÉE", "Charge corrective (anomalie / incident)", template_path)
        SH.add_text(slide, S.MARGIN_X, S.CONTENT_Y + 40, S.CONTENT_W, 100,
                    "Aucun ticket terminé avec date de résolution et jours-homme consommés "
                    "dans les catégories anomalie / incident / Us / US tech (anomaly_types, "
                    "incident_types, tech_types, us_types dans project.yaml).",
                    size=S.SIZE_BODY, color=S.TEXT_SECONDARY)
        SH.add_footer(slide, project_name, page_num, total_pages)
        return

    surtitre = f"{_fr_num(cc['corrective_pct'], 0)} % CORRECTIF · {_fr_num(cc['total_jh'])} JH"
    SH.add_header(slide, surtitre, "Charge consommée sur tickets terminés, par mois", template_path)

    ORDER = ["anomalie", "incident", "us", "us_tech"]
    LABELS = {"anomalie": "Conso anomalie", "incident": "Conso incident",
              "us": "Conso Us", "us_tech": "Conso US tech"}
    COLORS = {"anomalie": S.CORRECTIVE_ANOMALY, "incident": S.CORRECTIVE_INCIDENT,
              "us": S.CORRECTIVE_US, "us_tech": S.CORRECTIVE_TECH}

    cd = CategoryChartData()
    cd.categories = cc["categories"]
    for cat in ORDER:
        cd.add_series(LABELS[cat], cc["series"][cat])

    gf = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_STACKED_100, S.px(S.MARGIN_X), S.px(S.CONTENT_Y),
                                 S.px(CHART_W), S.px(S.CONTENT_H), cd)
    chart = gf.chart
    chart.has_title = False
    x_frac, y_frac, w_frac, h_frac = 0.02, 0.03, 0.96, 0.80
    _set_manual_plot_area(chart, x_frac, y_frac, w_frac, h_frac)

    for ser, cat in zip(chart.plots[0].series, ORDER):
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = COLORS[cat]
        ser.format.line.fill.background()

    chart.has_legend = True
    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.legend.include_in_layout = False
    chart.legend.font.size = S.SIZE_LEGEND
    chart.legend.font.color.rgb = S.TEXT_PRIMARY

    cat_ax = chart.category_axis
    cat_ax.format.line.color.rgb = S.CARD_BORDER
    cat_ax.tick_labels.font.size = Pt(9.5)
    cat_ax.tick_labels.font.color.rgb = S.TEXT_FOOTER
    skip = max(1, round(len(cc["categories"]) / 20))
    ax_el = cat_ax._element
    tls = ax_el.find(qn("c:tickLblSkip"))
    if tls is None:
        tls = ax_el.makeelement(qn("c:tickLblSkip"), {})
        ax_el.append(tls)
    tls.set("val", str(skip))

    val_ax = chart.value_axis
    val_ax.has_major_gridlines = True
    val_ax.major_gridlines.format.line.color.rgb = S.CARD_BORDER_INNER
    val_ax.tick_labels.font.size = Pt(9.5)
    val_ax.tick_labels.font.color.rgb = S.TEXT_FOOTER
    val_ax.tick_labels.number_format = "0%"
    val_ax.tick_labels.number_format_is_linked = False
    val_ax.format.line.fill.background()

    # ------------------------------------------------------------ rail droit
    y = S.CONTENT_Y
    _card_stat(slide, RAIL_X, y, RAIL_W, 174, "CHARGE CORRECTIVE",
               f"{_fr_num(cc['corrective_pct'], 0)} %",
               f"{_fr_num(cc['corrective_jh'])} jh anomalie + incident")
    y += 174 + 20
    _card_stat(slide, RAIL_X, y, RAIL_W, 174, "TOTAL CONSOMMÉ",
               f"{_fr_num(cc['total_jh'])} jh", "sur tickets terminés, 4 catégories")
    y += 174 + 20
    lecture = (data.get("coaching") or {}).get("conso_corrective_lecture", "")
    if lecture:
        rail_rest_h = S.CONTENT_H - 174 * 2 - 40
        SH.add_rounded_rect(slide, RAIL_X, y, RAIL_W, rail_rest_h)
        SH.add_text(slide, RAIL_X + 20, y + 20, RAIL_W - 40, rail_rest_h - 40,
                    lecture, size=S.SIZE_BODY, color=S.TEXT_SECONDARY)

    SH.add_footer(slide, project_name, page_num, total_pages)


# ============================================================ tempo_conso
def render_tempo_conso(slide, placeholder_shape, data, template_path, page_num, total_pages):
    m = data["metrics"]
    project_name = data["project_name"].strip()
    SH.clear_legacy_chrome(slide)
    SH.clear_placeholder(placeholder_shape)

    tc = m.get("tempo_conso")
    if not tc:
        SH.add_header(slide, "TEMPO", "Conso Tempo (CRA) par sprint vs US terminées", template_path)
        SH.add_text(slide, S.MARGIN_X, S.CONTENT_Y + 40, S.CONTENT_W, 100,
                    "Données Tempo JIRA non disponibles (application Tempo absente de ce "
                    "projet, ou TEMPO_API_TOKEN non configuré dans .env).",
                    size=S.SIZE_BODY, color=S.TEXT_SECONDARY)
        SH.add_footer(slide, project_name, page_num, total_pages)
        return

    surtitre = f"{_fr_num(tc['total_conso_jh'])} JH TEMPO · {tc['total_done_us']} US TERMINÉES"
    SH.add_header(slide, surtitre, "Conso Tempo (CRA) par sprint vs US terminées", template_path)

    cats = tc["categories"]
    cd = CategoryChartData()
    cd.categories = cats
    cd.add_series("Conso Tempo (jh)", tc["conso_jh"])
    gf = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, S.px(S.MARGIN_X), S.px(S.CONTENT_Y),
                                 S.px(CHART_W), S.px(S.CONTENT_H), cd)
    chart = gf.chart
    chart.has_title = False
    x_frac, y_frac, w_frac, h_frac = 0.02, 0.03, 0.96, 0.78
    _set_manual_plot_area(chart, x_frac, y_frac, w_frac, h_frac)

    bar_s = chart.plots[0].series[0]
    bar_s.format.fill.solid()
    bar_s.format.fill.fore_color.rgb = S.BRAND_PRIMARY
    bar_s.format.line.fill.background()

    cat_ax = chart.category_axis
    cat_ax.format.line.color.rgb = S.CARD_BORDER
    cat_ax.tick_labels.font.size = Pt(9.5)
    cat_ax.tick_labels.font.color.rgb = S.TEXT_FOOTER

    val_ax = chart.value_axis
    val_ax.has_major_gridlines = True
    val_ax.major_gridlines.format.line.color.rgb = S.CARD_BORDER_INNER
    val_ax.tick_labels.font.size = Pt(9.5)
    val_ax.tick_labels.font.color.rgb = S.TEXT_FOOTER
    val_ax.format.line.fill.background()

    _add_secondary_axis(chart, cats, [
        ("US terminées", tc["done_us"], "F04E23", 2.5, None),
    ])

    chart.has_legend = True
    chart.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart.legend.include_in_layout = False
    chart.legend.font.size = S.SIZE_LEGEND
    chart.legend.font.color.rgb = S.TEXT_PRIMARY

    # ------------------------------------------------------------ rail droit
    y = S.CONTENT_Y
    _card_stat(slide, RAIL_X, y, RAIL_W, 174, "CONSO TEMPO TOTALE",
               f"{_fr_num(tc['total_conso_jh'])} jh", "tous sprints, y compris backlog")
    y += 174 + 20
    avg = tc["avg_jh_per_us"]
    _card_stat(slide, RAIL_X, y, RAIL_W, 174, "MOYENNE / US",
               f"{_fr_num(avg)} jh" if avg is not None else "n/a",
               f"{tc['total_done_us']} US terminées au total")
    y += 174 + 20
    lecture = (data.get("coaching") or {}).get("tempo_conso_lecture", "")
    _card_lecture(slide, RAIL_X, y, RAIL_W, S.CONTENT_H - 2 * (174 + 20), lecture)

    SH.add_footer(slide, project_name, page_num, total_pages)


def _label_width_px(text, size_pt):
    """Largeur approximative (en px de maquette) d'un label gras — pas de
    métrique de police réelle disponible ici, estimation par caractère avec
    marge de sécurité pour ne jamais sous-estimer (préférer un label trop
    large, qui ne wrappe/chevauche jamais, à un trop juste)."""
    size_px = size_pt.pt * 2
    return len(text) * size_px * 0.62 + 16


def _declutter_centers(centers_widths, gap):
    """Écarte le minimum nécessaire des centres d'étiquettes déjà triés par
    position croissante pour qu'aucune paire ne se chevauche (aller-retour :
    on pousse d'abord vers la droite, puis on repousse vers la gauche celles
    qui empièteraient encore sur leur voisine de droite)."""
    lefts = [c - w / 2 for c, w in centers_widths]
    rights = [c + w / 2 for c, w in centers_widths]
    for i in range(1, len(centers_widths)):
        min_left = rights[i - 1] + gap
        if lefts[i] < min_left:
            shift = min_left - lefts[i]
            lefts[i] += shift
            rights[i] += shift
    for i in range(len(centers_widths) - 2, -1, -1):
        max_right = lefts[i + 1] - gap
        if rights[i] > max_right:
            shift = rights[i] - max_right
            lefts[i] -= shift
            rights[i] -= shift
    return [(l + r) / 2 for l, r in zip(lefts, rights)]


def _nice_step(raw):
    """Pas d'axe « propre » (1/2/5 × 10^n) le plus proche au-dessus de `raw`,
    pour éviter un nombre de graduations proportionnel à l'échelle brute."""
    if raw <= 0:
        return 1
    magnitude = 10 ** math.floor(math.log10(raw))
    for mult in (1, 2, 5, 10):
        step = mult * magnitude
        if step >= raw:
            return step
    return 10 * magnitude


# ================================================================ cycle_time
def render_cycle_time(slide, placeholder_shape, data, template_path, page_num, total_pages):
    m = data["metrics"]
    project_name = data["project_name"].strip()
    SH.clear_legacy_chrome(slide)
    SH.clear_placeholder(placeholder_shape)

    ct = m["cycle_time"]
    SH.add_header(slide, f"{ct['count']} US MESURÉES", "Cycle time", template_path)

    if not ct["count"]:
        SH.add_text(slide, S.MARGIN_X, S.CONTENT_Y + 40, S.CONTENT_W, 60,
                    "Aucune US terminée avec date de résolution mesurable.",
                    size=S.SIZE_BODY, color=S.TEXT_SECONDARY)
        SH.add_footer(slide, project_name, page_num, total_pages)
        return

    SH.add_rounded_rect(slide, S.MARGIN_X, S.CONTENT_Y, CHART_W, S.CONTENT_H)
    pad = S.CARD_PADDING_PX
    SH.add_text(slide, S.MARGIN_X + pad, S.CONTENT_Y + pad - 6, CHART_W - 2 * pad, 26,
                "DISPERSION DES DURÉES, EN JOURS", size=S.SIZE_CARD_LABEL,
                color=S.TEXT_SECONDARY, bold=True, all_caps=True)

    step = _nice_step(ct["p85"] / 8)
    axis_max = max(step, math.ceil(ct["p85"] / step) * step)
    plot_x0 = S.MARGIN_X + pad + 10
    plot_w = CHART_W - 2 * pad - 20
    track_y = S.CONTENT_Y + 260
    track_h = 15

    def xpos(v):
        return plot_x0 + plot_w * min(v / axis_max, 1)

    SH.add_rounded_rect(slide, plot_x0, track_y, plot_w, track_h, fill=S.CARD_BG,
                         line_color=None, radius_px=7)
    box_x0, box_x1 = xpos(ct["p15"]), xpos(ct["p85"])
    box_h = 48
    SH.add_rounded_rect(slide, box_x0, track_y - (box_h - track_h) / 2, max(box_x1 - box_x0, 4),
                         box_h, fill=S.BLUE_FILL_3, line_color=None, radius_px=10)
    med_x = xpos(ct["median"])
    line_h = 80
    SH.add_rect(slide, med_x - 3, track_y - (line_h - track_h) / 2, 6, line_h,
                fill=S.BRAND_PRIMARY, line_color=None)
    mean_x = xpos(ct["mean"])
    dia = slide.shapes.add_shape(MSO_SHAPE.DIAMOND,
                                  S.px(mean_x - 13), S.px(track_y + track_h / 2 - 13), S.px(26), S.px(26))
    dia.fill.solid()
    dia.fill.fore_color.rgb = S.BRAND_ACCENT
    dia.line.fill.background()
    dia.shadow.inherit = False

    label_size = Pt(12)
    label_gap = 12
    p15_text = f"P15 {_fr_num(ct['p15'])} j"
    med_text = f"Médiane {_fr_num(ct['median'])} j"
    p85_text = f"P85 {_fr_num(ct['p85'])} j"
    mean_text = f"Moyenne {_fr_num(ct['mean'])} j"
    p15_w = _label_width_px(p15_text, label_size)
    med_w = _label_width_px(med_text, label_size)
    p85_w = _label_width_px(p85_text, label_size)
    mean_w = _label_width_px(mean_text, label_size)

    # P15/Médiane/P85 sont toujours dans cet ordre sur l'axe : on écarte leurs
    # centres du minimum nécessaire pour qu'ils ne se chevauchent jamais,
    # même quand les trois valeurs sont proches les unes des autres.
    p15_c, med_c, p85_c = _declutter_centers(
        [(box_x0, p15_w), (med_x, med_w), (box_x1, p85_w)], label_gap)

    SH.add_text(slide, p15_c - p15_w / 2, track_y - 58, p15_w, 34, p15_text,
                size=label_size, color=S.TEXT_SECONDARY, bold=True,
                align=PP_ALIGN.CENTER, word_wrap=False)
    SH.add_text(slide, med_c - med_w / 2, track_y - 58, med_w, 34, med_text,
                size=label_size, color=S.BRAND_PRIMARY, bold=True,
                align=PP_ALIGN.CENTER, word_wrap=False)
    SH.add_text(slide, p85_c - p85_w / 2, track_y - 58, p85_w, 34, p85_text,
                size=label_size, color=S.TEXT_SECONDARY, bold=True,
                align=PP_ALIGN.CENTER, word_wrap=False)
    SH.add_text(slide, mean_x - mean_w / 2, track_y + line_h / 2 + 8, mean_w, 34,
                mean_text, size=label_size, color=S.BRAND_ACCENT, bold=True,
                align=PP_ALIGN.CENTER, word_wrap=False)

    axis_y = track_y + line_h / 2 + 60
    SH.add_rect(slide, plot_x0, axis_y, plot_w, 1.5, fill=S.CARD_BORDER, line_color=None)
    n_ticks = round(axis_max / step)
    for i in range(n_ticks + 1):
        v = i * step
        tx = xpos(v)
        SH.add_text(slide, tx - 30, axis_y + 12, 60, 26, f"{v} j", size=Pt(9.5),
                    color=S.TEXT_FOOTER, align=PP_ALIGN.CENTER)

    lecture = (data.get("coaching") or {}).get("cycle_time_lecture", "")
    if lecture:
        sep_y = axis_y + 60
        SH.add_rect(slide, S.MARGIN_X + pad, sep_y, CHART_W - 2 * pad, 1.5, fill=S.CARD_BORDER, line_color=None)
        SH.add_text(slide, S.MARGIN_X + pad, sep_y + 16, CHART_W - 2 * pad, 60,
                    lecture, size=S.SIZE_BODY, color=S.TEXT_PRIMARY)

    legend = ("P15 / P85 : 15ᵉ et 85ᵉ centile — 70 % des tickets se situent entre ces deux "
              "valeurs · Médiane : valeur qui sépare les tickets en deux moitiés égales · "
              "Moyenne : moyenne arithmétique, plus sensible aux valeurs extrêmes.")
    legend_h = 54
    legend_y = S.CONTENT_Y + S.CONTENT_H - pad - legend_h
    SH.add_text(slide, S.MARGIN_X + pad, legend_y, CHART_W - 2 * pad, legend_h,
                legend, size=S.SIZE_FOOTER, color=S.TEXT_FOOTER)

    # ------------------------------------------------------------ rail droit
    gap = 22
    card_h = (S.CONTENT_H - 3 * gap) / 4
    y = S.CONTENT_Y
    _card_stat(slide, RAIL_X, y, RAIL_W, card_h, "P15", f"{_fr_num(ct['p15'])} j", "")
    y += card_h + gap
    _card_stat(slide, RAIL_X, y, RAIL_W, card_h, "MÉDIANE", f"{_fr_num(ct['median'])} j", "")
    y += card_h + gap
    _card_stat(slide, RAIL_X, y, RAIL_W, card_h, "MOYENNE", f"{_fr_num(ct['mean'])} j", "")
    y += card_h + gap
    if ct["median"] and ct["p85"] > 3 * ct["median"]:
        _card_alert(slide, RAIL_X, y, RAIL_W, card_h, "P85", f"{_fr_num(ct['p85'])} j",
                    "plus de 3x la médiane")
    else:
        _card_stat(slide, RAIL_X, y, RAIL_W, card_h, "P85", f"{_fr_num(ct['p85'])} j", "")

    SH.add_footer(slide, project_name, page_num, total_pages)


# ======================================================================= kpi
def render_kpi(slide, placeholder_shape, data, template_path, page_num, total_pages):
    m = data["metrics"]
    project_name = data["project_name"].strip()
    SH.clear_legacy_chrome(slide)
    SH.clear_placeholder(placeholder_shape)
    gen_date = _parse_iso(data["generated_at"])
    SH.add_header(slide, f"À DATE · {_ddmmyyyy(gen_date)}", "Indicateurs clés", template_path)

    total_us = _total_us(m["status_counts_us"])
    br = m.get("burnup_release")
    ai = br["anchor_index"] if br else None
    scope = br["scope_cumul_us"][ai] if br else total_us
    done = br["done_cumul_us"][ai] if br else 0
    remaining = scope - done
    avancement = round(100 * done / scope) if scope else 0
    ct = m["cycle_time"]

    waiting = _waiting_us(m["status_counts_us"])
    affinage = {k: v for k, v in m["status_counts_us"].items() if "affinage" in k.lower()}
    n_waiting, n_affinage = sum(waiting.values()), sum(affinage.values())
    if n_waiting >= n_affinage and n_waiting:
        vigilance_n = n_waiting
        vigilance_sub = "US en attente externe — " + ", ".join(f"{k} : {v}" for k, v in waiting.items())
    elif n_affinage:
        vigilance_n = n_affinage
        vigilance_sub = "US en goulot d'affinage"
    else:
        vigilance_n = 0
        vigilance_sub = "Aucun point de vigilance identifié"

    cols, rows = 3, 2
    gap = 24
    card_w = (S.CONTENT_W - gap * (cols - 1)) / cols
    card_h = (S.CONTENT_H - gap * (rows - 1)) / rows

    cards = [
        ("PÉRIMÈTRE", str(total_us), f"US suivies, sur {m['total_issues']} tickets", "stat"),
        ("AVANCEMENT", f"{avancement} %", f"{done} US terminées", "fill"),
        ("RESTE À FAIRE", str(remaining), f"US sur {scope} au périmètre", "stat"),
        ("VÉLOCITÉ MÉDIANE", f"{m['median_velocity_us']:g}", "US par sprint, cadence à confirmer", "stat"),
        ("CYCLE TIME MÉDIAN", f"{_fr_num(ct['median'])} j", f"moyenne {_fr_num(ct['mean'])} j · P85 {_fr_num(ct['p85'])} j", "stat"),
        ("POINTS DE VIGILANCE", str(vigilance_n), vigilance_sub, "alert" if vigilance_n else "stat"),
    ]

    for i, (label, big, sub, kind) in enumerate(cards):
        r, c = divmod(i, cols)
        x = S.MARGIN_X + c * (card_w + gap)
        y = S.CONTENT_Y + r * (card_h + gap)
        if kind == "fill":
            _card_kpi_fill(slide, x, y, card_w, card_h, label, big, sub)
        elif kind == "alert":
            _card_kpi(slide, x, y, card_w, card_h, label, big, sub,
                      fill=S.ALERT_BG, border=S.ALERT_BORDER, label_color=S.ALERT_TEXT,
                      big_color=S.BRAND_ACCENT, sub_color=S.ALERT_TEXT)
        else:
            _card_kpi(slide, x, y, card_w, card_h, label, big, sub)

    SH.add_footer(slide, project_name, page_num, total_pages)


def _card_kpi(slide, x, y, w, h, label, big, sub, fill=S.CARD_BG, border=S.CARD_BORDER,
              label_color=S.TEXT_SECONDARY, big_color=S.BRAND_PRIMARY, sub_color=S.TEXT_SECONDARY):
    SH.add_rounded_rect(slide, x, y, w, h, fill=fill, line_color=border)
    pad = S.CARD_PADDING_PX
    SH.add_text(slide, x + pad, y + pad, w - 2 * pad, 30, label, size=S.SIZE_CARD_LABEL,
                color=label_color, bold=True, all_caps=True)
    SH.add_text(slide, x + pad, y + pad + 38, w - 2 * pad, 94, big, size=S.SIZE_KPI_BIG,
                color=big_color, bold=True)
    SH.add_text(slide, x + pad, y + h - pad - 33, w - 2 * pad, 33, sub, size=Pt(12), color=sub_color)


def _card_kpi_fill(slide, x, y, w, h, label, big, sub):
    _card_kpi(slide, x, y, w, h, label, big, sub, fill=S.BRAND_PRIMARY, border=None,
              label_color=S.TEXT_WHITE, big_color=S.TEXT_WHITE, sub_color=S.TEXT_WHITE)


# ==================================================================== cover
def render_cover(slide, data):
    """Slide de couverture : conserve les images déjà en place dans le
    template (fond plein cadre + bandeau logo), ne remplace que le texte."""
    project_name = data["project_name"].strip()
    m = data["metrics"]
    gen_date = _parse_iso(data["generated_at"])

    active = next((b for b in m.get("burnup", []) if b["state"] == "active"), None)
    if active:
        soustitre = f"Indicateurs au {_ddmmyyyy(gen_date)} — sprint {active['num']} en cours"
    else:
        soustitre = f"Indicateurs au {_ddmmyyyy(gen_date)}"

    for shape in list(slide.shapes):
        if (shape.is_placeholder and shape.has_text_frame
                and shape.placeholder_format.type == PP_PLACEHOLDER.TITLE):
            shape._element.getparent().remove(shape._element)

    x, w = 136, 1648
    SH.add_text(slide, x, 314, w, 34, "PORTEFEUILLE DE PROJET", size=Pt(13),
                color=S.TEXT_WHITE, bold=True, all_caps=True, letter_spacing_pt=1.5)
    SH.add_text(slide, x, 358, w, 150, project_name, size=Pt(48), color=S.TEXT_WHITE, bold=True)
    SH.add_text(slide, x, 522, w, 50, soustitre, size=Pt(17), color=S.TEXT_WHITE)


# =================================================================== coach
COACH_OVERFLOW_CHARS = 2000


def _dark_header(slide, surtitre, titre, template_path, logo_media=None):
    """`logo_media` optionnel, voir `shapes.add_header` — la pastille blanche
    n'est dessinée que si un logo est effectivement trouvé."""
    SH.add_text(slide, S.MARGIN_X, S.MARGIN_TOP, S.CONTENT_W - S.LOGO_WIDTH_PX - 20, 26,
                surtitre, size=S.SIZE_SURTITLE, color=S.SYNTH_ACCENT, bold=True,
                all_caps=True, letter_spacing_pt=1.2)
    SH.add_text(slide, S.MARGIN_X, S.MARGIN_TOP + 33, S.CONTENT_W - S.LOGO_WIDTH_PX - 20, 62,
                titre, size=S.SIZE_SLIDE_TITLE, color=S.TEXT_WHITE, bold=True,
                letter_spacing_pt=-0.3)
    logo_bytes = SH.template_image_bytes(template_path, logo_media) if logo_media else None
    if logo_bytes is not None:
        pastille_w, pastille_h = S.LOGO_WIDTH_PX + 26, 85
        SH.add_rounded_rect(slide, S.MARGIN_X + S.CONTENT_W - pastille_w, S.MARGIN_TOP - 5,
                             pastille_w, pastille_h, fill=S.TEXT_WHITE, line_color=None, radius_px=14)
        slide.shapes.add_picture(
            logo_bytes,
            S.px(S.MARGIN_X + S.CONTENT_W - pastille_w + 13), S.px(S.MARGIN_TOP + 15),
            S.px(S.LOGO_WIDTH_PX),
        )


def _dark_footer(slide, project_name, page_num, total_pages):
    y = S.SLIDE_H_PX - S.MARGIN_BOTTOM + 22
    SH.add_text(slide, S.MARGIN_X, y, 600, 30, project_name, size=S.SIZE_FOOTER, color=S.TEXT_WHITE)
    SH.add_text(slide, S.MARGIN_X + S.CONTENT_W - 150, y, 150, 30,
                f"{page_num:02d} / {total_pages}", size=S.SIZE_FOOTER, color=S.TEXT_WHITE,
                align=PP_ALIGN.RIGHT)


def render_coach(slide, placeholder_shape, data, template_path, page_num, total_pages, prs=None):
    coaching = data.get("coaching") or {}
    project_name = data["project_name"].strip()
    SH.clear_legacy_chrome(slide)
    SH.clear_placeholder(placeholder_shape)

    vue_ensemble = coaching.get("vue_ensemble", "")
    risque = coaching.get("risque_principal", "")
    lecture = list((coaching.get("lecture") or {}).items())
    recos = coaching.get("recommandations", [])

    if not (vue_ensemble or lecture or recos):
        SH.add_rect(slide, 0, 0, S.SLIDE_W_PX, S.SLIDE_H_PX, fill=S.SYNTH_BG, line_color=None)
        _dark_header(slide, "SYNTHÈSE", "Lecture du coach", template_path)
        SH.add_text(slide, S.MARGIN_X, S.CONTENT_Y + 40, S.CONTENT_W, 60,
                    "Synthèse non générée pour ce run — voir COACH_PROMPT.md.",
                    size=S.SIZE_BODY, color=S.TEXT_WHITE)
        _dark_footer(slide, project_name, page_num, total_pages)
        return [slide]

    total_chars = len(vue_ensemble) + len(risque) + sum(len(v) for _, v in lecture) + sum(len(r) for r in recos)
    split = total_chars > COACH_OVERFLOW_CHARS and len(lecture) > 3

    if not split or prs is None:
        _render_coach_slide(slide, project_name, template_path, page_num, total_pages,
                             vue_ensemble, risque, lecture, recos, suffix="")
        return [slide]

    slide2 = prs.slides.add_slide(slide.slide_layout)
    for shape in list(slide2.shapes):
        shape._element.getparent().remove(shape._element)
    _render_coach_slide(slide, project_name, template_path, page_num, total_pages + 1,
                         vue_ensemble, risque, lecture[:3], [], suffix=" — 1/2")
    _render_coach_slide(slide2, project_name, template_path, page_num + 1, total_pages + 1,
                         "", "", lecture[3:], recos, suffix=" — 2/2")
    return [slide, slide2]


def _render_coach_slide(slide, project_name, template_path, page_num, total_pages,
                         vue_ensemble, risque, lecture, recos, suffix):
    SH.add_rect(slide, 0, 0, S.SLIDE_W_PX, S.SLIDE_H_PX, fill=S.SYNTH_BG, line_color=None)
    _dark_header(slide, "SYNTHÈSE", f"Lecture du coach{suffix}", template_path)

    left_w = (S.CONTENT_W - 40) * 0.48
    right_x = S.MARGIN_X + left_w + 40
    right_w = S.CONTENT_W - left_w - 40

    # Hauteur de chaque bloc de la colonne gauche basée sur une estimation du
    # texte réel (voir _estimate_text_height_px) plutôt qu'une proportion
    # fixe de l'espace disponible — une proportion fixe fait chevaucher le
    # bloc suivant (ou déborder de sa propre carte) dès que le texte réel
    # s'écarte de la longueur "moyenne" que cette proportion supposait.
    gap_v = 28
    pad = S.CARD_PADDING_PX
    risque_label_h = 34  # espace réservé au libellé "LE RISQUE PRINCIPAL" au-dessus du texte
    BODY_PX = 25  # correspond à S.SIZE_BODY = pt_from_px(25)

    vue_h = _estimate_text_height_px(vue_ensemble, left_w, BODY_PX) if vue_ensemble else 0
    risque_h = (
        _estimate_text_height_px(risque, left_w - 2 * pad, BODY_PX) + pad + risque_label_h + pad
        if risque else 0
    )

    n_blocks = sum([bool(vue_ensemble), bool(risque), bool(recos)])
    avail_h = S.CONTENT_H - gap_v * max(n_blocks - 1, 0)
    # Les recommandations récupèrent ce qu'il reste — jamais négatif : si vue
    # + risque dépassent déjà l'espace dispo, elles priment (une rédaction
    # trop longue à raccourcir plutôt qu'un bug de mise en page à masquer).
    reco_h = max(avail_h - vue_h - risque_h, 0) if recos else 0

    y = S.CONTENT_Y
    if vue_ensemble:
        SH.add_text(slide, S.MARGIN_X, y, left_w, vue_h, vue_ensemble, size=S.SIZE_BODY,
                    color=S.TEXT_WHITE)
        y += vue_h + gap_v
    if risque:
        SH.add_rounded_rect(slide, S.MARGIN_X, y, left_w, risque_h, fill=S.BRAND_ACCENT, line_color=None)
        SH.add_text(slide, S.MARGIN_X + pad, y + pad - 4, left_w - 2 * pad, 26,
                    "LE RISQUE PRINCIPAL", size=S.SIZE_CARD_LABEL, color=S.TEXT_WHITE, bold=True,
                    all_caps=True)
        SH.add_text(slide, S.MARGIN_X + pad, y + pad + risque_label_h, left_w - 2 * pad,
                    risque_h - pad - risque_label_h - pad,
                    risque, size=S.SIZE_BODY, color=S.TEXT_WHITE)
        y += risque_h + gap_v

    if lecture:
        SH.add_text(slide, right_x, S.CONTENT_Y, right_w, 26, "LECTURE COACHING",
                    size=S.SIZE_CARD_LABEL, color=S.SYNTH_ACCENT, bold=True, all_caps=True)
        card_y = S.CONTENT_Y + 40
        card_h = S.CONTENT_H - 40
        lecture_card = SH.add_rounded_rect(slide, right_x, card_y, right_w, card_h,
                                            fill=S.TEXT_WHITE, line_color=None)
        SH.set_transparency(lecture_card, 92)  # carte 8 % opaque sur fond bleu
        pad = S.CARD_PADDING_PX
        row_h = (card_h - 2 * pad) / len(lecture)
        for i, (topic, text) in enumerate(lecture):
            ry = card_y + pad + i * row_h
            SH.add_text(slide, right_x + pad, ry, 160, row_h, topic, size=Pt(13),
                        color=S.SYNTH_ACCENT, bold=True)
            SH.add_text(slide, right_x + pad + 176, ry, right_w - 2 * pad - 176, row_h, text,
                        size=S.SIZE_BODY, color=S.TEXT_WHITE)
            if i > 0:
                rule = SH.add_rect(slide, right_x + pad, ry, right_w - 2 * pad, 1.2,
                                    fill=S.TEXT_WHITE, line_color=None)
                SH.set_transparency(rule, 86)

    if recos:
        reco_y = y
        SH.add_text(slide, S.MARGIN_X, reco_y - 34, left_w, 26, "RECOMMANDATIONS",
                    size=S.SIZE_CARD_LABEL, color=S.TEXT_WHITE, bold=True, all_caps=True)
        n = len(recos)
        gap = 16
        card_h = max((reco_h - gap * (n - 1)) / n, 10)
        for i, text in enumerate(recos):
            ry = reco_y + i * (card_h + gap)
            if i == 0:
                SH.add_rounded_rect(slide, S.MARGIN_X, ry, left_w, card_h, fill=S.BRAND_ACCENT, line_color=None)
            else:
                reco_card = SH.add_rounded_rect(slide, S.MARGIN_X, ry, left_w, card_h,
                                                 fill=S.TEXT_WHITE, line_color=None)
                SH.set_transparency(reco_card, 92)
            pad = S.CARD_PADDING_PX
            SH.add_text(slide, S.MARGIN_X + pad, ry + pad, left_w - 2 * pad, card_h - 2 * pad,
                        f"{i + 1}.  {text}", size=S.SIZE_BODY, color=S.TEXT_WHITE)

    _dark_footer(slide, project_name, page_num, total_pages)


def _card_stat(slide, x, y, w, h, label, big, sub):
    SH.add_rounded_rect(slide, x, y, w, h)
    pad = S.CARD_PADDING_PX
    SH.add_text(slide, x + pad, y + pad - 4, w - 2 * pad, 26, label,
                size=S.SIZE_CARD_LABEL, color=S.TEXT_SECONDARY, bold=True, all_caps=True)
    SH.add_text(slide, x + pad, y + pad + 26, w - 2 * pad, 64, big,
                size=S.SIZE_CARD_NUMBER, color=S.BRAND_PRIMARY, bold=True)
    SH.add_text(slide, x + pad, y + h - pad - 26, w - 2 * pad, 26, sub,
                size=S.SIZE_CARD_LABEL, color=S.TEXT_SECONDARY)


def _card_scenario(slide, x, y, w, h, label, color, headline, sub, date_line=""):
    SH.add_rounded_rect(slide, x, y, w, h)
    SH.add_rect(slide, x, y, 6, h, fill=color, line_color=None)
    pad = S.CARD_PADDING_PX
    SH.add_text(slide, x + pad, y + pad - 4, w - 2 * pad, 24, label,
                size=S.SIZE_CARD_LABEL, color=color, bold=True, all_caps=True)
    SH.add_text(slide, x + pad, y + pad + 22, w - 2 * pad, 40, headline,
                size=Pt(18), color=S.BRAND_PRIMARY, bold=True)
    if date_line:
        SH.add_text(slide, x + pad, y + pad + 62, w - 2 * pad, 22, date_line,
                    size=S.SIZE_CARD_LABEL, color=S.TEXT_SECONDARY)
    SH.add_text(slide, x + pad, y + h - pad - 24, w - 2 * pad, 24, sub,
                size=S.SIZE_CARD_LABEL, color=S.TEXT_SECONDARY)


def _card_alert(slide, x, y, w, h, label, big, text):
    SH.add_rounded_rect(slide, x, y, w, h, fill=S.ALERT_BG, line_color=S.ALERT_BORDER)
    pad = S.CARD_PADDING_PX
    SH.add_text(slide, x + pad, y + pad - 4, w - 2 * pad, 26, label,
                size=S.SIZE_CARD_LABEL, color=S.ALERT_TEXT, bold=True, all_caps=True)
    SH.add_text(slide, x + pad, y + pad + 26, w - 2 * pad, 44, big,
                size=Pt(18), color=S.BRAND_ACCENT, bold=True)
    SH.add_text(slide, x + pad, y + pad + 76, w - 2 * pad, h - pad - 76, text,
                size=S.SIZE_CARD_LABEL, color=S.ALERT_TEXT)


def _card_lecture(slide, x, y, w, h, text, label="LECTURE", color=S.TEXT_SECONDARY):
    SH.add_rounded_rect(slide, x, y, w, h)
    pad = S.CARD_PADDING_PX
    SH.add_text(slide, x + pad, y + pad - 4, w - 2 * pad, 26, label,
                size=S.SIZE_CARD_LABEL, color=color, bold=True, all_caps=True)
    if text:
        SH.add_text(slide, x + pad, y + pad + 32, w - 2 * pad, h - pad - 32 - pad, text,
                    size=S.SIZE_BODY, color=S.TEXT_PRIMARY)


# =============================================================== liste_sprints
SPRINT_TABLE_HEADERS = ["Sprint", "Dates", "Ajouts", "Terminés", "Cumul US",
                         "Cumul terminé", "Estim. cumul", "Conso cumul"]
SPRINT_TABLE_COL_FRACS = [0.1075, 0.1998, 0.1016, 0.1016, 0.1142, 0.1275, 0.1335, 0.1142]
MAX_SPRINT_ROWS = 17


def render_sprint_table(slide, placeholder_shape, data, template_path, page_num, total_pages):
    m = data["metrics"]
    project_name = data["project_name"].strip()
    SH.clear_legacy_chrome(slide)
    SH.clear_placeholder(placeholder_shape)

    rows_all = [b for b in m["sprint_table"] if b.get("added_us") or b.get("done_us")]
    if not rows_all:
        SH.add_header(slide, "AUCUNE ACTIVITÉ", "Historique par sprint", template_path)
        SH.add_text(slide, S.MARGIN_X, S.CONTENT_Y + 40, S.CONTENT_W, 60,
                    "Aucun sprint avec ajout ou clôture d'US à ce jour.",
                    size=S.SIZE_BODY, color=S.TEXT_SECONDARY)
        SH.add_footer(slide, project_name, page_num, total_pages)
        return

    last = rows_all[-1]
    surtitre = (f"{last['scope_cumul_us']} US · {last['done_cumul_us']} TERMINÉES · "
                f"{_fr_num(last['scope_cumul_us_jh'])} JH ESTIMÉS")
    SH.add_header(slide, surtitre, "Historique par sprint", template_path)

    # "Sprint 0" porte le cumul (ajouts + terminés) de tout ce qui précède la
    # date configurée (sprint_start_date) — si la table doit être tronquée pour
    # tenir sur la slide, cette ligne reste épinglée en première position :
    # le lecteur ne doit jamais perdre le cumul d'avant la fenêtre affichée.
    has_sprint0 = bool(rows_all) and rows_all[0]["sprint"] == "Sprint 0"
    truncated = len(rows_all) > MAX_SPRINT_ROWS
    if truncated:
        tail_slots = MAX_SPRINT_ROWS - (2 if has_sprint0 else 1)
        tail = rows_all[-tail_slots:]
        rows = ([rows_all[0]] + tail) if has_sprint0 else tail
    else:
        rows = rows_all

    n_rows = len(rows) + 1 + (1 if truncated else 0)
    header_h = 50
    row_h = max((S.CONTENT_H - header_h) / (n_rows - 1), 40)

    tbl_shape = slide.shapes.add_table(n_rows, len(SPRINT_TABLE_HEADERS),
                                        S.px(S.MARGIN_X), S.px(S.CONTENT_Y),
                                        S.px(S.CONTENT_W), S.px(header_h + row_h * (n_rows - 1)))
    table = tbl_shape.table
    table.first_row = False
    table.horz_banding = False
    for c, frac in enumerate(SPRINT_TABLE_COL_FRACS):
        table.columns[c].width = S.px(round(S.CONTENT_W * frac))
    table.rows[0].height = S.px(header_h)
    for r in range(1, n_rows):
        table.rows[r].height = S.px(row_h)

    def set_cell(r, c, text, bold=False, color=S.TEXT_PRIMARY, fill=None, align=PP_ALIGN.LEFT,
                 size=S.SIZE_TABLE_CELL):
        cell = table.cell(r, c)
        cell.margin_left = S.px(20)
        cell.margin_right = S.px(20)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        if fill is None:
            cell.fill.background()
        else:
            cell.fill.solid()
            cell.fill.fore_color.rgb = fill
        cell.text_frame.clear()
        p = cell.text_frame.paragraphs[0]
        p.alignment = align
        run = p.add_run()
        run.text = text
        run.font.size = size
        run.font.bold = bold
        run.font.name = S.FONT_FAMILY
        run.font.color.rgb = color

    for c, h in enumerate(SPRINT_TABLE_HEADERS):
        align = PP_ALIGN.LEFT if c < 2 else PP_ALIGN.RIGHT
        set_cell(0, c, h, bold=True, color=S.BRAND_PRIMARY, fill=S.CARD_BG, align=align)

    def render_row(r, b, zebra=0):
        is_current = b is rows_all[-1]
        row_fill = RGBColor(0xF0, 0xF6, 0xFA) if is_current else (
            RGBColor(0xFF, 0xFF, 0xFF) if zebra % 2 == 0 else RGBColor(0xFA, 0xFC, 0xFD))
        text_color = S.BRAND_PRIMARY if is_current else S.TEXT_PRIMARY
        bold = is_current

        start = _parse_iso(b.get("start"))
        end = _parse_iso(b.get("end"))
        dates = _ddmmyyyy(end) if not start else f"{_ddmm(start)} → {_ddmmyyyy(end)}"
        added = b.get("added_us", 0)
        added_color = S.BRAND_ACCENT if added > 10 else text_color
        added_bold = bold or added > 10

        set_cell(r, 0, f"S{b['num']}", bold=True, color=text_color, fill=row_fill)
        set_cell(r, 1, dates, color=text_color, fill=row_fill, bold=bold)
        set_cell(r, 2, str(added), color=added_color, fill=row_fill, align=PP_ALIGN.RIGHT, bold=added_bold)
        set_cell(r, 3, str(b.get("done_us", 0)), color=text_color, fill=row_fill, align=PP_ALIGN.RIGHT, bold=bold)
        set_cell(r, 4, str(b.get("scope_cumul_us", 0)), color=text_color, fill=row_fill, align=PP_ALIGN.RIGHT, bold=bold)
        set_cell(r, 5, str(b.get("done_cumul_us", 0)), color=text_color, fill=row_fill, align=PP_ALIGN.RIGHT, bold=bold)
        set_cell(r, 6, f"{_fr_num(b.get('scope_cumul_us_jh', 0))} jh", color=text_color, fill=row_fill, align=PP_ALIGN.RIGHT, bold=bold)
        set_cell(r, 7, f"{_fr_num(b.get('conso_cumul_us_jh', 0))} jh", color=text_color, fill=row_fill, align=PP_ALIGN.RIGHT, bold=bold)

    def render_ellipsis(r):
        set_cell(r, 0, "…", color=S.TEXT_FOOTER, fill=RGBColor(0xFF, 0xFF, 0xFF))
        for c in range(1, len(SPRINT_TABLE_HEADERS)):
            set_cell(r, c, "", fill=RGBColor(0xFF, 0xFF, 0xFF))

    if truncated and has_sprint0:
        render_row(1, rows[0], zebra=0)
        render_ellipsis(2)
        row_offset = 3
        body_rows = rows[1:]
    elif truncated:
        render_ellipsis(1)
        row_offset = 2
        body_rows = rows
    else:
        row_offset = 1
        body_rows = rows

    for i, b in enumerate(body_rows):
        render_row(i + row_offset, b, zebra=i)

    SH.add_footer(slide, project_name, page_num, total_pages)


