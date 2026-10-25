# -*- coding: utf-8 -*-
"""
斗六堰歷年資料擷取 (Full-history extraction for 斗六堰, all years available in the
latest compiled workbook). Source: 115 斗六堰水生生物調查表.xlsx (ROC115 = AD2026,
the most recent annual-compiled workbook; its 魚蝦類總資料/何氏棘鲃/特有保育表 sheets
are cumulative roll-ups that already span many years) + 115 南雲大橋流量水質報表.xlsx.

Writes four tidy CSVs into ../data/ ready for Postgres COPY:
  - fact_species_count.csv       (魚蝦類總資料: 2014-2026 species x station x date counts)
  - fact_specimen_hosp.csv       (何氏棘鲃: individual specimen capture records)
  - fact_conservation_species.csv(特有保育表: periodic conservation/endemic species summary)
  - fact_water_quality.csv       (南雲大橋水質: per-sampling-date water quality readings)
"""
import re
import csv
import openpyxl

SRC_DIR = "/mnt/user-data/uploads/z/11.集集斗六/2026/斗六堰/原始資料"
OUT_DIR = "/tmp/claude-0/-home-claude/48f600c1-8891-5f9f-b9f6-f360009e1c2d/scratchpad/bi_stack/data"

MAIN_WB = f"{SRC_DIR}/115 斗六堰水生生物調查表.xlsx"
WQ_WB = f"{SRC_DIR}/115 南雲大橋流量水質報表.xlsx"


PLACEHOLDER_VALUES = {"―", "-", "—", "ー", "", "無", "N/A", "NA"}

# The source workbook was authored with a legacy font that maps a handful of rare
# CJK fish-name characters into the Unicode Private Use Area (U+E000-U+F8FF)
# instead of their real Unicode code points, so they look fine in the original
# Excel (which still has that font) but come out wrong -- or invisible -- anywhere
# else. Each entry here was confirmed by inspecting the raw cell text byte-by-byte.
PUA_FIXES = {
    "": "\U00029f27",  # "台灣石" + PUA -> "台灣石𩼧" (Acrossocheilus paradoxus)
}


def fix_pua(s):
    """Replace known legacy Private-Use-Area glyph codes with their real Unicode
    characters. See PUA_FIXES above. No-op for non-string input."""
    if not isinstance(s, str):
        return s
    for bad, good in PUA_FIXES.items():
        if bad in s:
            s = s.replace(bad, good)
    return s


def clean_num(v):
    """Pass through real numbers; turn placeholder dash/text markers into None.
    A lab "below detection limit" reading like "<1.0" is stored as that numeric
    bound (a documented simplification -- see README) rather than dropped."""
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = v.strip()
        if s in PLACEHOLDER_VALUES:
            return None
        m = re.match(r"^[<>]\s*([\d.]+)$", s)
        if m:
            return float(m.group(1))
    return v


def roc_date_to_iso(s):
    """'103/01/25' (ROC) -> '2014-01-25'. Returns None if unparsable."""
    if not isinstance(s, str):
        return None
    m = re.match(r"^(\d{2,3})/(\d{1,2})/(\d{1,2})$", s.strip())
    if not m:
        return None
    roc, mo, da = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return f"{roc + 1911:04d}-{mo:02d}-{da:02d}"
    except Exception:
        return None


# ---------- 1. fact_species_count (魚蝦類總資料, already tidy, full history) ----------
wb = openpyxl.load_workbook(MAIN_WB, data_only=True, read_only=True)
ws = wb["魚蝦類總資料"]
rows_out = []
for i, row in enumerate(ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True)):
    station, date_roc, year, season, count, name_zh, name_full, category, order_full, order_zh, family_full, name_en, trait, habitat = row[:14]
    if year is None or count is None:
        continue
    rows_out.append({
        "station": station, "survey_date": roc_date_to_iso(date_roc), "survey_date_roc": date_roc,
        "year": int(year) if year else None, "season": int(season) if isinstance(season, (int, float)) else None,
        "count": int(count) if isinstance(count, (int, float)) else None,
        "species_name_zh": fix_pua(name_zh), "species_name_latin": name_en, "category": category,
        "order_name": order_zh.strip() if isinstance(order_zh, str) else order_zh,
        "family_name": family_full.split(" ")[0] if isinstance(family_full, str) else family_full,
        "trait": trait, "habitat": habitat,
    })
