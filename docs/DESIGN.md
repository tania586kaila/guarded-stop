# Reactive Omni Buildathon — Reactive Meets AI 赛道开工方案

> **Repo layout note (added when assembling this public repo):** this is
> the original design/plan document (formerly `PLAN.md`), kept verbatim.
> In this repo the contracts live in `contracts/`, the AI service in
> `ai-service/`, the demo page in `web/`, and the deployment log in
> `docs/DEPLOYMENT.md`.

> 调研日期：2026-11-16（只调研，未注册、未提交、未花钱）
> 目标赛道：**Reactive Meets AI**（第一名 $1,000，以 REACT 发放，无第二名）
> 赛事期：2026-11-05 至 2026-12-05（提交截止见 §1.4，按北京时间 2026-12-06 04:00 倒排，内部死线定 12-04）

---

## 1. 赛事详情（DoraHacks 赛事页 + 官方博客核对）

### 1.1 准确入口

| 入口 | URL | 出处 |
|---|---|---|
| DoraHacks 赛事详情页 | https://dorahacks.io/hackathon/reactive-omni-buildathon/detail | 由官方博客正文的 DoraHacks 链接跳转得到（链接指向 `dorahacks.io/hackathon/reactive-omni-buildathon`，详情页为 `/detail`）；2026-11-16 实抓，页面标题「Reactive Omni Buildathon」 |
| 官方博客（赛道 brief 原文） | https://blog.reactive.network/reactive-omni-buildathon-thirty-days-to-find-out-what-one-second-buys/ | 用户提供，2026-11-04 发布 |
| Reactive 开发者文档 | https://dev.reactive.network/ | 博客正文「Reactive docs」链接 |
| DoraHacks 官方通讯（佐证赛程） | https://hidorahacks.medium.com/dorahacks-hackathon-newsletter-november-2026-ii-5761efa2275b | 列明 Reactive Omni Buildathon，标签含 Solidity · OpenAI · Claude · Ethereum，Nov 5 — Dec 5, 2026 |

### 1.2 奖金与赛道

总奖池 **$5,500，以美元计价、按 REACT 代币发放**（赛事页与博客一致）：

| 赛道 | 第一名 | 第二名 | 备注 |
|---|---|---|---|
| Every Second Counts | $2,000 | $250 | 时效敏感型 DeFi，限定 Unichain Sepolia 和/或 Base Sepolia + Lasna |
| Set It and Forget It | $2,000 | $250 | 个人自动化，任意 Reactive 支持的链 |
| **Reactive Meets AI** | **$1,000** | 无 | 神经网络进入运行回路（见 §1.5 的硬规则） |

### 1.3 提交要求（赛事页 Submission 一节 + 博客 Getting Started，原文核对）

在 DoraHacks 赛事页提交 BUIDL，必须包含：

1. **公开仓库链接**（GitHub 等），且提交时仓库须 **public + 开源**；
2. **已部署的合约地址**；
3. **若干笔交易哈希，展示完整回路**：起源链事件 → Reactive 反应交易 → 目标链回调；
4. **3 分钟以内的演示视频**（赛事页原文 "A demo video under three minutes"，即视频是**必须项**，不是可选项）。

地面规则（Ground Rules）：

- 所有作品应在**赛事期间内新建**；既有工作只能作为依赖，不能作为提交本体；
- Every Second Counts 必须跑 Lasna 测试网；**另外两条赛道（含本赛道）可用 Reactive 主网或 Lasna**；
- 在 Base Sepolia 上，计时器/冷却/截止一律用**时间戳**而非区块数（Base Sepolia 现为 200ms 出块，区块计时会快约 10 倍）。

**BUIDL 表单字段层面**：赛事页未公开列出逐项字段；按 DoraHacks 通用 BUIDL 表单的已知结构（来自其他 DoraHacks 赛事的公开提交记录，属旁证、本赛事未逐项核实），一般包括：项目名、标语/一句话简介、项目描述（问题/方案/技术栈）、所选赛道（bounty 勾选）、GitHub 仓库、Demo 链接、演示视频链接，外加主办方自定义问题。⚠️ 有参赛者经验指出：**主办方自定义问题的答案在部分赛事里是「一次提交即锁定、不可修改」**，正式提交前务必先打开表单把问题原文抄下来、备好答案再填（见 §5 风险）。

### 1.4 提交截止（准确时间与时区）

