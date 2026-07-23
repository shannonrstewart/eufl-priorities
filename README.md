# EU Forced Labor Regulation Exposure Analysis

This repository estimates the likely exposure of EU imports to forced labor using the U.S. Department of Labor (DoL) List of Goods as a placeholder while the EU Risk Database is not yet available.

## Purpose

The goal is to surface the likely impacts of the EU Forced Labor Regulation by combining:

- the DoL List of Goods and origin countries from the forced-labor goods list,
- HS product codes from the goods-to-HS mapping file,
- BACI trade-flow data for 2024,
- and EU importer countries and ISO3 country codes.

The analysis identifies which goods and origin countries are most likely to matter for each EU Competent Authority by estimating import exposure by value and weight.

## What the analysis does

1. Reads the forced-labor goods list and keeps rows flagged as forced labor or forced child labor.
2. Maps each listed good to one or more HS codes using the goods-to-HS mapping file.
3. Treats shorter HS codes as prefix matches, so a code like 2205 covers deeper subcodes such as 220500, 220510, and 220590.
4. Joins those product-country pairs to BACI trade flows for 2024.
5. Aggregates the results to create:
   - a detailed row-level file showing importer, exporter, good, HS code, value, and weight;
   - a country-level summary showing total import value, total weight, and the top product by value for each EU importer.

## Repository structure

- data/
  - source files used by the analysis, including the forced-labor goods list, HS-code mapping files, country codes, and BACI trade data
- scripts/
  - analysis code, including the main Python script and the runner
- output/
  - generated CSV outputs from the analysis
- README.md
  - overview of the project and usage instructions

## How to run

Install dependencies:

```bash
pip install -r requirements.txt
```

Then run:

```bash
python3 scripts/run_analysis.py
```

This will create the output files in the output/ directory.

## Output files

- output/eu_forced_labor_exposure_by_origin.csv
  - one row per EU importer, exporter, product, and HS-code family
- output/eu_forced_labor_exposure_summary.csv
  - one row per EU importer with total value, total weight, and the top product by value

## Notes

- The DoL List of Goods is being used as a provisional proxy until the EU Risk Database becomes available.
- Country names are normalized to ISO3 codes where possible using the supplied country-code lookup.
- Some country names in the source data may require additional manual mapping if new lists are added.

## Suggested next steps

- Replace the placeholder goods list with the official EU Risk Database once it is available.
- Add a notebook or simple dashboard for exploring the output by product, country, or EU authority.
- Document the mapping assumptions for goods that are broad or ambiguous.
