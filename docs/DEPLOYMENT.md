# Deployment & full-loop evidence — Guarded Stop (phase 3)

> **Repo layout note (added when assembling this public repo):** this log
> was written against the original working folder. In this repo the
> contracts live in `contracts/`, the AI service in `ai-service/`, and
> `deployment.json` + the `evidence-*.json` files sit next to this
> document in `docs/`. The deploy driver `ops/run_phase3.py` was a local
> operations script (it reads the deployer key from a gitignored wallet
> file at runtime) and is intentionally **not** included in this repo;
> the deployment steps it executed are described in §2 and in the root
> README.

> Status as of **2026-11-16**: ✅ **COMPLETE.** All four contracts are
> deployed (Lasna + Base Sepolia, Sourcify-verified), and both demo acts
> ran end-to-end on testnet with full on-chain evidence:
> **wick → AI VETO → position kept** (order 3) and
> **trend → AI EXECUTE → callback sell executed** (order 6).
> Getting here took six act attempts; the failed ones (orders 1, 2, 4, 5)
> are documented honestly in §4 — two of them turned into unplanned but
> real demonstrations of the fail-safe and stale-decision guards.

Testnet deployer wallet (public address): `0xa1b25c5A83Bc5FAe2Ddd3EB94412C3971a54F425`
(testnet only — never send mainnet funds to it.)

Final balances after the runs (checked 2026-11-16): wallet ≈ 0.53 lREACT
(Lasna) / ≈ 0.017 Base Sepolia ETH / ≈ 0.04 Sepolia ETH;
GuardedStopReactive holds ≈ 4.49 lREACT; StopExecutor holds just under
0.01 Base Sepolia ETH (minus callback execution costs).

---

## 1. Funding — resolved

Goal amounts were ≥ 0.11 Sepolia ETH (0.1 ETH → lREACT exchange + gas)
and ≥ 0.02 Base Sepolia ETH. How each leg actually landed:

| Leg | Route | Evidence |
|---|---|---|
| Sepolia ETH | **pk910 PoW faucet** (sepolia-faucet.pk910.de) — the one route from the §1 survey that a human browser session could complete (captcha + in-browser mining). Programmatic routes remain gated as surveyed below. | Wallet funded with **0.17 Sepolia ETH**; balance verified on-chain via `cast balance` before use. |
| lREACT | Reactive faucet contract `0x9b9BB25f1A81078C544C829c5EB7822d747Cf434`, `request(wallet)` with 0.1 ETH (1 ETH → 100 lREACT) | Exchange tx `0x6cce6735b087e4ae4cbdb2c326585d020212f895c3fe6c49aed1f131a051e6c3`; Lasna balance after: **10.5 lREACT**. |
| Base Sepolia ETH | **Official bridge, contract path**: `OptimismPortal.depositTransaction(wallet, 0.03 ETH, …)` on Sepolia — portal `0x49f53e41452C74589E85cA1677426Ba426459e85` and L1StandardBridge `0xfd0Bf71F60660E2f608ed56e1659C450eB113120`, both taken from docs.base.org "Contract Addresses" (Ethereum Testnet (Sepolia) section) | L1 deposit tx `0x764d1a0dbd26f9218e2b651234aa4eb4ed4e70508c893cd86f47f704c1d55e7e`; **0.03 ETH** credited on Base Sepolia ≈ 5 min later (note: some public RPC backends served a stale 0 balance for several minutes after the credit — see §4). |

### Faucet survey (2026-11-16, historical — why pk910 was the route)

| # | Route | Result |
|---|---|---|
| 1 | pk910 PoW faucet | ✅ Worked **with a human in a real browser** (custom captcha gates session start; mining itself is CPU-feasible). Headless API clients cannot open a session. |
| 2 | QuickNode faucet (Sepolia + Base Sepolia) | ⛔ Bot check on the claim step; no public unauthenticated claim API. |
| 3 | Chainlink faucet | ⛔ Cloudflare Turnstile + interactive wallet-connect; no API path. |
| 4 | Alchemy faucet | ⛔ Eligibility requires ≥ 0.001 ETH *mainnet* balance + history; fresh wallet ineligible. |
| 5 | Google Cloud Web3 faucet | ⛔ Requires Google account sign-in. |
| 6 | Coinbase CDP / Superchain faucets | ⛔ Account sign-in required. |
| 7 | Bware / Stakely | ⛔ Hosts unreachable from this VM's egress; also captcha/social gated historically. |
| 8 | thirdweb universal faucet | ⛔ No chain page for Lasna (5318007); Kopli faucet is a retired network. |

