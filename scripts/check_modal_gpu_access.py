"""Probe which GPU types are allowed on the current Modal account."""

import modal

app = modal.App("test-account-gpus")


@app.function(timeout=60)
def test_cpu():
    return "CPU OK"


@app.function(gpu="T4", timeout=60)
def test_t4():
    return "T4 OK"


@app.function(gpu="A10G", timeout=60)
def test_a10g():
    return "A10G OK"


@app.function(gpu="L4", timeout=60)
def test_l4():
    return "L4 OK"


@app.function(gpu="A100", timeout=60)
def test_a100():
    return "A100 OK"


@app.local_entrypoint()
def main():
    print("Testing CPU...")
    print(test_cpu.remote())
