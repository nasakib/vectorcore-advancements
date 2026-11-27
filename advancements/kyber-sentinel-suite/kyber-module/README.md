# Kyber-Module-Leviathan: Post-Quantum Lattice Cryptography & Verification Suite

> **Corporate Division:** VectorCore Infrastructure & Specialized Deep-Tech Labs  
> **Parent Entity:** VectorCore Holdings, LLC (Georgia LLC)  
> **Role:** Post-quantum cryptographic simulation, CRYSTALS-Kyber (ML-KEM) key exchange, and mathematical security verification.  

---

## 1. Overview & Architectural Role

`kyber-module-leviathan` is the post-quantum cryptographic security lab for VectorCore Holdings. Built with **React 19, TypeScript 5.7, Vite 6, and Supabase**, it provides an interactive mathematical playground and verification harness for **lattice-based cryptography**—specifically the NIST-standardized **CRYSTALS-Kyber (ML-KEM)** key encapsulation mechanism.

```
[Quantum Decryption Threat Horizon]
                  │
                  ▼
    [kyber-module-leviathan]
├── Learning-with-Errors (LWE) Module Lattices
├── KaTeX Mathematical Formulation
└── Supabase Cloud State Synchronization
                  │
                  ▼
[Post-Quantum Shield for VectorCore & Spotlight-Local]
```

### Core Capabilities
1. **Lattice-Based Key Encapsulation:** Visualizes and executes Module Learning-with-Errors (M-LWE) problems that remain cryptographically intractable even for Shor's algorithm on quantum computers.
2. **Interactive Mathematical Exposition:** Renders high-precision KaTeX polynomial ring formulas ($\mathbb{R}_q = \mathbb{Z}_q[X]/(X^n + 1)$) for cryptographic auditing.
3. **Cloud State & Collaboration:** Supabase integration for persisting cryptographic keys, session transcripts, and proof artifacts.

---

## 2. Directory Structure

```
kyber-module-leviathan/
├── src/
│   ├── components/             # React 19 UI components & interactive lattice visualizers
│   ├── context/                # Cryptographic session & auth state providers
│   ├── lib/                    # Supabase client & mathematical helper utilities
│   ├── services/               # Cloud sync, community proofs, and key exchange services
│   ├── types/                  # TypeScript interfaces for Kyber parameters (512, 768, 1024)
│   ├── utils/                  # Polynomial arithmetic and NTT transform utilities
│   ├── App.tsx                 # Main application dashboard
│   └── main.tsx                # React root entrypoint
├── supabase/                   # Database migrations and schema definitions
├── package.json                # Project dependencies (React 19, Vite, KaTeX, Supabase)
└── README.md                   # This project manifest & roadmap
```

---

## 3. How to Run & Build

```bash
# Install dependencies
npm install

# Run the local Vite development server
npm run dev

# Build production bundle
npm run build
```

---

## 4. Role in VectorCore Holdings

* **Security Backbone:** As classical RSA and elliptic-curve cryptography (ECC) become vulnerable to quantum decryption, `kyber-module-leviathan` provides the reference implementations that will harden VectorCore's inter-node Fabric RPC and Spotlight-Local's financial ledger against future state-level decryption capabilities.

---

## 5. Next Steps & Tactical Roadmap

- [ ] **WebAssembly (WASM) Kyber-768 Core:** Compile a C/Rust reference implementation of ML-KEM-768 into WebAssembly for client-side sub-millisecond key encapsulation.
- [ ] **Direct Integration with `mycos`:** Implement Kyber-encrypted handshake tokens for wearable telemetry data packets.
- [ ] **Avatar Carryable Key Injection:** Research provisioning pre-shared post-quantum lattice keys into physical NFC Avatar Carryables.