- 赛事页 Events 一节给出的赛事窗口：**2026-11-04T12:00:00Z 至 2026-12-05T20:00:00Z**（页面抓取于 2026-11-06）。
- 即提交截止按 **2026-12-05 20:00 UTC = 北京时间 2026-12-06 04:00** 倒排。
- ⚠️ 口径不一致预警：博客与多数聚合站只写「December 5th」；个别聚合站（hackathonradar）把结束时间写成 12-06 12:00 UTC。**以 DoraHacks 赛事页的 12-05 20:00 UTC 为准**，且内部死线提前到 **12-04 晚**完成提交，留一天缓冲。

### 1.5 评审标准（赛事页 Judging + 博客 How Judging Works，逐字核对）

由 **Reactive 官方团队评审**（客座评委如有会在赛事页公布）。每项 1–5 分，**四项等权**：

| 标准 | 原文要点 | 对本赛道的含义 |
|---|---|---|
| **Execution（能跑）** | 要看到链上的 reactive 交易和它们触发的回调；**没有这些的作品直接不再评分** | 必须真部署、真跑通回路、交真实 tx hash；这是生死线 |
| **Integration（集成深度）** | Reactive 合约是否在做实事，还是「栓上去的」（bolted on）；每条赛道 brief 里有具体定义 | Reactive 合约要承担核心状态机（见 §3 主方案的「待决订单」设计），不能只是转发器 |
| **Usefulness（有用性）** | 是否解决真实用户的问题 | 选真实痛点（止损误触发），README 里讲清用户故事 |
| **Craft（完成度）** | 代码可读、有能跑的 demo、有别人能照着做的文档 | README + 架构图 + 一键复现步骤 + <3 分钟视频 |

**Reactive Meets AI 赛道专属硬规则**（博客原文）：

> "the AI has to be part of the running system, not just the tool you used to write the code" —— AI 必须在**运行系统**里（决定 Reactive 合约下一步做什么、解读它捕获的事件、或被事件触发）；只用 AI 写代码的项目会被归到 Set It and Forget It 赛道。

赛道定位是「deliberately open（刻意开放）」，没有更细的 brief/想法清单，评委自己也说还不知道最佳形态——**叙事空间大，但也意味着必须把「AI 在回路里」的证据做得无可辩驳**（AI 决策事件上链、决策影响链上执行路径、视频里现场演示）。

### 1.6 参赛资格与注册方式

- 赛事页与博客**未列出任何国家/地区排除条款**，博客明确写「无论你天天写 Solidity 还是从没部署过合约，都可以参加」（原文意译）。面向全球线上参加。
- DoraHacks 平台通用条款层面（2026-11-09 的第三方条款核查，旁证）：注册需具备完全民事行为能力，未成年人需监护人同意；平台已于 2026 年 1 月起下线 Bounties/Grants 功能、定位为黑客松平台（不影响本次赛事提交）。
- 注册方式：DoraHacks 账号（邮箱/GitHub/钱包等常规方式）→ 在赛事页报名（Register/Join）→ 截止前在赛事页提交 BUIDL 并勾选 Reactive Meets AI 赛道。**单人是否可参赛、组队人数上限，赛事页未写明**——DoraHacks 惯例允许单人，列入 §5 待确认。
- 领奖：奖金以 REACT 发放，具体是打到 DoraHacks 账号绑定的钱包还是另行收集地址、是否需要 KYC/税表，**赛事页未写明**，列入 §5 待确认。

---

## 2. Reactive Network 开发要点（Omni 版，以当前官方文档为准）

> ⚠️ 最重要的一条：**Omni 已换 API**。官方文档 Getting Started 页（dev.reactive.network，2026-11-16 实抓）明说：Omni 起不再有 RVM（ReactVM）双状态模型，Reactive 合约就是普通合约。GitHub 上的 `reactive-smart-contract-demos` 仓库仍是**旧版（legacy）API**（`vmOnly`、发 `Callback` 事件、`AbstractCallback` 单参构造），只能借鉴业务逻辑，**写法必须按 Omni 文档 + `reactive-lib-omni` 来**。照抄旧 demos 的 API 是本次最容易踩的坑。

### 2.1 网络参数

| 网络 | RPC | Chain ID | 币种 | 浏览器 | 出处 |
|---|---|---|---|---|---|
| Reactive 主网 | https://mainnet-rpc.rnk.dev/ | 1597 | REACT | https://reactscan.net/ | 文档 Reactive Mainnet / Lasna Testnet 页 |
| **Lasna 测试网** | https://lasna-rpc.rnk.dev/ | **5318007** | lREACT | https://lasna.reactscan.net/ | 同上（另注：2026-05 的 Omni 测试网公告曾给出 `lasna-omni-rpc.rnk.dev` 变体，部署当天以文档主页为准再验一次） |

