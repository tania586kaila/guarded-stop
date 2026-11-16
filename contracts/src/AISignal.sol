// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

/// @title AISignal — on-chain inbox for the off-chain AI guard's decisions (Base Sepolia)
/// @notice The AI service watches for pending stop orders, classifies the price
///         action (flash wick vs. real trend reversal) and posts its verdict
///         here. Posting on-chain makes every decision auditable and turns the
///         verdict into an event the Lasna Reactive contract can react to —
///         the AI is a link in the running loop, not a code-writing tool.
contract AISignal {
    enum Verdict {
        EXECUTE, // real downtrend: let the stop order execute
        VETO, // flash wick: cancel the pending state, keep the position
        HOLD // undecided: stay pending until the decision window lapses

    }

    event DecisionPosted(uint256 indexed orderId, Verdict verdict, uint256 score, bytes32 reasonHash);

    struct Decision {
        Verdict verdict;
        uint256 score; // model confidence, 0..1000
        bytes32 reasonHash; // hash of the feature vector + human-readable explanation
        uint256 postedAt;
        bool exists;
    }

    address public owner;
    /// @notice Version string of the model whose decisions are being posted.
    string public modelVersion;
    /// @notice Addresses allowed to post decisions (the AI guard service).
    mapping(address => bool) public posters;
    mapping(uint256 => Decision) public decisions;

    error NotOwner();
    error NotPoster();

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    modifier onlyPoster() {
        if (!posters[msg.sender]) revert NotPoster();
        _;
    }

    constructor(string memory modelVersion_) {
        owner = msg.sender;
        posters[msg.sender] = true;
        modelVersion = modelVersion_;
    }

    function setPoster(address poster_, bool allowed_) external onlyOwner {
        posters[poster_] = allowed_;
    }

    function setModelVersion(string memory modelVersion_) external onlyOwner {
        modelVersion = modelVersion_;
    }

    /// @notice Post the AI verdict for a pending stop order.
    /// @param orderId_   The stop order this decision is about.
    /// @param verdict_   EXECUTE / VETO / HOLD.
    /// @param score_     Model confidence, 0..1000.
    /// @param reasonHash_ Hash of the features + explanation, for off-chain reproducibility.
    function postDecision(uint256 orderId_, Verdict verdict_, uint256 score_, bytes32 reasonHash_)
        external
        onlyPoster
    {
        decisions[orderId_] =
            Decision({ verdict: verdict_, score: score_, reasonHash: reasonHash_, postedAt: block.timestamp, exists: true });
        emit DecisionPosted(orderId_, verdict_, score_, reasonHash_);
    }
}
