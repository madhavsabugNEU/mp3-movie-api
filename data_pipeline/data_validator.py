# src/data_validator.py
import logging
import pandas as pd


logger = logging.getLogger(__name__)


def validate_dataframe(df, required_columns, numeric_columns):
    """Validate the DataFrame and return valid data.

    required_columns: a list of column names that must exist.
    numeric_columns: a list of column names whose values should be numeric.
    """
    rows_before = len(df)

    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        logger.error("Missing required columns: %s", missing)
        raise ValueError(f"Missing required columns: {missing}")
    df = df.copy()

    for col in numeric_columns:
        invalid_rows = []
        for i, value in df[col].items():
            if pd.notna(value):
                try:
                    float(value)
                except ValueError:
                    logger.warning("Invalid numeric value in %s at row %s: %r", col, i, value)
                    invalid_rows.append(i)
        if invalid_rows:
            df = df.drop(index=invalid_rows)
            logger.warning("Removed %d rows with invalid numeric values in %s", len(invalid_rows), col)

        df[col] = pd.to_numeric(df[col])

    logger.debug("Validation: %d -> %d rows", rows_before, len(df))
    return df