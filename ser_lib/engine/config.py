"""实验运行时组件构建与配置文件加载兼容入口。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ser_lib.config.experiment import ExperimentConfig
from ser_lib.config.loader import load_versioned_config
from ser_lib.config.model import ModelConfig
from ser_lib.config.training import ObservabilityConfig, TrainerConfig
from ser_lib.engine._seed import seed_experiment_rng

if TYPE_CHECKING:
    from ser_lib.data.audio import AudioLoader
    from ser_lib.data.collate import SERCollator
    from ser_lib.data.pipeline import SamplePipeline
    from ser_lib.models.base import SERModel


@dataclass(frozen=True, slots=True)
class ExperimentComponents:
    """通过完整预检后可直接交给训练代码的运行时组件。"""

    model: "SERModel"
    audio_loader: "AudioLoader"
    pipeline: "SamplePipeline"
    collator: "SERCollator"


def build_experiment_components(
    config: ExperimentConfig,
    *,
    train: bool = True,
) -> ExperimentComponents:
    """构建实验组件，并在读取训练数据前完成全部静态兼容性检查。"""
    from ser_lib.data.collate import build_collator
    from ser_lib.data.pipeline import build_components
    from ser_lib.engine.compatibility import validate_compatibility
    from ser_lib.models.registry import model_registry

    # ExperimentConfig owns reproducibility for components it constructs.  This must
    # happen before model/pipeline creation so ambient process RNG state cannot affect
    # model initialization or stochastic training transforms.
    seed_experiment_rng(config.trainer.seed, deterministic=config.trainer.deterministic)
    model_params = model_registry.validate_config(config.model.type, config.model.params)
    model = model_registry.create(config.model.type, **model_params)
    audio_loader, pipeline = build_components(config.data, train=train)
    validate_compatibility(
        pipeline.output_specs,
        model.model_spec,
        config.data.batching,
        num_classes=config.data.num_classes,
        sample_rate=config.data.audio.target_sample_rate,
    )
    collator = build_collator(pipeline.output_specs, config.data.batching)
    return ExperimentComponents(model, audio_loader, pipeline, collator)


def load_experiment_config(path: Path | str) -> ExperimentConfig:
    """读取时迁移到当前 schema v1；相对输出路径基于配置文件目录。"""
    config = load_versioned_config(
        path,
        ExperimentConfig,
        supported_versions={1},
        schema_domain="experiment_config",
        target_version=1,
    )
    source = Path(path).expanduser().resolve()
    updates: dict[str, Any] = {}
    if not config.output_dir.is_absolute():
        updates["output_dir"] = (source.parent / config.output_dir).resolve()
    if (
        config.trainer.checkpoint_dir is not None
        and not config.trainer.checkpoint_dir.is_absolute()
    ):
        updates["trainer"] = config.trainer.model_copy(
            update={
                "checkpoint_dir": (source.parent / config.trainer.checkpoint_dir).resolve()
            }
        )
    if not config.data.manifest.is_absolute():
        updates["data"] = config.data.model_copy(
            update={"manifest": (source.parent / config.data.manifest).resolve()}
        )
    return config.model_copy(update=updates)


__all__ = [
    "ModelConfig",
    "ObservabilityConfig",
    "TrainerConfig",
    "ExperimentConfig",
    "ExperimentComponents",
    "load_experiment_config",
    "build_experiment_components",
]