- 共识：CometBFT，**~1 秒出块、即时最终性、无 reorg**（文档与博客一致）——这是整个赛事的卖点。
- 系统合约（主网与 Lasna 同址）：`0x8888888888888888888888888888888888888888`；旧系统合约地址 `0x0000000000000000000000000000000000fffFfF` 现在只负责发 CRON 事件（见 §2.3）。
- 测试网可用起源/目的地链（文档 Origins & Destinations 页，测试网表）：

| 链 | Chain ID | Callback Proxy |
|---|---|---|
| Ethereum Sepolia | 11155111 | `0xAa14d9Cd0f788Ca23d11805986C1d8bd035D23b4` |
| Base Sepolia | 84532 | `0x476F44b11F5C942c58f4c8E3d0300E5710743585` |
| Unichain Sepolia | 1301 | `0x775c9B990ADe401060B78D0e98684eEf8d2466C1` |
| Reactive Lasna 自身 | 5318007 | `0x8888888888888888888888888888888888888888`（即系统合约） |

主网与测试网**不得混用**：起源是测试网，目的地也必须是测试网。本方案全程测试网（Lasna + Base Sepolia），零真实资金。

> ⚠️ 地址出入预警：某第三方项目（Lambda）的部署手册把 Unichain Sepolia 的 callback proxy 写成 `0x9299472A…83e7837FC4`，与官方 Origins 页的 `0x775c9B9…2466C1` 不一致。**部署当天一律以官方 Origins & Destinations 页现值复核**，且本方案首选 Base Sepolia，避开这处争议。

### 2.2 水龙头（lREACT 获取）

没有网页点选式水龙头，是**合约兑换式**（文档 Get Testnet REACT 一节）：

- 向水龙头合约发送 Sepolia ETH，按 **1 ETH → 100 lREACT** 兑换到你的 Lasna 地址：
  - Ethereum Sepolia 入口：`0x9b9BB25f1A81078C544C829c5EB7822d747Cf434`
  - Base Sepolia 入口：`0x2afaFD298b23b62760711756088F75B7409f5967`
- 可直接转账，也可 `cast send <faucet> "request(address)" $WALLET_ADDR --value 0.1ether`；
- **单笔上限 5 ETH**（最多换 500 lREACT），超额部分直接损失，别多发；
- 前置成本：先要有 Sepolia 测试 ETH（公共水龙头领取，免费）；部署当天准备 0.1–0.5 SepETH 足够全程。
- 另需给**目标链上的回调合约**充目标链原生币（Base Sepolia ETH），因为回调执行费由回调合约（接收方）在目标链货币里支付（见 §2.4 计费）。

### 2.3 Reactive 合约基本写法（Omni 版）

依赖库：**`Reactive-Network/reactive-lib-omni`**（GitHub，2026-11-16 实抓 `src/base/AbstractReactive.sol`）；导入路径形如 `@reactive/src/base/AbstractReactive.sol`、`@reactive/src/interfaces/ISystemContract.sol`、`@reactive/src/interfaces/IReactive.sol`；Solidity `^0.8.29`。

**骨架**（文档 Reactive Contracts 页原文结构）：

```solidity
contract MyReactive is AbstractReactive {
    constructor(uint256 originChainId_, address originContract_, uint256 topic0_) payable {
        SYSTEM.subscribe(
            originChainId_, originContract_, topic0_,
            REACTIVE_IGNORE, REACTIVE_IGNORE, REACTIVE_IGNORE
        );
    }

    /// @inheritdoc IReactive
    function react(LogRecord memory log_) external onlySystem {
        // 你的逻辑：更新状态 / 请求回调 / 改订阅
    }
}
```

要点：