with open(f"{OUT_DIR}/fact_species_count.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
    w.writeheader()
    w.writerows(rows_out)
print("fact_species_count rows:", len(rows_out), "years:", sorted(set(r["year"] for r in rows_out)))

# ---------- 2. fact_specimen_hosp (何氏棘鲃, full history) ----------
ws2 = wb["何氏棘鲃"]
rows2 = list(ws2.iter_rows(min_row=3, max_row=ws2.max_row, values_only=True))
out2 = []
for row in rows2:
    date_roc = row[0]
    if not date_roc or not isinstance(date_roc, str) or not re.match(r"^\d{2,3}/\d{1,2}/\d{1,2}$", date_roc.strip()):
        continue
    out2.append({
        "capture_date": roc_date_to_iso(date_roc), "capture_date_roc": date_roc, "station": row[1],
        "body_length_cm": clean_num(row[2]), "total_length_cm": clean_num(row[3]), "weight_g": clean_num(row[4]),
        "stomach_algae": row[5], "stomach_debris": row[6], "stomach_bugs": row[7], "stomach_fish_tissue": row[8],
        "egg_mature": row[9], "egg_immature": row[10], "testis_mature": row[11],
    })
with open(f"{OUT_DIR}/fact_specimen_hosp.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(out2[0].keys()))
    w.writeheader()
    w.writerows(out2)
print("fact_specimen_hosp rows:", len(out2))

# ---------- 3. fact_conservation_species (特有保育表, ALL periodic blocks) ----------
ws3 = wb["特有保育表"]
rows3 = list(ws3.iter_rows(min_row=1, max_row=ws3.max_row, values_only=True))
col0 = [r[0] for r in rows3]
markers = [(i, v) for i, v in enumerate(col0) if v and re.search(r"20\d\d", str(v))]
out3 = []
for mi, (idx, label) in enumerate(markers):
    header_idx = idx + 1
    end_idx = markers[mi + 1][0] if mi + 1 < len(markers) else len(rows3)
    for row in rows3[header_idx + 1 : end_idx]:
        species = row[2]
        if not species or not isinstance(species, str):
            continue
        if re.match(r"^\d+種$", species.strip()):
            continue  # per-block footer summary row ("28種" = species-type count), not a record
        out3.append({
            "period_label": label, "order_name": row[0], "family_name": row[1], "species_name_latin": fix_pua(species),
            "endemic_status": row[3], "conservation_grade": row[4],
            "station_upstream": row[5], "station_fishway": row[6], "station_fishway_entrance": row[7],
            "station_downstream": row[8], "total": row[9],
        })
with open(f"{OUT_DIR}/fact_conservation_species.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(out3[0].keys()))
    w.writeheader()
    w.writerows(out3)
print("fact_conservation_species rows:", len(out3), "periods:", [m[1] for m in markers])

# ---------- 4. fact_water_quality (南雲大橋水質, clean per-date table) ----------
wbq = openpyxl.load_workbook(WQ_WB, data_only=True, read_only=True)
wsq = wbq["表4南雲大橋水質"]
rowsq = list(wsq.iter_rows(min_row=3, max_row=wsq.max_row, values_only=True))
out4 = []
for row in rowsq:
    date = row[0]
    if date is None or not hasattr(date, "strftime"):
        continue  # skips footer/reference rows like "乙級標準" (water-quality class standard)
    date_str = date.strftime("%Y-%m-%d")
    out4.append({
        "sample_date": date_str, "sample_time": str(row[1]) if row[1] else None,
        "air_temp_c": clean_num(row[2]), "water_temp_c": clean_num(row[3]), "ph": clean_num(row[4]),
        "conductivity_umho_cm25c": clean_num(row[5]), "dissolved_oxygen_mgl": clean_num(row[6]),
        "bod_mgl": clean_num(row[7]), "cod_mgl": clean_num(row[8]), "ss_mgl": clean_num(row[9]),
    })
with open(f"{OUT_DIR}/fact_water_quality.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(out4[0].keys()))
    w.writeheader()
    w.writerows(out4)
print("fact_water_quality rows:", len(out4))
