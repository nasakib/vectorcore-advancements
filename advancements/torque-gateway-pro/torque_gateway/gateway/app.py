"""
FastAPI OpenAI-Compatible Gateway Server for Loom Fabric.

Features:
- Full Integration with Pillar 1 (TORQUE): Zero-trust IP/PII scrubbing and rehydration.
- Real-time SSE token stream rehydration on the fly for Tier 3 Cloud Arbitrage.
- Telemetry headers: `X-Torque-Route`, `X-Torque-Scrubbed`, `X-Loom-Provider`, `X-Loom-TTFT-Ms`, `X-Loom-Tokens-Per-Sec`.
- Built-in Web UI Dashboard at `/` for monitoring cluster health, running test completions, and inspecting live scrubbing vaults.

Rust Migration Blueprint:
    In the native `loom-core` Rust crate:
    Built on `axum` with `tower-http` middleware and SSE streaming transforms:
    ```rust
    pub fn build_router(state: Arc<AppState>) -> Router {
        Router::new()
            .route("/", get(serve_dashboard_ui))
            .route("/v1/models", get(list_models))
            .route("/v1/chat/completions", post(chat_completions))
            .route("/health", get(health_check))
            .route("/metrics", get(cluster_metrics))
            .with_state(state)
    }
    ```
"""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import httpx

from loom.config import get_settings
from loom.gateway.metrics import CompletionTelemetry
from loom.gateway.router import GatewayRouter
from loom.models.registry import ModelRegistry, ModelPreset
from loom.stitch.profiler import HardwareProfiler
from loom.torque.router import TorqueRouter
from loom.torque.scrubber import TorqueScrubber, RehydrationVault
from loom.types import ExecutionTier, PromptPayload, ChatMessageDTO, RoutingDecision

app = FastAPI(
    title="Loom Fabric Compute Gateway",
    version="0.1.0",
    description="Heterogeneous Ray-Orchestrated Distributed AI Compute Engine with Zero-Trust Sovereign Routing",
)

# Enable CORS for standard web and desktop client integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core subsystems
torque_scrubber = TorqueScrubber()
torque_router = TorqueRouter()
gateway_router = GatewayRouter()
profiler_instance = HardwareProfiler()


