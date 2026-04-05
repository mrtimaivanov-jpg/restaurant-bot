import re
from difflib import SequenceMatcher
from typing import Optional, Dict, List, Tuple

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Restoran Botu", layout="wide")

# =========================
# SETTINGS
# =========================
RESTAURANT_BLACKLIST_PARTS = [
    "hotel",
    "ciao",
    "wyndham garden baku",
    "af beach",
    "beach",
    "istirahet",
    "spa",
    "fitness",
    "otel",
    "saray",
    "sadliq",
    "neolit",
]

BAD_ITEM_WORDS = [
    "limon",
    "göyərti",
    "goyerti",
    "qatıq",
    "gatiq",
    "sous",
    "sos",
    "ketçup",
    "ketcup",
    "ketchup",
    "mayonez",
    "duz",
    "istiot",
]

CATEGORY_LABELS = {
    "MAIN": "Əsas yeməklər",
    "SOUP": "Şorbalar",
    "APPETIZER": "Qəlyanaltılar",
    "SALAD": "Salatlar",
    "SOFT_DRINK": "İçkilər",
    "DESSERT": "Desertlər",
    "ALCOHOL": "Alkoqol",
    "HOOKAH": "Qəlyan",
    "FITNESS": "Fitness",
    "OTHER": "Digər",
}

BASKET_CATEGORY_OPTIONS = [
    ("Əsas yemək", "MAIN"),
    ("Şorba", "SOUP"),
    ("Qəlyanaltı", "APPETIZER"),
    ("Salat", "SALAD"),
    ("İçki", "SOFT_DRINK"),
    ("Desert", "DESSERT"),
    ("Alkoqol", "ALCOHOL"),
    ("Qəlyan", "HOOKAH"),
]

SEARCH_PRICE_BANDS = [
    ("Hamısı", None, None),
    ("0–5", 0, 5),
    ("5–10", 5, 10),
    ("10–20", 10, 20),
    ("20+", 20, None),
]

