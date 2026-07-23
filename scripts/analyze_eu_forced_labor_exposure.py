from pathlib import Path
import re
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"

EU_COUNTRIES = {
    "AUT": "Austria",
    "BEL": "Belgium",
    "BGR": "Bulgaria",
    "HRV": "Croatia",
    "CYP": "Cyprus",
    "CZE": "Czechia",
    "DNK": "Denmark",
    "EST": "Estonia",
    "FIN": "Finland",
    "FRA": "France",
    "DEU": "Germany",
    "GRC": "Greece",
    "HUN": "Hungary",
    "IRL": "Ireland",
    "ITA": "Italy",
    "LVA": "Latvia",
    "LTU": "Lithuania",
    "LUX": "Luxembourg",
    "MLT": "Malta",
    "NLD": "Netherlands",
    "POL": "Poland",
    "PRT": "Portugal",
    "ROU": "Romania",
    "SVK": "Slovakia",
    "SVN": "Slovenia",
    "ESP": "Spain",
    "SWE": "Sweden",
}


def normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()


def normalize_hs_code(value: object) -> str:
    """Preserve leading zeros and truncate to the first six digits."""
    if pd.isna(value):
        return ""
    digits = re.sub(r"\D", "", str(value))
    if not digits:
        return ""
    return digits[:6]


def build_country_lookup(path: Path) -> tuple[dict[int, str], dict[str, str]]:
    country_codes = pd.read_csv(path)
    country_codes["norm_name"] = country_codes["country_name"].apply(normalize_text)
    country_codes["norm_iso2"] = country_codes["country_iso2"].apply(normalize_text)
    country_codes["norm_iso3"] = country_codes["country_iso3"].apply(normalize_text)

    code_to_iso3 = {int(row.country_code): row.country_iso3 for row in country_codes.itertuples(index=False)}

    name_to_iso3 = {}
    for row in country_codes.itertuples(index=False):
        aliases = {
            str(row.country_name).strip(),
            str(row.country_iso2).strip(),
            str(row.country_iso3).strip(),
            normalize_text(row.country_name),
            normalize_text(row.country_iso2),
            normalize_text(row.country_iso3),
        }
        for alias in aliases:
            if alias:
                name_to_iso3[alias] = row.country_iso3

    explicit_aliases = {
        "bolivia": "BOL",
        "burma": "MMR",
        "democratic republic of the congo": "COD",
        "domincan republic": "DOM",
        "dominican republic": "DOM",
        "north korea": "PRK",
        "russia": "RUS",
        "taiwan": "TWN",
        "vietnam": "VNM",
    }
    name_to_iso3.update(explicit_aliases)

    return code_to_iso3, name_to_iso3


def load_forced_labor_goods(path: Path, name_to_iso3: dict[str, str]) -> pd.DataFrame:
    goods = pd.read_csv(path)
    goods = goods.loc[goods["Forced_Labor"].eq("X") | goods["Forced_Child_Labor"].eq("X")].copy()

    goods["country_norm"] = goods["Country"].apply(normalize_text)
    goods["country_iso3"] = goods["country_norm"].map(name_to_iso3)

    missing = goods[goods["country_iso3"].isna()][["Country"]].drop_duplicates()
    if not missing.empty:
        print("Countries without ISO3 mapping in 2024Goods.csv:")
        print(missing.to_string(index=False))

    return goods


def build_good_to_hs_codes(path: Path) -> dict[str, list[str]]:
    mapping = pd.read_csv(path)
    mapping = mapping.dropna(subset=["Good", "HTS_code_US"]).copy()
    mapping["good_norm"] = mapping["Good"].apply(normalize_text)
    mapping["hs6"] = mapping["HTS_code_US"].apply(normalize_hs_code)
    mapping = mapping.loc[mapping["hs6"].ne("")]

    good_to_hs = (
        mapping.groupby("good_norm")["hs6"]
        .agg(lambda s: sorted(set(s.tolist())))
        .to_dict()
    )
    return good_to_hs


def load_trade_data(path: Path) -> pd.DataFrame:
    trade = pd.read_csv(path, usecols=["t", "i", "j", "k", "v", "q"])
    trade = trade.loc[trade["t"].eq(2024)].copy()
    trade["k"] = trade["k"].astype(str).apply(normalize_hs_code)
    trade = trade.loc[trade["k"].ne("")].copy()
    return trade