# ============================================================================
# WEB UI DASHBOARD (Sovereign Control Pane)
# ============================================================================

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Loom Fabric Commander — Sovereign AI Operating System (Flora &amp; Breeze Edition)</title>
    <style>
        :root {
            --bg: #07120a;
            --card: #0d1e12;
            --border: #1d3d28;
            --border-hover: #10b981;
            --accent: #10b981;
            --accent-glow: rgba(16, 185, 129, 0.35);
            --amethyst: #c084fc;
            --purple: #a855f7;
            --royal: #7e22ce;
            --green: #10b981;
            --clover: #34d399;
            --dew: #6ee7b7;
            --breeze: #38bdf8;
            --yellow: #f59e0b;
            --red: #f43f5e;
            --text: #f0fdf4;
            --text-dim: #bbf7d0;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
            background: var(--bg);
            background-image: 
                radial-gradient(circle at 10% 15%, rgba(16, 185, 129, 0.14) 0%, transparent 45%),
                radial-gradient(circle at 90% 80%, rgba(168, 85, 247, 0.18) 0%, transparent 50%),
                radial-gradient(circle at 50% 30%, rgba(56, 189, 248, 0.08) 0%, transparent 60%);
            color: var(--text);
            padding: 24px;
            line-height: 1.5;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 24px;
        }
        .title { font-size: 26px; font-weight: 800; color: var(--clover); letter-spacing: 0.5px; }
        .subtitle { font-size: 13px; color: var(--amethyst); }
        .status-badge {
            background: rgba(16, 185, 129, 0.15);
            color: var(--green);
            padding: 6px 14px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            border: 1px solid rgba(16, 185, 129, 0.4);
            box-shadow: 0 0 12px rgba(168, 85, 247, 0.2);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }
        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px;
            transition: border-color 0.2s;
        }
        .card:hover { border-color: var(--border-hover); }
        .card-title {
            font-size: 14px;
            font-weight: 700;
            color: var(--amethyst);
            text-transform: uppercase;
            letter-spacing: 0.6px;
            margin-bottom: 12px;
            display: flex;
            justify-content: space-between;
        }
        .stat-row {
            display: flex;
            justify-content: space-between;
            font-size: 13px;
            padding: 7px 0;
            border-bottom: 1px solid rgba(255,255,255,0.04);
        }
        .stat-val { font-weight: 600; color: #fff; }
        .interactive-section {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 22px;
            margin-bottom: 24px;
        }
        .controls-bar {
            display: flex;
            flex-wrap: wrap;
            gap: 14px;
            align-items: center;
            margin-bottom: 14px;
        }
        select, input[type="text"] {
            background: #0b0a17;
            border: 1px solid var(--border);
            color: #fff;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 13px;
            font-family: inherit;
        }
        textarea {
            width: 100%;
            height: 95px;
            background: #080713;
            border: 1px solid var(--border);
            border-radius: 10px;
            color: #fff;
            padding: 12px;
            font-family: inherit;
            font-size: 14px;
            margin-bottom: 14px;
            resize: vertical;
        }
        textarea:focus, select:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 10px var(--accent-glow);
        }
        button {
            background: linear-gradient(135deg, var(--accent) 0%, var(--royal) 100%);
            color: #ffffff;
            font-weight: 700;
            border: none;
            padding: 10px 22px;
            border-radius: 8px;
            cursor: pointer;
            transition: transform 0.15s, opacity 0.2s, box-shadow 0.2s;
            box-shadow: 0 4px 14px var(--accent-glow);
        }
        button:hover { opacity: 0.95; transform: translateY(-1px); }
        button.secondary {
            background: #1c1830;
            color: var(--amethyst);
            border: 1px solid var(--border);
            box-shadow: none;
        }
        .progress-bar-container {
            width: 100%;
            height: 4px;
            background: #1a162b;
            border-radius: 999px;
            overflow: hidden;
            margin-top: 12px;
            display: none;
        }
        .progress-bar-fill {
            height: 100%;
            width: 0%;
            background: linear-gradient(90deg, var(--accent), var(--amethyst));
            transition: width 0.1s linear;
        }
        .output-box {
            background: #080713;
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 16px;
            margin-top: 14px;
            font-size: 13px;
            min-height: 110px;
            max-height: 400px;
            overflow-y: auto;
            white-space: pre-wrap;
            font-family: "JetBrains Mono", Consolas, monospace;
            line-height: 1.6;
        }
        .tag {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            margin-right: 6px;
        }
        .tag-tier1 { background: rgba(168, 85, 247, 0.2); color: var(--amethyst); border: 1px solid rgba(168, 85, 247, 0.4); }
        .tag-tier2 { background: rgba(245, 158, 11, 0.2); color: var(--yellow); border: 1px solid rgba(245, 158, 11, 0.4); }
        .tag-tier3 { background: rgba(244, 63, 94, 0.2); color: var(--red); border: 1px solid rgba(244, 63, 94, 0.4); }
        .table-recs {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            margin-top: 10px;
        }
        .table-recs th {
            text-align: left;
            padding: 10px;
            background: rgba(255,255,255,0.03);
            color: var(--amethyst);
            border-bottom: 1px solid var(--border);
        }
        .table-recs td {
            padding: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.04);
        }
    </style>
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#07120a">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
</head>
<body>
    <div class="header">
        <div>
            <div class="title">FABRIC</div>
            <div class="subtitle">ClothOS Agentic Operating System &bull; Loom (QCT Router) &bull; Stitch (ZeroMQ MMU) &bull; Torque (Zero-Trust Enclave)</div>
        </div>
        <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
            <button onclick="clusterAction('start')" style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 8px 16px;">&#9654; START FABRIC</button>
            <button onclick="clusterAction('restart_both')" style="background: linear-gradient(135deg, #a855f7 0%, #7e22ce 100%); padding: 8px 16px;">&#9889; Restart BOTH Machines</button>
            <button class="secondary" onclick="clusterAction('stop')" style="padding: 8px 14px; color: #f43f5e; border-color: rgba(244,63,94,0.4);">&#9632; Stop Local</button>
            <div class="status-badge" id="cluster-status">FABRIC + CLOTHOS UNIFIED &bull; PORT 8087</div>
        </div>
    </div>

    <div class="interactive-section" style="border-color: var(--purple); box-shadow: 0 0 24px rgba(168, 85, 247, 0.12);">
        <div class="card-title">
            <span>THE SHUTTLE // Prompt &amp; Real-Time Streaming Console (Press Enter to Dispatch)</span>
            <span id="cluster-action-status" style="font-size: 12px; color: var(--clover);">🛡 Zero-Terminal Auto-Heal: ON</span>
        </div>
        <div class="controls-bar">
            <div>
                <label style="font-size: 12px; color: var(--text-dim); display: block; margin-bottom: 4px;">Target Model</label>
                <select id="model-select">
                    <option value="auto">auto (Dynamic Compute Triage &amp; Delegation)</option>
                    <option value="claude-sonnet-4-5">claude-sonnet-4-5 (Anthropic Drop-In -> Sovereign 32B)</option>
                    <option value="claude-opus-4-5">claude-opus-4-5 (Anthropic Drop-In -> Apex 32B/70B)</option>
                    <option value="claude-haiku-4-5">claude-haiku-4-5 (Anthropic Drop-In -> CUDA 7B)</option>
                    <option value="qwen2.5:32b">qwen2.5:32b (Distributed Dual-GPU + Host RAM)</option>
                    <option value="deepseek-r1:14b">deepseek-r1:14b (Formal Reasoning &amp; Math)</option>
                    <option value="qwen2.5:7b">qwen2.5:7b (Pure RTX 3060 CUDA)</option>
                    <option value="qwen2.5:3b">qwen2.5:3b (Fast Drafter)</option>
                </select>
            </div>
            <div style="display: flex; align-items: center; gap: 6px; margin-top: 18px;">
                <input type="checkbox" id="stream-toggle" checked>
                <label for="stream-toggle" style="font-size: 13px; color: #fff; cursor: pointer;">Real-Time SSE Stream</label>
            </div>
            <div style="display: flex; align-items: center; gap: 6px; margin-top: 18px;">
                <input type="checkbox" id="sovereign-toggle">
                <label for="sovereign-toggle" style="font-size: 13px; color: #fff; cursor: pointer;">Force [SOVEREIGN] (No Cloud)</label>
            </div>
        </div>

        <textarea id="prompt-input" autofocus placeholder="Type your prompt and press Enter (Shift+Enter for new line)... e.g.: Prove the Fourier transform convergence theorem, synthesize a microkernel scheduler, or ask anything..."></textarea>

        <div style="display: flex; align-items: center; gap: 10px;">
            <button onclick="sendPrompt()">&#9654; Launch Prompt (Enter)</button>
            <button class="secondary" onclick="previewTriage()">Preview Triage</button>
            <span id="routing-badge" style="margin-left: 8px;"></span>
        </div>

        <div class="progress-bar-container" id="stream-progress">
            <div class="progress-bar-fill" id="progress-fill"></div>
        </div>

        <div class="output-box" id="output-box">Ready. Press [▶ START FABRIC] or type your prompt above and press Enter...</div>
    </div>

    <div class="grid">
        <div class="card">
            <div class="card-title">Worker Silicon Node (skyTech // Dual-GPU)</div>
            <div class="stat-row"><span>IP Address</span><span class="stat-val">192.168.99.1 (1Gbps Direct Wire)</span></div>
            <div class="stat-row"><span>GPU 0 (Primary)</span><span class="stat-val">RTX 3060 12GB (CUDA 12.x)</span></div>
            <div class="stat-row"><span>GPU 1 (Secondary)</span><span class="stat-val">RX 580 8GB (Vulkan 1.3)</span></div>
            <div class="stat-row"><span>Host Memory</span><span class="stat-val">54 GB DDR4</span></div>
            <div class="stat-row"><span>Live Ports</span><span class="stat-val" id="ports-99-1">:8087 :11434 :18789</span></div>
        </div>

        <div class="card">
            <div class="card-title">Head Coordinator Node (Ryzen 7 7730U)</div>
            <div class="stat-row"><span>IP Address</span><span class="stat-val">192.168.99.2 (1Gbps Direct Wire)</span></div>
            <div class="stat-row"><span>Processor</span><span class="stat-val">AMD Ryzen 7 7730U (16 vCPUs, 16 GB RAM)</span></div>
            <div class="stat-row"><span>Ray GCS / UI</span><span class="stat-val">Port 6379 / Port 8265</span></div>
            <div class="stat-row"><span>Unified ClothOS Hub</span><span class="stat-val">Port 8087 (SSE + Gateway Active)</span></div>
            <div class="stat-row"><span>Live Ports</span><span class="stat-val" id="ports-99-2">:8087 :6379 :8265 :11434</span></div>
        </div>

        <div class="card">
            <div class="card-title">Torque Sovereign Triage &amp; Vault</div>
            <div class="stat-row"><span>Delegation Mode</span><span class="stat-val">Dynamic Compute-Based</span></div>
            <div class="stat-row"><span>Guarded IP Terms</span><span class="stat-val">fouriersLibrary, VectorForge, Mycos</span></div>
            <div class="stat-row"><span>Cloud Arbitrage Limit</span><span class="stat-val">&gt;300s / &gt;65k Tokens</span></div>
            <div class="stat-row"><span>Local Force Tag</span><span class="stat-val">[LOCAL] / [SOVEREIGN]</span></div>
            <div class="stat-row"><span>Stream Rehydration</span><span class="stat-val">On-The-Fly Active</span></div>
        </div>
    </div>

    <div class="interactive-section" style="border-color: var(--breeze);">
        <div class="card-title">
            <span>SOVEREIGN UNIFIED NEXUS // Anthropic Drop-In (/v1/messages) &amp; Multi-Engine Verification</span>
            <span style="font-size: 12px; color: var(--breeze);">ANTHROPIC_BASE_URL=http://127.0.0.1:8087</span>
        </div>
        <div class="controls-bar">
            <button class="secondary" onclick="refreshUnifiedMesh()">Probe Unified Mesh</button>
            <button class="secondary" onclick="runSovereignAudit()">Run Constitutional + Deceit Audit</button>
            <button class="secondary" onclick="runTypemetricSync()">Run Dozenal Kuramoto Sync</button>
            <button class="secondary" onclick="runJitBench()">Run Bare-Metal ujit Kernel</button>
        </div>
        <div id="unified-mesh-grid" style="font-size: 12px; color: var(--text-dim); margin-bottom: 10px;">Probing ecosystem mesh...</div>
        <div class="output-box" id="nexus-output-box" style="min-height: 75px;">Ready. Click any Sovereign Nexus check above to verify Constitutional Gate, Dozenal Kuramoto, Z3/Topology, or x86-64 JIT execution.</div>
    </div>

    <div class="interactive-section">
        <div class="card-title">Hardware-Matched Model Recommender (MMLU / HumanEval Benchmarks)</div>
        <p style="font-size: 13px; color: var(--text-dim); margin-bottom: 12px;">
            Hardware profiling evaluates VRAM margins, memory bandwidth, and compute capabilities to recommend the highest benchmark model for this cluster.
        </p>
        <button class="secondary" onclick="loadRecommendations()" style="margin-bottom: 14px;">Refresh Recommendations</button>
        <div id="recs-table-container">Loading recommendations...</div>
    </div>

    <script>
        async function loadRecommendations() {
            const container = document.getElementById('recs-table-container');
            container.innerHTML = '<span style="color: var(--amethyst);">Analyzing cluster hardware benchmarks...</span>';
            try {
                const res = await fetch('/api/recommend');
                const recs = await res.json();
                let html = '<table class="table-recs"><thead><tr><th>Model</th><th>MMLU / Code</th><th>Hardware Fit</th><th>Speed (Est.)</th><th>Status</th><th>Rationale</th></tr></thead><tbody>';
                recs.forEach(r => {
                    const bench = `${r.benchmark.mmlu_score}% / ${r.benchmark.humaneval_coding}%`;
                    const status = r.is_installed ? '<span style="color: var(--green);">Installed</span>' : '<span style="color: var(--text-dim);">Available</span>';
                    html += `<tr>
                        <td style="font-weight: 700; color: #fff;">${r.preset.id}</td>
                        <td style="color: var(--amethyst);">${bench}</td>
                        <td style="color: #38bdf8;">${r.fit_status}</td>
                        <td style="color: var(--green);">${r.estimated_speed_tps.toFixed(1)} tps</td>
                        <td>${status}</td>
                        <td style="color: var(--text-dim);">${r.recommendation_reason}</td>
                    </tr>`;
                });
                html += '</tbody></table>';
                container.innerHTML = html;
            } catch (err) {
                container.innerHTML = `<span style="color: var(--red);">Error loading recommendations: ${err.message}</span>`;
            }
        }

        async function previewTriage() {
            const input = document.getElementById('prompt-input').value.trim();
            const badge = document.getElementById('routing-badge');
            const outBox = document.getElementById('output-box');
            if (!input) return;

            badge.innerHTML = '<span style="color: var(--amethyst);">Evaluating complexity heuristics...</span>';
            try {
                const res = await fetch('/api/triage/preview', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        prompt: input,
                        force_local: document.getElementById('sovereign-toggle').checked
                    })
                });
                const d = await res.json();
                const tierClass = d.tier.includes('Tier 1') ? 'tag-tier1' : (d.tier.includes('Tier 2') ? 'tag-tier2' : 'tag-tier3');
                badge.innerHTML = `<span class="tag ${tierClass}">${d.tier}</span> <span class="tag tag-tier1">Model: ${d.model_selected}</span> <span class="tag tag-tier2">${d.estimated_duration_seconds.toFixed(1)}s est</span>`;
                outBox.innerText = `[TRIAGE PREVIEW]\nSelected Model: ${d.model_selected}\nExecution Tier: ${d.tier}\nTarget Endpoint: ${d.target_endpoint}\nZero-Trust Scrubbing: ${d.is_scrubbed}\nReasoning: ${d.reasoning}`;
            } catch (err) {
                badge.innerHTML = `<span style="color: var(--red);">Triage error: ${err.message}</span>`;
            }
        }

        async function sendPrompt() {
            const input = document.getElementById('prompt-input').value.trim();
            const model = document.getElementById('model-select').value;
            const isStream = document.getElementById('stream-toggle').checked;
            const forceLocal = document.getElementById('sovereign-toggle').checked;
            const outBox = document.getElementById('output-box');
            const badge = document.getElementById('routing-badge');
            const pBar = document.getElementById('stream-progress');
            const pFill = document.getElementById('progress-fill');

            if (!input) return;

            outBox.innerText = 'Loom triaging compute and initiating execution...\\n';
            badge.innerHTML = '';
            pBar.style.display = 'block';
            pFill.style.width = '10%';

            const startTime = performance.now();
            let tokenCount = 0;

            try {
                const res = await fetch('/v1/chat/completions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        model: model,
                        messages: [{ role: 'user', content: input }],
                        stream: isStream,
                        force_local: forceLocal
                    })
                });

                const routeHdr = res.headers.get('X-Torque-Route') || 'Tier 1/2 Local';
                const modelHdr = res.headers.get('X-Torque-Model-Selected') || model;
                const scrubHdr = res.headers.get('X-Torque-Scrubbed') || 'false';
                const tierClass = routeHdr.includes('Tier 1') ? 'tag-tier1' : (routeHdr.includes('Tier 2') ? 'tag-tier2' : 'tag-tier3');

                if (isStream) {
                    outBox.innerText = '';
                    const reader = res.body.getReader();
                    const decoder = new TextDecoder();
                    let done = false;

                    while (!done) {
                        const chunk = await reader.read();
                        done = chunk.done;
                        if (chunk.value) {
                            const text = decoder.decode(chunk.value);
                            const lines = text.split('\\n');
                            for (const line of lines) {
                                if (line.startsWith('data: ') && line.trim() !== 'data: [DONE]') {
                                    try {
                                        const parsed = JSON.parse(line.slice(6));
                                        const delta = parsed.choices[0]?.delta?.content || '';
                                        if (delta) {
                                            outBox.innerText += delta;
                                            tokenCount++;
                                            pFill.style.width = `${Math.min(95, 10 + tokenCount * 1.5)}%`;
                                        }
                                    } catch (_) {}
                                }
                            }
                        }
                    }

                    pFill.style.width = '100%';
                    const elapsedSec = (performance.now() - startTime) / 1000.0;
                    const tps = (tokenCount / Math.max(0.001, elapsedSec)).toFixed(1);
                    badge.innerHTML = `<span class="tag ${tierClass}">${routeHdr}</span> <span class="tag tag-tier1">${modelHdr}</span> <span class="tag tag-tier2">Scrubbed: ${scrubHdr}</span> <span class="tag tag-tier1">${tps} tps</span>`;
                } else {
                    const data = await res.json();
                    pFill.style.width = '100%';
                    const tps = res.headers.get('X-Loom-Tokens-Per-Sec') || 'N/A';
                    badge.innerHTML = `<span class="tag ${tierClass}">${routeHdr}</span> <span class="tag tag-tier1">${modelHdr}</span> <span class="tag tag-tier2">Scrubbed: ${scrubHdr}</span> <span class="tag tag-tier1">${tps} tps</span>`;
                    outBox.innerText = data.choices && data.choices[0] ? data.choices[0].message.content : JSON.stringify(data, null, 2);
                }
            } catch (err) {
                outBox.innerText = 'Error: ' + err.message;
            } finally {
                setTimeout(() => { pBar.style.display = 'none'; pFill.style.width = '0%'; }, 1500);
            }
        }

        async function clusterAction(action) {
            const statusEl = document.getElementById('cluster-action-status');
            statusEl.innerText = `⚡ Executing '${action}' silently in background...`;
            statusEl.style.color = 'var(--yellow)';
            try {
                const res = await fetch('/api/cluster/action', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action })
                });
                const d = await res.json();
                statusEl.innerText = `✔ ${d.message || 'Cluster action dispatched'}`;
                statusEl.style.color = 'var(--clover)';
                setTimeout(refreshClusterPorts, 1200);
            } catch (err) {
                statusEl.innerText = `⚠ ${err.message}`;
                statusEl.style.color = 'var(--red)';
            }
        }

        async function refreshClusterPorts() {
            try {
                const res = await fetch('/api/cluster/status');
                const d = await res.json();
                const renderPorts = (obj) => Object.entries(obj || {}).map(([p, up]) =>
                    `<span style="color:${up ? 'var(--green)' : 'var(--red)'}; margin-right:6px;">●:${p}</span>`
                ).join('');
                if (d['192.168.99.1']) document.getElementById('ports-99-1').innerHTML = renderPorts(d['192.168.99.1']);
                if (d['192.168.99.2']) document.getElementById('ports-99-2').innerHTML = renderPorts(d['192.168.99.2']);
            } catch (_) {}
        }

        async function refreshUnifiedMesh() {
            const box = document.getElementById('unified-mesh-grid');
            try {
                const res = await fetch('/v1/sovereign/mesh');
                const d = await res.json();
                const badges = Object.entries(d.services || {}).map(([name, info]) => {
                    const color = info.online ? 'var(--green)' : 'var(--yellow)';
                    const dot = info.online ? '●' : '○';
                    return `<span class="tag tag-tier1" style="border-color:${color}; color:${color}; margin-bottom:4px;">${dot} ${name} (${info.endpoint})</span>`;
                }).join(' ');
                box.innerHTML = `<div style="margin-bottom:6px;">Services Online: <strong>${d.services_online}/${d.services_total}</strong> &bull; Ratchet Axioms: <strong>${d.ratchet_teeth_locked}</strong> &bull; JIT Kernels: <strong>${(d.ujit_kernels || []).length}</strong></div><div>${badges}</div>`;
            } catch (err) {
                box.innerText = 'Mesh probe error: ' + err.message;
            }
        }

        async function runSovereignAudit() {
            const input = document.getElementById('prompt-input').value.trim() || 'Synthesize verified ClothOS distributed compute schedule';
            const out = document.getElementById('nexus-output-box');
            const res = await fetch('/v1/sovereign/audit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action_intent: input, payload_or_claim: input, estimated_energy_joules: 12.0 })
            });
            out.innerText = JSON.stringify(await res.json(), null, 2);
        }

        async function runTypemetricSync() {
            const out = document.getElementById('nexus-output-box');
            const res = await fetch('/v1/sovereign/typemetric/sync', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ phases: [0, 768, 1536, 2304], omegas: [24, 42, 12, 36], trits: [1, 1, 1, 1], precisions: [1728, 1152, 864, 864], coupling_k: 24 })
            });
            out.innerText = JSON.stringify(await res.json(), null, 2);
        }

        async function runJitBench() {
            const out = document.getElementById('nexus-output-box');
            const res = await fetch('/v1/sovereign/jit/eval', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ kernel_name: 'grid_arbitrage', args: [1000, 15, 1] })
            });
            out.innerText = JSON.stringify(await res.json(), null, 2);
        }

        // Initial load & Enter key shortcut
        window.addEventListener('DOMContentLoaded', () => {
            loadRecommendations();
            refreshClusterPorts();
            refreshUnifiedMesh();
            setInterval(refreshClusterPorts, 5000);
            setInterval(refreshUnifiedMesh, 10000);
            const input = document.getElementById('prompt-input');
            if (input) {
                input.focus();
                input.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        sendPrompt();
                    }
                });
            }
        });
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard() -> str:
    """Serves the Loom Fabric Sovereign Web Dashboard."""
    return DASHBOARD_HTML


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Cluster and gateway health check."""
    return {
        "status": "healthy",
        "service": "loom-fabric-gateway",
        "version": "0.1.0",
        "timestamp": time.time(),
        "torque_guard_active": True,
    }


@app.get("/v1/models")
async def list_models() -> Dict[str, Any]:
    """OpenAI-compatible models enumeration endpoint."""
    presets = ModelRegistry.list_models()
    model_entries = []
    for p in presets:
        model_entries.append({
            "id": p.id,
            "object": "model",
            "created": 1700000000,
            "owned_by": "loom-fabric",
            "permission": [],
            "root": p.id,
            "parent": None,
            "details": {
                "display_name": p.display_name,
                "total_layers": p.total_layers,
                "default_context": p.default_context_length,
                "quant": p.quant_label,
                "size_mb": p.base_gguf_size_mb,
            },
        })
    return {"object": "list", "data": model_entries}


@app.post("/v1/chat/completions")
async def chat_completions(req: Request):
    """OpenAI-compatible chat completion endpoint supporting SSE streaming and Torque zero-trust routing."""
    telemetry = CompletionTelemetry()
    body_dict = await req.json()

    # 1. Normalize model name (strip provider prefix like 'loom-fabric/' or 'ollama/')
    raw_model = body_dict.get("model", "qwen2.5:32b")
    clean_model = raw_model.split("/", 1)[1] if "/" in raw_model else raw_model
    body_dict["model"] = clean_model

    # 2. Normalize messages so content is always a flat string
    # (prevents Ollama and backend 'format' errors with array/multimodal content)
    normalized_messages = []
    for m in body_dict.get("messages", []):
        if isinstance(m, dict):
            m_copy = dict(m)
            m_copy["content"] = ChatMessageDTO.normalize_content(m.get("content", ""))
            normalized_messages.append(m_copy)
        else:
            normalized_messages.append(m)
    body_dict["messages"] = normalized_messages

    # Parse into typed DTOs (Rust Struct equivalent)
    messages_dto = [
        ChatMessageDTO(
            role=m.get("role", "user") if isinstance(m, dict) else "user",
            content=m.get("content", "") if isinstance(m, dict) else str(m),
            name=m.get("name") if isinstance(m, dict) else None,
            tool_call_id=m.get("tool_call_id") if isinstance(m, dict) else None,
            tool_calls=m.get("tool_calls") if isinstance(m, dict) else None,
        )
        for m in body_dict.get("messages", [])
    ]
    payload = PromptPayload(
        model=clean_model,
        messages=messages_dto,
        temperature=float(body_dict.get("temperature")) if body_dict.get("temperature") is not None else 0.7,
        top_p=float(body_dict.get("top_p")) if body_dict.get("top_p") is not None else 0.95,
        max_tokens=int(body_dict.get("max_tokens") or body_dict.get("max_completion_tokens") or 4096),
        stream=bool(body_dict.get("stream", False)),
        force_local=bool(body_dict.get("force_local", False)),
    )

    # 1. Torque Complexity Routing & Model Triage Decision (Pillar 1)
    decision = torque_router.route(payload)

    # Dispatched model: triage dynamically based on compute needed
    dispatched_model = decision.model_name
    body_dict["model"] = dispatched_model

    # 2. Torque Zero-Trust Scrubbing if routing to Cloud Tier 3
    active_vault_map: Dict[str, str] = {}
    is_scrubbed = False

    if decision.tier == ExecutionTier.TIER_3_SOVEREIGN_CLOUD:
        # Scrub all messages through the local RehydrationVault
        scrubbed_messages = []
        for msg in payload.messages:
            scrub_res = torque_scrubber.tokenize_and_store(msg.content)
            scrubbed_messages.append({"role": msg.role, "content": scrub_res.scrubbed_text})
            active_vault_map.update(scrub_res.vault_token_map)
        body_dict["messages"] = scrubbed_messages
        is_scrubbed = len(active_vault_map) > 0

    target_url, provider_name = await gateway_router.determine_target_endpoint(
        dispatched_model, tier=decision.tier, cloud_url=decision.target_endpoint
    )

    # Build response headers
    base_headers = {
        "X-Torque-Route": decision.tier.value,
        "X-Torque-Model-Selected": dispatched_model,
        "X-Torque-Model-Requested": clean_model,
        "X-Torque-Scrubbed": str(is_scrubbed).lower(),
        "X-Torque-Reasoning": decision.reasoning,
        "X-Loom-Provider": provider_name,
    }

    if payload.stream:
        async def event_generator() -> AsyncIterator[str]:
            telemetry.mark_first_token()
            token_count = 0
            async for sse_chunk in gateway_router.stream_chat_completion(body_dict, target_url, provider_name):
                token_count += 1
                # If Tier 3 Cloud path, rehydrate SSE chunk on the fly before emitting
                if is_scrubbed and active_vault_map:
                    rehydrated_chunk = torque_scrubber.rehydrate(sse_chunk, active_vault_map)
                    yield rehydrated_chunk
                else:
                    yield sse_chunk

            telemetry.mark_completed(
                prompt_tokens=sum(len(m.content) for m in payload.messages) // 4,
                completion_tokens=token_count,
            )

        # Merge telemetry headers
        headers = {**base_headers, **telemetry.export_http_headers()}
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers=headers,
        )
    else:
        telemetry.mark_first_token()
        completion_data = await gateway_router.execute_non_streaming_completion(body_dict, target_url, provider_name)

        # Rehydrate final assistant message if scrubbed
        if is_scrubbed and active_vault_map:
            try:
                for choice in completion_data.get("choices", []):
                    msg_content = choice.get("message", {}).get("content", "")
                    if msg_content:
                        choice["message"]["content"] = torque_scrubber.rehydrate(msg_content, active_vault_map)
            except Exception:
                pass

        completion_tokens = completion_data.get("usage", {}).get("completion_tokens", 50)
        prompt_tokens = completion_data.get("usage", {}).get("prompt_tokens", 10)
        telemetry.mark_completed(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)

        headers = {**base_headers, **telemetry.export_http_headers()}
        return JSONResponse(content=completion_data, headers=headers)


@app.get("/metrics")
async def cluster_metrics() -> Dict[str, Any]:
    """Exposes cluster hardware, memory budgets, and node allocations."""
    hardware_state = profiler_instance.probe_cluster_state()
    return {
        "cluster_hardware": hardware_state.model_dump(),
        "active_models": [p.id for p in ModelRegistry.list_models()],
        "gateway_port": get_settings().endpoints.gateway_port,
        "vault_active_tokens": len(torque_scrubber.vault.snapshot()),
    }


@app.get("/api/recommend")
async def api_recommend() -> List[Dict[str, Any]]:
    """Analyzes hardware benchmarks and returns recommended model architecture fits."""
    from loom.models.recommender import ModelHardwareRecommender
    recommender = ModelHardwareRecommender()
    recs = recommender.evaluate_hardware_fit()
    return [r.model_dump() for r in recs]


@app.post("/api/triage/preview")
async def api_triage_preview(req: Request) -> Dict[str, Any]:
    """Evaluates prompt payload heuristics and returns execution triage decision without running."""
    body = await req.json()
    prompt = body.get("prompt", "")
    force_local = body.get("force_local", False)
    payload = PromptPayload(
        model="auto",
        messages=[ChatMessageDTO(role="user", content=prompt)],
        max_tokens=body.get("max_tokens", 4096),
        force_local=force_local,
    )
    decision = torque_router.route(payload)
    est_duration = torque_router.estimate_compute_duration_seconds(payload)
    return {
        "tier": decision.tier.value,
        "model_selected": decision.model_name,
        "is_scrubbed": decision.is_scrubbed,
        "estimated_duration_seconds": est_duration,
        "reasoning": decision.reasoning,
        "target_endpoint": decision.target_endpoint,
    }


@app.post("/api/models/pull")
async def api_pull_model(req: Request) -> Dict[str, Any]:
    """Downloads or pulls a recommended model locally."""
    body = await req.json()
    model = body.get("model", "qwen2.5:7b")
    from loom.models.recommender import ModelHardwareRecommender
    recommender = ModelHardwareRecommender()
    success = recommender.install_model_cli(model)
    return {"status": "success" if success else "failed", "model": model}


@app.get("/manifest.json")
async def pwa_manifest() -> Dict[str, Any]:
    """PWA Web App Manifest for installing Fabric across Windows, macOS, Linux, iOS, and Android."""
    return {
        "name": "Fabric // ClothOS Agentic Operating System",
        "short_name": "Fabric",
        "description": "Zero-Terminal Sovereign AI Compute Fabric (Loom · Stitch · Torque · ClothOS)",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#07120a",
        "theme_color": "#a855f7",
        "icons": [
            {
                "src": "https://cdn-icons-png.flaticon.com/512/2103/2103633.png",
                "sizes": "512x512",
                "type": "image/png",
            }
        ],
    }


@app.get("/v1/clothos/status")
def clothos_status() -> Dict[str, Any]:
    """Returns a Torque-scrubbed, frozen=True Pydantic v2 ClothOS state snapshot including DAG & Moltbook telemetry."""
    from loom.clothos.kernel import ClothOSKernel
    kernel = ClothOSKernel()
    snap = kernel.snapshot(probe_network=False)
    return json.loads(snap.model_dump_json())


@app.get("/v1/clothos/dag")
def clothos_dag_get(prompt: str = "Analyze ClothOS DAG & QCT routing", model: str = "auto", prefer_riscv: bool = False) -> Dict[str, Any]:
    """Evaluates a prompt through the Fabric QCTHybridRouter and returns the frozen QCTRouteDecision + DAGExecutionPlan."""
    from fabric.routing.router import QCTHybridRouter
    router = QCTHybridRouter()
    decision = router.route_query(prompt=prompt, requested_model=model, prefer_riscv=prefer_riscv)
    return json.loads(decision.model_dump_json())


@app.post("/v1/clothos/dag")
async def clothos_dag_plan(req: Request) -> Dict[str, Any]:
    """POST handler for /v1/clothos/dag."""
    body = await req.json()
    return clothos_dag_get(
        prompt=body.get("prompt", "Analyze ClothOS DAG & QCT routing"),
        model=body.get("model", "auto"),
        prefer_riscv=bool(body.get("prefer_riscv", False)),
    )


@app.api_route("/v1/clothos/moltbook/synergy", methods=["GET", "POST"])
def clothos_moltbook_synergy() -> Dict[str, Any]:
    """Executes a ClothOS + Moltbook R&D Wisdom Bridge synergy cycle and writes .agent/STATUS.md."""
    from loom.clothos.kernel import ClothOSKernel
    kernel = ClothOSKernel()
    status_path = kernel.sync_agent_status_markdown(probe_network=False)
    snap = kernel.snapshot(probe_network=False)
    return {
        "status": "synergy_synced",
        "status_file": str(status_path),
        "registration": json.loads(snap.registration.model_dump_json()),
        "hypotheses": [json.loads(h.model_dump_json()) for h in snap.active_hypotheses],
        "latest_dag": json.loads(snap.latest_route.dag.model_dump_json()),
    }


@app.get("/api/cluster/status")
async def api_cluster_status() -> Dict[str, Any]:
    """Probes live TCP ports across both 192.168.99.1 and 192.168.99.2."""
    from loom.gui import CrossPlatformClusterController
    ctrl = CrossPlatformClusterController()
    result: Dict[str, Dict[str, bool]] = {"192.168.99.1": {}, "192.168.99.2": {}}
    for port in [8087, 11434, 18789]:
        host1 = "127.0.0.1" if ctrl.self_ip == "192.168.99.1" else "192.168.99.1"
        result["192.168.99.1"][str(port)] = ctrl.is_port_open(host1, port, timeout=0.4)
    for port in [8087, 6379, 8265, 11434]:
        host2 = "127.0.0.1" if ctrl.self_ip == "192.168.99.2" else "192.168.99.2"
        result["192.168.99.2"][str(port)] = ctrl.is_port_open(host2, port, timeout=0.4)
    return result


@app.post("/api/cluster/action")
async def api_cluster_action(req: Request) -> Dict[str, Any]:
    """Executes windowless start, restart_both, or stop actions across the cluster."""
    import threading
    from loom.gui import CrossPlatformClusterController
    body = await req.json()
    action = body.get("action", "start")
    ctrl = CrossPlatformClusterController()

    if action == "start":
        threading.Thread(target=ctrl.ensure_local_services_alive, daemon=True).start()
        return {"status": "ok", "message": "Local services verified & started silently (zero terminals)."}
    elif action == "restart_both":
        def _restart_both():
            ctrl.ensure_local_services_alive()
            ctrl.trigger_peer_action("restart")
        threading.Thread(target=_restart_both, daemon=True).start()
        return {"status": "ok", "message": "Both machines healing & restarting in background."}
    elif action == "stop":
        threading.Thread(target=lambda: ctrl.sanitize_local_ports(ports=[8000, 8080, 18789]), daemon=True).start()
        return {"status": "ok", "message": "Auxiliary ports sanitized."}
    return {"status": "unknown_action", "message": f"Unknown action: {action}"}


# Mount OpenClaw Autonomic Bridge
from loom.gateway.openclaw_bridge import router as openclaw_router
app.include_router(openclaw_router)

# Mount Spotlight-Local Compute Service Provider (sL-CSP) Router
from loom.gateway.csp_router import router as csp_router
app.include_router(csp_router)

# Mount VectorCore CaaS and Sovereign Bank Router
from loom.gateway.caas_router import router as caas_router
app.include_router(caas_router)

# Mount Ollama Protocol Compatibility & Network Onboarding Bridge
from loom.gateway.ollama_bridge import router as ollama_bridge_router
app.include_router(ollama_bridge_router)

# Mount Loom Fabric Modem & Seamless Mesh Router ("Wi-Fi for Compute")
from loom.gateway.modem_router import router as modem_router
app.include_router(modem_router)

# Mount Anthropic Drop-In Messages API (/v1/messages) & Unified Sovereign Nexus (/v1/sovereign/*)
from loom.gateway.anthropic_bridge import anthropic_router, sovereign_router
app.include_router(anthropic_router)
app.include_router(sovereign_router)





