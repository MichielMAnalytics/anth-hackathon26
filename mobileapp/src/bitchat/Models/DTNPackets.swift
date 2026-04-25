import Foundation
import CryptoKit

// MARK: - DTN (Delay-Tolerant Networking) packet formats
//
// Three new payload types implement opportunistic store-and-forward for amber
// payloads when no path to the hub currently exists:
//
//   - DTNBundle  (0x25): an opaque envelope gossipped phone-to-phone, carrying a
//                        sighting / message / location-report / profile-update
//                        encrypted to the hub's X25519 pubkey.
//   - DTNReceipt (0x26): hub-signed delivery confirmation. Floods the same way
//                        as bundles and triggers carriers to evict the matching
//                        bundle from their on-disk store.
//   - DTNSummary (0x27): anti-entropy summary vector — a list of bundle_ids the
//                        sender already holds. Peers exchange these on connect
//                        so we only transfer bundles the other side is missing.
//
// Wire format is fixed-binary (not TLV) — DTN packets travel in volume across a
// constrained mesh, and 50% smaller wire size = noticeably less BLE radio time
// = less battery. A 1-byte version prefix gives us forward-compat: clients
// drop unknown versions silently.
//
// Spray-and-wait: each bundle carries `copies_remaining`. When we hand a copy to
// another carrier we halve the budget; once a bundle is at 1 copy the holder
// only delivers to the hub directly, never re-gossips.

// MARK: - DTNBundle

/// Opaque envelope addressed to the hub, signed by the originating reporter,
/// gossipped peer-to-peer until it reaches a phone with internet (or until
/// the hub broadcasts a receipt that triggers eviction).
struct DTNBundle {
    static let version: UInt8 = 0x01

    let bundleID: Data            // 16B random; also the dedup key
    let hubPubkey: Data           // 32B X25519 — the destination
    let expiresAt: UInt64         // unix seconds
    var copiesRemaining: UInt8    // spray-and-wait budget, mutated on hand-off
    let innerType: UInt8          // original NoisePayloadType.rawValue (sighting, etc.)
    let ephemeralPubkey: Data     // 32B X25519 ephemeral, for sealed-box
    let nonce: Data               // 12B for ChaChaPoly
    let ciphertext: Data          // sealed inner payload (includes 16B Poly1305 tag)
    let sig: Data                 // 64B Ed25519 over all preceding bytes, by reporter key

    func encode() -> Data {
        var data = Data()
        data.append(Self.version)
        data.append(bundleID)
        data.append(hubPubkey)
        var ts = expiresAt.bigEndian
        data.append(Data(bytes: &ts, count: 8))
        data.append(copiesRemaining)
        data.append(innerType)
        data.append(ephemeralPubkey)
        data.append(nonce)
        var clen = UInt32(ciphertext.count).bigEndian
        data.append(Data(bytes: &clen, count: 4))
        data.append(ciphertext)
        data.append(sig)
        return data
    }

    static func decode(from data: Data) -> DTNBundle? {
        // Minimum size: 1 + 16 + 32 + 8 + 1 + 1 + 32 + 12 + 4 + 64 = 171 bytes (with empty ciphertext).
        guard data.count >= 171 else { return nil }
        let bytes = Array(data)
        var off = 0

        guard bytes[off] == Self.version else { return nil }
        off += 1

        let bundleID = Data(bytes[off..<off+16]); off += 16
        let hubPubkey = Data(bytes[off..<off+32]); off += 32

        var ts: UInt64 = 0
        for i in 0..<8 { ts = (ts << 8) | UInt64(bytes[off+i]) }
        off += 8

        let copies = bytes[off]; off += 1
        let inner = bytes[off]; off += 1

        let ephem = Data(bytes[off..<off+32]); off += 32
        let nonce = Data(bytes[off..<off+12]); off += 12

        var clen: UInt32 = 0
        for i in 0..<4 { clen = (clen << 8) | UInt32(bytes[off+i]) }
        off += 4

        guard off + Int(clen) + 64 <= data.count else { return nil }
        let ct = Data(bytes[off..<off+Int(clen)]); off += Int(clen)
        let sig = Data(bytes[off..<off+64])

        return DTNBundle(
            bundleID: bundleID,
            hubPubkey: hubPubkey,
            expiresAt: ts,
            copiesRemaining: copies,
            innerType: inner,
            ephemeralPubkey: ephem,
            nonce: nonce,
            ciphertext: ct,
            sig: sig
        )
    }