- **继承 `AbstractReactive`**：它提供 `SYSTEM`（系统合约常量 `0x8888…8888`）、`REACTIVE_IGNORE`（通配 topic 值 `0xa65f96fc…2313ad`）、`onlySystem` 修饰符，并经 `AbstractPayer` 提供付费/还债机制（`pay()` 已实现，不要自己写；`receive()` 可收款）。
- **订阅 `SYSTEM.subscribe(chainId, contract, topic0, topic1, topic2, topic3)`**：六个条件各自可通配（chainId 用 `0`、合约用 `address(0)`、topic 用 `REACTIVE_IGNORE`），但**至少一个条件必须具体**；只支持精确匹配，无范围/OR，一个组合一次调用，可多次调用订多个事件；运行时（包括在 `react()` 里）可 `subscribe`/`unsubscribe`，但 unsubscribe 必须六参完全一致，否则静默失败。订阅存在节点里、不在合约存储里，链上读不回来，自己记账。
- **`react(LogRecord memory log_) external onlySystem`**：Omni 版**去掉了旧版的 `vm`/`vmOnly`**，改为 `onlySystem`（校验 msg.sender == SYSTEM，否则 revert `NotAuthorized`——没有它，任何人都能伪造 LogRecord 骗你的合约）。`LogRecord` 字段：chainId、contractAddress、topic0–3、data（非索引参数的 ABI 编码）、blockNumber、opCode（原日志的 topic 个数，解码前先看它）、blockHash、txHash、logIndex。多订阅时先按 topic0 路由；**不匹配的日志应直接放行，不要用 revert 当过滤器**（系统会捕获 revert、发 `ReactiveContractReverted` 且照样扣费）。
- **CRON 定时事件**：旧系统合约地址 `0x0000…fffFfF` 按区块间隔发 `Cron` 事件，可当链上闹钟订阅：Cron1（每块 ~1s，topic0 `0xf02d6ea5…cb514`）、Cron10（~10s，`0x04463f7c…0b687`）、Cron100（~2min，`0xb49937fb…503c70`）、Cron1000（~17min）、Cron10000（~3h）。每个 tick 都计费，选能满足需求的最长间隔，并留可关闭的开关。
- **保持合约有钱**：Reactive 交易的 gas 由合约自己付；欠费后系统**停止投递**一切 reactive 交易，直到清偿。构造器 `payable` 部署时注资最简单，之后可转账/`depositTo()` 续费，必要时暴露一个调 `_coverDebt()` 的 `coverDebt()`。

### 2.4 Callback 机制（Omni 版）

- 请求回调：`SYSTEM.requestCallbackV_1_0(ISystemContract.CallbackConfiguration_V_1_0{ chainId, recipient, gasLimit, payload })`（也有泛型 `requestCallback(version, config)`，现只有 V_1_0 一个版本）。系统随即发 `CallbackRequest` 事件，网络的 Signer 把交易投递到目标链、经该链的 **callback proxy** 调用目标合约。旧版 `emit Callback(...)` 事件方式**已弃用**（老合约兼容，新代码别用）。
- **payload 第一参数必须是 `address` 且传 `address(0)` 占位**：网络会把 payload 前 160 bit 替换成发起回调的 Reactive 合约地址，供目标链验真。忘了这条是「最常见的回调翻车原因」（文档原文）。
- 目标链侧回调合约继承 **`AbstractCallback`**（Omni 版构造器**两个参数**：`AbstractCallback(callbackProxy_, callbackSender_)`，两者 immutable、写错只能重部署）：
  - 回调方法第一参数声明为 `address`（即被注入的 Reactive 合约地址），且**同时**加 `onlyServiceProvider`（校验调用者是 callback proxy）+ `onlyCallbackSender(reactive_)`（校验注入地址是你授权的那个 Reactive 合约）两个修饰符，缺一不可；
  - 一个合约不能同时是 Reactive 合约和 Callback 合约（`_SERVICE_PROVIDER` 冲突，编译不过）；Reactive 合约想回调自己需手工校验。
- 部署顺序（文档给的破环法）：**先部署 Reactive 合约 → 再部署回调合约（构造时传入 proxy 地址 + Reactive 合约地址）→ 用 owner-only setter 把回调合约地址回填给 Reactive 合约 → 两边都注资**。
- 计费（最容易忽略的成本项）：**回调执行费由目标链上的接收方合约付**，用目标链原生币（不是 REACT）；失败的回调照样收费并发 `CallbackFailure`；gasLimit 太小会在方法执行前以 `InsufficientGas` 失败，要给足（文档示例 1,000,000）。
- ReactVM 说明：Omni 后**已无独立的 ReactVM/RVM 概念**——旧文档/旧 demos 里的 RVM id、`vmOnly`、双状态、自定义 RPC 追踪方法全部作废；现在就是单网络普通 EVM 执行，Reactscan/Blockscout 按标准浏览器看（Getting Started 页 Code Changes 一节）。方案里凡引用旧资料出现 RVM 字样，一律按此口径翻译为「Reactive 合约本体」。

### 2.5 部署与验证工具

