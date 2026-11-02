"""Test pure CPU function on Modal."""

import modal

app = modal.App("test-account-cpu")


@app.function(timeout=60)
def test_cpu():
    import os

    return {"status": "ok", "env": os.environ.get("MODAL_ENVIRONMENT", "default")}


@app.local_entrypoint()
def main():
    print("Testing CPU...")
    res = test_cpu.remote()
    print("CPU result:", res)
