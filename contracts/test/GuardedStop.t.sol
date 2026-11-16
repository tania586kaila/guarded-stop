// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { Test } from "forge-std/Test.sol";
import { IReactive } from "@reactive/src/interfaces/IReactive.sol";
import { MockPool } from "../src/MockPool.sol";
import { AISignal } from "../src/AISignal.sol";
import { GuardedStopReactive } from "../src/GuardedStopReactive.sol";
import { StopExecutor } from "../src/StopExecutor.sol";
import { MockSystemContract } from "./mocks/MockSystemContract.sol";

/// @notice State-machine tests for the AI-guarded stop order.
///         The Reactive system contract is replaced by an etched mock at its
///         real address, so `onlySystem` checks and `requestCallbackV_1_0`
///         calls behave exactly as they would on Lasna.
contract GuardedStopTest is Test {
    address internal constant SYSTEM_ADDR = 0x8888888888888888888888888888888888888888;
    address internal constant CRON_CONTRACT = 0x0000000000000000000000000000000000fffFfF;
    uint256 internal constant CRON100_TOPIC = 0xb49937fb8970e19fd46d48f7e3fb00d659deac0347f79cd7cb542f0fc1503c70;
    uint256 internal constant PRICE_TOPIC = uint256(keccak256("PriceUpdate(uint256)"));
    uint256 internal constant ORDER_TOPIC = uint256(keccak256("StopOrderPlaced(uint256,address,uint256,uint256,bool)"));
    uint256 internal constant DECISION_TOPIC = uint256(keccak256("DecisionPosted(uint256,uint8,uint256,bytes32)"));

    uint256 internal constant BASE_SEPOLIA = 84532;
    uint256 internal constant LASNA = 5318007;
    uint256 internal constant START_PRICE = 2500 ether;
    uint256 internal constant STOP_PRICE = 2000 ether;
    uint256 internal constant AMOUNT = 10 ether;

    // GuardedStopReactive.State ordinals
    uint8 internal constant STATE_MONITORING = 1;
    uint8 internal constant STATE_PENDING = 2;
    uint8 internal constant STATE_EXECUTED = 3;
    uint8 internal constant STATE_TIMED_OUT = 4;

    MockSystemContract internal system; // etched view at SYSTEM_ADDR
    MockPool internal pool;
    AISignal internal aiSignal;
    GuardedStopReactive internal reactive;
    StopExecutor internal executor;
    address internal callbackProxy = makeAddr("callbackProxy");
    address internal user = makeAddr("user");

    function setUp() public {
        vm.warp(1_000_000);
        // Etch the mock system contract onto the real system address.
        MockSystemContract mock = new MockSystemContract();
        vm.etch(SYSTEM_ADDR, address(mock).code);
        system = MockSystemContract(payable(SYSTEM_ADDR));

        pool = new MockPool(START_PRICE);
        aiSignal = new AISignal("guard-mlp-v1");
        // Deployment order per the Omni docs: reactive first, executor second,
        // then the executor address is backfilled into the reactive contract.
        reactive = new GuardedStopReactive(BASE_SEPOLIA, address(pool), address(aiSignal), BASE_SEPOLIA);
        executor = new StopExecutor(callbackProxy, address(reactive), address(pool));
        reactive.setExecutor(address(executor));
        pool.setExecutor(address(executor));
    }

    // ---------- helpers ----------

    function _log(address source, uint256 topic0, uint256 topic1, uint256 topic2, bytes memory data, uint256 chainId)
        internal
        pure
        returns (IReactive.LogRecord memory)
    {
        return IReactive.LogRecord({
            chainId: chainId,
            contractAddress: source,
            topic0: topic0,
            topic1: topic1,
            topic2: topic2,
            topic3: 0,
            data: data,
            blockNumber: 1,
            opCode: 3,
            blockHash: 0,
            txHash: 0,
            logIndex: 0
        });
    }

    function _react(IReactive.LogRecord memory log_) internal {
        vm.prank(SYSTEM_ADDR);
        reactive.react(log_);
    }

    /// @dev Place an order on the pool and deliver its StopOrderPlaced log to the guard.
    function _placeOrder(bool failSafeExecute) internal returns (uint256 orderId) {
        vm.prank(user);
        orderId = pool.placeStopOrder(AMOUNT, STOP_PRICE, failSafeExecute);
        _react(
            _log(
                address(pool),
                ORDER_TOPIC,
                orderId,
                uint256(uint160(user)),
                abi.encode(AMOUNT, STOP_PRICE, failSafeExecute),
                BASE_SEPOLIA
            )
        );
    }

    function _feedPrice(uint256 price) internal {
        pool.feedPrice(price);
        _react(_log(address(pool), PRICE_TOPIC, 0, 0, abi.encode(price), BASE_SEPOLIA));
    }

    function _postDecision(uint256 orderId, uint8 verdict, uint256 score) internal {
        _react(
            _log(
                address(aiSignal),
                DECISION_TOPIC,
                orderId,
                0,
                abi.encode(verdict, score, bytes32(uint256(0xFEA7))),
                BASE_SEPOLIA
            )
        );
    }

    function _cronTick() internal {
        _react(_log(CRON_CONTRACT, CRON100_TOPIC, 0, 0, bytes(""), LASNA));
    }

    function _stateOf(uint256 orderId) internal view returns (uint8) {
        (,,,,, GuardedStopReactive.State state,,) = reactive.guarded(orderId);
        return uint8(state);
    }

    // ---------- tests ----------

    function test_SubscribesToAllFourSources() public view {
        assertEq(system.subscriptionCount(), 4, "pool order + pool price + AI decision + cron100");
    }

    /// Path 1: a price breach moves the order into PENDING, and only into PENDING.
    function test_BreachEntersPending() public {
        uint256 orderId = _placeOrder(false);
        assertEq(_stateOf(orderId), STATE_MONITORING);

        _feedPrice(2100 ether); // still above the stop: nothing happens
        assertEq(_stateOf(orderId), STATE_MONITORING);

        _feedPrice(1950 ether); // breach
        assertEq(_stateOf(orderId), STATE_PENDING);
        assertEq(system.callbackCount(), 0, "no execution before the AI answers");
    }

    /// Path 2: an AI VETO cancels the pending state and nothing is executed.
    function test_VetoCancelsPendingAndDoesNotExecute() public {
        uint256 orderId = _placeOrder(false);
        _feedPrice(1500 ether); // deep, fast wick
        assertEq(_stateOf(orderId), STATE_PENDING);

        _postDecision(orderId, 1, 920); // VETO, high confidence it was a wick
        assertEq(_stateOf(orderId), STATE_MONITORING, "veto returns the order to monitoring");
        assertEq(system.callbackCount(), 0, "veto must never request an execution callback");

        // And the position is untouched on the pool side.
        (,,,, bool active, bool settled) = pool.orders(orderId);
        assertTrue(active);
        assertFalse(settled);
    }

    /// Path 3: an AI EXECUTE inside the window requests exactly one callback,
    /// addressed to the executor, whose payload is the executeStop call with the
    /// address(0) placeholder the network will overwrite.
    function test_ExecuteRequestsCallback() public {
        uint256 orderId = _placeOrder(false);
        _feedPrice(1900 ether);
        _postDecision(orderId, 0, 870); // EXECUTE

        assertEq(_stateOf(orderId), STATE_EXECUTED);
        assertEq(system.callbackCount(), 1);
        assertEq(system.lastCallbackChainId(), BASE_SEPOLIA);
        assertEq(system.lastCallbackRecipient(), address(executor));
        assertEq(system.lastCallbackGasLimit(), 1_000_000);

        bytes memory payload = system.lastCallbackPayload();
        bytes memory expected = abi.encodeWithSelector(StopExecutor.executeStop.selector, address(0), orderId);
        assertEq(payload, expected, "payload must carry the address(0) placeholder");
    }

    /// Path 4: no AI answer inside the window + Cron100 sweep → fail-safe.
    /// The default policy is do NOT sell on silence.
    function test_TimeoutFailSafeDoesNotSell() public {
        uint256 orderId = _placeOrder(false); // failSafeExecute = false
        _feedPrice(1900 ether);
        assertEq(_stateOf(orderId), STATE_PENDING);

        vm.warp(block.timestamp + reactive.decisionWindow() + 1);
        _cronTick();

        assertEq(_stateOf(orderId), STATE_TIMED_OUT);
        assertEq(system.callbackCount(), 0, "fail-safe default must not sell");
        (,,,, bool active, bool settled) = pool.orders(orderId);
        assertTrue(active);
        assertFalse(settled);
    }

    /// Companion to path 4: a user who pre-committed failSafeExecute=true is
    /// sold on timeout — the policy is the user's, set at order placement.
    function test_TimeoutFailSafeExecuteWhenUserOptedIn() public {
        uint256 orderId = _placeOrder(true);
        _feedPrice(1900 ether);
        vm.warp(block.timestamp + reactive.decisionWindow() + 1);
        _cronTick();
        assertEq(_stateOf(orderId), STATE_EXECUTED);
        assertEq(system.callbackCount(), 1);
    }

    /// HOLD keeps the order pending and a later EXECUTE still lands.
    function test_HoldThenExecute() public {
        uint256 orderId = _placeOrder(false);
        _feedPrice(1900 ether);
        _postDecision(orderId, 2, 500); // HOLD
        assertEq(_stateOf(orderId), STATE_PENDING);
        _postDecision(orderId, 0, 800); // EXECUTE
        assertEq(_stateOf(orderId), STATE_EXECUTED);
        assertEq(system.callbackCount(), 1);
    }

    /// End to end on the destination side: the callback proxy delivers the
    /// callback, the executor verifies both guards and settles the order.
    function test_CallbackSettlesOrderEndToEnd() public {
        uint256 orderId = _placeOrder(false);
        _feedPrice(1900 ether);
        _postDecision(orderId, 0, 870);
        assertEq(system.callbackCount(), 1);

        // The network delivers via the Base Sepolia callback proxy, injecting
        // the reactive contract's address as the first argument.
        vm.prank(callbackProxy);
        executor.executeStop(address(reactive), orderId);

        assertTrue(executor.executed(orderId));
        (,,,, bool active, bool settled) = pool.orders(orderId);
        assertFalse(active);
        assertTrue(settled);
    }

    /// The executor must reject callbacks that don't come from the proxy, and
    /// callbacks whose injected sender is not our reactive contract.
    function test_CallbackGuardsRejectStrangers() public {
        uint256 orderId = _placeOrder(false);
        vm.expectRevert();
        executor.executeStop(address(reactive), orderId); // caller is not the proxy

        vm.prank(callbackProxy);
        vm.expectRevert();
        executor.executeStop(makeAddr("fakeReactive"), orderId); // wrong injected sender
    }

    /// react() is system-only: a forged LogRecord from anyone else reverts.
    function test_ReactRejectsNonSystemCaller() public {
        IReactive.LogRecord memory log_ = _log(address(pool), PRICE_TOPIC, 0, 0, abi.encode(1 ether), BASE_SEPOLIA);
        vm.expectRevert();
        reactive.react(log_);
    }
}