- **Foundry 为主**（文档全程用 `forge`/`cast`）：`forge create --broadcast --rpc-url $REACTIVE_RPC --private-key $KEY --value 0.1ether <Contract> --constructor-args …` 部署；`cast send` 触发与调水龙头。Omni 后标准工具开箱可用，Hardhat/Remix 亦可（2026-05 Omni 测试网公告原文：Hardhat、Foundry、Remix、Blockscout 都按预期工作）。
- ⚠️ 旧版经验帖曾警告「`forge script` 部署 Reactive 合约会因 subscribe 预编译在本地模拟 revert、须用 `cast send --create`」——那是 legacy 预编译时代的说法；Omni 文档已明确「RC 专用预编译全部移除、就是标准 EVM 链」。部署当天先用 Basic 流程小额实测一次，以实测为准。
- 合约验证：Sourcify——`forge verify-contract --verifier sourcify --chain-id 5318007 $ADDR $NAME`，或部署时 `forge create --verify --verifier sourcify`。验证过的地址对 Craft/Execution 评分友好。

### 2.6 官方示例项目清单（均来自官方文档 Demos 页与官方仓库）

官方总仓库：**Reactive-Network/reactive-smart-contract-demos** — https://github.com/Reactive-Network/reactive-smart-contract-demos （legacy API，借鉴逻辑）；Omni 库：**Reactive-Network/reactive-lib-omni** — https://github.com/Reactive-Network/reactive-lib-omni 。文档 Demos 页：https://dev.reactive.network/legacy/demos

| 示例 | 一句话用途 | 链接（文档 Demos 页内链至该仓库对应目录） |
|---|---|---|
| Basic Demo | 最小闭环：起源链事件 → Reactive 检测 → 目标链回调，新手起点 | https://github.com/Reactive-Network/reactive-smart-contract-demos/tree/main/src/demos/basic |
| Uniswap V2 Stop Order | 订阅 Pair 的 `Sync` 事件，汇率越过阈值即回调执行卖出——**与本方案主构想最接近** | 同仓库 `src/demos/uniswap-v2-stop-order/`（文档 Demos 页） |
| Uniswap V2 Stop-Loss & Take-Profit | 止损+止盈双向、用户自有部署版的进阶止损单 | 同仓库（文档 Demos 页） |
| Aave Liquidation Protection | 订阅 CRON 周期检查 Aave 仓位健康因子，过低即回调补仓/还款 | 同仓库（文档 Demos 页） |
| Leverage Loop | 检测到存款事件后自动循环加杠杆到达目标健康因子 | 同仓库（文档 Demos 页） |
| Automated Prediction Market | 预测市场结果揭晓事件触发后，自动批量派奖 | 同仓库（文档 Demos 页） |
| Gasless Cross-Chain Atomic Swap | 无桥跨链原子交换的双边状态编排 | 同仓库（文档 Demos 页） |
| Approval Magic | 以 ERC-20 `Approval` 事件为触发的订阅制自动化 | 同仓库 `src/demos/approval-magic/`（文档 Demos 页） |
| Hyperlane Demo | Reactive 与 Hyperlane 跨链消息协议的双向集成 | 同仓库（文档 Demos 页） |
| Cron Demo | 只用内置 CRON 事件做定时任务（定时更新/派奖/巡检） | 同仓库（文档 Demos 页） |

另可参考官方博客的实战拆解系列（UHI9 黑客松项目，Lasna 实跑）：Unistrata（CRON+波动率双订阅触发结算）、Lambda（Uniswap v4 Hook 事件 → 跨链对冲回调）、Veritas（新内容登记事件 → 回调更新风险分）——写法是 legacy 口径，但「订阅什么事件、回调做什么」的设计思路可直接借用。

---

## 3. Reactive Meets AI 赛道项目构想（2 个）

### 构想 A（★ 主方案）：AI 守卫止损单 ——「插针不卖，趋势才卖」

**一句话**：给 DEX 止损单装一个链下 AI 守卫：价格触线先「报警待决」，AI 在 1 秒级回路里判断这是闪崩插针还是真实趋势反转，Reactive 合约只在 AI 确认后才执行卖出，插针则撤销待决、保住仓位。

**解决什么问题**：传统阈值止损（官方 Stop Order demo 就是这类）有两个真实痛点：① 流动性薄的池子经常出现瞬间插针（wick），价格触线一秒又弹回，机械止损把用户卖在最低点；② 真跌势里固定阈值又反应迟钝。区分「插针 vs 趋势」需要看触线前后的价格序列形态——这正是小型时序模型擅长、而纯合约逻辑（只能做等值/阈值判断，订阅条件连范围比较都不支持）做不到的事。

**系统分工**：

