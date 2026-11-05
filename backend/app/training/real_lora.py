"""Concrete LoRA training hook (Phase 31).

Runs a short causal-LM LoRA fine-tune when peft/transformers/torch are installed.
Falls back to a tiny public model when the configured base is unavailable.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TINY_FALLBACK = "sshleifer/tiny-gpt2"


def run_real_lora_train(
    *,
    specialty: str,
    dataset_path: Path,
    out_dir: Path,
    base_model: str,
    rank: int = 8,
    max_steps: int = 30,
    tiny_fallback: bool = True,
) -> dict[str, Any]:
    import importlib.util

    missing = [
        name
        for name in ("torch", "transformers", "peft", "datasets")
        if importlib.util.find_spec(name) is None
    ]
    if missing:
        raise RuntimeError(f"missing packages for real LoRA: {', '.join(missing)}")

    import torch
    from datasets import Dataset
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    if not dataset_path.exists():
        raise FileNotFoundError(f"dataset missing: {dataset_path}")

    rows: list[dict[str, str]] = []
    for line in dataset_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        prompt = str(obj.get("prompt") or obj.get("input") or obj.get("instruction") or "")
        completion = str(obj.get("completion") or obj.get("output") or obj.get("response") or "")
        # Distillation corpora use OpenAI-style messages[]
        messages = obj.get("messages")
        if isinstance(messages, list) and messages:
            system_bits: list[str] = []
            user_bits: list[str] = []
            assistant_bits: list[str] = []
            for m in messages:
                if not isinstance(m, dict):
                    continue
                role = str(m.get("role") or "")
                content = str(m.get("content") or "").strip()
                if not content:
                    continue
                if role == "system":
                    system_bits.append(content)
                elif role == "user":
                    user_bits.append(content)
                elif role == "assistant":
                    assistant_bits.append(content)
            if user_bits and not prompt:
                prompt = "\n\n".join(user_bits)
            if system_bits and prompt:
                prompt = "System:\n" + "\n\n".join(system_bits) + "\n\nUser:\n" + prompt
            if assistant_bits and not completion:
                completion = "\n\n".join(assistant_bits)
        if not prompt and not completion:
            continue
        text = f"### Instruction:\n{prompt}\n\n### Response:\n{completion}".strip()
        if text:
            rows.append({"text": text})
    if len(rows) < 2:
        raise RuntimeError(f"need >=2 parseable JSONL rows, have {len(rows)}")

    chosen = (base_model or "").strip() or TINY_FALLBACK
    load_error: str | None = None
    tokenizer = None
    model = None
    for candidate in ([chosen, TINY_FALLBACK] if tiny_fallback and chosen != TINY_FALLBACK else [chosen]):
        try:
            tokenizer = AutoTokenizer.from_pretrained(candidate)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            model = AutoModelForCausalLM.from_pretrained(candidate)
            chosen = candidate
            break
        except Exception as exc:  # noqa: BLE001
            load_error = str(exc)
            tokenizer = None
            model = None
    if model is None or tokenizer is None:
        raise RuntimeError(f"could not load base model ({base_model}): {load_error}")

    # Prefer common decoder modules; fall back to all Linear names if needed
    target_modules = ["c_attn", "q_proj", "v_proj", "k_proj", "o_proj"]
    lora = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=int(rank),
        lora_alpha=max(16, int(rank) * 2),
        lora_dropout=0.05,
        target_modules=target_modules,
        bias="none",
    )
    try:
        model = get_peft_model(model, lora)
    except ValueError:
        # tiny-gpt2 / odd arch — let peft pick Linear modules
        lora = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=int(rank),
            lora_alpha=max(16, int(rank) * 2),
            lora_dropout=0.05,
            bias="none",
        )
        model = get_peft_model(model, lora)

    ds = Dataset.from_list(rows)

    def _tok(batch: dict[str, list[str]]) -> dict[str, Any]:
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=256,
            padding="max_length",
        )

    tokenized = ds.map(_tok, batched=True, remove_columns=["text"])
    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
    steps = max(1, int(max_steps))
    train_dir = out_dir / "hf-run"
    train_dir.mkdir(parents=True, exist_ok=True)
    args = TrainingArguments(
        output_dir=str(train_dir),
        per_device_train_batch_size=1,
        num_train_epochs=1,
        max_steps=steps,
        logging_steps=max(1, steps // 5),
        save_steps=steps,
        save_total_limit=1,
        report_to=[],
        learning_rate=2e-4,
        fp16=bool(torch.cuda.is_available()),
        remove_unused_columns=False,
    )
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=tokenized,
        data_collator=collator,
    )
    train_out = trainer.train()
    model.save_pretrained(str(out_dir))
    tokenizer.save_pretrained(str(out_dir))
    (out_dir / "adapter_config.json").write_text(
        json.dumps(
            {
                "peft_type": "LORA",
                "r": int(rank),
                "evolve_placeholder": False,
                "base_model": chosen,
                "specialty": specialty,
                "trained_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    cuda = bool(torch.cuda.is_available())
    return {
        "gpu_training": cuda,
        "real_train": True,
        "status": "trained",
        "base_model_used": chosen,
        "requested_base": base_model,
        "cuda": cuda,
        "device": torch.cuda.get_device_name(0) if cuda else "cpu",
        "max_steps": steps,
        "train_loss": float(getattr(train_out, "training_loss", 0.0) or 0.0),
        "examples_used": len(rows),
        "note": (
            "Real LoRA adapter weights written; promote still requires eval gates."
            + ("" if cuda else " Ran on CPU (install CUDA torch wheel for GPU).")
        ),
    }