---

## 2. Deployment (executed 2026-11-16)

Deployment order follows the Omni cycle-breaking order (origin contracts
→ Reactive → callback → setters), driven by `ops/run_phase3.py deploy`
plus a resume script after the first run died at the executor-funding
step (see §4 for the runner bugs found and fixed along the way).

| Contract | Chain | Address | Deploy tx |
|---|---|---|---|
| MockPool | Base Sepolia (84532) | `0x61E94433Ea4B03185c8272CC4D4B0F537C89528c` | `0x780346772080f8cb74a530eceaa8c30e3bc8884513baa06c06831f281b2e4fcc` |
| AISignal | Base Sepolia (84532) | `0xe194670A23B15a748c12c9dEA510B93F3bdd46C0` | `0x9f38e1c05e5d1db8e4bd475075cdd211e62c16d3714ed084f6d67a0b9436f8a4` |
| GuardedStopReactive | Lasna (5318007) | `0x74797ad794C71D7f58d0a0109192fc83AAb5fE3A` | `0xe816f596abffc57b1229543d8fc05d02c2eaca21e970f5cd0f53384c623bcdc3` |
| StopExecutor | Base Sepolia (84532) | `0x098D7c8f80F699508be44B1145D41394faD17cDe` | `0xa12bb9719b22e507e650a90a007ba3991936052e8b30ef6e1fa82068f4ff2f72` |

Wiring & funding txs:

- GuardedStopReactive initial funding: **5.25 lREACT** (sent with the
  deploy tx); top-up of **+4.5 lREACT** after the §4 debt incident:
  `0x03daacac6ca66647571a0c77692c9b49a32a9e263b8291fb442af8ce5a2070c6`;
  `coverDebt()` (settled ≈ 0.0142 lREACT):
  `0xffee6d587f0ada6ad64e20b02febb6fd55771f819cd4a4d7d0cbbd4684622920`.
- StopExecutor funding: **0.01 Base Sepolia ETH**,
  tx `0x6408a73453dc03ed0c0ab14c5715c16e9df5a52fbcdde2c3e895dd31f55dfa40`.
- `GuardedStopReactive.setExecutor(StopExecutor)` (Lasna):
  `0xbb93dc0678cea3e30236cf3cfa2950e7820d1f7d4cdb2e0175224c7b6066fd6b`.
- `MockPool.setExecutor(StopExecutor)` (Base Sepolia):
  `0xe87ec22d9f6a6f0fd4c3bf980cffad6856955ca8b621bb9526212cd079ad2d68`.
