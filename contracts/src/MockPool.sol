// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

/// @title MockPool — demo price-feed / stop-order registry (Base Sepolia)
/// @notice Stands in for a Uniswap V2 style pair: the operator feeds a scripted
///         price series (so wicks and real downtrends can be staged on testnet,
///         which a real testnet pool cannot do on cue), and users register stop
///         orders against it. Event shapes mirror a real Pair (`Sync` plus an
///         explicit `PriceUpdate`), so swapping this for a real pool only means
///         pointing the Reactive contract at the pair address and its `Sync`
///         topic — see README.
contract MockPool {
    /// @notice Pair-shaped reserve event, kept for interface parity with a real V2 pair.
    event Sync(uint112 reserve0, uint112 reserve1);
    /// @notice Emitted on every price feed; this is what the Reactive contract subscribes to.
    event PriceUpdate(uint256 price);
    /// @notice Emitted when a stop order is registered; the Reactive contract learns orders from it.
    event StopOrderPlaced(
        uint256 indexed orderId, address indexed owner, uint256 amount, uint256 stopPrice, bool failSafeExecute
    );
    /// @notice Emitted when a stop order is settled by the authorized executor.
    event StopSettled(uint256 indexed orderId, address indexed owner, uint256 amount, uint256 price, uint256 proceeds);

    struct Order {
        address owner;
        uint256 amount; // token amount to sell (1e18 = 1 token, demo accounting)
        uint256 stopPrice; // trigger price, 1e18-scaled USD
        bool failSafeExecute; // user's timeout policy: true = sell anyway if AI never answers
        bool active;
        bool settled;
    }

    address public owner;
    /// @notice The only address allowed to settle orders (the StopExecutor callback contract).
    address public executor;
    /// @notice Current price, 1e18-scaled USD.
    uint256 public price;
    uint256 public nextOrderId = 1;
    mapping(uint256 => Order) public orders;

    error NotOwner();
    error NotExecutor();
    error OrderNotActive(uint256 orderId);

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    constructor(uint256 initialPrice_) {
        owner = msg.sender;
        price = initialPrice_;
    }

    function setExecutor(address executor_) external onlyOwner {
        executor = executor_;
    }

    /// @notice Feed a new price (demo operator / script). Emits the Pair-shaped
    ///         `Sync` first, then the explicit `PriceUpdate` the guard listens to.
    function feedPrice(uint256 newPrice_) external onlyOwner {
        price = newPrice_;
        uint112 reserve0 = 1_000_000 ether;
        uint112 reserve1 = uint112(uint256(reserve0) * newPrice_ / 1 ether);
        emit Sync(reserve0, reserve1);
        emit PriceUpdate(newPrice_);
    }

    /// @notice Register a stop order. `failSafeExecute` is the user's pre-committed
    ///         timeout policy; the Reactive contract reads it from this event.
    function placeStopOrder(uint256 amount_, uint256 stopPrice_, bool failSafeExecute_)
        external
        returns (uint256 orderId)
    {
        orderId = nextOrderId++;
        orders[orderId] = Order({
            owner: msg.sender,
            amount: amount_,
            stopPrice: stopPrice_,
            failSafeExecute: failSafeExecute_,
            active: true,
            settled: false
        });
        emit StopOrderPlaced(orderId, msg.sender, amount_, stopPrice_, failSafeExecute_);
    }

    /// @notice Settle a stop order at the current price. Only the StopExecutor
    ///         (reached via a verified Reactive callback) may call this.
    function settleStopOrder(uint256 orderId_)
        external
        returns (address orderOwner, uint256 amount, uint256 executionPrice, uint256 proceeds)
    {
        if (msg.sender != executor) revert NotExecutor();
        Order storage order = orders[orderId_];
        if (!order.active || order.settled) revert OrderNotActive(orderId_);
        order.settled = true;
        order.active = false;
        executionPrice = price;
        amount = order.amount;
        orderOwner = order.owner;
        proceeds = amount * executionPrice / 1 ether;
        emit StopSettled(orderId_, orderOwner, amount, executionPrice, proceeds);
    }
}
