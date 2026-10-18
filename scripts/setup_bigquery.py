"""Load data/*.csv into BigQuery and (re)create the views in sql/."""
import sys
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from promo_intel.config import get_settings  # noqa: E402

F = bigquery.SchemaField
SCHEMAS = {
    "products": [F("product_id", "STRING"), F("name", "STRING"), F("category", "STRING"),
                 F("list_price", "FLOAT64"), F("unit_cost", "FLOAT64")],
    "promotions": [F("promo_id", "STRING"), F("promo_name", "STRING"), F("product_id", "STRING"),
                   F("discount_pct", "FLOAT64"), F("start_date", "DATE"), F("end_date", "DATE")],
    "sales": [F("order_id", "STRING"), F("order_date", "DATE"), F("product_id", "STRING"),
              F("quantity", "INT64"), F("unit_price", "FLOAT64"), F("discount_amount", "FLOAT64"),
              F("promo_id", "STRING")],
}


def load_tables(client: bigquery.Client, dataset_ref: str) -> None:
    for table, schema in SCHEMAS.items():
        df = pd.read_csv(ROOT / "data" / f"{table}.csv")
        for field in schema:
            if field.field_type == "STRING":
                df[field.name] = df[field.name].astype("string")
            elif field.field_type == "DATE":
                df[field.name] = pd.to_datetime(df[field.name]).dt.date
        config = bigquery.LoadJobConfig(schema=schema, write_disposition="WRITE_TRUNCATE")
        client.load_table_from_dataframe(df, f"{dataset_ref}.{table}", job_config=config).result()
        print(f"loaded {table}: {len(df)} rows")


def create_views(client: bigquery.Client, dataset_ref: str) -> None:
    for path in sorted((ROOT / "sql").glob("*.sql")):
        client.query(path.read_text().format(dataset=dataset_ref)).result()
        print(f"applied {path.name}")


def main() -> None:
    s = get_settings()
    client = bigquery.Client(project=s.project)
    dataset = bigquery.Dataset(s.dataset_ref)
    dataset.location = "US"
    client.create_dataset(dataset, exists_ok=True)
    load_tables(client, s.dataset_ref)
    create_views(client, s.dataset_ref)


if __name__ == "__main__":
    main()