| 层 | 部署在哪 | 做什么 |
|---|---|---|
| 信号源合约 `MockPool`（模拟池） | Base Sepolia | 可控价格喂价的演示池：按脚本/手动喂入价格序列并 emit `PriceUpdate`；同时是用户仓位/止损单登记处（下单 emit `StopOrderPlaced`）。演示用模拟池是因为真实 Uniswap 池在测试网无法按剧本制造插针行情；合约接口按真实 Pair 的 `Sync` 形态设计，README 注明可替换为真实池 |
| AI 信号合约 `AISignal` | Base Sepolia | 接收链下 AI 的决策上链：`postDecision(orderId, verdict, score, reasonHash)`，emit `DecisionPosted`；verdict ∈ {EXECUTE, VETO, HOLD}，附模型版本与特征哈希，保证决策可审计、可复现 |
| Reactive 合约 `GuardedStopReactive` | Lasna（5318007） | **核心状态机**：订阅 `PriceUpdate`（触线 → 把订单置为 PENDING 并记录触线时刻/价格）+ 订阅 `DecisionPosted`（AI 确认 EXECUTE 且订单仍在待决窗口内 → `requestCallbackV_1_0` 回调执行卖出；VETO → 撤销待决、订单恢复监控；窗口超时无决策 → 按用户预设的 fail-safe 策略处理，默认不卖并记录）。另订阅 Cron100 做待决单超时巡检 |
| 执行合约 `StopExecutor`（AbstractCallback） | Base Sepolia | 验真（双修饰符）后执行卖出动作（演示池内即结算仓位并 emit `StopExecuted`），全程留痕 |
| AI 守卫服务（链下，Python） | 本地/任意小服务器 | 监听 `PriceUpdate` 与待决状态 → 拉取最近 N 个价格点构造特征（回撤深度、触线持续时长、反弹速度、波动率突变、成交量代理量）→ 本地模型推理出 verdict+score → 签名调用 `AISignal.postDecision` 上链。模型输出与特征哈希一并上链，评委可离线复算 |

**AI 部分（零付费 key 可演示）**：

- 主模型：**本地训练的小模型**——scikit-learn 梯度提升（或 PyTorch 小 MLP）二分类器，训练数据为程序合成的标注价格序列（插针/趋势/横盘三类形态参数化生成，附生成脚本，仓库内一键复现训练）。推理在 CPU 上毫秒级，无任何外部 API 依赖，断网可演示。
- 可选增强（不作为依赖）：用现有的 OpenRouter 免费模型给每次决策生成一句人话解释（如「触线后 0.8 秒内反弹 62%，判定插针」），解释文本哈希上链；免费额度不可用时自动退化为模板解释，主流程不受影响。
- 为什么这满足赛道硬规则：AI 在**运行回路正中央**——没有 AI 的 EXECUTE，Reactive 合约不会卖；AI 的每一次决策都以链上事件形式成为回路的一环，且直接改变合约后续行为（执行/撤销/继续等）。这正是 brief 原文的 "A model could decide what a reactive contract does next"。

**为什么契合 ~1 秒卖点**：插针的存续时间就是几秒级——旧版 ~7 秒出块时，待决窗口内行情早已反转或恶化，「先待决、等确认」的状态机根本来不及跑完两跳（触线事件→AI 决策事件→回调）。Omni 的 ~1 秒出块 + 即时最终性让「触线 → AI 推理（亚秒）→ 决策上链 → Lasna 反应 → Base 回调执行」全回路压到数秒内可完成，且每一段都有 tx 时间戳可量。演示视频里直接对比两幕：同一价格剧本，① 插针：机械止损会卖、AI 守卫否决保仓；② 真跌：AI 确认、秒级执行——并打出全回路延迟数字，正面回应 Execution 评分里「看真实反应交易与回调」的要求。

**工作量估计**：合约 4 个（含模拟池）约 2 天；AI 服务+合成数据+训练约 1 天；部署联调+刷出完整回路 tx 约 0.5–1 天；前端可视化（静态页读链上事件画价格线与决策点）0.5 天；README+视频 0.5 天。**合计约 4–5 个工作日**（单人/AI 协作节奏），11-17 开工可于 11 月底前完成、留足缓冲。

### 构想 B（备选）：Reactive 合约的 AI 运维哨兵 ——「会自己喊疼的自动化」

**一句话**：给 Reactive 合约本身做 AI 运维：哨兵订阅 CRON 与目标合约的欠费/失败事件流，链下异常检测模型判断「只是行情抖动还是真要断气」，再经 Reactive 回调自动 `coverDebt()` 续命、暂停订阅或升级告警。

