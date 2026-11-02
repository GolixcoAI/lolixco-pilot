"""Test adapter reload and multimodal inference on NVIDIA H100 GPU."""

from pathlib import Path

import modal

app = modal.App("test-h100-adapter-infer")

checkpoint_volume = modal.Volume.from_name(
    "lolixcopilot-checkpoints", create_if_missing=False
)

image = modal.Image.from_registry("axolotlai/axolotl:0.19.0-py3.12-cu130-2.12.1").env(
    {"PATH": "/workspace/axolotl-venv/bin:/usr/local/bin:/usr/bin:/bin"}
)


@app.function(
    image=image,
    gpu="H100",
    timeout=600,
    volumes={"/checkpoints": checkpoint_volume},
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
def test_infer():
    import torch
    from peft import PeftModel
    from PIL import Image
    from transformers import (
        AutoModelForImageTextToText,
        AutoProcessor,
        AutoTokenizer,
        BitsAndBytesConfig,
    )

    adapter_path = Path("/checkpoints/training-runs/smoke_qlora_step2/checkpoint-2")
    if not adapter_path.exists():
        adapter_path = Path("/checkpoints/training-runs/smoke_qlora_step2")
    if not adapter_path.exists():
        raise FileNotFoundError(f"Checkpoint directory {adapter_path} not found.")

    local_weights = Path("/checkpoints/muse-glimmer-30b")
    if not local_weights.is_dir():
        raise FileNotFoundError(f"Base model directory {local_weights} not found.")

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
        llm_int8_skip_modules=[
            "model.vision_tower",
            "vision_tower",
            "model.multi_modal_projector",
            "multi_modal_projector",
        ],
    )

    print("Loading base model in 4-bit with BitsAndBytes (skipping vision_tower)...")
    model = AutoModelForImageTextToText.from_pretrained(
        str(local_weights),
        quantization_config=bnb_config,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        local_files_only=True,
        trust_remote_code=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(
        str(local_weights), local_files_only=True, trust_remote_code=True
    )
    processor = AutoProcessor.from_pretrained(
        str(local_weights), local_files_only=True, trust_remote_code=True
    )

    print(f"Reloading QLoRA adapter from {adapter_path}...")
    peft_model = PeftModel.from_pretrained(model, str(adapter_path))
    peft_model.eval()

    smoke_images = sorted(Path("/checkpoints/smoke_dataset/images").glob("*.png"))
    if not smoke_images:
        raise FileNotFoundError("No genuine Docmatix document images found.")
    test_img = Image.open(smoke_images[0]).convert("RGB")

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": "What is the primary topic of this document?"},
            ],
        }
    ]
    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = processor(text=[prompt], images=[[test_img]], return_tensors="pt")
    inputs = {
        k: (v.to(torch.bfloat16) if v.is_floating_point() else v).to("cuda")
        if isinstance(v, torch.Tensor)
        else v
        for k, v in inputs.items()
    }

    print("Generating tokens with reloaded QLoRA adapter...")
    with torch.no_grad():
        output_ids = peft_model.generate(**inputs, max_new_tokens=64, do_sample=False)

    prompt_len = inputs["input_ids"].shape[1]
    generated_text = tokenizer.decode(
        output_ids[0][prompt_len:], skip_special_tokens=True
    )

    return {
        "status": "success",
        "adapter_path": str(adapter_path),
        "generated_text": generated_text.strip(),
    }


@app.local_entrypoint()
def main():
    print("Testing adapter reload and inference on H100...")
    res = test_infer.remote()
    print("\nInference Result:")
    for k, v in res.items():
        print(f"  {k}: {v}")