def compute_exposure(
    trade: pd.DataFrame,
    forced_goods: pd.DataFrame,
    good_to_hs_codes: dict[str, list[str]],
    code_to_iso3: dict[int, str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    exploded = []
    for row in forced_goods.itertuples(index=False):
        hs_codes = good_to_hs_codes.get(normalize_text(row.Good), [])
        for hs_code in hs_codes:
            exploded.append(
                {
                    "origin_iso3": row.country_iso3,
                    "good": row.Good,
                    "hs_code": hs_code,
                }
            )

    if not exploded:
        raise ValueError("No forced-labor goods were matched to HS codes.")

    matched_products = pd.DataFrame(exploded).dropna(subset=["origin_iso3", "hs_code"])
    matched_products = matched_products.drop_duplicates(subset=["origin_iso3", "good", "hs_code"])

    trade = trade.copy()
    trade["exporter_iso3"] = trade["i"].map(code_to_iso3)
    trade["importer_iso3"] = trade["j"].map(code_to_iso3)
    trade = trade.loc[trade["exporter_iso3"].notna() & trade["importer_iso3"].notna()].copy()

    trade = trade.loc[trade["importer_iso3"].isin(EU_COUNTRIES)].copy()

    exposure_parts = []
    for _, match in matched_products.iterrows():
        origin_iso3 = match["origin_iso3"]
        hs_code = match["hs_code"]
        good = match["good"]
        subset = trade.loc[
            (trade["exporter_iso3"].eq(origin_iso3))
            & (trade["k"].astype(str).str.startswith(hs_code, na=False))
        ].copy()
        if subset.empty:
            continue
        subset["good"] = good
        subset["hs_code"] = hs_code
        exposure_parts.append(subset)

    if not exposure_parts:
        raise ValueError("No trade flows matched the forced-labor country/product pairs.")

    exposure = pd.concat(exposure_parts, ignore_index=True)
    exposure = exposure.rename(columns={"v": "value_thousand_usd", "q": "weight_metric_tons"})
    exposure = exposure[[
        "importer_iso3",
        "exporter_iso3",
        "good",
        "hs_code",
        "value_thousand_usd",
        "weight_metric_tons",
    ]]

    exposure = (
        exposure.groupby(["importer_iso3", "exporter_iso3", "good", "hs_code"], as_index=False)
        .agg(
            value_thousand_usd=("value_thousand_usd", "sum"),
            weight_metric_tons=("weight_metric_tons", "sum"),
        )
    )
    exposure["value_usd"] = exposure["value_thousand_usd"] * 1000

    exposure = exposure.sort_values(
        ["importer_iso3", "value_usd", "weight_metric_tons", "good", "exporter_iso3"],
        ascending=[True, False, False, True, True],
    ).reset_index(drop=True)

    summary = (
        exposure.groupby("importer_iso3", as_index=False)
        .agg(
            total_value_usd=("value_usd", "sum"),
            total_weight_metric_tons=("weight_metric_tons", "sum"),
        )
    )

    top_products = (
        exposure.groupby(["importer_iso3", "good"], as_index=False)
        .agg(
            value_usd=("value_usd", "sum"),
            weight_metric_tons=("weight_metric_tons", "sum"),
        )
    )
    top_products = (
        top_products.sort_values(
            ["importer_iso3", "value_usd", "weight_metric_tons", "good"],
            ascending=[True, False, False, True],
        )
        .drop_duplicates("importer_iso3")
        .rename(columns={"good": "top_good", "value_usd": "top_value_usd"})
    )

    summary = summary.merge(
        top_products[["importer_iso3", "top_good", "top_value_usd"]],
        on="importer_iso3",
        how="left",
    )

    return exposure, summary


def main() -> None:
    code_to_iso3, name_to_iso3 = build_country_lookup(DATA_DIR / "country_codes_V202601.csv")
    forced_goods = load_forced_labor_goods(DATA_DIR / "2024Goods.csv", name_to_iso3)
    good_to_hs_codes = build_good_to_hs_codes(DATA_DIR / "list_of_goods_hs_codes.csv")
    trade = load_trade_data(DATA_DIR / "BACI_HS22_Y2024_V202601.csv")

    exposure, summary = compute_exposure(trade, forced_goods, good_to_hs_codes, code_to_iso3)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    exposure.to_csv(OUTPUT_DIR / "eu_forced_labor_exposure_by_origin.csv", index=False)
    summary.to_csv(OUTPUT_DIR / "eu_forced_labor_exposure_summary.csv", index=False)

    print("Saved eu_forced_labor_exposure_by_origin.csv")
    print("Saved eu_forced_labor_exposure_summary.csv")
    print("\nEU importer summary:")
    print(summary.sort_values("importer_iso3").to_string(index=False))


if __name__ == "__main__":
    main()
