"""Direct-API 示例：Preset、Runtime 与已有 run 的轻量详情读取。

传入实际 run 目录时才访问磁盘；列表/详情接口不会隐式加载 checkpoint 权重，
Evaluation detail 也不会整文件读取 predictions.jsonl。
"""

from __future__ import annotations

import argparse
import json

from ser_lib.engine import (
    inspect_evaluation_run_detail,
    inspect_training_run_detail,
    list_experiment_presets,
)
from ser_lib.runtime import get_runtime_metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-run")
    parser.add_argument("--evaluation-run")
    args = parser.parse_args()

    presets = list_experiment_presets()
    runtime = get_runtime_metrics("cpu")
    payload: dict[str, object] = {
        "presets": presets.to_dict(),
        "runtime": runtime.to_dict(),
    }

    if args.training_run:
        payload["training_run"] = inspect_training_run_detail(args.training_run).to_dict()
    if args.evaluation_run:
        payload["evaluation_run"] = inspect_evaluation_run_detail(args.evaluation_run).to_dict()

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
