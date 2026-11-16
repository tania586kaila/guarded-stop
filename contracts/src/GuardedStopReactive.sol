// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { AbstractReactive } from "@reactive/src/base/AbstractReactive.sol";
import { ISystemContract } from "@reactive/src/interfaces/ISystemContract.sol";
import { IReactive } from "@reactive/src/interfaces/IReactive.sol";

/// @notice Minimal view of the destination-chain executor, for its callback selector.
interface IStopExecutor {
    function executeStop(address reactive_, uint256 orderId_) external;
}

/// @title GuardedStopReactive — the pending-order state machine (Reactive Lasna)
/// @notice Core of the AI-guarded stop order. Subscribes to:
///           1. MockPool.StopOrderPlaced  — learn new stop orders (→ MONITORING)
///           2. MockPool.PriceUpdate      — price at/below stop → PENDING ("breach")
///           3. AISignal.DecisionPosted   — the AI verdict decides what happens next:
///                EXECUTE (inside the decision window) → requestCallbackV_1_0 to StopExecutor
///                VETO    → cancel the pending state, back to MONITORING (position kept)
///                HOLD    → stay PENDING until the window lapses
///           4. Cron100 (Lasna)           — timeout sweep: a PENDING order whose window
///              lapsed with no AI answer falls back to the user's pre-committed
///              fail-safe policy, which defaults to NOT selling.
///         Written against the Omni API (reactive-lib-omni): `onlySystem`,
///         `requestCallbackV_1_0`, no legacy `vmOnly` / `Callback` events.
contract GuardedStopReactive is AbstractReactive {
    // ---- Event topics (keccak256 of the canonical signatures) ----
    uint256 internal constant PRICE_UPDATE_TOPIC = uint256(keccak256("PriceUpdate(uint256)"));
    uint256 internal constant STOP_ORDER_TOPIC =
        uint256(keccak256("StopOrderPlaced(uint256,address,uint256,uint256,bool)"));
    uint256 internal constant DECISION_TOPIC = uint256(keccak256("DecisionPosted(uint256,uint8,uint256,bytes32)"));

    // ---- Cron (emitted by the legacy system contract on the Reactive network itself) ----
    address internal constant CRON_CONTRACT = 0x0000000000000000000000000000000000fffFfF;
    uint256 internal constant CRON100_TOPIC = 0xb49937fb8970e19fd46d48f7e3fb00d659deac0347f79cd7cb542f0fc1503c70;
    uint256 public constant LASNA_CHAIN_ID = 5318007;

    // AISignal.Verdict ordinals
    uint8 internal constant VERDICT_EXECUTE = 0;
    uint8 internal constant VERDICT_VETO = 1;
    uint8 internal constant VERDICT_HOLD = 2;

    enum State {
        None,
        Monitoring, // watching the price, stop not breached
        Pending, // breached, waiting for the AI verdict inside the decision window
        Executed, // execution callback requested
        TimedOut // window lapsed, fail-safe applied (default: not sold)

    }

    struct GuardedOrder {
        bool known;
        address owner;
        uint256 amount;
        uint256 stopPrice;
        bool failSafeExecute;
        State state;
        uint256 breachAt; // Lasna timestamp of the breach (timestamps, not blocks)
        uint256 breachPrice;
    }

    event OrderRegistered(uint256 indexed orderId, address indexed owner, uint256 stopPrice, bool failSafeExecute);
    event OrderPending(uint256 indexed orderId, uint256 price, uint256 breachAt);
    event ExecutionRequested(uint256 indexed orderId, uint256 score);
    event OrderVetoed(uint256 indexed orderId, uint256 score, bytes32 reasonHash);
    event DecisionHold(uint256 indexed orderId, uint256 score);
    event DecisionLate(uint256 indexed orderId);
    event ExecutionDeferred(uint256 indexed orderId);
    event OrderTimedOut(uint256 indexed orderId);
    event FailSafeExecuted(uint256 indexed orderId);
    event ExecutorUpdated(address indexed executor);

    address public owner;
    uint256 public originChainId; // Base Sepolia: 84532
    uint256 public destChainId; // Base Sepolia: 84532
    address public pool; // MockPool on the origin chain
    address public aiSignal; // AISignal on the origin chain
    /// @notice StopExecutor on the destination chain; backfilled via setExecutor
    ///         after it is deployed with this contract's address (see README deploy order).
    address public executor;
    /// @notice Seconds the AI has to answer after a breach before the fail-safe applies.
    uint256 public decisionWindow = 120;
    uint64 public callbackGasLimit = 1_000_000;

    mapping(uint256 => GuardedOrder) public guarded;
    uint256[] public orderIds;

    error NotOwner();

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    constructor(uint256 originChainId_, address pool_, address aiSignal_, uint256 destChainId_) payable {
        owner = msg.sender;
        originChainId = originChainId_;
        destChainId = destChainId_;
        pool = pool_;
        aiSignal = aiSignal_;

        SYSTEM.subscribe(originChainId_, pool_, STOP_ORDER_TOPIC, REACTIVE_IGNORE, REACTIVE_IGNORE, REACTIVE_IGNORE);
        SYSTEM.subscribe(originChainId_, pool_, PRICE_UPDATE_TOPIC, REACTIVE_IGNORE, REACTIVE_IGNORE, REACTIVE_IGNORE);
        SYSTEM.subscribe(originChainId_, aiSignal_, DECISION_TOPIC, REACTIVE_IGNORE, REACTIVE_IGNORE, REACTIVE_IGNORE);
        // Timeout sweeps on Cron100 (~2 min) from the Reactive network's own cron source.
        SYSTEM.subscribe(LASNA_CHAIN_ID, CRON_CONTRACT, CRON100_TOPIC, REACTIVE_IGNORE, REACTIVE_IGNORE, REACTIVE_IGNORE);
    }

    // ---- Owner backfill / tuning (deployment order: reactive → executor → setExecutor) ----

    function setExecutor(address executor_) external onlyOwner {
        executor = executor_;
        emit ExecutorUpdated(executor_);
    }

    function setDecisionWindow(uint256 decisionWindow_) external onlyOwner {
        decisionWindow = decisionWindow_;
    }

    function setCallbackGasLimit(uint64 callbackGasLimit_) external onlyOwner {
        callbackGasLimit = callbackGasLimit_;
    }

    /// @notice Re-arm an order whose fail-safe timed it out (back to MONITORING).
    function rearmOrder(uint256 orderId_) external onlyOwner {
        GuardedOrder storage order = guarded[orderId_];
        if (order.known && order.state == State.TimedOut) {
            order.state = State.Monitoring;
            order.breachAt = 0;
            order.breachPrice = 0;
        }
    }

    /// @notice Settle any outstanding debt to the system contract so delivery resumes.
    function coverDebt() external onlyOwner {
        _coverDebt();
    }

    // ---- Reactive entry point ----

    /// @inheritdoc IReactive
    function react(LogRecord calldata log_) external override onlySystem {
        // Cron ticks come from the Reactive network itself; route them first.
        if (log_.contractAddress == CRON_CONTRACT && log_.topic0 == CRON100_TOPIC) {
            _sweepTimeouts();
            return;
        }
        if (log_.chainId != originChainId) return; // not ours: ignore, never revert

        if (log_.contractAddress == pool) {
            if (log_.topic0 == STOP_ORDER_TOPIC) {
                _onOrderPlaced(log_);
            } else if (log_.topic0 == PRICE_UPDATE_TOPIC) {
                _onPriceUpdate(log_);
            }
        } else if (log_.contractAddress == aiSignal && log_.topic0 == DECISION_TOPIC) {
            _onDecision(log_);
        }
        // Anything else is silently ignored: reverting here would still be charged.
    }

    // ---- State machine ----

    function _onOrderPlaced(LogRecord calldata log_) internal {
        uint256 orderId = log_.topic1;
        address orderOwner = address(uint160(log_.topic2));
        (uint256 amount, uint256 stopPrice, bool failSafeExecute) =
            abi.decode(log_.data, (uint256, uint256, bool));
        GuardedOrder storage order = guarded[orderId];
        if (!order.known) {
            orderIds.push(orderId);
            order.known = true;
        }
        order.owner = orderOwner;
        order.amount = amount;
        order.stopPrice = stopPrice;
        order.failSafeExecute = failSafeExecute;
        order.state = State.Monitoring;
        order.breachAt = 0;
        order.breachPrice = 0;
        emit OrderRegistered(orderId, orderOwner, stopPrice, failSafeExecute);
    }

    function _onPriceUpdate(LogRecord calldata log_) internal {
        uint256 price = abi.decode(log_.data, (uint256));
        for (uint256 i = 0; i < orderIds.length; i++) {
            GuardedOrder storage order = guarded[orderIds[i]];
            if (order.state == State.Monitoring && order.stopPrice > 0 && price <= order.stopPrice) {
                order.state = State.Pending;
                order.breachAt = block.timestamp;
                order.breachPrice = price;
                emit OrderPending(orderIds[i], price, block.timestamp);
            }
        }
    }

    function _onDecision(LogRecord calldata log_) internal {
        uint256 orderId = log_.topic1;
        (uint8 verdict, uint256 score, bytes32 reasonHash) = abi.decode(log_.data, (uint8, uint256, bytes32));
        GuardedOrder storage order = guarded[orderId];
        if (!order.known || order.state != State.Pending) return; // stale decision: ignore

        if (verdict == VERDICT_EXECUTE) {
            if (block.timestamp > order.breachAt + decisionWindow) {
                emit DecisionLate(orderId); // too late; the cron sweep will apply the fail-safe
                return;
            }
            if (executor == address(0)) {
                emit ExecutionDeferred(orderId); // executor not backfilled yet; stay pending
                return;
            }
            order.state = State.Executed;
            _requestExecution(orderId);
            emit ExecutionRequested(orderId, score);
        } else if (verdict == VERDICT_VETO) {
            // Flash wick: cancel the pending state, keep the position, resume watching.
            order.state = State.Monitoring;
            order.breachAt = 0;
            order.breachPrice = 0;
            emit OrderVetoed(orderId, score, reasonHash);
        } else if (verdict == VERDICT_HOLD) {
            emit DecisionHold(orderId, score); // stay Pending; window keeps running
        }
    }

    function _sweepTimeouts() internal {
        for (uint256 i = 0; i < orderIds.length; i++) {
            GuardedOrder storage order = guarded[orderIds[i]];
            if (order.state != State.Pending) continue;
            if (block.timestamp <= order.breachAt + decisionWindow) continue;
            if (order.failSafeExecute && executor != address(0)) {
                // The user pre-committed to selling even without an AI answer.
                order.state = State.Executed;
                _requestExecution(orderIds[i]);
                emit FailSafeExecuted(orderIds[i]);
            } else {
                // Default fail-safe: do NOT sell on silence.
                order.state = State.TimedOut;
                emit OrderTimedOut(orderIds[i]);
            }
        }
    }

    function _requestExecution(uint256 orderId_) internal {
        // Payload rule (Omni): the first argument must be address(0) — the network
        // overwrites it with this contract's address for the recipient to verify.
        bytes memory payload = abi.encodeWithSelector(IStopExecutor.executeStop.selector, address(0), orderId_);
        SYSTEM.requestCallbackV_1_0(
            ISystemContract.CallbackConfiguration_V_1_0({
                chainId: destChainId, recipient: executor, gasLimit: callbackGasLimit, payload: payload
            })
        );
    }
}
