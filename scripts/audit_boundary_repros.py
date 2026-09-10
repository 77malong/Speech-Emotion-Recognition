"""Independent numerical probes for the 2026-09-10 audit (CPU only)."""
import copy
import json
import torch
from ser_lib.data.types import SERBatch, TensorSpec
from ser_lib.models.cnn_models import CNNBaseline
from ser_lib.models.adapters.torch import TorchModelAdapter
from ser_lib.config.training import TrainerConfig
from ser_lib.engine.trainer import Trainer
from ser_lib.data.representations.acoustic import _PitchF0, _JitterShimmerHNR
from ser_lib.inference.streaming import _LinearResampler
from ser_lib.engine.config import load_experiment_config, build_experiment_components
from ser_lib.data.editor import DatasetEditor

torch.set_num_threads(1)
torch.manual_seed(123)

def batch(x, length=None):
    n = x.shape[0]
    lengths = {} if length is None else {'features': torch.tensor([length] * n)}
    masks = {} if length is None else {'features': torch.arange(x.shape[-1])[None, :].expand(n, -1) < length}
    return SERBatch({'features': x}, lengths, masks, torch.zeros(n, dtype=torch.long), [str(i) for i in range(n)], [{} for _ in range(n)])

result = {}
cnn = CNNBaseline(2, 2, hidden_dim=4, dropout=0).eval()
x = torch.randn(1, 2, 7)
with torch.no_grad():
    a = cnn(batch(x, 7)).logits
    b = cnn(batch(torch.nn.functional.pad(x, (0, 15)), 7)).logits
result['cnn_zero_padding_max_logit_difference'] = float((a-b).abs().max())

base = torch.nn.Linear(2, 2, bias=False)
initial = base.weight.detach().clone()
updates = []
for steps in (1, 4):
    module = copy.deepcopy(base)
    model = TorchModelAdapter.wrap(module, required_inputs={'features': TensorSpec(layout='D', feature_dim=2)}, input_map={'input': 'inputs.features'}, num_classes=2)
    trainer = Trainer(model, TrainerConfig(gradient_accumulation_steps=steps), optimizer=torch.optim.SGD(model.parameters(), lr=0.1))
    trainer.train_epoch([batch(torch.tensor([[1., 2.]]))], epoch=1)
    updates.append(float((module.weight.detach()-initial).norm()))
result['one_batch_update_norm_accumulation_1_vs_4'] = updates

wave = torch.sin(2*torch.pi*200*torch.arange(16000)/16000)[None, :]
try:
    pitch = _PitchF0(16000, 256).compute(wave)
    result['f0_one_second_200hz'] = {'shape': list(pitch.shape), 'mean': float(pitch.mean())}
except Exception as exc:
    result['f0_one_second_200hz'] = type(exc).__name__ + ': ' + str(exc)
result['quality_vector'] = _JitterShimmerHNR().compute(wave, torch.tensor([190., 200., 210.])).tolist()
high = torch.sin(2*torch.pi*12000*torch.arange(48000)/48000)
low = _LinearResampler(48000, 16000).push(high, final=True)
result['12khz_downsampled_to_16khz_rms'] = float(low.square().mean().sqrt())
config = load_experiment_config('tests/fixtures/release_compat/experiment_v1.yaml')
raw_config = config.model_dump()
raw_config['data']['representation']['params']['n_mels'] = 16
raw_config['model']['params']['feature_dim'] = 16
config = type(config).model_validate(raw_config)
states = []
for ambient_seed in (111, 222):
    torch.manual_seed(ambient_seed)
    components = build_experiment_components(config)
    Trainer.from_experiment(components.model, config)
    states.append(next(components.model.parameters()).detach().clone())
result['same_config_seed_initial_weight_difference'] = float((states[0]-states[1]).abs().max())
editor = DatasetEditor('tests/fixtures/release_compat/dataset_v1.yaml')
record = editor.snapshot().records[0]
try:
    editor.update_record(record.uid, speaker_id='audit-change', split='')
except Exception as exc:
    result['editor_failed_update'] = {'error': type(exc).__name__, 'dirty': editor.dirty, 'speaker_after_error': editor.snapshot().records[0].speaker_id}
print(json.dumps(result, indent=2))
