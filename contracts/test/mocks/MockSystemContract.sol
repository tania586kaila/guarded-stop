// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { ISystemContract } from "@reactive/src/interfaces/ISystemContract.sol";

/// @title MockSystemContract — test double for the Reactive system contract.
/// @notice In tests this contract's code is etched onto the real system contract
///         address (0x8888…8888) so GuardedStopReactive's constructor-time
///         subscriptions and its callback requests land here and can be asserted.
///         It records subscriptions and the last callback request.
contract MockSystemContract is ISystemContract {
    struct Subscription {
        uint256 chainId;
        address contractAddress;
        uint256 topic0;
    }

    Subscription[] public subscriptions;
    uint256 public unsubscribeCount;

    uint256 public callbackCount;
    uint256 public lastCallbackChainId;
    address public lastCallbackRecipient;
    uint64 public lastCallbackGasLimit;
    bytes public lastCallbackPayload;

    function subscribe(
        uint256 chainId_,
        address contract_,
        uint256 topic0_,
        uint256, // topic1_
        uint256, // topic2_
        uint256 // topic3_
    ) external override {
        subscriptions.push(Subscription({ chainId: chainId_, contractAddress: contract_, topic0: topic0_ }));
    }

    function unsubscribe(uint256, address, uint256, uint256, uint256, uint256) external override {
        unsubscribeCount++;
    }

    function requestCallback(CallbackVersion, bytes memory) external override {
        callbackCount++;
    }

    function requestCallbackV_1_0(CallbackConfiguration_V_1_0 memory config_) external override {
        callbackCount++;
        lastCallbackChainId = config_.chainId;
        lastCallbackRecipient = config_.recipient;
        lastCallbackGasLimit = config_.gasLimit;
        lastCallbackPayload = config_.payload;
    }

    function subscriptionCount() external view returns (uint256) {
        return subscriptions.length;
    }

    function debt(address) external pure override returns (uint256) {
        return 0;
    }

    receive() external payable override {}
}