    /// Bytes covered by `sig` — everything in the encoded packet except the trailing 64B signature.
    func canonicalBytesForSigning() -> Data {
        var data = Data()
        data.append(Self.version)
        data.append(bundleID)
        data.append(hubPubkey)
        var ts = expiresAt.bigEndian
        data.append(Data(bytes: &ts, count: 8))
        data.append(copiesRemaining)
        data.append(innerType)
        data.append(ephemeralPubkey)
        data.append(nonce)
        var clen = UInt32(ciphertext.count).bigEndian
        data.append(Data(bytes: &clen, count: 4))
        data.append(ciphertext)
        return data
    }
}

// MARK: - DTNReceipt

/// Hub-signed delivery confirmation. When carriers receive this they evict the
/// matching bundle and re-broadcast the receipt once so it propagates.
struct DTNReceipt {
    static let version: UInt8 = 0x01

    let bundleID: Data        // 16B
    let hubPubkey: Data       // 32B — also the verifier
    let signedAt: UInt64      // unix seconds
    let sig: Data             // 64B Ed25519 by hubPubkey

    func encode() -> Data {
        var data = Data()
        data.append(Self.version)
        data.append(bundleID)
        data.append(hubPubkey)
        var ts = signedAt.bigEndian
        data.append(Data(bytes: &ts, count: 8))
        data.append(sig)
        return data
    }

    static func decode(from data: Data) -> DTNReceipt? {
        // 1 + 16 + 32 + 8 + 64 = 121 bytes.
        guard data.count >= 121 else { return nil }
        let bytes = Array(data)
        var off = 0

        guard bytes[off] == Self.version else { return nil }
        off += 1

        let bundleID = Data(bytes[off..<off+16]); off += 16
        let hubPubkey = Data(bytes[off..<off+32]); off += 32

        var ts: UInt64 = 0
        for i in 0..<8 { ts = (ts << 8) | UInt64(bytes[off+i]) }
        off += 8

        let sig = Data(bytes[off..<off+64])

        return DTNReceipt(bundleID: bundleID, hubPubkey: hubPubkey, signedAt: ts, sig: sig)
    }

    func canonicalBytesForSigning() -> Data {
        var data = Data()
        data.append(Self.version)
        data.append(bundleID)
        data.append(hubPubkey)
        var ts = signedAt.bigEndian
        data.append(Data(bytes: &ts, count: 8))
        return data
    }
}

// MARK: - DTNSummary

/// Anti-entropy summary vector. Peers exchange these on connect; the receiver
/// computes the diff and transfers only bundles the sender is missing.
struct DTNSummary {
    static let version: UInt8 = 0x01
    static let maxBundleIDs: Int = 256   // caps wire size at ~4KB

    let bundleIDs: [Data]   // each 16B

    func encode() -> Data? {
        guard bundleIDs.count <= Self.maxBundleIDs else { return nil }
        guard bundleIDs.allSatisfy({ $0.count == 16 }) else { return nil }
        var data = Data()
        data.append(Self.version)
        var count = UInt16(bundleIDs.count).bigEndian
        data.append(Data(bytes: &count, count: 2))
        for id in bundleIDs { data.append(id) }
        return data
    }

    static func decode(from data: Data) -> DTNSummary? {
        guard data.count >= 3 else { return nil }
        let bytes = Array(data)
        guard bytes[0] == Self.version else { return nil }

        var count: UInt16 = 0
        count = (UInt16(bytes[1]) << 8) | UInt16(bytes[2])
        let n = Int(count)
        guard n <= Self.maxBundleIDs else { return nil }
        guard data.count >= 3 + n * 16 else { return nil }

        var ids: [Data] = []
        ids.reserveCapacity(n)
        var off = 3
        for _ in 0..<n {
            ids.append(Data(bytes[off..<off+16]))
            off += 16
        }
        return DTNSummary(bundleIDs: ids)
    }
}

