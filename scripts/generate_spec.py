#!/usr/bin/env python3
"""
Render ZeroFold's frozen design specification to a standalone HTML file.

This is the production-ready version of the throwaway snippet that started
this project: no hardcoded output path, real error handling, and a CLI you
can wire into a docs build instead of running by hand.

Usage:
    python3 scripts/generate_spec.py                       # writes docs/spec.html
    python3 scripts/generate_spec.py -o /tmp/spec.html      # custom output path
    python3 scripts/generate_spec.py --stdout               # print to stdout instead
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SPEC_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Zero Supervisor — Frozen System Specification</title>
<style>
  :root{
    --bg:#07111f;
    --panel:#0c1828;
    --panel2:#111f33;
    --line:#233954;
    --text:#edf4ff;
    --muted:#9db0c7;
    --accent:#7dc4ff;
    --good:#63d6a3;
    --warn:#ffd166;
    --bad:#ff7b7b;
  }
  *{box-sizing:border-box}
  body{
    margin:0;
    background:linear-gradient(180deg,#06101d,#091522 45%,#06101d);
    color:var(--text);
    font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    line-height:1.55;
  }
  .wrap{max-width:1180px;margin:auto;padding:32px 20px 80px}
  header{
    border:1px solid var(--line);
    background:linear-gradient(135deg,#0b1727,#10243b);
    border-radius:22px;
    padding:32px;
    box-shadow:0 20px 70px rgba(0,0,0,.28);
  }
  h1{font-size:clamp(2rem,5vw,4.3rem);line-height:1;margin:0 0 14px}
  h2{margin-top:46px;font-size:1.7rem}
  h3{margin-top:28px;font-size:1.15rem}
  p{color:#d7e2ef}
  .kicker{color:var(--accent);text-transform:uppercase;letter-spacing:.16em;font-weight:800;font-size:.78rem}
  .sub{font-size:1.06rem;max-width:900px;color:var(--muted)}
  .invariant{
    margin-top:22px;padding:18px 20px;border-left:4px solid var(--good);
    background:#0b221d;border-radius:12px;font-weight:800;color:#dffcef
  }
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
  .card{
    background:var(--panel);border:1px solid var(--line);border-radius:16px;
    padding:20px;
  }
  .card h3{margin-top:0}
  code,pre{
    font-family:"SFMono-Regular",Consolas,"Liberation Mono",monospace;
  }
  pre{
    white-space:pre-wrap;overflow:auto;background:#050b13;border:1px solid #1a2a3e;
    color:#dfeeff;border-radius:14px;padding:18px;
  }
  table{width:100%;border-collapse:collapse;background:var(--panel);border-radius:14px;overflow:hidden}
  th,td{padding:12px 14px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
  th{background:#102139;color:#fff}
  .tag{display:inline-block;border:1px solid var(--line);background:#0d1b2c;padding:4px 8px;border-radius:999px;color:var(--accent);margin:3px;font-size:.8rem}
  .good{color:var(--good)} .warn{color:var(--warn)} .bad{color:var(--bad)}
  .flow{
    background:#060d16;border:1px solid var(--line);border-radius:16px;padding:20px;
    font-family:"SFMono-Regular",Consolas,monospace;color:#dcecff
  }
  .small{font-size:.9rem;color:var(--muted)}
  nav{
    margin:18px 0 0;display:flex;gap:8px;flex-wrap:wrap
  }
  nav a{color:#dceeff;text-decoration:none;border:1px solid var(--line);padding:8px 10px;border-radius:10px;background:#0a1624}
  a{color:var(--accent)}
  .footer{margin-top:54px;color:var(--muted);font-size:.88rem;text-align:center}
</style>
</head>
<body>
<div class="wrap">

<header>
  <div class="kicker">Frozen Architecture Specification</div>
  <h1>Zero Supervisor</h1>
  <p class="sub">
    A full-duplex conservation wrapper for LLM systems that reduces token waste, preserves semantic fidelity,
    routes to the minimum capable model, distills evicted context into reusable semantic atoms, and continuously
    measures whether memory economically earns the right to survive.
  </p>
  <div class="invariant">
    No conservation optimization may silently change semantic state.
    If uncertainty exists, preserve more information or fall back.
  </div>
  <nav>
    <a href="#architecture">Architecture</a>
    <a href="#intake">Zero Intake</a>
    <a href="#conveyor">Memory Conveyor</a>
    <a href="#schema">Frozen Schema</a>
    <a href="#roi">ROI Loop</a>
    <a href="#routing">Complexity Routing</a>
    <a href="#output">Outbound Validator</a>
    <a href="#build">Build Order</a>
  </nav>
</header>

<section id="architecture">
<h2>1. System Architecture</h2>
<div class="flow">
USER / FILE / DATA
        ↓
ZERO SUPERVISOR — INTAKE
  relevance · PII · strip · prune · compress · fidelity
        ↓
COMPLEXITY FLOOR
  task difficulty · capability · risk · context size
        ↓
CHEAPEST CAPABLE MODEL
        ↓
AGENT
        ↓
ZERO SUPERVISOR — OUTPUT
  completion · evidence · focus · waste · contract
        ↓
USER

Meanwhile:
evicted context → Memory Conveyor → CNS Memory Core
future Zero Intake → compact atom retrieval → cheaper future inference
</div>
</section>

<section>
<h2>2. Component Boundaries</h2>
<div class="grid">
  <div class="card"><h3>CNS</h3><p><strong>Owns truth/state.</strong> Stores atoms, provenance, tiers, TTL, supersession, counters, and ROI substrate.</p></div>
  <div class="card"><h3>Zero Language</h3><p><strong>Owns representation.</strong> Canonical compact form, semantic roots, references, dictionary codec, and future machine-native syntax.</p></div>
  <div class="card"><h3>Navigation Layer</h3><p><strong>Owns finding.</strong> Bloom filter, fingerprint lookup, namespace index, local embeddings, similarity candidate generation.</p></div>
  <div class="card"><h3>Supervisor</h3><p><strong>Owns decisions.</strong> Relevance, compression, fidelity, model floor, promotion, TTL policy, output contracts, and fallback.</p></div>
</div>
</section>

<section id="intake">
<h2>3. Zero Intake — Pre-Agent Conservation Gate</h2>
<div class="flow">
RAW USER QUERY / FILE
    ↓
1. Security + PII gate
2. Relevance / intent extraction
3. Deterministic strip
4. Conversation pruning
5. Zero-language / canonical encoding
6. Reference substitution
7. Cheap semantic compression only if still needed
8. Fidelity gate
9. Intent classification
10. Output budget recommendation
11. Complexity floor
    ↓
LEAN TASK PACKET
    ↓
AGENT
</div>

<h3>Compression Modes</h3>
<table>
<tr><th>Mode</th><th>Meaning</th><th>Use</th></tr>
<tr><td>Z0</td><td>No semantic compression</td><td>Exact/legal/code/math/high-risk source fidelity</td></tr>
<tr><td>Z1</td><td>Structural cleanup only</td><td>Whitespace, duplicate formatting, safe normalization</td></tr>
<tr><td>Z2</td><td>Safe semantic compression</td><td>Ordinary user prompts</td></tr>
<tr><td>Z3</td><td>Aggressive semantic compression</td><td>Low-risk conversational or repetitive input</td></tr>
<tr><td>Z4</td><td>Reference/dictionary representation</td><td>Established concepts already defined in Zero/CNS</td></tr>
</table>

<h3>Fidelity Gate — RelAi Race</h3>
<pre>
compressed = cheap_model.compress(raw)

deterministic_diff = compare(
    entities,
    numbers,
    dates,
    negation,
    constraints,
    explicit decisions
)

if deterministic_diff fails:
    retry_or_fallback_raw()

else:
    fidelity_score = independent_model.score(
        original=raw,
        candidate=compressed,
        check="preserve every claim and constraint"
    )

    if fidelity_score >= threshold:
        dispatch(compressed)
    elif retries_remaining:
        retry_with_failure_feedback()
    else:
        dispatch(raw)
</pre>
<p class="small">
The fidelity checker must not be the same model that produced the compression.
</p>
</section>

<section id="routing">
<h2>4. Complexity Estimator</h2>
<p>
The existing router price/quality strategy receives a <strong>minimum capability floor</strong> rather than guessing from price tier alone.
</p>
<pre>
complexity_score = f(
    task_difficulty,      # reuse intake intent classifier
    required_capability,  # code/reasoning/longform floor
    risk,                 # destructive action / user-facing factual claim
    context_size          # post-prune tokens
)

min_capable_model = smallest_model_meeting(complexity_score)
route_from(min_capable_model)
</pre>
<div class="card">
<strong>Principle:</strong> free deterministic work first → cache/reference second → small/local model third → expensive reasoning last.
</div>
</section>

<section id="conveyor">
<h2>5. Memory Eviction Conveyor</h2>
<p>
The pruner no longer simply drops old turns. It safely converts potentially durable information into reusable semantic assets before eviction.
</p>
<div class="flow">
OLD TURN / OLD SEGMENT
    ↓
RELEVANCE GATE — deterministic, no LLM
    ├─ NO → discard
    └─ YES
         ↓
SEGMENT RESOLVER
  merge related turns into final durable state
         ↓
DEDICATED STEP ZERO DISTILLER
  facts · decisions · commitments · constraints
  discard pleasantries · retries · dead ends
         ↓
DETERMINISTIC FIDELITY CHECK
         ↓
SEMANTIC ATOMS
         ↓
CANONICAL STRUCTURE + FINGERPRINT
         ↓
BLOOM FILTER
    ├─ definitely absent → new atom write path
    └─ maybe present
          ↓
       indexed fingerprint lookup
          ↓
       local embedding similarity
          ↓
       hard polarity / constraint verification
          ├─ true duplicate → reinforce existing
          ├─ contradictory update → NEW atom supersedes OLD
          └─ different meaning → NEW atom
         ↓
CNS
         ↓
RAW TURN DROPPED FROM ACTIVE CONTEXT
</div>

<h3>Why Segments, Not Every Turn</h3>
<p>
Six conversational turns may resolve to one durable state. Distilling each turn separately creates overlapping memory.
The Conveyor should compact related turns first, then extract the final semantic state.
</p>
</section>

<section>
<h2>6. Semantic Atom Canonical Shape</h2>
<pre>
subject
predicate
object
polarity
scope
time
confidence
source_refs[]
flags
</pre>
<p>
The inner representation may later become a compact Zero Language or integer-referenced constant pool.
Human-readable language is an interface, not a storage requirement.
</p>

<h3>Two Hashes</h3>
<pre>
source_hash = sha256(canonical_raw_source)
object_id   = sha256(canonical_semantic_atom)
</pre>
<p>
The source hash prevents reprocessing the exact same source. The object hash identifies a canonical distilled object.
</p>
</section>

<section>
<h2>7. Duplicate / Reinforcement Safety</h2>
<p>Embedding similarity generates candidates only. It may never silently merge truth.</p>
<pre>
candidate = similarity_search(atom)

if polarity_mismatch(candidate, atom):
    create_new_atom()
    new_atom.supersedes_id = candidate.object_id
    candidate.superseded_at = now()
    candidate.expires_at = accelerated_decay()
elif constraints_compatible(candidate, atom):
    reinforce(candidate)
else:
    create_new_atom()
</pre>

<p>
A historical fact may remain true historically even after a new fact supersedes its current applicability.
Supersession preserves provenance instead of deleting history.
</p>
</section>

<section id="schema">
<h2>8. Frozen CNS Schema</h2>
<pre>
CREATE TABLE cns_atom (
    object_id               TEXT PRIMARY KEY,
    namespace               TEXT NOT NULL,
    tier                    TEXT DEFAULT 'episodic',
    value                   BLOB,
    flags                   INTEGER DEFAULT 0,
    source_refs             TEXT,

    retrieval_count         INTEGER DEFAULT 0,
    reinforcement_count     INTEGER DEFAULT 0,

    tokens_saved_total      INTEGER DEFAULT 0,
    production_cost_tokens  INTEGER,
    dedup_cost_tokens       INTEGER DEFAULT 0,

    production_cost_usd     REAL,
    retrieval_savings_usd   REAL DEFAULT 0,

    payback_count           INTEGER,
    payback_achieved        INTEGER DEFAULT 0,

    last_accessed           TEXT,
    last_confirmed          TEXT,

    expires_at              TEXT,
    created_at              TEXT DEFAULT CURRENT_TIMESTAMP,

    supersedes_id           TEXT REFERENCES cns_atom(object_id),
    superseded_at           TEXT
);

CREATE INDEX idx_atom_namespace ON cns_atom(namespace);
CREATE INDEX idx_atom_tier ON cns_atom(tier);
CREATE INDEX idx_atom_expires ON cns_atom(expires_at);
CREATE INDEX idx_atom_supersedes ON cns_atom(supersedes_id);
</pre>

<h3>Namespace Policy Table</h3>
<pre>
CREATE TABLE cns_namespace_policy (
    namespace               TEXT PRIMARY KEY,
    extraction_threshold    REAL DEFAULT 0.5,
    promotion_reinforce_n   INTEGER DEFAULT 2,
    avg_payback_achievers   REAL,
    payback_rate            REAL,
    total_atoms_created     INTEGER DEFAULT 0,
    updated_at              TEXT
);
</pre>

<h3>Bitpacked Flags</h3>
<pre>
FLAG_EXPLICIT_USER_RULE = 1 << 0
FLAG_CONFIRMED          = 1 << 1
FLAG_HIGH_IMPORTANCE    = 1 << 2
FLAG_SUPERSEDED         = 1 << 3   # optional convenience flag
</pre>
</section>

<section id="roi">
<h2>9. Live Per-Atom ROI</h2>
<p>Memory must prove that it earns the right to exist.</p>

<pre>
roi_tokens =
    tokens_saved_total
    - production_cost_tokens
    - dedup_cost_tokens

roi_usd =
    retrieval_savings_usd
    - production_cost_usd
</pre>

<h3>Payback Crossing Event</h3>
<pre>
running_savings = tokens_saved_total

on successful retrieval:
    retrieval_count += 1
    tokens_saved_total += avoided_tokens
    retrieval_savings_usd += avoided_cost

    if payback_achieved == FALSE
       and tokens_saved_total >= production_cost_tokens + dedup_cost_tokens:

        payback_count = retrieval_count
        payback_achieved = TRUE
</pre>
<p>
<code>payback_count</code> freezes at the crossing event and is never rewritten.
</p>

<h3>Namespace Health</h3>
<table>
<tr><th>Metric</th><th>Definition</th><th>Meaning</th></tr>
<tr><td>avg_payback_achievers</td><td>Average payback_count only where payback_achieved=TRUE</td><td>How quickly successful atoms pay back</td></tr>
<tr><td>payback_rate</td><td>achievers / total_atoms_ever_created</td><td>How often atoms in this namespace ever become worthwhile</td></tr>
</table>

<p>
A namespace with average payback 1.4 but a 10% payback rate may be worse than one with average payback 3.2 and a 70% payback rate.
The extraction gate should learn primarily from <strong>rate plus ROI</strong>, not speed alone.
</p>
</section>

<section>
<h2>10. Closed Learning Loop</h2>
<div class="flow">
TURN CONSIDERED FOR EVICTION
        ↓
NAMESPACE HISTORY
  payback_rate · avg_payback · roi
        ↓
ADAPTIVE EXTRACTION THRESHOLD
        ↓
ATOM PRODUCED OR DISCARDED
        ↓
RETRIEVAL / REINFORCEMENT
        ↓
LIVE ROI + PAYBACK CROSSING
        ↓
PROMOTION / TTL / DECAY
        ↓
DAILY NAMESPACE POLICY RECOMPUTE
        ↺
</div>

<p>
Retrieval and reinforcement are structurally different:
</p>
<pre>
retrieval_count     = memory was used
reinforcement_count = new evidence independently restated or confirmed it
</pre>
<p>
Popularity must never masquerade as truth.
</p>
</section>

<section>
<h2>11. Promotion Rules</h2>
<pre>
promote_to_long_term if:

    explicit_user_rule
    OR reinforcement_count >= promotion_reinforce_n
    OR (high_importance AND confirmed)

otherwise:
    remain episodic
    decay via TTL policy
</pre>

<p>
Unreferenced episodic atoms that never achieve payback should decay more aggressively.
Namespace policy may raise the extraction threshold when low-value atoms consistently fail to pay back.
</p>
</section>

<section>
<h2>12. Bloom + Fingerprint + Local Similarity</h2>
<pre>
ATOM
 ↓
canonical fingerprint
 ↓
Bloom filter
 ├─ DEFINITELY ABSENT → skip DB duplicate lookup → write
 └─ MAYBE PRESENT
        ↓
    indexed fingerprint lookup
        ↓
    candidate object_ids
        ↓
    local embedding similarity
        ↓
    polarity/constraint hard gate
        ↓
    reinforce / supersede / create
</pre>
<p>
Bloom filters have false positives but no false negatives, which is the safe failure direction here.
They are membership tests, not candidate retrieval systems.
</p>
</section>

<section>
<h2>13. Compression Strategy</h2>
<div class="grid">
  <div class="card">
    <h3>Day-One</h3>
    <p>Canonical semantic atoms, references, hashes, normal SQLite storage, and compact value encoding.</p>
  </div>
  <div class="card">
    <h3>Scale-Triggered</h3>
    <p>Shared zstd dictionaries trained on actual atom corpora; optionally one dictionary per namespace class.</p>
  </div>
</div>

<p>
Per-message zlib/gzip is not preferred for tiny atoms because fixed compression overhead can erase or reverse gains.
Shared dictionary compression is better suited to repeated short semantic structures.
</p>
</section>

<section>
<h2>14. Future Zero Language</h2>
<p>
Zero Language is a machine-oriented semantic intermediate representation, not “English with vowels removed.”
It should encode semantic meaning through reusable primitives, positional schemas, references, deltas, and macros.
</p>

<pre>
Human:
"External AI systems must be verified before authority is granted."

Possible Zero IR:
RULE|EXT_AI|TRUST=UNVERIFIED|VERIFY>AUTH

Later with dictionary refs:
R7|@E4|T0|V>A
</pre>

<p>
Principle:
<strong>store only the minimum state required to reproduce the same correct behavior.</strong>
</p>
</section>

<section>
<h2>15. Outbound Supervisor</h2>
<div class="flow">
AGENT RESULT
   ↓
completion check
evidence / unsupported-claim check
repetition detector
output contract check
requested format check
token budget check
   ↓
PASS → USER
FAIL → targeted delta correction only
</div>

<pre>
Example correction:
FIX:citation:claim_3

Do not regenerate the entire answer
when one local defect can be repaired.
</pre>
</section>

<section id="output">
<h2>16. Output Contract</h2>
<pre>
ANSWER:
detail=2
repeat=0
preface=0
evidence=required
max_tokens=<task-specific>
format=<requested format>
</pre>
<p>
The goal is not to generate a bloated answer and compress it afterward.
The goal is to prevent unnecessary tokens from being generated in the first place.
</p>
</section>

<section>
<h2>17. Reusable Existing SubtracToken Components</h2>
<div class="grid">
  <div class="card"><h3>Keep</h3><p>PII-first ordering, budget enforcement, provider fallback, request hashing, usage/savings logs, intent classifier, output caps.</p></div>
  <div class="card"><h3>Extend</h3><p>Optimizer pipeline, semantic compressor, pruner, route planner.</p></div>
  <div class="card"><h3>Add</h3><p>Fidelity gate, complexity floor, Conveyor, semantic atoms, CNS object interface, ROI tuning, supersession, output validator.</p></div>
</div>
</section>

<section>
<h2>18. Existing CNS Upgrades</h2>
<table>
<tr><th>Upgrade</th><th>Decision</th></tr>
<tr><td>Redis L1 cache</td><td class="good">Adopt now</td></tr>
<tr><td>Working / episodic / long-term tiers</td><td class="good">Adopt now</td></tr>
<tr><td>TTL sweep</td><td class="good">Adopt now</td></tr>
<tr><td>Namespace index / scoped load</td><td class="good">Adopt now</td></tr>
<tr><td>Live ROI counters</td><td class="good">Adopt now</td></tr>
<tr><td>Bloom precheck</td><td class="good">Adopt now</td></tr>
<tr><td>Polarity / constraint gate</td><td class="good">Mandatory</td></tr>
<tr><td>Shared zstd dictionary</td><td class="warn">Scale-triggered</td></tr>
<tr><td>String pool / interning</td><td class="warn">Scale-triggered</td></tr>
<tr><td>Real trie</td><td class="warn">Profile first</td></tr>
<tr><td>Vector database</td><td class="warn">Defer until measured need</td></tr>
<tr><td>Custom varints</td><td class="bad">Skip</td></tr>
<tr><td>SQLite page compression</td><td class="bad">Skip</td></tr>
</table>
</section>

<section id="build">
<h2>19. Frozen Build Order</h2>
<pre>
1. CNS schema / state foundation
2. Atom format + provenance
3. Memory Eviction Conveyor
4. Dedup + polarity + supersession safety
5. Live ROI + payback loop
6. Zero Supervisor intake
7. Complexity routing
8. Outbound validator
9. Scale-triggered optimizations
</pre>
</section>

<section>
<h2>20. Day-One vs Scale-Triggered</h2>
<div class="grid">
<div class="card">
<h3>Day-One Load-Bearing</h3>
<p>
CNS schema, tiers, TTL, provenance, atoms, relevance gate, dedicated distiller,
fidelity validation, Bloom + fingerprint index, local similarity, polarity gate,
reinforcement, supersession, live ROI, payback crossing, complexity floor, Supervisor
intake, output contract, outbound validator.
</p>
</div>
<div class="card">
<h3>Scale-Triggered</h3>
<p>
Shared zstd dictionaries, namespace-specific dictionaries, string pools, integer
interning, true trie structures, ANN/vector infrastructure, binary sync formats,
advanced constant-pool encoding.
</p>
</div>
</div>
</section>

<section>
<h2>21. Core Conservation Laws</h2>
<div class="card">
<span class="tag">Never store twice if a reference can recreate it.</span>
<span class="tag">Never decode until needed.</span>
<span class="tag">Free deterministic work before paid inference.</span>
<span class="tag">Reuse before recompute.</span>
<span class="tag">Compress before expensive cognition.</span>
<span class="tag">Constrain during cognition.</span>
<span class="tag">Compact after cognition.</span>
<span class="tag">Expand only at the human boundary.</span>
<span class="tag">Popularity is not truth.</span>
<span class="tag">Historical truth is not deleted by current truth.</span>
<span class="tag">Memory must prove durable value relative to preservation cost.</span>
</div>
</section>

<section>
<h2>22. Product-Level Definition</h2>
<div class="card">
<p><strong>Zero Supervisor</strong> is a conservation wrapper that protects the user's intent, logic, compute, and cost without taking over the agent's reasoning.</p>
<p><strong>Zero Memory</strong> does not preserve information because it merely appears important. It preserves information that demonstrates durable semantic value relative to the cost of keeping and reusing it.</p>
<p><strong>Compounding behavior</strong> exists only where reuse value exceeds production cost and is proven through per-atom ROI and payback metrics.</p>
</div>
</section>

<section>
<h2>23. Acceptance Test for Every Future Feature</h2>
<div class="invariant">
  If a proposed optimization cannot demonstrate that it preserves semantic state under ambiguity,
  it does not ship — regardless of projected efficiency gain.
</div>
</section>

<div class="footer">
Zero Supervisor — Frozen Design Specification · 2026
</div>

</div>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "docs" / "spec.html",
        help="Output file path (default: docs/spec.html relative to the repo root)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print the rendered HTML to stdout instead of writing a file",
    )
    args = parser.parse_args()

    if args.stdout:
        sys.stdout.write(SPEC_HTML)
        return 0

    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(SPEC_HTML, encoding="utf-8")
    except OSError as e:
        print(f"error: could not write {args.output}: {e}", file=sys.stderr)
        return 1

    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