**解决什么问题**：Reactive 合约欠费即停摆是官方文档反复强调的运维痛点（Economy 一节、Reactivate 项目背景都讲这事）；回调失败、gas 异常飙升同样需要人盯。把「监控+判断+处置」做成事件驱动闭环，等于用 Reactive 运维 Reactive（dogfooding 叙事评委友好）。

**分工**：链上——Lasna 上的哨兵 Reactive 合约订阅 Cron100 + 目标合约所在链的 `CallbackFailure`/余额相关事件，维护处置状态机，回调执行 `coverDebt()`/暂停/恢复；链下——Python 异常检测（孤立森林或简单时序模型，本地训练于合成的正常/异常事件流）给事件打分，分数上链留痕后哨兵才行动。AI 同样零付费 key、本地可跑。

**为什么落选为备选**：① 演示观感弱——「余额低了自动充值」很难在 3 分钟视频里做出戏剧性对比；② 处置动作多为运维内部事务，Usefulness 的「真实用户」故事不如止损单直观（普通交易者 >> 合约运维者）；③ 与官方已背书的 Reactivate（2025 年 9 月官方黑客松二等奖）题材撞车，容易被评委拿来直接比较。优点是工作量略小（约 3–4 天）、纯 Lasna 单链可起步；若主方案在 Base Sepolia 联调受阻，可降级为此方案保底交付。

### 推荐结论

**主方案 = 构想 A（AI 守卫止损单）**。理由：① 与赛道 brief 的原话逐字对位（模型决定 Reactive 合约下一步）；② 痛点真实、用户故事一句话讲清，四项评分各有明确着力点（Execution：双幕完整回路 tx + 延迟数字；Integration：Reactive 合约是待决状态机而非转发器；Usefulness：插针误卖是 DEX 用户公认的坑；Craft：合成数据与模型全开源可复现）；③ 技术上站在官方 Stop Order demo 的肩膀上，风险集中在「多一跳 AI 决策事件」的联调，而非全新协议；④ ~1 秒卖点不是口号——待决窗口机制本身就是为快链设计的，慢链做不了，这正是主办方办这场比赛想看的东西。

**建议排期**（内部死线 12-04）：

| 时间 | 里程碑 |
|---|---|
| 11-17 ~ 11-18 | DoraHacks 注册报名（待用户完成）；Foundry 工程脚手架；先按 Basic 闭环在 Lasna+Base Sepolia 跑通一遍官方模式（订阅→react→回调），验证 Omni API 与本机工具链 |
| 11-19 ~ 11-22 | 四个合约完成 + 本地测试；合成数据生成与模型训练、离线评估 |
| 11-23 ~ 11-26 | AI 服务联调；双幕剧本（插针/真跌）在测试网各跑通 ≥3 次，留存 tx hash 与延迟统计 |
| 11-27 ~ 11-30 | 静态前端（价格线+决策点+回路时间轴）；README/架构图；合约 Sourcify 验证 |
| 12-01 ~ 12-03 | 录 <3 分钟视频；BUIDL 文案定稿；**12-03 正式提交**（不压 12-05 死线） |
| 12-04 ~ 12-05 | 缓冲：只做 BUIDL 信息补漏，不动代码 |

---

## 4. 关键事实速查（开发时贴墙版）

- Lasna：RPC `https://lasna-rpc.rnk.dev/`，chainId **5318007**，币 lREACT，浏览器 lasna.reactscan.net
- 主网：RPC `https://mainnet-rpc.rnk.dev/`，chainId 1597（本方案不用主网）
- 系统合约 SYSTEM：`0x8888888888888888888888888888888888888888`（主网/测试网同址）
- CRON 事件源（旧系统合约）：`0x0000000000000000000000000000000000fffFfF`；Cron100 topic0 `0xb49937fb8970e19fd46d48f7e3fb00d659deac0347f79cd7cb542f0fc1503c70`
- Base Sepolia：chainId 84532，callback proxy `0x476F44b11F5C942c58f4c8E3d0300E5710743585`（部署当天以官方 Origins 页复核）
- 水龙头（换 lREACT）：Sepolia ETH 入口 `0x9b9BB25f1A81078C544C829c5EB7822d747Cf434`，1 ETH → 100 lREACT，单笔 ≤5 ETH
- 库：`Reactive-Network/reactive-lib-omni`（Omni）；demos 仓库是 legacy，只看逻辑
- 回调三铁律：payload 首参 `address(0)` 占位；回调合约双修饰符验真；两边合约都要注资（Reactive 侧付 REACT/lREACT，目标链侧付该链原生币）