# =========================
# STYLES
# =========================
st.markdown(
    """
    <style>
    .page-subtitle {
        font-size: 14px;
        opacity: 0.82;
        margin-top: -8px;
        margin-bottom: 18px;
    }

    .item-card {
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 14px;
        padding: 14px 16px;
        margin-bottom: 10px;
        background: rgba(255,255,255,0.02);
    }

    .restaurant-card {
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 14px;
        background: rgba(255,255,255,0.03);
    }

    .item-title {
        font-size: 16px;
        font-weight: 600;
        margin-bottom: 6px;
    }

    .item-meta {
        font-size: 13px;
        opacity: 0.85;
    }

    .summary-box {
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 14px;
        padding: 12px 14px;
        background: rgba(255,255,255,0.025);
        margin-bottom: 10px;
    }

    .small-muted {
        font-size: 12px;
        opacity: 0.80;
    }

    .mode-box {
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 10px 12px;
        background: rgba(255,255,255,0.015);
        margin-bottom: 10px;
    }

    div.stButton > button {
        border-radius: 10px;
        min-height: 2.15rem;
        padding: 0.22rem 0.70rem;
        font-size: 0.90rem;
    }

    div[data-testid="stHorizontalBlock"] {
        align-items: end;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# TEXT / FILTER HELPERS
# =========================
def normalize_text(text) -> str:
    if pd.isna(text):
        return ""
    text = str(text).strip().lower()
    replacements = {
        "ə": "e",
        "ğ": "g",
        "ı": "i",
        "ö": "o",
        "ü": "u",
        "ş": "s",
        "ç": "c",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def restaurant_is_blacklisted(name: str) -> bool:
    n = normalize_text(name)
    return any(part in n for part in RESTAURANT_BLACKLIST_PARTS)


def item_is_bad(item_name: str) -> bool:
    n = normalize_text(item_name)
    return any(word in n for word in BAD_ITEM_WORDS)


def parse_price(text) -> Optional[float]:
    t = str(text).strip()
    if t == "":
        return None
    try:
        return float(t.replace(",", "."))
    except Exception:
        return None


def validate_min_max(min_val: Optional[float], max_val: Optional[float]) -> bool:
    if min_val is not None and max_val is not None and min_val > max_val:
        st.error("Minimum qiymət maksimum qiymətdən böyük ola bilməz.")
        return False
    return True


def midpoint(min_val: Optional[float], max_val: Optional[float]) -> Optional[float]:
    if min_val is not None and max_val is not None:
        return (min_val + max_val) / 2
    return None


def apply_price_range(df: pd.DataFrame, price_col: str, min_price: Optional[float], max_price: Optional[float]) -> pd.DataFrame:
    work = df.copy()
    if min_price is not None:
        work = work[work[price_col] >= min_price].copy()
    if max_price is not None:
        work = work[work[price_col] <= max_price].copy()
    return work


def get_category_label(final_class: str) -> str:
    return CATEGORY_LABELS.get(str(final_class).upper(), str(final_class))


# =========================
# SESSION HELPERS
# =========================
def safe_session_default(key: str, value):
    if key not in st.session_state:
        st.session_state[key] = value


def set_widget_value(key: str, value):
    st.session_state[key] = value


def clear_text_key(key: str):
    st.session_state[key] = ""


def clear_select_key(key: str):
    st.session_state[key] = ""


def clear_multiselect_key(key: str):
    st.session_state[key] = []


def clear_number_key(key: str):
    st.session_state[key] = 0


def reset_many(default_map: Dict[str, object]):
    for k, v in default_map.items():
        st.session_state[k] = v


# =========================
# UI HELPERS
# =========================
def render_tab_reset_button(label: str, reset_map: Dict[str, object], key: str):
    st.button(
        label,
        key=key,
        on_click=reset_many,
        args=(reset_map,)
    )


def render_clearable_text(label: str, key: str, placeholder: str = "") -> str:
    safe_session_default(key, "")
    c1, c2 = st.columns([18, 1])

    with c1:
        value = st.text_input(label, key=key, placeholder=placeholder)

    with c2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        st.button("×", key=f"clear_{key}", on_click=clear_text_key, args=(key,), help="Təmizlə")

    return value


def render_clearable_selectbox(
    label: str,
    options: List[str],
    key: str,
    placeholder_label: str = "Seç...",
    format_map: Optional[Dict[str, str]] = None,
) -> str:
    safe_session_default(key, "")
    final_options = [""] + options

    def _fmt(x):
        if x == "":
            return placeholder_label
        if format_map and x in format_map:
            return format_map[x]
        return x

    c1, c2 = st.columns([18, 1])

    with c1:
        value = st.selectbox(
            label,
            options=final_options,
            key=key,
            format_func=_fmt,
        )

    with c2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        st.button("×", key=f"clear_{key}", on_click=clear_select_key, args=(key,), help="Təmizlə")

    return value


def render_clearable_multiselect(
    label: str,
    options: List[str],
    key: str,
    format_map: Optional[Dict[str, str]] = None,
) -> List[str]:
    safe_session_default(key, [])
    c1, c2 = st.columns([18, 1])

    with c1:
        if format_map:
            value = st.multiselect(
                label,
                options=options,
                key=key,
                format_func=lambda x: format_map.get(x, x)
            )
        else:
            value = st.multiselect(label, options=options, key=key)

    with c2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        st.button("×", key=f"clear_{key}", on_click=clear_multiselect_key, args=(key,), help="Təmizlə")

    return value


def render_price_range(prefix: str, min_key: str, max_key: str) -> Tuple[Optional[float], Optional[float]]:
    safe_session_default(min_key, "")
    safe_session_default(max_key, "")

    c1, c2 = st.columns(2)
    with c1:
        min_text = render_clearable_text(f"{prefix} minimum", min_key, placeholder="məs: 5")
    with c2:
        max_text = render_clearable_text(f"{prefix} maksimum", max_key, placeholder="məs: 25")

    return parse_price(min_text), parse_price(max_text)


# =========================
# BASKET STATE
# =========================
def init_basket_state():
    safe_session_default("basket_restaurant", None)
    safe_session_default("basket_items", [])


def clear_basket():
    st.session_state["basket_restaurant"] = None
    st.session_state["basket_items"] = []


def basket_total():
    return round(sum(x["price"] for x in st.session_state["basket_items"]), 2)


def add_to_basket(restaurant_name: str, item_name: str, price: float, final_class: str):
    current_restaurant = st.session_state["basket_restaurant"]
    if current_restaurant is None:
        st.session_state["basket_restaurant"] = restaurant_name
    elif current_restaurant != restaurant_name:
        st.warning("Səbət yalnız bir restoran üçün ola bilər. Əvvəl səbəti təmizlə.")
        return

    st.session_state["basket_items"].append({
        "restaurant_name": restaurant_name,
        "item_name": item_name,
        "price": float(price),
        "class": final_class
    })


def load_result_basket(row: Dict):
    clear_basket()
    for item in row["items"]:
        add_to_basket(
            restaurant_name=row["restaurant_name"],
            item_name=item["item_name"],
            price=item["price"],
            final_class=item["class"]
        )


# =========================
# LOAD DATA
# =========================
@st.cache_data
def load_menu_data() -> pd.DataFrame:
    df = pd.read_parquet("menu_items.parquet")

    required_cols = ["SLUG", "RESTAURANT_NAME", "ITEM_NAME", "ITEM_NORM", "FINAL_CLASS", "PRICE"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Çatışmayan sütunlar: {missing}")

    df["PRICE"] = pd.to_numeric(df["PRICE"], errors="coerce")
    df = df.dropna(subset=["PRICE"]).copy()

    for col in ["SLUG", "RESTAURANT_NAME", "ITEM_NAME", "ITEM_NORM", "FINAL_CLASS"]:
        df[col] = df[col].astype(str).str.strip()

    df = df[~df["RESTAURANT_NAME"].apply(restaurant_is_blacklisted)].copy()
    df = df[~df["ITEM_NAME"].apply(item_is_bad)].copy()

    df["FINAL_CLASS"] = df["FINAL_CLASS"].astype(str).str.upper().str.strip()
    df["ITEM_NAME_NORM"] = df["ITEM_NAME"].apply(normalize_text)
    df["ITEM_NORM_NORM"] = df["ITEM_NORM"].apply(normalize_text)
    df["RESTAURANT_NAME_NORM"] = df["RESTAURANT_NAME"].apply(normalize_text)

    return df


@st.cache_data
def build_choice_df(df: pd.DataFrame) -> pd.DataFrame:
    work = (
        df.sort_values(["SLUG", "FINAL_CLASS", "ITEM_NAME", "PRICE"], ascending=[True, True, True, True])
        .drop_duplicates(subset=["SLUG", "FINAL_CLASS", "ITEM_NAME"], keep="first")
        .copy()
    )
    return work


@st.cache_data
def get_class_price_stats(df: pd.DataFrame) -> pd.DataFrame:
    stats = (
        df.groupby("FINAL_CLASS")["PRICE"]
        .agg(
            q25=lambda s: s.quantile(0.25),
            median="median",
            q75=lambda s: s.quantile(0.75),
            min_price="min",
            max_price="max",
        )
        .reset_index()
    )
    return stats


def get_class_stats_map(df: pd.DataFrame) -> Dict[str, Dict]:
    stats = get_class_price_stats(df)
    return stats.set_index("FINAL_CLASS").to_dict(orient="index")


# =========================
# SEARCH / SCORING
# =========================
def get_token_overlap_score(query_norm: str, candidate_norm: str) -> float:
    if not query_norm or not candidate_norm:
        return 0.0

    q_tokens = set(query_norm.split())
    c_tokens = set(candidate_norm.split())
    if not q_tokens or not c_tokens:
        return 0.0

    overlap = len(q_tokens.intersection(c_tokens))
    return overlap / max(1, len(q_tokens))


def get_fuzzy_match_score(query_text: str, item_name: str, item_norm: str) -> float:
    q = normalize_text(query_text)
    cand = item_norm if item_norm else normalize_text(item_name)

    if not q:
        return 0.0

    score = 0.0

    if cand == q:
        score += 100
    if cand.startswith(q):
        score += 35
    if q in cand:
        score += 25

    score += get_token_overlap_score(q, cand) * 30
    score += SequenceMatcher(None, q, cand).ratio() * 25

    q_tokens = q.split()
    cand_tokens = cand.split()

    for qt in q_tokens:
        for ct in cand_tokens:
            if qt == ct:
                score += 6
            elif ct.startswith(qt):
                score += 4
            elif SequenceMatcher(None, qt, ct).ratio() >= 0.78:
                score += 3

    return score


def score_candidate_row(
    row: pd.Series,
    class_stats_map: Dict[str, Dict],
    target_price: Optional[float] = None,
    query_text: str = ""
) -> float:
    fc = row["FINAL_CLASS"]
    price = float(row["PRICE"])
    item_name = str(row["ITEM_NAME"])
    item_norm = normalize_text(item_name)

    stats = class_stats_map.get(fc, {})
    q25 = float(stats.get("q25", price))
    med = float(stats.get("median", price))

    score = 0.0

    if price < q25 * 0.7:
        score -= 4.0
    elif price < q25:
        score -= 2.0
    elif price <= med * 1.35:
        score += 2.0

    word_count = len([x for x in item_norm.split(" ") if x.strip()])
    char_count = len(item_norm)
    if word_count >= 2:
        score += 1.2
    if char_count >= 8:
        score += 0.8

    ultra_simple = {
        "su", "cay", "cola", "fanta", "sprite", "ayran",
        "espresso", "americano", "latte", "kapucino"
    }
    if item_norm in ultra_simple:
        score -= 2.0

    score += get_fuzzy_match_score(query_text, item_name, item_norm)

    if target_price is not None:
        score -= abs(price - target_price) * 0.18

    return score


def get_top_query_suggestions(df: pd.DataFrame, query_text: str, max_suggestions: int = 8) -> List[str]:
    q = normalize_text(query_text)
    if not q:
        return []

    temp = df[["ITEM_NAME", "ITEM_NAME_NORM"]].drop_duplicates().copy()
    temp["suggest_score"] = temp.apply(
        lambda row: get_fuzzy_match_score(q, row["ITEM_NAME"], row["ITEM_NAME_NORM"]),
        axis=1
    )
    temp = temp[temp["suggest_score"] > 12].copy()
    temp = temp.sort_values(["suggest_score", "ITEM_NAME"], ascending=[False, True])
    return temp["ITEM_NAME"].head(max_suggestions).tolist()


def search_market_items(
    df: pd.DataFrame,
    selected_item: str,
    query_text: str,
    selected_restaurants: List[str],
    selected_classes: List[str],
    min_price: Optional[float],
    max_price: Optional[float],
    top_n: int,
) -> pd.DataFrame:
    work = df.copy()

    if selected_restaurants:
        work = work[work["RESTAURANT_NAME"].isin(selected_restaurants)].copy()

    if selected_classes:
        work = work[work["FINAL_CLASS"].isin(selected_classes)].copy()

    if selected_item:
        work = work[work["ITEM_NAME"] == selected_item].copy()

    work = apply_price_range(work, "PRICE", min_price, max_price)

    if work.empty:
        return work

    active_query = selected_item if selected_item else query_text.strip()

    class_stats_map = get_class_stats_map(df)
    target_mid = midpoint(min_price, max_price)

    if active_query:
        q_norm = normalize_text(active_query)
        q_tokens = [t for t in q_norm.split() if t]

        mask = pd.Series(False, index=work.index)
        for token in q_tokens:
            mask = mask | work["ITEM_NAME_NORM"].str.contains(token, regex=False)

        rough = work[mask].copy()

        if rough.empty:
            rough = work.copy()

        rough["match_score"] = rough.apply(
            lambda row: score_candidate_row(
                row,
                class_stats_map=class_stats_map,
                target_price=target_mid,
                query_text=active_query
            ),
            axis=1
        )

        rough = rough[rough["match_score"] > 8].copy()
        rough = rough.sort_values(
            ["match_score", "PRICE", "RESTAURANT_NAME", "ITEM_NAME"],
            ascending=[False, True, True, True]
        )
        return rough.head(top_n).copy()

    work["match_score"] = work.apply(
        lambda row: score_candidate_row(
            row,
            class_stats_map=class_stats_map,
            target_price=target_mid,
            query_text=""
        ),
        axis=1
    )

    work = work.sort_values(
        ["match_score", "PRICE", "RESTAURANT_NAME", "ITEM_NAME"],
        ascending=[False, True, True, True]
    )
    return work.head(top_n).copy()


def group_search_results_by_restaurant(
    results_df: pd.DataFrame,
    top_restaurants: int = 12,
    sample_items_per_restaurant: int = 4
) -> List[Dict]:
    if results_df.empty:
        return []

    rows = []
    for rest_name, part in results_df.groupby("RESTAURANT_NAME"):
        part = part.sort_values(["match_score", "PRICE", "ITEM_NAME"], ascending=[False, True, True]).copy()
        sample_items = part.head(sample_items_per_restaurant)[["ITEM_NAME", "PRICE", "FINAL_CLASS"]].to_dict("records")

        rows.append({
            "restaurant_name": rest_name,
            "match_count": int(len(part)),
            "min_price": float(part["PRICE"].min()),
            "median_price": float(part["PRICE"].median()),
            "max_price": float(part["PRICE"].max()),
            "best_score": float(part["match_score"].max()),
            "sample_items": sample_items,
        })

    rows = sorted(
        rows,
        key=lambda x: (-x["best_score"], -x["match_count"], x["min_price"], x["restaurant_name"])
    )
    return rows[:top_restaurants]


def build_search_overview(results_df: pd.DataFrame) -> Dict:
    by_restaurant = (
        results_df.groupby("RESTAURANT_NAME")
        .agg(
            item_count=("ITEM_NAME", "count"),
            min_price=("PRICE", "min"),
            median_price=("PRICE", "median"),
        )
        .reset_index()
    )

    return {
        "restaurant_count": int(results_df["RESTAURANT_NAME"].nunique()),
        "item_count": int(len(results_df)),
        "min_price": float(results_df["PRICE"].min()),
        "median_price": float(results_df["PRICE"].median()),
        "max_price": float(results_df["PRICE"].max()),
        "top_restaurant_by_count": by_restaurant.sort_values(
            ["item_count", "min_price", "RESTAURANT_NAME"],
            ascending=[False, True, True]
        ).iloc[0]["RESTAURANT_NAME"],
    }


# =========================
# MENU / OPTIONS HELPERS
# =========================
def get_restaurant_menu(df: pd.DataFrame, restaurant_name: str) -> pd.DataFrame:
    return df[df["RESTAURANT_NAME"] == restaurant_name].copy()


def get_item_options_for_df(df: pd.DataFrame, final_class: Optional[str] = None) -> Tuple[List[str], Dict[str, str]]:
    work = df.copy()
    if final_class:
        work = work[work["FINAL_CLASS"] == final_class].copy()

    if work.empty:
        return [], {}

    work = work.sort_values(["ITEM_NAME", "PRICE"], ascending=[True, True]).copy()
    work = work.drop_duplicates(subset=["ITEM_NAME"], keep="first")

    options = work["ITEM_NAME"].astype(str).tolist()
    display_map = {row["ITEM_NAME"]: f"{row['PRICE']:.2f} AZN — {row['ITEM_NAME']}" for _, row in work.iterrows()}
    return options, display_map


# =========================
# BASKET LOGIC
# =========================
def build_exact_basket_for_restaurant(rest_df: pd.DataFrame, selected_map: Dict[str, str]) -> Optional[Dict]:
    basket_items = []
    total = 0.0

    for class_code, selected_item_name in selected_map.items():
        candidates = rest_df[
            (rest_df["FINAL_CLASS"] == class_code) &
            (rest_df["ITEM_NAME"] == selected_item_name)
        ].copy()

        candidates = candidates.sort_values(["PRICE", "ITEM_NAME"], ascending=[True, True])
        if candidates.empty:
            return None

        chosen = candidates.iloc[0]

        basket_items.append({
            "item_name": chosen["ITEM_NAME"],
            "price": float(chosen["PRICE"]),
            "class": chosen["FINAL_CLASS"]
        })
        total += float(chosen["PRICE"])

    return {
        "restaurant_name": rest_df["RESTAURANT_NAME"].iloc[0],
        "total_price": round(total, 2),
        "items": basket_items
    }


def build_cross_restaurant_exact_baskets(
    df: pd.DataFrame,
    selected_map: Dict[str, str],
    min_total: Optional[float],
    max_total: Optional[float],
    top_n: int
) -> List[Dict]:
    rows = []
    target_mid = midpoint(min_total, max_total)

    for _, rest_df in df.groupby("SLUG"):
        built = build_exact_basket_for_restaurant(rest_df, selected_map)
        if built is None:
            continue

        total = built["total_price"]
        if min_total is not None and total < min_total:
            continue
        if max_total is not None and total > max_total:
            continue

        budget_distance = abs(total - target_mid) if target_mid is not None else 0
        built["budget_distance"] = budget_distance
        rows.append(built)

    rows = sorted(rows, key=lambda x: (x["budget_distance"], x["total_price"], x["restaurant_name"]))
    return rows[:top_n]


def choose_best_items_for_category_count(
    rest_df: pd.DataFrame,
    class_code: str,
    count_needed: int,
    class_stats_map: Dict[str, Dict],
    target_price_per_item: Optional[float] = None,
) -> List[Dict]:
    if count_needed <= 0:
        return []

    part = rest_df[rest_df["FINAL_CLASS"] == class_code].copy()
    if part.empty:
        return []

    part["score"] = part.apply(
        lambda row: score_candidate_row(row, class_stats_map, target_price=target_price_per_item),
        axis=1
    )

    part = part.sort_values(["score", "PRICE", "ITEM_NAME"], ascending=[False, True, True]).copy()
    chosen = part.head(count_needed).copy()

    if len(chosen) < count_needed:
        return []

    rows = []
    for _, row in chosen.iterrows():
        rows.append({
            "item_name": row["ITEM_NAME"],
            "price": float(row["PRICE"]),
            "class": row["FINAL_CLASS"],
            "score": float(row["score"])
        })
    return rows


def build_category_count_baskets(
    df: pd.DataFrame,
    category_counts: Dict[str, int],
    min_total: Optional[float],
    max_total: Optional[float],
    top_n: int,
) -> List[Dict]:
    rows = []
    class_stats_map = get_class_stats_map(df)
    total_item_count = sum(category_counts.values())

    target_mid = midpoint(min_total, max_total)
    target_price_per_item = None
    if target_mid is not None and total_item_count > 0:
        target_price_per_item = target_mid / total_item_count

    for _, rest_df in df.groupby("SLUG"):
        restaurant_name = rest_df["RESTAURANT_NAME"].iloc[0]
        basket_items = []
        ok = True

        for class_code, count_needed in category_counts.items():
            picked = choose_best_items_for_category_count(
                rest_df=rest_df,
                class_code=class_code,
                count_needed=count_needed,
                class_stats_map=class_stats_map,
                target_price_per_item=target_price_per_item,
            )
            if count_needed > 0 and not picked:
                ok = False
                break
            basket_items.extend(picked)

        if not ok:
            continue

        total = round(sum(x["price"] for x in basket_items), 2)

        if min_total is not None and total < min_total:
            continue
        if max_total is not None and total > max_total:
            continue

        avg_score = round(sum(x["score"] for x in basket_items) / len(basket_items), 3) if basket_items else 0.0
        budget_distance = abs(total - target_mid) if target_mid is not None else 0.0

        rows.append({
            "restaurant_name": restaurant_name,
            "total_price": total,
            "items": basket_items,
            "avg_score": avg_score,
            "budget_distance": budget_distance,
        })

    rows = sorted(
        rows,
        key=lambda x: (x["budget_distance"], -x["avg_score"], x["total_price"], x["restaurant_name"])
    )
    return rows[:top_n]


# =========================
# RENDER HELPERS
# =========================
def render_item_card(item_name: str, price: float, class_code: str, add_key: str, restaurant_name: str):
    st.markdown(
        f"""
        <div class="item-card">
            <div class="item-title">{item_name}</div>
            <div class="item-meta">{get_category_label(class_code)} · {price:.2f} AZN</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Səbətə əlavə et", key=add_key):
        add_to_basket(restaurant_name, item_name, price, class_code)


def render_basket_result_card(row: Dict, idx: str):
    st.markdown(f"### {row['restaurant_name']}")
    st.markdown(
        f"""
        <div class="restaurant-card">
            <div><b>Ümumi qiymət:</b> {row['total_price']:.2f} AZN</div>
            <div class="small-muted">Seçilən məhsullar: {len(row['items'])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for item in row["items"]:
        st.write(f"- {item['item_name']} — {item['price']:.2f} AZN")

    st.button(
        "Bu səbəti səbətə əlavə et",
        key=f"choose_rest_{idx}",
        on_click=load_result_basket,
        args=(row,)
    )


def render_search_summary_boxes(summary: Dict):
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"<div class='summary-box'><b>Restoran sayı</b><br>{summary['restaurant_count']}</div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='summary-box'><b>Məhsul sayı</b><br>{summary['item_count']}</div>", unsafe_allow_html=True)
    with c3:
        st.markdown(
            f"<div class='summary-box'><b>Qiymət aralığı</b><br>{summary['min_price']:.2f} – {summary['max_price']:.2f} AZN</div>",
            unsafe_allow_html=True
        )
    with c4:
        st.markdown(f"<div class='summary-box'><b>Median qiymət</b><br>{summary['median_price']:.2f} AZN</div>", unsafe_allow_html=True)


# =========================
# APP LOAD
# =========================
try:
    menu_df = load_menu_data()
    choice_df = build_choice_df(menu_df)
except Exception as e:
    st.error(f"Fayl oxunarkən xəta baş verdi: {e}")
    st.stop()

init_basket_state()

all_restaurants = sorted(choice_df["RESTAURANT_NAME"].dropna().astype(str).unique().tolist())
all_classes = sorted(choice_df["FINAL_CLASS"].dropna().astype(str).unique().tolist())
class_format_map = {x: get_category_label(x) for x in all_classes}
global_item_options, global_item_display_map = get_item_options_for_df(choice_df)

st.title("🍽️ Restoran Botu")

tab1, tab2, tab3 = st.tabs(["Menyu", "Səbət", "Axtarış"])

# =========================
# TAB 1 - MENU
# =========================
with tab1:
    st.subheader("Restoranın menyusu")
    st.markdown(
        "<div class='page-subtitle'>Bir restoran seç və onun menyusuna bax. Məhsulları filtr edə və səbətə əlavə edə bilərsən.</div>",
        unsafe_allow_html=True,
    )

    menu_reset_map = {
        "menu_restaurant_select": "",
        "menu_item_select": "",
        "menu_classes_multiselect": [],
        "menu_min_price_input": "",
        "menu_max_price_input": "",
    }

    top_left, top_right = st.columns([6, 2])
    with top_right:
        render_tab_reset_button("Hamısını sıfırla", menu_reset_map, "reset_menu_tab")

    menu_restaurant = render_clearable_selectbox(
        label="Restoran seç",
        options=all_restaurants,
        key="menu_restaurant_select",
        placeholder_label="Restoran seç..."
    )

    menu_item_selected = ""
    if menu_restaurant:
        menu_source_for_items = get_restaurant_menu(choice_df, menu_restaurant)
        menu_item_options, menu_item_display_map = get_item_options_for_df(menu_source_for_items)

        menu_item_selected = render_clearable_selectbox(
            label="Məhsulu siyahıdan seç",
            options=menu_item_options,
            key="menu_item_select",
            placeholder_label="Məhsul seç...",
            format_map=menu_item_display_map
        )

    menu_selected_classes = render_clearable_multiselect(
        "Kateqoriyalar",
        options=all_classes,
        key="menu_classes_multiselect",
        format_map=class_format_map
    )

    menu_min_price, menu_max_price = render_price_range(
        "Qiymət",
        "menu_min_price_input",
        "menu_max_price_input"
    )

    if validate_min_max(menu_min_price, menu_max_price):
        if menu_restaurant:
            with st.spinner("Menyu yüklənir..."):
                work = get_restaurant_menu(choice_df, menu_restaurant)

                if menu_selected_classes:
                    work = work[work["FINAL_CLASS"].isin(menu_selected_classes)].copy()

                if menu_item_selected:
                    work = work[work["ITEM_NAME"] == menu_item_selected].copy()

                work = apply_price_range(work, "PRICE", menu_min_price, menu_max_price)

                if work.empty:
                    st.warning("Bu filtrərə uyğun məhsul tapılmadı.")
                else:
                    grouped_classes = sorted(work["FINAL_CLASS"].dropna().astype(str).unique().tolist())

                    for fc in grouped_classes:
                        section_df = work[work["FINAL_CLASS"] == fc].copy()
                        section_df = section_df.sort_values(["PRICE", "ITEM_NAME"], ascending=[True, True])

                        st.markdown(f"### {get_category_label(fc)}")
                        for _, row in section_df.iterrows():
                            render_item_card(
                                item_name=row["ITEM_NAME"],
                                price=float(row["PRICE"]),
                                class_code=row["FINAL_CLASS"],
                                add_key=f"menu_add_{row.name}",
                                restaurant_name=row["RESTAURANT_NAME"]
                            )
                        st.divider()
        else:
            st.info("Bu bölmədə əvvəl restoran seç.")

# =========================
# TAB 2 - BASKET
# =========================
with tab2:
    st.subheader("Səbət yarat")
    st.markdown(
        "<div class='page-subtitle'>Ya konkret məhsullar seç, ya da kateqoriya üzrə səbət qur. Sistem uyğun restoranları və ümumi qiyməti hesablayacaq.</div>",
        unsafe_allow_html=True,
    )

    basket_reset_map = {
        "basket_mode_radio": "Dəqiq seçim",
        "basket_restaurant_choice_select": "",
        "basket_min_total_input": "",
        "basket_max_total_input": "",
        "basket_top_n_number": 10,
    }
    for _, class_code in BASKET_CATEGORY_OPTIONS:
        basket_reset_map[f"basket_select_{class_code}"] = ""
        basket_reset_map[f"basket_count_{class_code}"] = 0

    top_left, top_right = st.columns([6, 2])
    with top_right:
        render_tab_reset_button("Hamısını sıfırla", basket_reset_map, "reset_basket_tab")

    basket_mode = st.radio(
        "Rejim",
        options=["Dəqiq seçim", "Kateqoriya üzrə say"],
        horizontal=True,
        key="basket_mode_radio"
    )

    if basket_mode == "Dəqiq seçim":
        st.markdown(
            "<div class='mode-box'><b>Dəqiq seçim</b><br><span class='small-muted'>Konkret məhsulları seç və hansı restoranda birlikdə toplana bildiyini gör.</span></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='mode-box'><b>Kateqoriya üzrə say</b><br><span class='small-muted'>Sadəcə neçə əsas yemək, içki və s. istədiyini göstər. Sistem uyğun səbətləri özü quracaq.</span></div>",
            unsafe_allow_html=True,
        )

    basket_restaurant_choice = render_clearable_selectbox(
        label="Restoran seç",
        options=all_restaurants,
        key="basket_restaurant_choice_select",
        placeholder_label="Restoran seç..."
    )

    basket_min_total, basket_max_total = render_price_range(
        "Ümumi səbət qiyməti",
        "basket_min_total_input",
        "basket_max_total_input"
    )

    basket_top_n = st.number_input(
        "Neçə variant göstərilsin?",
        min_value=1,
        value=10,
        step=1,
        key="basket_top_n_number"
    )

    if basket_restaurant_choice:
        basket_source_df = choice_df[choice_df["RESTAURANT_NAME"] == basket_restaurant_choice].copy()
    else:
        basket_source_df = choice_df.copy()

    if validate_min_max(basket_min_total, basket_max_total):
        if basket_mode == "Dəqiq seçim":
            basket_selected_items = {}
            cols = st.columns(2)

            for i, (label, class_code) in enumerate(BASKET_CATEGORY_OPTIONS):
                class_df = basket_source_df[basket_source_df["FINAL_CLASS"] == class_code].copy()
                options, display_map = get_item_options_for_df(class_df)

                with cols[i % 2]:
                    selected_value = render_clearable_selectbox(
                        label=label,
                        options=options,
                        key=f"basket_select_{class_code}",
                        placeholder_label=f"{label} seç...",
                        format_map=display_map
                    )
                    if selected_value:
                        basket_selected_items[class_code] = selected_value

            if st.button("Səbəti hesabla", key="basket_find_button_exact"):
                with st.spinner("Variantlar hesablanır..."):
                    if not basket_selected_items:
                        st.info("Ən azı bir kateqoriya üzrə məhsul seç.")
                    else:
                        if basket_restaurant_choice:
                            built = build_exact_basket_for_restaurant(
                                rest_df=basket_source_df,
                                selected_map=basket_selected_items
                            )
                            if built is None:
                                st.warning("Seçilmiş məhsullar bu restoranda birlikdə tapılmadı.")
                            else:
                                total = built["total_price"]
                                if basket_min_total is not None and total < basket_min_total:
                                    st.warning("Bu səbətin ümumi qiyməti minimum limitdən aşağıdır.")
                                elif basket_max_total is not None and total > basket_max_total:
                                    st.warning("Bu səbətin ümumi qiyməti maksimum limiti keçir.")
                                else:
                                    st.success("Səbət hesablandı.")
                                    render_basket_result_card(built, idx="fixed")
                        else:
                            rows = build_cross_restaurant_exact_baskets(
                                df=basket_source_df,
                                selected_map=basket_selected_items,
                                min_total=basket_min_total,
                                max_total=basket_max_total,
                                top_n=int(basket_top_n)
                            )
                            if not rows:
                                st.warning("Bu seçimi toplamaq üçün uyğun restoran tapılmadı.")
                            else:
                                st.success(f"{len(rows)} uyğun variant tapıldı.")
                                for idx, row in enumerate(rows):
                                    render_basket_result_card(row, idx=f"exact_{idx}")
                                    st.divider()

        else:
            count_values = {}
            cols = st.columns(2)

            for i, (label, class_code) in enumerate(BASKET_CATEGORY_OPTIONS):
                with cols[i % 2]:
                    c1, c2 = st.columns([18, 1])
                    with c1:
                        val = st.number_input(
                            f"{label} sayı",
                            min_value=0,
                            max_value=10,
                            value=0,
                            step=1,
                            key=f"basket_count_{class_code}"
                        )
                    with c2:
                        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                        st.button(
                            "×",
                            key=f"clear_basket_count_{class_code}",
                            on_click=clear_number_key,
                            args=(f"basket_count_{class_code}",),
                            help="Təmizlə"
                        )
                    count_values[class_code] = int(val)

            if st.button("Səbəti hesabla", key="basket_find_button_count"):
                with st.spinner("Variantlar hesablanır..."):
                    count_values = {k: v for k, v in count_values.items() if v > 0}

                    if not count_values:
                        st.info("Ən azı bir kateqoriya üzrə say seç.")
                    else:
                        rows = build_category_count_baskets(
                            df=basket_source_df,
                            category_counts=count_values,
                            min_total=basket_min_total,
                            max_total=basket_max_total,
                            top_n=int(basket_top_n)
                        )

                        if not rows:
                            st.warning("Bu tərkibdə uyğun səbət tapılmadı.")
                        else:
                            st.success(f"{len(rows)} variant hesablandı.")
                            for idx, row in enumerate(rows):
                                render_basket_result_card(row, idx=f"count_{idx}")
                                st.divider()

    st.markdown("## Cari səbət")

    if not st.session_state["basket_items"]:
        st.write("Səbət boşdur.")
    else:
        st.write(f"**Restoran:** {st.session_state['basket_restaurant']}")
        st.write(f"**Ümumi:** {basket_total():.2f} AZN")

        for i, item in enumerate(st.session_state["basket_items"]):
            c1, c2, c3 = st.columns([6, 2, 2])
            with c1:
                st.write(item["item_name"])
            with c2:
                st.write(f"{item['price']:.2f} AZN")
            with c3:
                if st.button("Sil", key=f"remove_{i}"):
                    st.session_state["basket_items"].pop(i)
                    st.rerun()

        if st.button("Səbəti təmizlə", key="basket_clear_button"):
            clear_basket()
            st.rerun()

# =========================
# TAB 3 - SEARCH
# =========================
with tab3:
    st.subheader("Bazarda axtar")
    st.markdown(
        "<div class='page-subtitle'>İstədiyin yeməyi və ya içkini axtar. Sistem ən uyğun məhsulları və uyğun restoranları göstərəcək.</div>",
        unsafe_allow_html=True,
    )

    search_reset_map = {
        "search_query_input": "",
        "search_item_select": "",
        "search_restaurants_multiselect": [],
        "search_classes_multiselect": [],
        "search_min_price_input": "",
        "search_max_price_input": "",
        "search_top_n_number": 30,
        "search_price_band_radio": "Hamısı",
    }

    top_left, top_right = st.columns([6, 2])
    with top_right:
        render_tab_reset_button("Hamısını sıfırla", search_reset_map, "reset_search_tab")

    c1, c2 = st.columns(2)

    with c1:
        search_query = render_clearable_text(
            "Nə axtarırsan?",
            key="search_query_input",
            placeholder="məs: toyuq, burger, plov, çay"
        )

        search_item_selected = render_clearable_selectbox(
            label="Məhsulu siyahıdan seç",
            options=global_item_options,
            key="search_item_select",
            placeholder_label="Məhsul seç...",
            format_map=global_item_display_map
        )

    with c2:
        search_classes = render_clearable_multiselect(
            "Kateqoriyalar",
            options=all_classes,
            key="search_classes_multiselect",
            format_map=class_format_map
        )

        search_restaurants = render_clearable_multiselect(
            "Restoranlar",
            options=all_restaurants,
            key="search_restaurants_multiselect"
        )

    st.markdown("#### Sürətli qiymət seçimi")
    selected_band_label = st.radio(
        "Qiymət bandı",
        options=[x[0] for x in SEARCH_PRICE_BANDS],
        horizontal=True,
        key="search_price_band_radio",
        label_visibility="collapsed"
    )

    band_map = {x[0]: (x[1], x[2]) for x in SEARCH_PRICE_BANDS}
    band_min, band_max = band_map[selected_band_label]

    search_min_price, search_max_price = render_price_range(
        "Qiymət",
        "search_min_price_input",
        "search_max_price_input"
    )

    if search_min_price is None and band_min is not None:
        search_min_price = band_min
    if search_max_price is None and band_max is not None:
        search_max_price = band_max

    search_top_n = st.number_input(
        "Neçə nəticə göstərilsin?",
        min_value=1,
        value=30,
        step=1,
        key="search_top_n_number"
    )

    if search_query.strip():
        suggestions = get_top_query_suggestions(choice_df, search_query, max_suggestions=8)
        if suggestions:
            st.caption("Oxşar axtarış variantları:")
            st.write(" • " + " • ".join(suggestions))

    if st.button("Axtar", key="search_market_button"):
        with st.spinner("Axtarış aparılır..."):
            if validate_min_max(search_min_price, search_max_price):
                results = search_market_items(
                    df=choice_df,
                    selected_item=search_item_selected,
                    query_text=search_query,
                    selected_restaurants=search_restaurants,
                    selected_classes=search_classes,
                    min_price=search_min_price,
                    max_price=search_max_price,
                    top_n=int(search_top_n)
                )

                if results.empty:
                    st.warning("Uyğun nəticə tapılmadı.")
                else:
                    summary = build_search_overview(results)
                    render_search_summary_boxes(summary)
                    st.caption(f"Ən çox uyğun mövqe olan restoran: {summary['top_restaurant_by_count']}")
                    st.divider()

                    st.markdown("## Ən uyğun məhsullar")
                    for _, row in results.iterrows():
                        st.markdown(
                            f"""
                            <div class="item-card">
                                <div class="item-title">{row["ITEM_NAME"]}</div>
                                <div class="item-meta">
                                    {row["RESTAURANT_NAME"]} · {get_category_label(row["FINAL_CLASS"])} · {float(row["PRICE"]):.2f} AZN
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        a1, a2 = st.columns([2, 2])
                        with a1:
                            if st.button("Səbətə əlavə et", key=f"search_add_{row.name}"):
                                add_to_basket(
                                    restaurant_name=row["RESTAURANT_NAME"],
                                    item_name=row["ITEM_NAME"],
                                    price=float(row["PRICE"]),
                                    final_class=row["FINAL_CLASS"]
                                )
                        with a2:
                            st.button(
                                "Bu restoranın menyusuna bax",
                                key=f"search_menu_jump_{row.name}",
                                on_click=set_widget_value,
                                args=("menu_restaurant_select", row["RESTAURANT_NAME"])
                            )

                    st.divider()
                    st.markdown("## Bu sorğu üçün uyğun restoranlar")

                    grouped = group_search_results_by_restaurant(
                        results_df=results,
                        top_restaurants=min(12, int(search_top_n)),
                        sample_items_per_restaurant=4
                    )

                    for idx, row in enumerate(grouped):
                        st.markdown(
                            f"""
                            <div class="restaurant-card">
                                <div class="item-title">{row['restaurant_name']}</div>
                                <div class="item-meta">
                                    {row['match_count']} uyğun mövqe · {row['min_price']:.2f} – {row['max_price']:.2f} AZN
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        st.write("Nümunə məhsullar:")
                        for sample in row["sample_items"]:
                            st.write(
                                f"- {sample['ITEM_NAME']} — {float(sample['PRICE']):.2f} AZN "
                                f"({get_category_label(sample['FINAL_CLASS'])})"
                            )

                        b1, b2 = st.columns([2, 2])
                        with b1:
                            st.button(
                                "Menyuya keç",
                                key=f"group_jump_menu_{idx}",
                                on_click=set_widget_value,
                                args=("menu_restaurant_select", row["restaurant_name"])
                            )
                        with b2:
                            st.button(
                                "Səbət üçün seç",
                                key=f"group_jump_basket_{idx}",
                                on_click=set_widget_value,
                                args=("basket_restaurant_choice_select", row["restaurant_name"])
                            )
                        st.divider()