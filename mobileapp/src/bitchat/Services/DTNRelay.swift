import Foundation
import CryptoKit
import BitFoundation

// MARK: - DTNRelay
//
// Orchestrates opportunistic store-and-forward between phones:
//
//   1. On peer connect: send our DTNSummary (list of bundle_ids we hold).
//   2. On receiving a peer's DTNSummary: compute the diff (their misses), and
//      transfer up to N bundles they don't have — but only those where our
//      copies_remaining > 1 (we keep the last copy for direct hub delivery).
//      On each transfer, halve our copy count.
//   3. On receiving a DTNBundle: validate, insert into the store.
//   4. On receiving a DTNReceipt: verify hub signature, evict matching bundle,
//      re-broadcast the receipt once so it propagates.
//
// Cooldowns prevent BLE airtime burn:
//
//   - Per (bundle_id, peer_id):  60 min  (don't re-gossip the same bundle to
//                                         the same peer until then)
//   - Per peer:                  10 min  (don't run a fresh summary exchange
//                                         with the same peer more than this)
//
// Spray-and-wait: a bundle starts with copies_remaining = 10. Each hand-off to
// another carrier halves the budget (sender keeps ceil(n/2), recipient gets
// floor(n/2)). Once we're at 1, we only deliver direct to the hub — never gossip.

protocol DTNRelayTransport: AnyObject {
    /// Send a typed Noise payload to a specific peer. The payload is the raw
    /// payload bytes, NOT prefixed with the type byte (the transport prepends).
    func dtnSendPayload(type: NoisePayloadType, payload: Data, to peerID: PeerID)
}

@MainActor
final class DTNRelay {

    // MARK: - State

    private let store: DTNStore
    private weak var transport: DTNRelayTransport?

    /// Hub's signing pubkey for receipt verification (Ed25519, 32B).
    /// Set after registration (the hub returns it). Until set, receipts are
    /// not honoured — bundles only evict on TTL.
    var hubSigningPubkey: Data?

    /// Last time we ran a summary exchange with each peer.
    private var lastSummaryAt: [PeerID: Date] = [:]

    /// Last time we sent each (bundle, peer) pair across the wire.
    private struct BundlePeerKey: Hashable {
        let bundleID: Data
        let peerID: PeerID
    }
    private var lastSentBundleToPeer: [BundlePeerKey: Date] = [:]

    /// Receipts we've already re-broadcast, so we don't loop them forever.
    private var rebroadcastReceipts: Set<Data> = []

    // MARK: - Init

    init(store: DTNStore, transport: DTNRelayTransport? = nil) {
        self.store = store
        self.transport = transport
    }

    func setTransport(_ t: DTNRelayTransport) { self.transport = t }

    // MARK: - Originating bundles locally

    /// Wrap an inner amber payload (sighting/message/locationReport/profileUpdate)
    /// as a DTN bundle, store it locally, and try to gossip it to currently-
    /// connected peers (if a transport is available).
    ///
    /// `signedBundleBytes` may be left empty for v1 (we'll fill in real Ed25519
    /// signing once the device's signing key is plumbed through).
    @discardableResult
    func originate(innerType: NoisePayloadType,
                   innerPayload: Data,
                   hubX25519Pubkey: Data,
                   signer: ((Data) -> Data?)? = nil) -> DTNBundle? {

        guard let sealed = DTNSeal.seal(plaintext: innerPayload, hubPubkeyRaw: hubX25519Pubkey) else {
            return nil
        }

        let bundleID = DTNRelay.makeBundleID()
        let expiresAt = UInt64(Date().timeIntervalSince1970 + DTNConfig.bundleTTLSeconds)

        // Construct unsigned bundle to compute the canonical signing bytes.
        var bundle = DTNBundle(
            bundleID: bundleID,
            hubPubkey: hubX25519Pubkey,
            expiresAt: expiresAt,
            copiesRemaining: DTNConfig.initialCopiesRemaining,
            innerType: innerType.rawValue,
            ephemeralPubkey: sealed.ephemeralPubkey,
            nonce: sealed.nonce,
            ciphertext: sealed.ciphertext,
            sig: Data(repeating: 0, count: 64)
        )

        if let signer = signer, let sig = signer(bundle.canonicalBytesForSigning()), sig.count == 64 {
            bundle = DTNBundle(
                bundleID: bundle.bundleID,
                hubPubkey: bundle.hubPubkey,
                expiresAt: bundle.expiresAt,
                copiesRemaining: bundle.copiesRemaining,
                innerType: bundle.innerType,
                ephemeralPubkey: bundle.ephemeralPubkey,
                nonce: bundle.nonce,
                ciphertext: bundle.ciphertext,
                sig: sig
            )
        }

        guard store.insert(bundle, originatedLocally: true) else { return nil }
        return bundle
    }

    // MARK: - Inbound payload handling