// MARK: - Sealed-box encryption helpers
//
// One-shot encryption of a payload to the hub's X25519 public key, using:
//   ephemeral X25519 keypair  →  shared secret with hub  →  HKDF(SHA256)
//   →  symmetric key  →  ChaChaPoly.seal
//
// The hub decrypts using its X25519 private key + the bundle's ephemeral_pubkey.

enum DTNSeal {
    private static let hkdfInfo = Data("safethread-dtn-v1".utf8)

    struct Sealed {
        let ephemeralPubkey: Data   // 32B
        let nonce: Data             // 12B
        let ciphertext: Data        // includes 16B tag
    }

    /// Seal `plaintext` to `hubPubkeyRaw` (32B X25519 raw representation).
    static func seal(plaintext: Data, hubPubkeyRaw: Data) -> Sealed? {
        guard hubPubkeyRaw.count == 32 else { return nil }
        do {
            let hubPub = try Curve25519.KeyAgreement.PublicKey(rawRepresentation: hubPubkeyRaw)
            let ephem = Curve25519.KeyAgreement.PrivateKey()
            let shared = try ephem.sharedSecretFromKeyAgreement(with: hubPub)
            let key = shared.hkdfDerivedSymmetricKey(
                using: SHA256.self,
                salt: Data(),
                sharedInfo: hkdfInfo,
                outputByteCount: 32
            )
            let sealedBox = try ChaChaPoly.seal(plaintext, using: key)
            return Sealed(
                ephemeralPubkey: ephem.publicKey.rawRepresentation,
                nonce: sealedBox.nonce.withUnsafeBytes { Data($0) },
                ciphertext: sealedBox.ciphertext + sealedBox.tag
            )
        } catch {
            return nil
        }
    }

    /// Decrypt a bundle's sealed payload using the hub's X25519 private key.
    /// Used hub-side only; included here so client tests can round-trip.
    static func open(ephemeralPubkeyRaw: Data, nonce: Data, ciphertext: Data,
                     hubPrivateKey: Curve25519.KeyAgreement.PrivateKey) -> Data? {
        guard ephemeralPubkeyRaw.count == 32, nonce.count == 12, ciphertext.count >= 16 else { return nil }
        do {
            let ephem = try Curve25519.KeyAgreement.PublicKey(rawRepresentation: ephemeralPubkeyRaw)
            let shared = try hubPrivateKey.sharedSecretFromKeyAgreement(with: ephem)
            let key = shared.hkdfDerivedSymmetricKey(
                using: SHA256.self,
                salt: Data(),
                sharedInfo: hkdfInfo,
                outputByteCount: 32
            )
            let ct = ciphertext.prefix(ciphertext.count - 16)
            let tag = ciphertext.suffix(16)
            let cpNonce = try ChaChaPoly.Nonce(data: nonce)
            let box = try ChaChaPoly.SealedBox(nonce: cpNonce, ciphertext: ct, tag: tag)
            return try ChaChaPoly.open(box, using: key)
        } catch {
            return nil
        }
    }
}

// MARK: - DTN tuning constants

enum DTNConfig {
    /// Total on-disk store cap. Kept low — war-zone phones are storage-starved.
    static let storeMaxBytes: Int = 512 * 1024     // 512 KB

    /// Hard cap on bundle count regardless of byte budget.
    static let storeMaxBundles: Int = 15

    /// Bundle TTL after creation. Long enough to find a route over a few days
    /// of intermittent connectivity, short enough to bound the storage burden.
    static let bundleTTLSeconds: TimeInterval = 48 * 60 * 60   // 48 h

    /// Initial spray-and-wait copy budget when a phone originates a bundle.
    static let initialCopiesRemaining: UInt8 = 10

    /// Don't re-gossip the same bundle to the same peer more than once per this window.
    static let perBundlePeerCooldownSeconds: TimeInterval = 60 * 60   // 60 min

    /// Don't run a summary-vector exchange with the same peer more than once per this window.
    static let perPeerGossipCooldownSeconds: TimeInterval = 10 * 60   // 10 min

    /// Periodic on-disk purge cadence (drops expired bundles).
    static let purgeIntervalSeconds: TimeInterval = 10 * 60   // 10 min
}
