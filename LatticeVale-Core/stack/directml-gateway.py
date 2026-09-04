#!/usr/bin/env python3
"""LatticeVale DirectML/OpenAI-compatible local text gateway.

This process deliberately runs on the WSL host instead of in Docker so
``torch-directml`` can use WSL's DirectML device path without making the
container stack depend on GPU-device plumbing.  It exposes only the Docker
host-gateway interface and routes text generation to DirectML when healthy.
If DirectML/model execution fails, the same request is retried through the
already-selected Ollama backend.  Honcho embeddings bypass this gateway and
continue using Ollama directly so the existing 1536-dimension vector store is
not changed.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

VERSION = "14.5.42"
MAX_BODY_BYTES = 2 * 1024 * 1024
MODEL_ID = os.environ.get("LATTICEVALE_DIRECTML_MODEL", "Qwen/Qwen2.5-1.5B-Instruct").strip()
FALLBACK_MODEL = os.environ.get("LATTICEVALE_OLLAMA_TEXT_MODEL", "qwen3.5:4b").strip()
OLLAMA_BACKEND = os.environ.get("LATTICEVALE_OLLAMA_BACKEND", "managed").strip()
STACK_DIR = Path(os.environ.get("LATTICEVALE_STACK_DIR", os.getcwd())).resolve()
HF_HOME = Path(os.environ.get("HF_HOME", str(STACK_DIR / "data" / "directml" / "hf-cache"))).resolve()
MAX_CONTEXT = max(1024, min(int(os.environ.get("LATTICEVALE_DIRECTML_CONTEXT", "8192")), 32768))
VRAM_LIMIT_PCT = max(5, min(int(os.environ.get("LATTICEVALE_DIRECTML_VRAM_LIMIT_PCT", "75")), 85))
DEFAULT_MAX_NEW = max(32, min(int(os.environ.get("LATTICEVALE_DIRECTML_MAX_NEW_TOKENS", "512")), 2048))
IDLE_UNLOAD_SECONDS = max(60, min(int(os.environ.get("LATTICEVALE_DIRECTML_IDLE_UNLOAD_SECONDS", "300")), 3600))
FAILURE_COOLDOWN_SECONDS = max(15, min(int(os.environ.get("LATTICEVALE_DIRECTML_FAILURE_COOLDOWN_SECONDS", "60")), 600))
NATIVE_FALLBACK_URL = os.environ.get("LATTICEVALE_NATIVE_OLLAMA_URL", "").rstrip("/")
REQUESTED_ADAPTER_NAME = os.environ.get("LATTICEVALE_DIRECTML_ADAPTER_NAME", "").strip()
REQUESTED_GPU_VENDOR = os.environ.get("LATTICEVALE_DIRECTML_GPU_VENDOR", "").strip().lower()
FORCE_FALLBACK = os.environ.get("LATTICEVALE_DIRECTML_FORCE_FALLBACK", "0").strip().lower() in {"1", "true", "yes", "on"}

os.environ.setdefault("HF_HOME", str(HF_HOME))
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", str(max(1, min(4, (os.cpu_count() or 2) // 2))))
os.environ.setdefault("MKL_NUM_THREADS", os.environ["OMP_NUM_THREADS"])

MODEL_LOCK = threading.RLock()
INFERENCE_LOCK = threading.Lock()  # one GPU generation at a time: bounded VRAM/RAM spikes
STATE_LOCK = threading.RLock()
MODEL: Any = None
TOKENIZER: Any = None
DML_DEVICE: Any = None
TORCH: Any = None
LAST_USED = 0.0
LAST_ERROR = ""
LAST_FAILURE = 0.0
DEPENDENCY_PROBE: dict[str, Any] = {"ready": False, "detail": "not-probed"}
VRAM_TOTAL_MIB = 0
VRAM_BUDGET_MIB = 0
MODEL_WEIGHT_MIB = 0
ESTIMATED_MODEL_VRAM_MIB = 0
EFFECTIVE_MAX_CONTEXT = MAX_CONTEXT
VRAM_POLICY_DETAIL = "not-evaluated"
STOP_EVENT = threading.Event()


def _no_proxy_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _http_json(url: str, payload: dict[str, Any] | None = None, timeout: int = 180) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method="POST" if data is not None else "GET",
    )
    with _no_proxy_opener().open(req, timeout=timeout) as resp:
        raw = resp.read(16 * 1024 * 1024)
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, dict):
        raise RuntimeError("upstream returned non-object JSON")
    return obj


def _managed_ollama_url() -> str:
    """Resolve the current managed Ollama container address at request time.

    Container IPs can change after repair/recreate, so the gateway must not cache one
    in a generated config file. Prefer hermes-edge because it is non-internal, then
    fall back to any assigned Docker network address.
    """
    cp = subprocess.run(
        ["docker", "inspect", "hermes-ollama"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=8,
        check=False,
    )
    if cp.returncode != 0:
        raise RuntimeError("managed Ollama container is not inspectable")
    arr = json.loads(cp.stdout)
    networks = (((arr or [{}])[0].get("NetworkSettings") or {}).get("Networks") or {})
    preferred = []
    for key in ("hermes-edge", "hermes-backend"):
        item = networks.get(key)
        if isinstance(item, dict) and item.get("IPAddress"):
            preferred.append(str(item["IPAddress"]))
    if not preferred:
        for item in networks.values():
            if isinstance(item, dict) and item.get("IPAddress"):
                preferred.append(str(item["IPAddress"]))
    if not preferred:
        raise RuntimeError("managed Ollama has no current Docker IP")
    return f"http://{preferred[0]}:11434/v1"


def fallback_base_url() -> str:
    if OLLAMA_BACKEND == "windows-native":
        if not NATIVE_FALLBACK_URL:
            raise RuntimeError("native Windows Ollama fallback URL is unavailable")
        return NATIVE_FALLBACK_URL.rstrip("/") + ("" if NATIVE_FALLBACK_URL.endswith("/v1") else "/v1")
    return _managed_ollama_url()


def fallback_ready() -> tuple[bool, str]:
    try:
        base = fallback_base_url()
        if OLLAMA_BACKEND == "managed":
            api = base[:-3] if base.endswith("/v1") else base
            _http_json(api + "/api/version", timeout=5)
        else:
            # Native relay is Ollama-compatible too.
            api = base[:-3] if base.endswith("/v1") else base
            _http_json(api + "/api/version", timeout=5)
        return True, base
    except Exception as exc:
        return False, str(exc)


def _normalize_vram_mib(raw: Any) -> int:
    """Normalize torch-directml gpu_memory() output to MiB without guessing tiny values."""
    try:
        value = int(raw)
    except Exception:
        return 0
    if value <= 0:
        return 0
    # torch-directml has historically exposed this as bytes. Keep compatibility with
    # builds/wrappers that may already normalize to MiB. Values below 256 MiB are
    # not useful for this managed LLM backend and are treated as unavailable.
    mib = value // (1024 * 1024) if value >= 1024 * 1024 else value
    return mib if mib >= 256 else 0


def _adapter_vendor(name: str) -> str:
    n = name.lower()
    if any(x in n for x in ("amd", "radeon", "advanced micro devices")):
        return "amd"
    if any(x in n for x in ("nvidia", "geforce", "quadro", "tesla", "rtx", "gtx")):
        return "nvidia"
    if any(x in n for x in ("intel", "arc", "iris", "uhd graphics", "hd graphics")):
        return "intel"
    if any(x in n for x in ("qualcomm", "adreno")):
        return "qualcomm"
    return "other"


def _directml_device_and_vram(torch_directml: Any) -> tuple[Any, int, int, str]:
    count = 0
    try:
        count = int(torch_directml.device_count())
    except Exception:
        count = 0
    if count <= 0:
        raise RuntimeError("torch-directml reports no DirectML adapters")

    adapters: list[tuple[int, str, str]] = []
    for idx in range(count):
        try:
            name = str(torch_directml.device_name(idx))
        except Exception:
            name = f"DirectML adapter {idx}"
        adapters.append((idx, name, _adapter_vendor(name)))

    index: int | None = None
    if REQUESTED_ADAPTER_NAME:
        wanted = REQUESTED_ADAPTER_NAME.lower()
        exact = [idx for idx, name, _vendor in adapters if name.lower() == wanted]
        partial = [idx for idx, name, _vendor in adapters if wanted in name.lower() or name.lower() in wanted]
        matches = exact or partial
        if len(matches) == 1:
            index = matches[0]
        elif len(matches) > 1:
            raise RuntimeError(f"saved DirectML adapter name is ambiguous: {REQUESTED_ADAPTER_NAME!r}")

    if index is None and REQUESTED_GPU_VENDOR in {"amd", "nvidia", "intel", "qualcomm"}:
        vendor_matches = [idx for idx, _name, vendor in adapters if vendor == REQUESTED_GPU_VENDOR]
        if len(vendor_matches) == 1:
            index = vendor_matches[0]
        elif len(vendor_matches) > 1 and not REQUESTED_ADAPTER_NAME:
            raise RuntimeError(
                f"multiple {REQUESTED_GPU_VENDOR} DirectML adapters are visible; choose an exact adapter in the Windows installer"
            )

    if index is None:
        if REQUESTED_ADAPTER_NAME or REQUESTED_GPU_VENDOR:
            visible = "; ".join(f"{i}:{name}" for i, name, _vendor in adapters)
            raise RuntimeError(
                f"saved DirectML GPU selection is not visible (adapter={REQUESTED_ADAPTER_NAME!r}, "
                f"vendor={REQUESTED_GPU_VENDOR!r}); visible={visible}"
            )
        try:
            index = int(torch_directml.default_device()) if hasattr(torch_directml, "default_device") else 0
        except Exception:
            index = 0

    device = torch_directml.device(index)
    name = next((name for idx, name, _vendor in adapters if idx == index), f"DirectML adapter {index}")
    vram_mib = 0
    try:
        if hasattr(torch_directml, "gpu_memory"):
            vram_mib = _normalize_vram_mib(torch_directml.gpu_memory(index))
    except Exception:
        vram_mib = 0
    return device, index, vram_mib, name


def _model_vram_plan(model: Any) -> tuple[int, int, int, int, str]:
    """Return weight MiB, estimated MiB, effective context, budget MiB, detail.

    torch-directml does not expose a stable allocator hard-limit API. LatticeVale
    therefore enforces a fail-closed admission budget before the model is moved to
    DirectML. Exact parameter bytes plus a KV-cache estimate and a deliberately
    conservative runtime/activation reserve must fit within the configured share of
    detected dedicated VRAM. If not, DirectML is rejected and Ollama handles text.
    """
    global VRAM_TOTAL_MIB, VRAM_BUDGET_MIB
    if VRAM_TOTAL_MIB <= 0:
        raise RuntimeError("DirectML VRAM capacity could not be measured; refusing unbounded GPU model admission")
    budget_mib = VRAM_TOTAL_MIB * VRAM_LIMIT_PCT // 100
    VRAM_BUDGET_MIB = budget_mib
    if budget_mib < 1024:
        raise RuntimeError(
            f"LatticeVale policy-selected DirectML VRAM budget={budget_mib}MiB "
            f"({VRAM_LIMIT_PCT}% of detected {VRAM_TOTAL_MIB}MiB) is below the 1024MiB safe minimum; "
            "refusing to exceed the requested percentage"
        )
    weight_bytes = 0
    for item in list(model.parameters()) + list(model.buffers()):
        try:
            weight_bytes += int(item.numel()) * int(item.element_size())
        except Exception:
            continue
    weight_mib = (weight_bytes + 1048575) // 1048576
    cfg = getattr(model, "config", None)
    layers = int(getattr(cfg, "num_hidden_layers", getattr(cfg, "n_layer", 0)) or 0)
    hidden = int(getattr(cfg, "hidden_size", getattr(cfg, "n_embd", 0)) or 0)
    heads = int(getattr(cfg, "num_attention_heads", getattr(cfg, "n_head", 0)) or 0)
    kv_heads = int(getattr(cfg, "num_key_value_heads", heads) or heads or 0)
    head_dim = hidden // heads if hidden > 0 and heads > 0 else 0
    # Key + value, fp16, per layer/head/token. When architecture metadata is not
    # available, use a conservative generic 96 KiB/token allowance.
    kv_per_token = 2 * layers * kv_heads * head_dim * 2 if layers and kv_heads and head_dim else 96 * 1024
    runtime_reserve_mib = max(768, (weight_mib * 30 + 99) // 100)
    fixed_mib = weight_mib + runtime_reserve_mib
    if fixed_mib >= budget_mib:
        raise RuntimeError(
            f"DirectML model admission refused: weights={weight_mib}MiB + runtime reserve={runtime_reserve_mib}MiB "
            f"exceeds LatticeVale VRAM budget={budget_mib}MiB ({VRAM_LIMIT_PCT}% of detected {VRAM_TOTAL_MIB}MiB)"
        )
    available_kv_bytes = max(0, (budget_mib - fixed_mib) * 1048576)
    context_fit = available_kv_bytes // max(1, kv_per_token)
    effective_context = min(MAX_CONTEXT, int(context_fit))
    effective_context = (effective_context // 256) * 256
    if effective_context < 1024:
        raise RuntimeError(
            f"DirectML model admission refused: only {effective_context} context tokens fit inside "
            f"the {budget_mib}MiB VRAM safety budget"
        )
    kv_mib = (kv_per_token * effective_context + 1048575) // 1048576
    estimated_mib = fixed_mib + kv_mib
    detail = (
        f"weights={weight_mib}MiB runtime-reserve={runtime_reserve_mib}MiB kv={kv_mib}MiB "
        f"context={effective_context} budget={budget_mib}MiB/{VRAM_TOTAL_MIB}MiB ({VRAM_LIMIT_PCT}%)"
    )
    return weight_mib, estimated_mib, effective_context, budget_mib, detail


def probe_dependencies() -> dict[str, Any]:
    global TORCH, DML_DEVICE, DEPENDENCY_PROBE, LAST_ERROR
    with STATE_LOCK:
        try:
            import torch
            import torch_directml
            import transformers

            if FORCE_FALLBACK:
                raise RuntimeError("DirectML is temporarily disabled after a prior hard gateway/model failure; Resume / repair will retry it")
            device, device_index, vram_mib, device_name = _directml_device_and_vram(torch_directml)
            # A real operation proves more than merely constructing the device handle.
            value = (torch.tensor([1.0], dtype=torch.float32).to(device) + 2.0).cpu().item()
            if abs(float(value) - 3.0) > 0.001:
                raise RuntimeError("DirectML tensor verification produced an unexpected result")
            try:
                torch.set_num_threads(max(1, min(4, (os.cpu_count() or 2) // 2)))
            except Exception:
                pass
            TORCH = torch
            DML_DEVICE = device
            global VRAM_TOTAL_MIB, VRAM_BUDGET_MIB
            VRAM_TOTAL_MIB = vram_mib
            VRAM_BUDGET_MIB = vram_mib * VRAM_LIMIT_PCT // 100
            DEPENDENCY_PROBE = {
                "ready": True,
                "detail": "DirectML tensor + VRAM-capacity probe passed",
                "torch": getattr(torch, "__version__", "unknown"),
                "transformers": getattr(transformers, "__version__", "unknown"),
                "device": str(device),
                "device_index": device_index,
                "device_name": device_name,
                "vram_total_mib": VRAM_TOTAL_MIB,
                "vram_budget_mib": VRAM_BUDGET_MIB,
                "vram_limit_pct": VRAM_LIMIT_PCT,
            }
            return dict(DEPENDENCY_PROBE)
        except Exception as exc:
            LAST_ERROR = f"DirectML dependency/device probe failed: {exc}"
            DEPENDENCY_PROBE = {"ready": False, "detail": LAST_ERROR}
            return dict(DEPENDENCY_PROBE)


def _load_model() -> tuple[Any, Any, Any]:
    global MODEL, TOKENIZER, TORCH, DML_DEVICE, LAST_USED, LAST_ERROR, LAST_FAILURE
    global MODEL_WEIGHT_MIB, ESTIMATED_MODEL_VRAM_MIB, EFFECTIVE_MAX_CONTEXT, VRAM_POLICY_DETAIL
    with MODEL_LOCK:
        now = time.monotonic()
        if MODEL is not None and TOKENIZER is not None and DML_DEVICE is not None:
            LAST_USED = now
            return MODEL, TOKENIZER, DML_DEVICE
        if LAST_FAILURE and now - LAST_FAILURE < FAILURE_COOLDOWN_SECONDS:
            raise RuntimeError(f"DirectML load is in {FAILURE_COOLDOWN_SECONDS}s cooldown after: {LAST_ERROR}")
        probe = probe_dependencies()
        if not probe.get("ready"):
            LAST_FAILURE = time.monotonic()
            raise RuntimeError(str(probe.get("detail") or "DirectML is not ready"))
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer

            HF_HOME.mkdir(parents=True, exist_ok=True)
            tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, cache_dir=str(HF_HOME), trust_remote_code=False)
            kwargs: dict[str, Any] = {
                "cache_dir": str(HF_HOME),
                "trust_remote_code": False,
                "torch_dtype": TORCH.float16,
                # Meta/sharded loading avoids the old ~2x model-size CPU peak before
                # weights are moved to DirectML, which is critical on 16GB hosts.
                "low_cpu_mem_usage": True,
            }
            # Eager attention avoids newer CUDA/SDPA-only fast paths that are not the
            # compatibility target for the torch-directml 0.2.5 / PyTorch 2.4.1 wheel envelope.
            kwargs["attn_implementation"] = "eager"
            model = AutoModelForCausalLM.from_pretrained(MODEL_ID, **kwargs)
            model.eval()
            weight_mib, estimated_mib, effective_context, _budget_mib, policy_detail = _model_vram_plan(model)
            MODEL_WEIGHT_MIB = weight_mib
            ESTIMATED_MODEL_VRAM_MIB = estimated_mib
            EFFECTIVE_MAX_CONTEXT = effective_context
            VRAM_POLICY_DETAIL = policy_detail
            # This is the admission boundary: no model is moved to the DirectML
            # device until LatticeVale proves its conservative estimate fits.
            model.to(DML_DEVICE)
            TOKENIZER = tokenizer
            MODEL = model
            LAST_USED = time.monotonic()
            LAST_ERROR = ""
            LAST_FAILURE = 0.0
            return MODEL, TOKENIZER, DML_DEVICE
        except Exception as exc:
            MODEL = None
            TOKENIZER = None
            LAST_ERROR = f"DirectML model load failed: {exc}"
            LAST_FAILURE = time.monotonic()
            raise RuntimeError(LAST_ERROR) from exc


def unload_model(reason: str = "idle") -> None:
    global MODEL, TOKENIZER, LAST_USED
    with MODEL_LOCK:
        if MODEL is None and TOKENIZER is None:
            return
        MODEL = None
        TOKENIZER = None
        LAST_USED = 0.0
        gc.collect()
        # torch-directml does not expose a stable empty_cache equivalent across all
        # preview builds; releasing model references is the portable bounded action.
        sys.stderr.write(f"DirectML model unloaded ({reason}).\n")
        sys.stderr.flush()


def idle_unloader() -> None:
    while not STOP_EVENT.wait(15):
        with MODEL_LOCK:
            last = LAST_USED
            loaded = MODEL is not None
        if loaded and last and time.monotonic() - last >= IDLE_UNLOAD_SECONDS and not INFERENCE_LOCK.locked():
            unload_model("idle timeout")


def _render_prompt(tokenizer: Any, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None) -> str:
    kwargs: dict[str, Any] = {"tokenize": False, "add_generation_prompt": True}
    if tools:
        kwargs["tools"] = tools
    try:
        return tokenizer.apply_chat_template(messages, **kwargs)
    except Exception:
        # Conservative fallback for tokenizers without a tool-aware chat template.
        parts: list[str] = []
        if tools:
            parts.append(
                "Available tools (respond with <tool_call>{\"name\":...,\"arguments\":{...}}</tool_call> when needed):\n"
                + json.dumps(tools, ensure_ascii=False)
            )
        for item in messages:
            role = str(item.get("role") or "user")
            content = item.get("content", "")
            if isinstance(content, list):
                content = "\n".join(str(x.get("text", "")) if isinstance(x, dict) else str(x) for x in content)
            parts.append(f"{role}: {content}")
        parts.append("assistant:")
        return "\n".join(parts)


_TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


def parse_tool_calls(text: str) -> tuple[str | None, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []
    for match in _TOOL_CALL_RE.finditer(text):
        try:
            obj = json.loads(match.group(1))
            if not isinstance(obj, dict):
                continue
            name = str(obj.get("name") or "").strip()
            args = obj.get("arguments", {})
            if not name:
                continue
            if isinstance(args, str):
                arg_text = args
            else:
                arg_text = json.dumps(args, separators=(",", ":"), ensure_ascii=False)
            calls.append(
                {
                    "id": "call_" + uuid.uuid4().hex[:24],
                    "type": "function",
                    "function": {"name": name, "arguments": arg_text},
                }
            )
        except Exception:
            continue
    cleaned = _TOOL_CALL_RE.sub("", text).strip()
    return (cleaned or None), calls


def directml_chat(payload: dict[str, Any]) -> dict[str, Any]:
    global LAST_USED, LAST_ERROR, LAST_FAILURE
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty array")
    tools = payload.get("tools") if isinstance(payload.get("tools"), list) else None
    requested = payload.get("max_tokens", payload.get("max_completion_tokens", DEFAULT_MAX_NEW))
    try:
        max_new = int(requested)
    except Exception:
        max_new = DEFAULT_MAX_NEW
    max_new = max(1, min(max_new, DEFAULT_MAX_NEW, 2048))

    # Serializing model generation bounds transient VRAM and host RAM.  HTTP handling
    # remains threaded, so concurrent clients wait rather than creating multiple model
    # copies or generation graphs.
    acquired = INFERENCE_LOCK.acquire(timeout=300)
    if not acquired:
        raise RuntimeError("DirectML inference queue timed out")
    try:
        model, tokenizer, device = _load_model()
        prompt = _render_prompt(tokenizer, messages, tools)
        max_input = max(256, EFFECTIVE_MAX_CONTEXT - max_new)
        encoded = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=max_input)
        input_ids = encoded["input_ids"].to(device)
        attention_mask = encoded.get("attention_mask")
        if attention_mask is not None:
            attention_mask = attention_mask.to(device)
        input_tokens = int(input_ids.shape[-1])
        generation: dict[str, Any] = {
            "max_new_tokens": max_new,
            "do_sample": False,
            "use_cache": True,
            "pad_token_id": tokenizer.eos_token_id,
        }
        if attention_mask is not None:
            generation["attention_mask"] = attention_mask
        with TORCH.inference_mode():
            output = model.generate(input_ids=input_ids, **generation)
        generated = output[0][input_tokens:].detach().cpu()
        text = tokenizer.decode(generated, skip_special_tokens=True).strip()
        output_tokens = int(generated.shape[-1])
        stops = payload.get("stop")
        if isinstance(stops, str):
            stops = [stops]
        if isinstance(stops, list):
            for stop in [str(x) for x in stops if str(x)]:
                pos = text.find(stop)
                if pos >= 0:
                    text = text[:pos]
        content, tool_calls = parse_tool_calls(text)
        LAST_USED = time.monotonic()
        LAST_ERROR = ""
        return {
            "backend": "directml",
            "content": content,
            "tool_calls": tool_calls,
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
        }
    except Exception as exc:
        LAST_ERROR = f"DirectML inference failed: {exc}"
        LAST_FAILURE = time.monotonic()
        raise
    finally:
        INFERENCE_LOCK.release()


def ollama_chat(payload: dict[str, Any], directml_error: str = "") -> dict[str, Any]:
    base = fallback_base_url()
    forwarded = dict(payload)
    forwarded["model"] = FALLBACK_MODEL
    # Always request a complete response so the gateway can provide one consistent
    # OpenAI-compatible streaming implementation to callers.
    forwarded["stream"] = False
    obj = _http_json(base.rstrip("/") + "/chat/completions", forwarded, timeout=300)
    message = ((obj.get("choices") or [{}])[0].get("message") or {})
    usage = obj.get("usage") or {}
    return {
        "backend": "ollama-fallback",
        "content": message.get("content"),
        "tool_calls": message.get("tool_calls") or [],
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "directml_error": directml_error,
    }


def routed_chat(payload: dict[str, Any]) -> dict[str, Any]:
    if FORCE_FALLBACK:
        return ollama_chat(payload, "DirectML temporarily disabled after a prior hard gateway/model failure")
    try:
        return directml_chat(payload)
    except Exception as exc:
        error = str(exc)
        # When this request owned the completed DirectML attempt, release the model
        # before invoking Ollama so fallback does not unnecessarily compete for VRAM.
        # A queue-timeout request does not unload a model still used by another request.
        if not INFERENCE_LOCK.locked():
            unload_model("inference failure before Ollama fallback")
        gc.collect()
        try:
            return ollama_chat(payload, error)
        except Exception as fallback_exc:
            raise RuntimeError(f"DirectML failed ({error}); Ollama fallback also failed ({fallback_exc})") from fallback_exc


def completion_object(result: dict[str, Any], model: str) -> dict[str, Any]:
    now = int(time.time())
    cid = "chatcmpl-lv-" + uuid.uuid4().hex
    tool_calls = result.get("tool_calls") or []
    message: dict[str, Any] = {"role": "assistant", "content": result.get("content")}
    if tool_calls:
        message["tool_calls"] = tool_calls
    prompt_tokens = int(result.get("prompt_tokens") or 0)
    completion_tokens = int(result.get("completion_tokens") or 0)
    return {
        "id": cid,
        "object": "chat.completion",
        "created": now,
        "model": model,
        "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls" if tool_calls else "stop"}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
        "x_latticevale_backend": result.get("backend"),
        "x_latticevale_directml_error": result.get("directml_error") or None,
    }


def stream_chunks(handler: BaseHTTPRequestHandler, result: dict[str, Any], model: str) -> None:
    cid = "chatcmpl-lv-" + uuid.uuid4().hex
    created = int(time.time())

    def send(delta: dict[str, Any], finish: str | None = None) -> None:
        obj = {
            "id": cid,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            "x_latticevale_backend": result.get("backend"),
        }
        handler.wfile.write(("data: " + json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n\n").encode("utf-8"))
        handler.wfile.flush()

    send({"role": "assistant"})
    calls = result.get("tool_calls") or []
    if calls:
        for index, call in enumerate(calls):
            fn = call.get("function") or {}
            send(
                {
                    "tool_calls": [
                        {
                            "index": index,
                            "id": call.get("id"),
                            "type": "function",
                            "function": {"name": fn.get("name"), "arguments": fn.get("arguments", "")},
                        }
                    ]
                }
            )
        send({}, "tool_calls")
    else:
        text = str(result.get("content") or "")
        # Chunk completed output for client compatibility. Generation itself is not
        # token-streamed because the preview DirectML backend is intentionally kept on
        # one bounded generation path for reliability.
        for start in range(0, len(text), 96):
            send({"content": text[start : start + 96]})
        send({}, "stop")
    handler.wfile.write(b"data: [DONE]\n\n")
    handler.wfile.flush()


class GatewayHandler(BaseHTTPRequestHandler):
    server_version = "LatticeValeDirectML/14.5.4"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), fmt % args))

    def _json(self, status: int, obj: dict[str, Any]) -> None:
        raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _read_payload(self) -> dict[str, Any]:
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("invalid Content-Length")
        if size <= 0 or size > MAX_BODY_BYTES:
            raise ValueError("request body is empty or too large")
        obj = json.loads(self.rfile.read(size).decode("utf-8"))
        if not isinstance(obj, dict):
            raise ValueError("request JSON must be an object")
        return obj

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("", "/health"):
            fb_ok, fb_detail = fallback_ready()
            with STATE_LOCK, MODEL_LOCK:
                payload = {
                    "status": "ok" if DEPENDENCY_PROBE.get("ready") or fb_ok else "degraded",
                    "selected_backend": "directml",
                    "directml_ready": bool(DEPENDENCY_PROBE.get("ready")),
                    "directml_detail": DEPENDENCY_PROBE.get("detail"),
                    "model": MODEL_ID,
                    "model_loaded": MODEL is not None,
                    "fallback_backend": OLLAMA_BACKEND,
                    "fallback_ready": fb_ok,
                    "fallback_detail": fb_detail,
                    "last_error": LAST_ERROR or None,
                    "idle_unload_seconds": IDLE_UNLOAD_SECONDS,
                    "max_context": MAX_CONTEXT,
                    "effective_max_context": EFFECTIVE_MAX_CONTEXT,
                    "vram_total_mib": VRAM_TOTAL_MIB or None,
                    "vram_limit_pct": VRAM_LIMIT_PCT,
                    "vram_budget_mib": VRAM_BUDGET_MIB or None,
                    "model_weight_mib": MODEL_WEIGHT_MIB or None,
                    "estimated_model_vram_mib": ESTIMATED_MODEL_VRAM_MIB or None,
                    "vram_policy_detail": VRAM_POLICY_DETAIL,
                    "requested_adapter_name": REQUESTED_ADAPTER_NAME or None,
                    "requested_gpu_vendor": REQUESTED_GPU_VENDOR or None,
                    "force_fallback": FORCE_FALLBACK,
                    "version": VERSION,
                }
            self._json(200 if payload["status"] == "ok" else 503, payload)
            return
        if self.path.rstrip("/") == "/v1/models":
            self._json(
                200,
                {
                    "object": "list",
                    "data": [
                        {
                            "id": MODEL_ID,
                            "object": "model",
                            "created": 0,
                            "owned_by": "latticevale-directml",
                        }
                    ],
                },
            )
            return
        self._json(404, {"error": {"message": "not found", "type": "invalid_request_error"}})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/v1/chat/completions":
            self._json(404, {"error": {"message": "not found", "type": "invalid_request_error"}})
            return
        try:
            payload = self._read_payload()
            result = routed_chat(payload)
            model = MODEL_ID
            if bool(payload.get("stream")):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                stream_chunks(self, result, model)
            else:
                self._json(200, completion_object(result, model))
        except ValueError as exc:
            self._json(400, {"error": {"message": str(exc), "type": "invalid_request_error"}})
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            self._json(503, {"error": {"message": str(exc), "type": "service_unavailable"}})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen-address", required=True)
    parser.add_argument("--listen-port", required=True, type=int)
    args = parser.parse_args()
    if not 1 <= args.listen_port <= 65535:
        parser.error("listen port must be 1..65535")

    probe_dependencies()
    HF_HOME.mkdir(parents=True, exist_ok=True)
    unloader = threading.Thread(target=idle_unloader, name="directml-idle-unloader", daemon=True)
    unloader.start()
    server = ThreadingHTTPServer((args.listen_address, args.listen_port), GatewayHandler)
    server.daemon_threads = True
    server.request_queue_size = 32

    def _term(_signum: int, _frame: Any) -> None:
        STOP_EVENT.set()
        # Avoid BaseServer.shutdown() from the serving thread/signal handler; close
        # the listening socket and let serve_forever exit through its poll loop.
        try:
            server.socket.close()
        except Exception:
            pass

    signal.signal(signal.SIGTERM, _term)
    signal.signal(signal.SIGINT, _term)
    sys.stderr.write(
        f"LatticeVale DirectML gateway {VERSION} listening on {args.listen_address}:{args.listen_port}; "
        f"model={MODEL_ID}; fallback={OLLAMA_BACKEND}; dependency_ready={DEPENDENCY_PROBE.get('ready')}\n"
    )
    sys.stderr.flush()
    try:
        server.serve_forever(poll_interval=0.5)
    except (KeyboardInterrupt, OSError):
        pass
    finally:
        STOP_EVENT.set()
        unload_model("shutdown")
        try:
            server.server_close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
