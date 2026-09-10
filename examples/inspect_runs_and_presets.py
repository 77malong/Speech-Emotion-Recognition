"""Direct-API 示例：Preset、Runtime 与已有 run 的领域资源读取。

传入实际 run 目录时才访问磁盘；checkpoint 与 prediction 内容不会被隐式加载。
"""

from __future__ import annotations

import argparse
import json

from ser_lib.config import get_experiment_preset_payload, list_experiment_preset_ids
from ser_lib.engine import (
    inspect_evaluation_prediction_file,
    inspect_evaluation_report,
    load_evaluation_run_info,
    load_training_history,
    load_training_run_info,
)
from ser_lib.runtime import get_runtime_metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-run")
    parser.add_argument("--evaluation-run")
    args = parser.parse_args()

    payload: dict[str, object] = {
        "presets": {
            preset_id: get_experiment_preset_payload(preset_id)
            for preset_id in list_experiment_preset_ids()
        },
        "runtime": get_runtime_metrics("cpu").to_dict(),
    }

    if args.training_run:
        payload["training_run"] = load_training_run_info(args.training_run).to_dict()
        payload["training_history"] = load_training_history(args.training_run).to_dict()
    if args.evaluation_run:
        run = load_evaluation_run_info(args.evaluation_run)
        payload["evaluation_run"] = run.to_dict()
        payload["evaluation_report"] = inspect_evaluation_report(args.evaluation_run).to_dict()
        payload["evaluation_predictions"] = inspect_evaluation_prediction_file(run).to_dict()

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
