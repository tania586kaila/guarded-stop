// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { AbstractCallback } from "@reactive/src/base/AbstractCallback.sol";
import { IPayable } from "@reactive/src/interfaces/IPayable.sol";

/// @notice Minimal view of MockPool's settlement entry point.
interface IMockPool {
    function settleStopOrder(uint256 orderId_)
        external
        returns (address orderOwner, uint256 amount, uint256 executionPrice, uint256 proceeds);
}

/// @title StopExecutor — callback recipient that executes the sell (Base Sepolia)
/// @notice Omni callback pattern: inherits AbstractCallback with BOTH constructor
///         arguments (callback proxy + authorized Reactive contract). The callback
///         method is guarded by `onlyServiceProvider` (the caller really is the
///         chain's callback proxy) AND `onlyCallbackSender` (the address the
///         network injected into the payload really is our Reactive contract).
///         This contract pays for its own callback execution in the destination
///         chain's native coin, so it must be funded on Base Sepolia.
contract StopExecutor is AbstractCallback {
    event StopExecuted(
        uint256 indexed orderId, address indexed owner, uint256 amount, uint256 price, uint256 proceeds
    );

    IMockPool public pool;
    mapping(uint256 => bool) public executed;

    error AlreadyExecuted(uint256 orderId);

    constructor(address callbackProxy_, address reactive_, address pool_)
        AbstractCallback(IPayable(payable(callbackProxy_)), reactive_)
    {
        pool = IMockPool(pool_);
    }

    /// @notice Execute the stop order. `reactive_` is injected by the network
    ///         (it replaces the address(0) placeholder in the request payload).
    function executeStop(address reactive_, uint256 orderId_)
        external
        onlyServiceProvider
        onlyCallbackSender(reactive_)
    {
        if (executed[orderId_]) revert AlreadyExecuted(orderId_);
        executed[orderId_] = true;
        (address orderOwner, uint256 amount, uint256 executionPrice, uint256 proceeds) =
            pool.settleStopOrder(orderId_);
        emit StopExecuted(orderId_, orderOwner, amount, executionPrice, proceeds);
    }
}
