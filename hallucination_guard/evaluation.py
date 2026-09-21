"""Evaluate completed predictions against a separately supplied answer key.

This module does not import the detector or load files. ``type_match_rate`` is
coverage of the answer key's single primary label among positive ground-truth
samples, including missed detections; it is not multilabel classification
accuracy and does not penalize extra predicted labels.
"""

from typing import Any


GROUND_TRUTH_TYPE_MAP = {
    "政策编造": "政策与优惠",
    "政策偏差": "政策与优惠",
    "优惠编造": "政策与优惠",
    "参数编造": "产品参数",
    "信息编造": "事实信息",
    "能力越界": "能力越界",
    "安全误导": "安全误导",
    "信息遗漏": "误导性遗漏",
}


def _index_records(records: list[dict], label: str) -> dict[str, dict]:
    if not isinstance(records, list):
        raise ValueError(f"{label}必须是列表")
    if not records:
        raise ValueError(f"{label}必须为非空列表")
    indexed = {}
    for position, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"{label}[{position}]必须是对象")
        sample_id = record.get("id")
        if not isinstance(sample_id, str) or not sample_id.strip():
            raise ValueError(f"{label}[{position}]缺少有效字符串 id")
        if sample_id in indexed:
            raise ValueError(f"{label}包含重复 id: {sample_id}")
        if type(record.get("is_hallucination")) is not bool:
            raise ValueError(f"{label}[{sample_id}].is_hallucination 必须是 bool")
        indexed[sample_id] = record
    return indexed


def _ratio(numerator: int, denominator: int) -> float | None:
    """Preserve undefined metrics rather than claiming a measured zero."""
    return numerator / denominator if denominator else None


def evaluate(predictions: list[dict], ground_truth: list[dict]) -> dict[str, Any]:
    """Return binary metrics and auditable rows matched by exact sample id.

    Rows and error-id lists follow ground-truth order. Invalid/partial inputs
    raise ValueError instead of quietly changing the evaluation denominator.
    All rates are fractions in [0, 1], or None when the denominator is zero.
    """
    prediction_index = _index_records(predictions, "预测结果")
    truth_index = _index_records(ground_truth, "人工标注")
    missing = sorted(truth_index.keys() - prediction_index.keys())
    extra = sorted(prediction_index.keys() - truth_index.keys())
    if missing or extra:
        raise ValueError(f"预测 id 与人工标注不一致；缺少: {missing}；多余: {extra}")

    rows = []
    counts = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    matched_types = 0
    for sample_id, target in truth_index.items():
        prediction = prediction_index[sample_id]
        predicted_types = prediction.get("types")
        if not isinstance(predicted_types, list) or any(
            not isinstance(kind, str) or not kind.strip() for kind in predicted_types
        ):
            raise ValueError(f"预测结果[{sample_id}].types 必须是非空字符串组成的列表")
        actual = target["is_hallucination"]
        predicted = prediction["is_hallucination"]
        source_type = target.get("hallucination_type")
        if actual:
            if not isinstance(source_type, str) or source_type not in GROUND_TRUTH_TYPE_MAP:
                raise ValueError(f"人工标注[{sample_id}]包含未知幻觉类型: {source_type!r}")
            expected_type = GROUND_TRUTH_TYPE_MAP[source_type]
        else:
            if source_type not in (None, "", "无"):
                raise ValueError(f"人工标注[{sample_id}]为正常回复，却设置了幻觉类型")
            expected_type = None
        detail = target.get("detail")
        if not isinstance(detail, str):
            raise ValueError(f"人工标注[{sample_id}].detail 必须是字符串")

        if actual:
            outcome = "TP" if predicted else "FN"
            type_match = predicted and expected_type in predicted_types
            matched_types += int(type_match)
        else:
            outcome = "FP" if predicted else "TN"
            type_match = None
        counts[outcome.lower()] += 1
        rows.append({
            "id": sample_id,
            "predicted": predicted,
            "actual": actual,
            "outcome": outcome,
            "predicted_types": list(predicted_types),
            "expected_type": expected_type,
            "type_match": type_match,
            "detail": detail,
        })

    tp, tn, fp, fn = (counts[name] for name in ("tp", "tn", "fp", "fn"))
    return {
        "total": len(rows),
        **counts,
        "precision": _ratio(tp, tp + fp),
        "recall": _ratio(tp, tp + fn),
        "f1": _ratio(2 * tp, 2 * tp + fp + fn),
        "accuracy": _ratio(tp + tn, len(rows)),
        "false_positive_rate": _ratio(fp, fp + tn),
        "false_negative_rate": _ratio(fn, fn + tp),
        "false_positive_ids": [row["id"] for row in rows if row["outcome"] == "FP"],
        "false_negative_ids": [row["id"] for row in rows if row["outcome"] == "FN"],
        "type_match_rate": _ratio(matched_types, tp + fn),
        "rows": rows,
    }