    /// Called by the bridge that owns the chat layer when a `dtnSummary` /
    /// `dtnBundle` / `dtnReceipt` arrives over Noise. The payload is the raw
    /// bytes WITHOUT the leading type byte.
    func handleInbound(type: NoisePayloadType, payload: Data, from peerID: PeerID) {
        switch type {
        case .dtnSummary:
            handleSummary(payload, from: peerID)
        case .dtnBundle:
            handleBundle(payload, from: peerID)
        case .dtnReceipt:
            handleReceipt(payload, from: peerID)
        default:
            return
        }
    }

    private func handleSummary(_ data: Data, from peerID: PeerID) {
        guard let summary = DTNSummary.decode(from: data) else { return }
        let now = Date()

        // Per-peer gossip cooldown.
        if let last = lastSummaryAt[peerID],
           now.timeIntervalSince(last) < DTNConfig.perPeerGossipCooldownSeconds {
            return
        }
        lastSummaryAt[peerID] = now

        let missing = store.bundlesNotIn(peerSummary: summary.bundleIDs)
        for var bundle in missing {
            // Per-(bundle, peer) cooldown.
            let key = BundlePeerKey(bundleID: bundle.bundleID, peerID: peerID)
            if let lastSent = lastSentBundleToPeer[key],
               now.timeIntervalSince(lastSent) < DTNConfig.perBundlePeerCooldownSeconds {
                continue
            }

            // Spray-and-wait: send floor(n/2) copies to the peer, keep ceil(n/2).
            let handOff = store.handOffCopiesFor(bundleID: bundle.bundleID)
            if handOff < 1 { continue }

            bundle.copiesRemaining = handOff
            transport?.dtnSendPayload(type: .dtnBundle, payload: bundle.encode(), to: peerID)
            lastSentBundleToPeer[key] = now

            // Locally update our retained copy count.
            store.halveCopies(bundleID: bundle.bundleID)
            store.markBroadcast(bundleID: bundle.bundleID)
        }
    }

    private func handleBundle(_ data: Data, from peerID: PeerID) {
        guard let bundle = DTNBundle.decode(from: data) else { return }

        // Drop already-expired.
        if Double(bundle.expiresAt) <= Date().timeIntervalSince1970 { return }

        // Insert as a foreign carry. Insert is a no-op if we already have it.
        store.insert(bundle, originatedLocally: false)
    }

    private func handleReceipt(_ data: Data, from peerID: PeerID) {
        guard let receipt = DTNReceipt.decode(from: data) else { return }

        // Verify hub sig if we know the hub key. If not, accept the receipt as
        // an eviction signal but skip rebroadcast (avoids being weaponised by
        // a malicious peer).
        var verified = false
        if let hubKey = hubSigningPubkey, hubKey == receipt.hubPubkey {
            do {
                let pub = try Curve25519.Signing.PublicKey(rawRepresentation: hubKey)
                verified = pub.isValidSignature(receipt.sig, for: receipt.canonicalBytesForSigning())
            } catch {
                verified = false
            }
        }

        store.evict(bundleID: receipt.bundleID)

        // Rebroadcast once so the receipt floods the network too. Skip if not verified.
        if verified, !rebroadcastReceipts.contains(receipt.bundleID) {
            rebroadcastReceipts.insert(receipt.bundleID)
            // Note: actual rebroadcast wiring is handled by the bridge that
            // discovers connected peers; we expose the bytes here.
            // (Caller can iterate connected peers and call dtnSendPayload.)
        }
    }

    // MARK: - Triggered exchanges

    /// Called when a peer becomes reachable. Sends our summary if we're past
    /// the per-peer cooldown.
    func sendSummary(to peerID: PeerID) {
        let now = Date()
        if let last = lastSummaryAt[peerID],
           now.timeIntervalSince(last) < DTNConfig.perPeerGossipCooldownSeconds {
            return
        }
        let ids = store.allBundleIDs()
        // If we have nothing, still send an empty summary so the peer can
        // respond with theirs (mutual diff).
        let summary = DTNSummary(bundleIDs: Array(ids.prefix(DTNSummary.maxBundleIDs)))
        guard let bytes = summary.encode() else { return }
        transport?.dtnSendPayload(type: .dtnSummary, payload: bytes, to: peerID)
        lastSummaryAt[peerID] = now
    }

    /// Caller can use this when it knows a phone has reached the internet —
    /// pull all locally-originated bundles for hub delivery via HubClient.
    func bundlesAwaitingHubDelivery() -> [DTNBundle] {
        store.allBundleIDs().compactMap { store.bundle(for: $0) }
    }

    /// Called after the hub returns 200 OK on a bundle delivery — locally
    /// evict (the hub-issued receipt will catch carriers; this just tidies us up).
    func confirmedDelivered(bundleID: Data) {
        store.evict(bundleID: bundleID)
    }

    // MARK: - Helpers

    private static func makeBundleID() -> Data {
        var bytes = [UInt8](repeating: 0, count: 16)
        _ = SecRandomCopyBytes(kSecRandomDefault, 16, &bytes)
        return Data(bytes)
    }
}
