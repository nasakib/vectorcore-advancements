# ClothOS System Guide (Plain-English Edition)

Everything runs through **one unified address**: `http://127.0.0.1:8087/`

---

## 1. Quick Start

| Action | How to Do It |
| :--- | :--- |
| **Start the System** | Double-click **ClothOS System Starter** on your Desktop (`ClothOS System Starter.lnk`). It starts Ollama (`:11434`) and ClothOS (`:8087`) safely and opens your browser. |
| **Carry One Goal Across Tools** | Type your project/question in **Current Task** at the top, click **Save Task**, then use **Send to** (`AI Prompt`, `3D CAD`, `Media`, `Chemistry`, `Safety Check`). |
| **Check System Health** | Open **Step 5 → System & Ports** (`Hardware Monitor` & `Network Ports (:8087)`). |

---

## 2. Capabilities Grouped by Stage

### Step 1 — Ask & Run (`Chat & Commands`)
- **AI Chat & Model Router**: Talk to local AI models (Ollama on your RTX 3060) or route larger tasks across your 2-PC cluster.
- **Privacy Filter**: Automatically masks sensitive details (keys, personal info) before any external request leaves your PC.
- **Terminal & Files**: Run shell commands and browse/manage workspace files inside the dashboard.

### Step 2 — Research & Explore (`Research & Notes`)
- **Topic Map & File Vault**: Searches and maps your local research notes and markdown deliverables.
- **Gap Finder & State Monitor**: Highlights missing links or open questions in your notes.

### Step 3 — Build & Design (`3D CAD, Media & Lab`)
- **3D CAD Studio**: Generates parametric 3D solid parts (heat exchangers, brackets, resonators, lattices) with live 3D inspection and **`.stl` / `.step`** export.
- **Media Studio, Chemistry Lab & Circuit Designer**: Create visual media, inspect molecular properties, and design circuits from your active task.

### Step 4 — Safety & Checks (`Safety & Audit`)
- **Safety Check & Audit Log**: Verifies outputs against safety rules and keeps a tamper-evident log of actions.
- **Usage Limits & Energy/Health**: Tracks resource quotas and system operating bounds.

### Step 5 — Hardware & Network (`System & Ports`)
- **Hardware Monitor**: Auto-discovers and streams live CPU, RAM, and GPU stats (RTX 3060 via NVML, RX 580 via Windows PDH + AMD ADL, plus Node 2 when online).
- **Running Processes & Network Ports (:8087)**: Shows active cluster processes and live port status for Node 1 and Node 2.

---

## 3. The 24/7 Compute Cycle (How to Use It Effectively)

Your system is organized around a **Daytime Interactive / Night-time Background** rhythm:

| Time of Day | Primary Mode | What Runs Where | What You Should Do |
| :--- | :--- | :--- | :--- |
| **Morning** | Review & Sync | **System Controls → Daily Summary** | Review overnight findings, new notes, and completed sweeps before starting your day. |
| **Daytime (Active Work)** | Interactive & Low-Latency | **GPU 0 (RTX 3060)** handles your live prompts & 3D CAD; **Zero-OOM Auto-Preemption** pauses background sweeps automatically when you send a prompt. | Use **Current Task** + **Steps 1–3** (`AI Chat`, `3D CAD Studio`, `Media`, `Research`). |
| **Night-time / Idle** | 24/7 Autonomous Batch (`continuous_worker.py`) | **GPU 0 (RTX 3060)** generates/refines ideas; **GPU 1 (RX 580)** runs parallel numerical sweeps concurrently; **Node 2** assists via Ray when awake. | Leave the PC and **Node 2** awake on the network so overnight sweeps and indexing finish before morning. |

---

## 4. Two-PC Cluster Roles

| Machine | Role | Hardware | Key Ports |
| :--- | :--- | :--- | :--- |
| **Node 1 (This PC — `skyTech-Worker`)** | Primary Hub, Interactive UI, 3D CAD, Fast Local AI | NVIDIA RTX 3060 (12 GB) + AMD RX 580 (8 GB) | `:8087` (Unified UI), `:11434` (Ollama) |
| **Node 2 (`WIN-7CMAQLVP8MV`)** | Distributed Worker & Cross-Validation | Ryzen 7 + AMD Radeon Graphics + Ray Head | `:8087` (Peer UI), `:6379` (Ray GCS), `:8265` (Ray Dashboard) |

*Tip: Whenever you update code on Node 1 and Node 2 is awake, run `python -m loom.fabric.node2_sync` from `c:\Users\natsa\Documents\loom-fabric` to push the latest build to Node 2.*
