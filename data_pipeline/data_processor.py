# data_processor.py
import logging
import pandas as pd

logger = logging.getLogger(__name__)

def remove_duplicates(df):
    """Remove duplicate rows."""
    rows_before = len(df)
    results = df.drop_duplicates()
    logger.debug("remove duplicates: %d -> %d rows", rows_before, len(results))
    return results

def handle_missing(df, axis="rows"):
    """Drop rows or columns containing missing values."""
    if axis == "rows":
        rows_before = len(df)
        result = df.dropna(axis=0)
        logger.debug("handle_missing: %d -> %d rows", rows_before, len(result))
    elif axis == "columns":
        cols_before = df.shape[1]
        result = df.dropna(axis=1)
        logger.debug("handle_missing %d -> %d columns", cols_before, result.shape[1])
    else:
        logger.error("Unsupported axis: %s", axis)
        raise ValueError(f"Unsupported axis: {axis}")
    return result

def remove_outliers(df, columns, method, threshold):
    """Remove outliers from the specified numeric columns."""
    if method not in ("iqr", "zscore"):
        logger.error("Unsupported outlier method: %s", method)
        raise ValueError(f"Unsupported outlier method: {method}")
    logger.debug("remove_outliers: method=%s, threshold=%s", method, threshold)
    result = df

    for col in columns:
        if col not in result.columns:
            logger.warning("Column not found: %s", col)
            continue
        if not pd.api.types.is_numeric_dtype(result[col]):
            logger.warning("Column is not numeric: %s", col)
            continue

        series = result[col]
        rows_before = len(result)

        if method == "iqr":
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - threshold * iqr
            upper = q3 + threshold * iqr
            is_outlier = (series < lower) | (series > upper)
            result = result[~is_outlier]
            logger.debug("%s: lower=%s, upper=%s, removed=%d", col,lower, upper, rows_before - len(result))
        else:
            z_scores = (series - series.mean())/ series.std()
            is_outlier = z_scores.abs() > threshold
            result = result[~is_outlier]
            logger.debug("%s: zscore threshold=%s, removed=%d", col, threshold, rows_before - len(result))
    return result 


def process_data(df, config):
    """Apply the processing steps enabled in the configuration."""
    processing = config["processing"]

    if processing.get("remove_duplicates"):
        df = remove_duplicates(df)

    missing = processing.get("missing", {})
    if missing.get("enabled"):
        df = handle_missing(df, axis=missing["axis"])

    outliers = processing.get("outliers", {})
    if outliers.get("enabled"):
        df = remove_outliers(
            df,
            columns=outliers["columns"],
            method=outliers["method"],
            threshold=outliers["threshold"],
        )
    return df


def create_cleaning_report(df_before, df_after):
    """Return a dictionary summarizing the cleaning results."""
    return {
        "rows_before": len(df_before),
        "rows_after": len(df_after),
        "rows_removed": len(df_before) - len(df_after),
        "columns_before": df_before.shape[1],
        "columns_after": df_after.shape[1],
        "columns_removed": df_before.shape[1] - df_after.shape[1],
    }