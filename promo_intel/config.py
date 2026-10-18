"""Runtime settings read from environment variables."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    project: str | None
    location: str
    dataset: str
    gemini_model: str
    use_fixtures: bool

    @property
    def dataset_ref(self) -> str:
        if not self.project:
            raise RuntimeError("GCP_PROJECT is not set (or set USE_FIXTURES=1)")
        return f"{self.project}.{self.dataset}"


def get_settings() -> Settings:
    return Settings(
        project=os.environ.get("GCP_PROJECT"),
        location=os.environ.get("GCP_LOCATION", "us-central1"),
        dataset=os.environ.get("BQ_DATASET", "promo_intel"),
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        use_fixtures=os.environ.get("USE_FIXTURES", "0") == "1",
    )
