"""validator.py — validates Weekly_Planting upload Excel files"""
import openpyxl
from datetime import datetime

FIELD_SCHEMA = [
    {"name": "week_number",  "dtype": "integer", "required": True,  "unique": False},
    {"name": "week_label",   "dtype": "string",  "required": True,  "unique": False},
    {"name": "season",       "dtype": "string",  "required": True,  "unique": False},
    {"name": "field_id",     "dtype": "string",  "required": True,  "unique": False},
    {"name": "field_name",   "dtype": "string",  "required": True,  "unique": False},
    {"name": "block",        "dtype": "string",  "required": True,  "unique": False},
    {"name": "crop",         "dtype": "string",  "required": True,  "unique": False},
    {"name": "planned_date", "dtype": "date",    "required": True,  "unique": False},
    {"name": "actual_date",  "dtype": "date",    "required": True,  "unique": False},
    {"name": "labor_cost",   "dtype": "float",   "required": True,  "unique": False},
    {"name": "qty_planted",  "dtype": "integer", "required": True,  "unique": False},
    {"name": "target_qty",   "dtype": "integer", "required": True,  "unique": False},
    {"name": "notes",        "dtype": "string",  "required": False, "unique": False},
]

COMPOSITE_UNIQUE_KEYS = [("week_number", "season", "field_id")]
REQUIRED_FIELDS = {f["name"] for f in FIELD_SCHEMA if f["required"]}
KNOWN_FIELDS    = {f["name"] for f in FIELD_SCHEMA}
FIELD_DTYPES    = {f["name"]: f["dtype"] for f in FIELD_SCHEMA}


def _parse_date(val):
    if isinstance(val, datetime): return val.date()
    if hasattr(val, "date") and not callable(val.date): return val
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try: return datetime.strptime(str(val).strip(), fmt).date()
        except: pass
    return None


def _check_dtype(val, dtype):
    if val is None or str(val).strip() == "": return False, "empty"
    if dtype == "integer":
        try: int(float(str(val))); return True, None
        except: return False, f"'{val}' is not an integer"
    if dtype == "float":
        try: float(str(val)); return True, None
        except: return False, f"'{val}' is not a number"
    if dtype == "date":
        return (True, None) if _parse_date(val) else (False, f"'{val}' is not a valid date (use YYYY-MM-DD)")
    return True, None


def validate_excel(filepath):
    errors, rows = [], []
    try:
        wb = openpyxl.load_workbook(filepath, data_only=True)
        ws = wb.active
    except Exception as e:
        return [{"row": None, "field": None, "error_type": "FILE_ERROR", "message": str(e)}], [], []

    all_rows = list(ws.iter_rows(values_only=True))
    if not all_rows:
        return [{"row": None, "field": None, "error_type": "EMPTY_FILE", "message": "File is empty."}], [], []

    raw_headers = [str(h).strip().lower() if h is not None else "" for h in all_rows[0]]
    missing = REQUIRED_FIELDS - set(raw_headers)
    if missing:
        return [{"row": 1, "field": None, "error_type": "MISSING_REQUIRED_FIELDS",
                 "message": f"Required columns not found: {', '.join(sorted(missing))}"}], [], raw_headers

    col_idx   = {h: i for i, h in enumerate(raw_headers) if h in KNOWN_FIELDS}
    data_rows = all_rows[1:]
    if not data_rows:
        return [{"row": None, "field": None, "error_type": "NO_DATA", "message": "No data rows found."}], [], raw_headers

    parsed_rows = []
    for r_idx, row in enumerate(data_rows, start=2):
        row_dict, row_ok = {}, True
        for f in FIELD_SCHEMA:
            fname = f["name"]
            if fname not in col_idx: continue
            val = row[col_idx[fname]]
            if f["required"] and (val is None or str(val).strip() == ""):
                errors.append({"row": r_idx, "field": fname, "error_type": "MISSING_VALUE",
                               "message": f"Row {r_idx}: '{fname}' is required but empty."})
                row_ok = False; continue
            if val is not None and str(val).strip() != "":
                ok, msg = _check_dtype(val, FIELD_DTYPES[fname])
                if not ok and msg != "empty":
                    errors.append({"row": r_idx, "field": fname, "error_type": "WRONG_DTYPE",
                                   "message": f"Row {r_idx}, '{fname}': {msg} (expected {FIELD_DTYPES[fname]})"})
                    row_ok = False
            row_dict[fname] = val
        if row_ok: parsed_rows.append((r_idx, row_dict))

    # Composite unique key
    for key_fields in COMPOSITE_UNIQUE_KEYS:
        seen = {}
        for r_idx, row in parsed_rows:
            key_vals = tuple(str(row.get(k, "")).strip() for k in key_fields)
            if any(v == "" for v in key_vals): continue
            if key_vals in seen:
                errors.append({"row": r_idx, "field": "+".join(key_fields),
                               "error_type": "DUPLICATE_COMPOSITE_KEY",
                               "message": f"Row {r_idx}: Duplicate key {key_vals}. First seen row {seen[key_vals]}."})
            else: seen[key_vals] = r_idx

    if not errors:
        for r_idx, row in parsed_rows:
            rows.append({
                "row_number":  r_idx,
                "week_number": int(float(str(row.get("week_number", 0)))),
                "week_label":  str(row.get("week_label", "")).strip(),
                "season":      str(row.get("season", "")).strip(),
                "field_id":    str(row.get("field_id", "")).strip(),
                "field_name":  str(row.get("field_name", "")).strip(),
                "block":       str(row.get("block", "")).strip(),
                "crop":        str(row.get("crop", "")).strip(),
                "planned_date": _parse_date(row.get("planned_date")),
                "actual_date":  _parse_date(row.get("actual_date")),
                "labor_cost":  float(row.get("labor_cost", 0)),
                "qty_planted": int(float(str(row.get("qty_planted", 0)))),
                "target_qty":  int(float(str(row.get("target_qty", 0)))),
                "notes":       str(row.get("notes") or "").strip(),
            })
    wb.close()
    return errors, rows, raw_headers