---

## 5. 风险与待确认项

| # | 事项 | 状态/影响 | 处置 |
|---|---|---|---|
| 1 | **演示视频是否必须** | ✅ 已确认：**必须**，<3 分钟（赛事页 Submission 明列）。需要真人侧录制/上传配合（脚本与录屏内容可提前备好） | 排期已含录制日；提前备录屏剧本 |
| 2 | **主网还是测试网部署** | ✅ 已确认：本赛道主网/Lasna 均可。**决定用 Lasna 测试网**：零资金成本，且 Execution 只看回路真实性不看主网 | 若评委偏好主网再评估迁移（合约可平移，需真 REACT 注资） |
| 3 | **提交截止的准确钟点** | ⚠️ 赛事页窗口止于 12-05 20:00 UTC，与聚合站口径不一致（有写 12-06 的） | 按最早口径倒排，12-03 提交 |
| 4 | **REACT 奖金领取方式** | ❓ 赛事页未写：发放到哪个钱包地址、是否需 KYC/税表、何时发放、REACT 结算价时点均未公布 | 注册后看 DoraHacks 站内通知/问主办方（Discord/Telegram）；领奖主体须为真人账户，提前备好可收 REACT 的钱包地址 |
| 5 | **BUIDL 自定义问题是否一次锁定** | ❓ 本赛事未核实；其他 DoraHacks 赛事有「组织者问题提交后不可改」的先例 | 报名后第一时间打开表单抄录全部问题原文，答案定稿后才点提交 |
| 6 | **单人参赛/组队上限** | ❓ 赛事页未写明 | 注册时在赛事页确认；默认按单人（+AI 协作）推进 |
| 7 | **资格地区限制** | 赛事页与博客未见排除条款；DoraHacks 平台条款仅见行为能力要求（第三方核查旁证）。中国居民参赛未见明文障碍，但领奖环节可能另有合规要求 | 与 #4 一并向主办方确认；不预设结论 |
| 8 | **Omni API 与旧 demos 不兼容** | ⚠️ 已确认差异（§2 开头）：旧仓库代码直接抄会编译/运行失败；另 RPC 曾有 `lasna-omni-rpc` 变体、Unichain proxy 地址有第三方出入 | 只按 dev.reactive.network 当前文档 + reactive-lib-omni 写；部署首日先跑通最小闭环验证工具链 |
| 9 | **AI「在回路里」的举证** | 赛道硬规则，只用 AI 写代码会被转赛道 | 决策上链 + 决策改变执行路径 + 视频现场演示三重举证（已纳入主方案设计） |
| 10 | **测试币与联调稳定性** | 水龙头需先有 Sepolia ETH；公共水龙头偶有限流；回调计费涉及两链余额，欠费即停摆 | 开工首日先领足测试币；合约余额监控写进联调清单；fail-safe 默认不卖，联调失败不产生错误执行 |
| 11 | **模拟池的说服力** | 用 MockPool 演示可能被质疑「非真实协议」 | 接口对齐真实 Pair `Sync` 形态、README 写明替换路径；有余力时加一个真实 Base Sepolia 测试池的只读订阅演示 |

---

## 附：主要出处

1. DoraHacks 赛事详情页（2026-11-16 抓取，页面缓存 2026-11-06）：https://dorahacks.io/hackathon/reactive-omni-buildathon/detail —— 奖金、评审四标准、提交四件套、地面规则、赛事窗口时间
2. Reactive 官方博客（2026-11-04）：https://blog.reactive.network/reactive-omni-buildathon-thirty-days-to-find-out-what-one-second-buys/ —— 三赛道 brief、AI 赛道硬规则、Lasna/主网适用范围、水龙头与文档入口
3. Reactive 文档 Getting Started / Reactive Contracts / Callback Contracts / Reactive Mainnet & Lasna Testnet / Origins & Destinations / Demos（dev.reactive.network，2026-11-16 实抓）—— Omni API、网络参数、proxy 地址、计费与部署顺序
4. GitHub Reactive-Network/reactive-lib-omni（AbstractReactive.sol，2026-11-16 实抓）与 reactive-smart-contract-demos（Basic Demo README）—— 库地址与最小闭环流程
5. 旁证：DoraHacks 2026-11-10 官方通讯（赛程/标签）；AlphaGrowth 聚合（赛道与开源要求汇总）；其他 DoraHacks 赛事的公开 BUIDL 记录（表单字段结构与自定义问题锁定先例，仅作风险提示用）