- Base Sepolia callback proxy used in StopExecutor's constructor:
  `0x476F44b11F5C942c58f4c8E3d0300E5710743585` (PLAN §2.1 value;
  cross-checked on-chain — live code + balance — because the official
  Origins table is not exposed via the docs' text extraction).
- **Sourcify: all four contracts verified.** AISignal and StopExecutor
  verified during the deploy run; GuardedStopReactive and MockPool were
  reported "already verified" on retry — their first attempts had
  completed server-side while the CLI waited out a 180 s timeout.
- Orphaned contracts from the first, crashed deploy run (not part of the
  system, no funds at risk): MockPool
  `0x131BD16A09aF19c3F6F4f952BfE78D7c8264449C`, AISignal
  `0x7B996de2a2E9f67acFE6D6F55B82a071E33B34Be`.

Machine-readable copy: `deployment.json` (written by the deploy/resume
scripts); per-act raw evidence: `evidence-wick-order3.json`,
`evidence-trend-order6.json` (plus the failed attempts' files).

---

## 3. Full-loop evidence

Both acts feed the *same seeded synthetic series* the dry-run classified
(wick seed 20261116 → VETO 1000; trend seed 20261117 → EXECUTE 1000), so
the on-chain outcomes are the model's real verdicts on the same inputs.
Timestamps are block timestamps (UTC).

### Act 1 — wick → VETO, position kept (order 3, 2026-11-16)

Stop 83.4312 on a 87.82 base; the wick dips to 80.91 (−3.3% through the
stop) and recovers 91% of the drop inside the observation window.

| Step | Chain | Tx | Time (UTC) |
|---|---|---|---|
| StopOrderPlaced (origin) | Base | `0x3f02880453856741fa0716f6751afef4eb2fc765aad958a6450b40858cbd895a` | 10:46:54 |
| OrderRegistered (react) | Lasna | `0xe993527e6bc257bbe11d5566422a9df8a618a3bef148b2b73706535654fef713` | 10:46:54 |
| Breach tick — feedPrice #61 @ 80.91 | Base | `0x127dfd6a623135544fd14ea73ce4b72ce280dca4707010e0fa242b02300b9851` | — |
| OrderPending (breach seen) | Lasna | `0x7cc8e27a46e619a95450fa22bbcd87fa851620d9ec6b7529f1f5059dcea139a1` | 10:47:28 |
| DecisionPosted — **VETO**, score 1000 | Base | `0x2e2bec71151261a3e4e2a5648a798526acd6e872179ca6f2010e8de683fcbd32` | 10:48:06 |
| OrderVetoed (pending cancelled) | Lasna | `0x310a2cd04307dbe6e2d6d588cc4ed17d7aeb7652318b99a345d2473c52dbaa86` | 10:48:06 |
| StopExecuted | — | **none (by design)** | — |

Final state check: MockPool `orders(3)` → `active=true, settled=false`
— the position was **kept**, exactly as the VETO requires.
Latency: breach → veto **38 s** (dominated by the AI's 30-tick
observation window at feed cadence, plus same-wallet nonce contention
retries — see §4); DecisionPosted → OrderVetoed **< 1 s** (same block
timestamp) — the Reactive leg itself is effectively instant.

### Act 2 — trend → EXECUTE, sell executed via callback (order 6, 2026-11-16)

Stop 84.9604 on a 89.43 base; price breaks and keeps falling to 73.70
(−9.6% below the stop at window end, 0% rebound).

| Step | Chain | Tx | Time (UTC) |
|---|---|---|---|
| StopOrderPlaced (origin) | Base | `0x0f3b7d9b30d4695a4b82661fe7541c85dd0b09bfc6cee4cd0f5d4e96ca2fa1cf` | 11:04:31 |
| OrderRegistered (react) | Lasna | `0x60bace1a0f167dd82715bd3d0aa506a39cd1338fcb67979768aba6e78d452ed0` | 11:04:30 |
| Breach tick — feedPrice #75 @ 84.8577 | Base | `0x924da9844996301e1c180099bc2258b3ae70eb532f5169eb984f5358736647e8` | — |
| OrderPending (breach seen) | Lasna | `0x00af7bc75f5bda39395db7310060492c9d42ec901e3a54351d099421d5d530eb` | 11:05:33 |
| ExecutionRequested (callback requested) | Lasna | `0xf2e76260f0b555f878b565fbfed9c5754d314476436c9e1c17ed625b753af3a0` | 11:06:12 |
| DecisionPosted — **EXECUTE**, score 1000 | Base | `0x724b5c8903542d82095f8ecaa039d04a6f65fdd62b215eb1da5a115a8f3f96a7` | 11:06:13 |
| StopExecuted (callback settles the sell @ 73.6956, proceeds 73.6956) | Base | `0x93340bf38ddd650950e5c31d7c519677a0f74b5549b438414aef90c5590116a3` | 11:06:14 |

(OrderRegistered's timestamp reads 1 s *before* the origin event's —
cross-chain block-clock skew, not causality violation; ExecutionRequested
likewise precedes DecisionPosted by 1 s for the same reason.)
Final state checks: MockPool `orders(6)` → `active=false, settled=true`;
StopExecutor `executed(6)=true`; GuardedStopReactive `guarded(6)` →
`state=Executed, breachAt=11:05:33, breachPrice=84.8577`.
Latency: breach → executed **41 s** end-to-end;
DecisionPosted → StopExecuted **1 s**; ExecutionRequested → callback
settled **2 s**.

---

## 4. Incident log — what broke on the way, and the fixes

All failures were in *tooling and operations*, not in the four contracts
(`forge test` stayed 10/10 throughout; no contract code changed).

**Runner bugs (`ops/run_phase3.py`, all fixed in place):**
1. `send()` used `setdefault("value", …)` but `build_transaction()`
   pre-fills `value=0` — the faucet exchange silently carried 0 ETH and
   reverted with the faucet's `Just no`. Fixed by assigning the value
   explicitly (and building the faucet tx with its value up front).
2. First MockPool deploy ran out of gas at *exactly* the estimated
   807562 gas (failed tx
   `0xc1b4ee9f9425598f3e757ed8be0d75d097e37391b4ce794e85cce7b1423429e8`):
   on OP Stack chains the raw `eth_estimateGas` under-runs deployments.
   `send()` now always re-estimates on the final tx with a ×1.3 buffer.
3. Lasna rejects `maxPriorityFeePerGas = 0` ("gas tip cap 0, minimum
   needed 1") while its RPC *suggests* 0 — `send()` floors the tip at
   1 gwei.
4. Hand-built transfer dicts carried no fee fields and could not be
   signed — `send()` fills EIP-1559 defaults when absent.
5. `build_transaction({})` with no `from` estimates as `address(0)`, so
   `onlyOwner` calls (setExecutor) reverted `NotOwner` in simulation —
   explicit `{"from": …}` added.
6. Evidence collection scanned 20000 blocks in one `eth_getLogs` —
   the Base public RPC caps ranges at **200 blocks** (HTTP 413).
   Scanning is now chunked (150 Base / 10000 Lasna) with a 4000-block
   Base lookback.

**Guard service (`ai-service/guard.py`, orders 1–2):** the live guard
wedged silently — no HTTP timeout on its RPC provider (a throttled
connection blocked the poll loop indefinitely), unchunked `getLogs`
(ranges > 200 blocks → HTTP 413 once a backlog formed), no exception
guard in the loop, and buffered stdout hid all of it. Orders 1 and 2
therefore got no AI decision. On Lasna both registered and went
pending correctly, and **order 1 then demonstrated the fail-safe for
real**: `OrderTimedOut`
(`0xff78de20c63c168e991877517c8b3210a6bf5888a1ce86e7d8164313a1bde194`)
with `failSafeExecute=false` → no sell, position untouched.
Fixes: 15 s RPC timeout, ≤150-block poll chunking with incremental
cursor, per-iteration exception logging, unbuffered launch (`python -u`).

**Same-wallet nonce contention (order 3):** the guard and the feeder
share one wallet; the feeder pre-assigns nonces for its 120-tx burst,
so the guard's first decision posts failed `nonce too low` until the
burst drained (its loop retries every poll, and the post landed —
visible in `guard-wick.log`). Decision posting now uses the *pending*
nonce count, which queues it behind the burst (order 6 posted after
only two transient retries).

**Reactive contract debt (orders 4–5) — the expensive lesson:**
deliveries cost ≈ 0.011 lREACT each (Lasna gas price is 100 gwei);
~490 deliveries across the first acts burned the initial 5.25 lREACT
funding down to 0.0074 and the contract slipped into debt mid-act.
Per the network rules, **a reactive contract in debt receives no
deliveries**. Order 4 (trend) registered but its breach ticks were
never delivered (state stayed `Monitoring`); the AI's EXECUTE
(`0xd6e996aaa9e7951a22b2cca93d75685c8ce3f8fac35de575ae1b05ae3ca4b9ec`)
was delivered but correctly ignored as stale — decisions for
non-pending orders are dropped by design, so **no wrong execution
happened**. Order 5 was placed while still in debt; its
`StopOrderPlaced` was never delivered and was **not backfilled** after
the debt was cleared — it exists only on Base. Recovery: +4.5 lREACT
top-up + `coverDebt()` (txs in §2); deliveries resumed immediately
(order 6 registered within seconds). Operational takeaway, now part of
the runbook: budget ≳ 0.011 lREACT per delivered event and top up /
`coverDebt()` *before* the balance approaches zero — a 120-tick act
needs ≈ 1.4 lREACT of headroom.

**RPC quality (Base Sepolia):** `sepolia.base.org` backends
intermittently served stale state (a confirmed 0.03 ETH bridge credit
read as 0 for minutes; a guard session pinned to a lagging backend saw
a frozen head). The guard's `.env` now points at
`https://base-sepolia-rpc.publicnode.com` (current head, ≥2000-block
`getLogs` ranges). The runner keeps `sepolia.base.org` for sends, which
was unaffected.
