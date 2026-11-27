"""
Ollama Protocol Compatibility Bridge & Universal Network Onboarding Router.

Enables OpenClaw and any tool supporting Ollama or OpenAI to discover Loom Fabric
as a native AI provider with zero manual setup. Also serves one-click network
join scripts for Consumers and Compute Service Providers (CSPs).
"""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional
from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
import httpx

from loom.models.registry import ModelRegistry

router = APIRouter(tags=["Ollama & Network Onboarding Bridge"])


@router.get("/api/version")
def get_ollama_version() -> Dict[str, str]:
    """Ollama version endpoint for automatic provider handshake."""
    return {"version": "0.1.0-loom-fabric"}


@router.get("/api/tags")
def get_ollama_tags() -> Dict[str, Any]:
    """
    Exposes Loom Fabric models as native Ollama tags.
    When OpenClaw points to this host, all models appear directly in the model picker.
    """
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    models_list = [
        {
            "name": "loom-fabric/auto",
            "model": "loom-fabric/auto",
            "modified_at": now_iso,
            "size": 19800000000,
            "digest": "sha256:loom_fabric_auto_triage",
            "details": {
                "parent_model": "",
                "format": "gguf",
                "family": "loom-fabric",
                "families": ["loom-fabric", "clothos"],
                "parameter_size": "Dynamic",
                "quantization_level": "Adaptive"
            }
        },
        {
            "name": "loom-fabric/clothos",
            "model": "loom-fabric/clothos",
            "modified_at": now_iso,
            "size": 19800000000,
            "digest": "sha256:loom_fabric_clothos",
            "details": {
                "parent_model": "",
                "format": "gguf",
                "family": "loom-fabric",
                "families": ["clothos"],
                "parameter_size": "Base-12 AGI",
                "quantization_level": "Adaptive"
            }
        },
        {
            "name": "loom-fabric/deepseek-r1:14b",
            "model": "loom-fabric/deepseek-r1:14b",
            "modified_at": now_iso,
            "size": 9000000000,
            "digest": "sha256:loom_fabric_deepseek_r1_14b",
            "details": {
                "parent_model": "",
                "format": "gguf",
                "family": "deepseek",
                "families": ["deepseek", "qwen2.5"],
                "parameter_size": "14B",
                "quantization_level": "Q4_K_M"
            }
        },
        {
            "name": "loom-fabric/qwen2.5:32b",
            "model": "loom-fabric/qwen2.5:32b",
            "modified_at": now_iso,
            "size": 19800000000,
            "digest": "sha256:loom_fabric_qwen25_32b",
            "details": {
                "parent_model": "",
                "format": "gguf",
                "family": "qwen2.5",
                "families": ["qwen2.5"],
                "parameter_size": "32B",
                "quantization_level": "Q4_K_M"
            }
        },
        {
            "name": "loom-fabric/qwen2.5:7b",
            "model": "loom-fabric/qwen2.5:7b",
            "modified_at": now_iso,
            "size": 4700000000,
            "digest": "sha256:loom_fabric_qwen25_7b",
            "details": {
                "parent_model": "",
                "format": "gguf",
                "family": "qwen2.5",
                "families": ["qwen2.5"],
                "parameter_size": "7B",
                "quantization_level": "Q4_K_M"
            }
        },
        {
            "name": "loom-fabric/qwen2.5:3b",
            "model": "loom-fabric/qwen2.5:3b",
            "modified_at": now_iso,
            "size": 1900000000,
            "digest": "sha256:loom_fabric_qwen25_3b",
            "details": {
                "parent_model": "",
                "format": "gguf",
                "family": "qwen2.5",
                "families": ["qwen2.5"],
                "parameter_size": "3B",
                "quantization_level": "Q4_K_M"
            }
        }
    ]
    return {"models": models_list}


@router.post("/api/show")
async def get_ollama_show(req: Request) -> Dict[str, Any]:
    """Returns model information to Ollama clients."""
    body = await req.json()
    model_name = body.get("name", "loom-fabric/auto")
    return {
        "modelfile": f"# Loom Fabric Model: {model_name}\nFROM {model_name}\nPARAMETER temperature 0.7",
        "parameters": "temperature 0.7\ntop_p 0.95",
        "template": "{{ .Prompt }}",
        "details": {
            "format": "gguf",
            "family": "loom-fabric",
            "parameter_size": "32B",
            "quantization_level": "Q4_K_M"
        }
    }


