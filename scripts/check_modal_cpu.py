"""Test pure CPU function on Modal to inspect transformers muse_glimmer classes."""

import modal

app = modal.App("probe-muse-glimmer-classes")

image = modal.Image.from_registry("axolotlai/axolotl:0.19.0-py3.12-cu130-2.12.1").env(
    {"PATH": "/workspace/axolotl-venv/bin:/usr/local/bin:/usr/bin:/bin"}
)


checkpoint_volume = modal.Volume.from_name(
    "lolixcopilot-checkpoints", create_if_missing=False
)


@app.function(
    image=image,
    timeout=60,
    volumes={"/checkpoints": checkpoint_volume},
)
def inspect_module_names():
    from pathlib import Path

    import transformers
    from transformers.models.muse_glimmer import MuseGlimmerForConditionalGeneration

    local_weights = Path("/checkpoints/muse-glimmer-30b")
    config = transformers.AutoConfig.from_pretrained(
        str(local_weights), local_files_only=True
    )

    # Instantiate with meta device (zero memory, instant)
    import torch

    with torch.device("meta"):
        meta_model = MuseGlimmerForConditionalGeneration(config)
        module_names = [name for name, _ in meta_model.named_modules()]

    vision_modules = [
        m for m in module_names if "vision" in m or "ln_pre" in m or "patch" in m
    ]
    projector_modules = [m for m in module_names if "projector" in m]

    return {
        "vision_modules": vision_modules[:20],
        "projector_modules": projector_modules[:20],
    }


@app.local_entrypoint()
def main():
    print("Inspecting module names on Modal CPU...")
    res = inspect_module_names.remote()
    import pprint

    pprint.pprint(res)