@router.post("/api/chat")
async def ollama_chat(req: Request):
    """
    Translates Ollama `/api/chat` requests to the Loom Fabric OpenAI-compatible router.
    """
    body = await req.json()
    model = body.get("model", "auto")
    messages = body.get("messages", [])
    stream = body.get("stream", True)

    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "temperature": body.get("options", {}).get("temperature", 0.7),
        "max_tokens": body.get("options", {}).get("num_predict", 4096),
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        if not stream:
            res = await client.post("http://127.0.0.1:8087/v1/chat/completions", json=payload)
            if res.status_code != 200:
                return JSONResponse(status_code=res.status_code, content={"error": res.text})
            openai_resp = res.json()
            content = openai_resp["choices"][0]["message"]["content"]
            return {
                "model": model,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "message": {"role": "assistant", "content": content},
                "done": True,
                "total_duration": 100000000,
                "load_duration": 10000000,
                "prompt_eval_count": openai_resp.get("usage", {}).get("prompt_tokens", 10),
                "eval_count": openai_resp.get("usage", {}).get("completion_tokens", len(content) // 4),
            }

        async def _stream_ollama() -> AsyncIterator[str]:
            async with client.stream("POST", "http://127.0.0.1:8087/v1/chat/completions", json=payload) as r:
                async for chunk in r.aiter_lines():
                    if not chunk or not chunk.startswith("data: "):
                        continue
                    data_str = chunk[6:].strip()
                    if data_str == "[DONE]":
                        done_msg = {
                            "model": model,
                            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "message": {"role": "assistant", "content": ""},
                            "done": True
                        }
                        yield json.dumps(done_msg) + "\n"
                        break
                    try:
                        parsed = json.loads(data_str)
                        delta = parsed["choices"][0].get("delta", {}).get("content", "")
                        if delta:
                            item = {
                                "model": model,
                                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                "message": {"role": "assistant", "content": delta},
                                "done": False
                            }
                            yield json.dumps(item) + "\n"
                    except Exception:
                        continue

        return StreamingResponse(_stream_ollama(), media_type="application/x-ndjson")


@router.get("/join.ps1", response_class=PlainTextResponse)
def get_windows_join_script(request: Request) -> str:
    """Returns a 1-click Windows PowerShell onboarding script for OpenClaw users."""
    host = request.headers.get("host", "127.0.0.1:8087")
    protocol = "https" if "https" in str(request.url) else "http"
    gateway_url = f"{protocol}://{host}"

    script = f'''# Loom Fabric Instant Network Join Script (Windows)
# Run via: irm {gateway_url}/join.ps1 | iex

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Joining the Loom Fabric Sovereign Compute Network" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

$GatewayUrl = "{gateway_url}"
$OpenClawPath = "$env:USERPROFILE\\.openclaw\\openclaw.json"

if (-not (Test-Path $OpenClawPath)) {{
    Write-Host "[!] openclaw.json not found. Creating fresh configuration..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path "$env:USERPROFILE\\.openclaw" -Force | Out-Null
    Set-Content -Path $OpenClawPath -Value '{{ "models": {{ "providers": {{}} }} }}'
}}

# Read and update config
$cfg = Get-Content $OpenClawPath -Raw | ConvertFrom-Json

# 1. Register Loom Fabric as AI Provider
if (-not $cfg.models) {{ $cfg | Add-Member -MemberType NoteProperty -Name "models" -Value ([PSCustomObject]@{{}}) }}
if (-not $cfg.models.providers) {{ $cfg.models | Add-Member -MemberType NoteProperty -Name "providers" -Value ([PSCustomObject]@{{}}) }}

$loomProvider = [PSCustomObject]@{{
    api = "openai-completions"
    apiKey = "loom-fabric-local"
    baseUrl = "$GatewayUrl/v1"
    models = @(
        [PSCustomObject]@{{ id = "auto"; name = "Loom Fabric - Dynamic Compute Triage (Auto)"; contextTokens = 65536; contextWindow = 131072 }},
        [PSCustomObject]@{{ id = "loom-sovereign-fast:latest"; name = "Loom Fabric - Sovereign Fast (ClothOS)"; contextTokens = 32768; contextWindow = 32768 }},
        [PSCustomObject]@{{ id = "qwen2.5:32b"; name = "Loom Fabric - Qwen 2.5 32B (Distributed Dual-GPU)"; contextTokens = 65536; contextWindow = 131072 }},
        [PSCustomObject]@{{ id = "deepseek-r1:14b"; name = "Loom Fabric - DeepSeek R1 14B (Reasoning)"; contextTokens = 65536; contextWindow = 131072 }},
        [PSCustomObject]@{{ id = "qwen2.5:7b"; name = "Loom Fabric - Qwen 2.5 7B (Pure CUDA)"; contextTokens = 65536; contextWindow = 131072 }}
    )
}}

$cfg.models.providers | Add-Member -MemberType NoteProperty -Name "loom-fabric" -Value $loomProvider -Force

# 2. Add auth profile
if (-not $cfg.auth) {{ $cfg | Add-Member -MemberType NoteProperty -Name "auth" -Value ([PSCustomObject]@{{ profiles = ([PSCustomObject]@{{}}) }}) }}
if (-not $cfg.auth.profiles) {{ $cfg.auth | Add-Member -MemberType NoteProperty -Name "profiles" -Value ([PSCustomObject]@{{}}) }}
$cfg.auth.profiles | Add-Member -MemberType NoteProperty -Name "loom-fabric:default" -Value ([PSCustomObject]@{{ mode = "api_key"; provider = "loom-fabric" }}) -Force

# 3. Add direct aliases and fallbacks in openclaw.json
if (-not $cfg.agents) {{ $cfg | Add-Member -MemberType NoteProperty -Name "agents" -Value ([PSCustomObject]@{{}}) }}
if (-not $cfg.agents.defaults) {{ $cfg.agents | Add-Member -MemberType NoteProperty -Name "defaults" -Value ([PSCustomObject]@{{}}) }}
if (-not $cfg.agents.defaults.models) {{ $cfg.agents.defaults | Add-Member -MemberType NoteProperty -Name "models" -Value ([PSCustomObject]@{{}}) }}

$cfg.agents.defaults.models | Add-Member -MemberType NoteProperty -Name "loom-fabric/auto" -Value ([PSCustomObject]@{{ alias = "clothos" }}) -Force
$cfg.agents.defaults.models | Add-Member -MemberType NoteProperty -Name "loom-fabric/qwen2.5:32b" -Value ([PSCustomObject]@{{ alias = "qwen32b" }}) -Force

# Save back
$cfg | ConvertTo-Json -Depth 30 | Set-Content -Path $OpenClawPath -Encoding utf8

Write-Host "[OK] Loom Fabric successfully registered in OpenClaw config!" -ForegroundColor Green

# 4. Probe Virtual Compute Devices
try {{
    $devResp = Invoke-RestMethod -Uri "$GatewayUrl/v1/csp/virtual-devices" -Method Get -TimeoutSec 3
    Write-Host ""
    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host "  Virtual Compute Accelerator (VCA) Active" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Cyan
    Write-Host "  Your operating system and AI runtimes now see:" -ForegroundColor White
    foreach ($d in $devResp.devices) {{
        if ($d.device_type -eq "PHYSICAL_GPU") {{
            Write-Host "    [Device $($d.device_index)] $($d.name) ($($d.total_memory_gb) GB Physical VRAM, $($d.available_memory_gb) GB Free)" -ForegroundColor Gray
        }} else {{
            Write-Host "    [Device $($d.device_index)] $($d.name)" -ForegroundColor Green
            Write-Host "               -> Real Physical Silicon: $($d.cpu_cores) Cores | $($d.total_memory_gb) GB Pooled Memory" -ForegroundColor White
            Write-Host "               -> Cluster Topology: Ray GCS Redis Mesh (skyTech + WIN-7CMAQLVP8MV) | ZERO-OOM" -ForegroundColor Yellow
        }}
    }}
}} catch {{ }}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Success! You can now select 'loom-fabric' in OpenClaw" -ForegroundColor Green
Write-Host "  Or type: /model clothos in any OpenClaw chat window" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
'''
    return script


@router.get("/join.sh", response_class=PlainTextResponse)
def get_unix_join_script(request: Request) -> str:
    """Returns a 1-click macOS/Linux onboarding script for OpenClaw users."""
    host = request.headers.get("host", "127.0.0.1:8087")
    protocol = "https" if "https" in str(request.url) else "http"
    gateway_url = f"{protocol}://{host}"

    script = f'''#!/usr/bin/env bash
# Loom Fabric Instant Network Join Script (macOS / Linux)
# Run via: curl -fsSL {gateway_url}/join.sh | bash

echo "=========================================================="
echo "  Joining the Loom Fabric Sovereign Compute Network"
echo "=========================================================="

GATEWAY_URL="{gateway_url}"
OPENCLAW_PATH="$HOME/.openclaw/openclaw.json"

mkdir -p "$HOME/.openclaw"
if [ ! -f "$OPENCLAW_PATH" ]; then
    echo '{{"models": {{"providers": {{}}}}}}' > "$OPENCLAW_PATH"
fi

python3 -c "
import json
path = '$OPENCLAW_PATH'
with open(path, 'r') as f:
    cfg = json.load(f)

cfg.setdefault('models', {{}}).setdefault('providers', {{}})['loom-fabric'] = {{
    'api': 'openai-completions',
    'apiKey': 'loom-fabric-local',
    'baseUrl': '$GATEWAY_URL/v1',
    'models': [
        {{'id': 'auto', 'name': 'Loom Fabric - Dynamic Compute Triage (Auto)', 'contextTokens': 65536, 'contextWindow': 131072}},
        {{'id': 'loom-sovereign-fast:latest', 'name': 'Loom Fabric - Sovereign Fast', 'contextTokens': 32768, 'contextWindow': 32768}},
        {{'id': 'qwen2.5:32b', 'name': 'Loom Fabric - Qwen 2.5 32B', 'contextTokens': 65536, 'contextWindow': 131072}},
        {{'id': 'deepseek-r1:14b', 'name': 'Loom Fabric - DeepSeek R1 14B', 'contextTokens': 65536, 'contextWindow': 131072}},
        {{'id': 'qwen2.5:7b', 'name': 'Loom Fabric - Qwen 2.5 7B', 'contextTokens': 65536, 'contextWindow': 131072}}
    ]
}}
cfg.setdefault('auth', {{}}).setdefault('profiles', {{}})['loom-fabric:default'] = {{
    'mode': 'api_key',
    'provider': 'loom-fabric'
}}
with open(path, 'w') as f:
    json.dump(cfg, f, indent=2)
print('[OK] Loom Fabric registered in OpenClaw config!')
"

if command -v openclaw >/dev/null 2>&1; then
    openclaw models aliases add clothos loom-fabric/auto >/dev/null 2>&1
    openclaw models aliases add fabric loom-fabric/auto >/dev/null 2>&1
    openclaw models aliases add loom loom-fabric/auto >/dev/null 2>&1
    echo "[OK] Aliases registered: /model clothos, /model fabric, /model loom"
fi

echo "=========================================================="
echo "  Success! Select 'loom-fabric' in OpenClaw or type:"
echo "  /model clothos"
echo "=========================================================="
'''
    return script


@router.get("/join", response_class=HTMLResponse)
def get_join_portal_ui(request: Request) -> str:
    """Interactive visual portal for joining Loom Fabric as a Consumer or Provider."""
    host = request.headers.get("host", "127.0.0.1:8087")
    protocol = "https" if "https" in str(request.url) else "http"
    gateway_url = f"{protocol}://{host}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Join the Loom Fabric Network | VectorCore Holdings</title>
    <style>
        :root {{
            --bg: #090a10;
            --card: rgba(18, 20, 32, 0.85);
            --border: rgba(168, 85, 247, 0.25);
            --clover: #c084fc;
            --green: #10b981;
            --accent: #8b5cf6;
            --text: #f3f4f6;
            --text-muted: #9ca3af;
        }}
        body {{
            margin: 0;
            padding: 40px 20px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: radial-gradient(circle at 50% 20%, #171126 0%, var(--bg) 70%);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .container {{
            max-width: 900px;
            width: 100%;
        }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
        }}
        .badge {{
            display: inline-block;
            background: rgba(16, 185, 129, 0.15);
            color: var(--green);
            border: 1px solid rgba(16, 185, 129, 0.35);
            padding: 6px 16px;
            border-radius: 999px;
            font-size: 13px;
            font-weight: 700;
            margin-bottom: 16px;
        }}
        h1 {{
            font-size: 38px;
            font-weight: 800;
            color: #fff;
            margin: 0 0 12px 0;
            letter-spacing: -0.5px;
        }}
        .subtitle {{
            font-size: 16px;
            color: var(--text-muted);
            line-height: 1.5;
            max-width: 650px;
            margin: 0 auto;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-bottom: 30px;
        }}
        @media (max-width: 768px) {{
            .grid {{ grid-template-columns: 1fr; }}
        }}
        .card {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 28px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.4);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .card-title {{
            font-size: 20px;
            font-weight: 700;
            color: var(--clover);
            margin-bottom: 8px;
        }}
        .card-desc {{
            font-size: 14px;
            color: var(--text-muted);
            line-height: 1.6;
            margin-bottom: 20px;
        }}
        .code-box {{
            background: #050608;
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 8px;
            padding: 12px 14px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 13px;
            color: #38bdf8;
            overflow-x: auto;
            margin-bottom: 16px;
            user-select: all;
        }}
        .btn {{
            display: block;
            text-align: center;
            background: linear-gradient(135deg, var(--accent), #6366f1);
            color: #fff;
            padding: 12px 20px;
            border-radius: 10px;
            text-decoration: none;
            font-weight: 600;
            font-size: 14px;
            transition: opacity 0.2s;
        }}
        .btn:hover {{ opacity: 0.9; }}
        .btn-green {{
            background: linear-gradient(135deg, #10b981, #059669);
        }}
        .footer {{
            text-align: center;
            font-size: 13px;
            color: #6b7280;
            margin-top: 40px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="badge">● LIVE PEER-TO-PEER MESH ACTIVE</div>
            <h1>Join the Loom Fabric Network</h1>
            <div class="subtitle">
                Connect your OpenClaw to distributed sovereign compute, or monetize your GPU / Apple Silicon as a local Compute Service Provider.
            </div>
        </div>

        <div class="grid">
            <!-- Consumer Card -->
            <div class="card">
                <div>
                    <div class="card-title">1. Connect OpenClaw (Consumer)</div>
                    <div class="card-desc">
                        Select <strong>loom-fabric</strong> in OpenClaw Chat. Run this command in PowerShell or Terminal to configure your local OpenClaw gateway automatically:
                    </div>
                    <strong>Windows (PowerShell):</strong>
                    <div class="code-box">irm {gateway_url}/join.ps1 | iex</div>
                    <strong>macOS / Linux (Terminal):</strong>
                    <div class="code-box">curl -fsSL {gateway_url}/join.sh | bash</div>
                </div>
                <a href="http://127.0.0.1:18789/" target="_blank" class="btn">Launch OpenClaw Chat</a>
            </div>

            <!-- Provider Card -->
            <div class="card">
                <div>
                    <div class="card-title">2. Become a Provider (CSP)</div>
                    <div class="card-desc">
                        Turn your gaming rig, mining setup, or Mac Pro into a paid node on the Spotlight-Local mesh. Automatically probe your VRAM and earn cash ($ USD) when neighbors stream inferences or gaming sessions:
                    </div>
                    <strong>Run Host Agent Daemon:</strong>
                    <div class="code-box">python -m loom.caas.daemon --solar</div>
                    <div class="card-desc" style="font-size: 12px; margin-top: 10px;">
                        ✓ Sub-2ms low latency • 1.0% flat platform fee • 99.0% host payout via Spotlight-Local Neobank card.
                    </div>
                </div>
                <a href="/v1/csp/manifest" target="_blank" class="btn btn-green">View Node Manifest</a>
            </div>
        </div>

        <div class="footer">
            VectorCore Holdings, LLC • Spotlight-Local, Inc. • ClothOS Sovereign AGI
        </div>
    </div>
</body>
</html>
"""
    return html
