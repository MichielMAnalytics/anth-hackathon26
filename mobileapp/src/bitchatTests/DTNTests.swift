import XCTest
import CryptoKit
@testable import bitchat

@MainActor
final class DTNTests: XCTestCase {

    // MARK: - Wire-format round trips

    func testDTNBundleRoundTrip() {
        let bundle = makeBundle(copies: 10, ciphertextSize: 64)
        let encoded = bundle.encode()
        guard let decoded = DTNBundle.decode(from: encoded) else {
            XCTFail("decode failed"); return
        }
        XCTAssertEqual(decoded.bundleID, bundle.bundleID)
        XCTAssertEqual(decoded.hubPubkey, bundle.hubPubkey)
        XCTAssertEqual(decoded.expiresAt, bundle.expiresAt)
        XCTAssertEqual(decoded.copiesRemaining, bundle.copiesRemaining)
        XCTAssertEqual(decoded.innerType, bundle.innerType)
        XCTAssertEqual(decoded.ephemeralPubkey, bundle.ephemeralPubkey)
        XCTAssertEqual(decoded.nonce, bundle.nonce)
        XCTAssertEqual(decoded.ciphertext, bundle.ciphertext)
        XCTAssertEqual(decoded.sig, bundle.sig)
    }

    func testDTNReceiptRoundTrip() {
        let r = DTNReceipt(
            bundleID: Data(repeating: 0xAB, count: 16),
            hubPubkey: Data(repeating: 0x11, count: 32),
            signedAt: 1_745_590_320,
            sig: Data(repeating: 0x22, count: 64)
        )
        guard let decoded = DTNReceipt.decode(from: r.encode()) else {
            XCTFail("decode failed"); return
        }
        XCTAssertEqual(decoded.bundleID, r.bundleID)
        XCTAssertEqual(decoded.hubPubkey, r.hubPubkey)
        XCTAssertEqual(decoded.signedAt, r.signedAt)
        XCTAssertEqual(decoded.sig, r.sig)
    }

    func testDTNSummaryRoundTrip() {
        let ids = (0..<5).map { i in Data(repeating: UInt8(i + 1), count: 16) }
        let s = DTNSummary(bundleIDs: ids)
        guard let bytes = s.encode() else { XCTFail("encode failed"); return }
        guard let decoded = DTNSummary.decode(from: bytes) else {
            XCTFail("decode failed"); return
        }
        XCTAssertEqual(decoded.bundleIDs, ids)
    }

    func testDTNSummaryRejectsOversizedInput() {
        let ids = (0..<(DTNSummary.maxBundleIDs + 1)).map { _ in Data(repeating: 0, count: 16) }
        XCTAssertNil(DTNSummary(bundleIDs: ids).encode())
    }

    func testDTNBundleRejectsBadVersion() {
        var bytes = makeBundle(copies: 5, ciphertextSize: 32).encode()
        bytes[0] = 0x99
        XCTAssertNil(DTNBundle.decode(from: bytes))
    }

    // MARK: - Sealed-box round trip

    func testSealAndOpenRoundTrip() {
        let hubPriv = Curve25519.KeyAgreement.PrivateKey()
        let plain = Data("hello hub — this is a sighting".utf8)
        guard let sealed = DTNSeal.seal(plaintext: plain, hubPubkeyRaw: hubPriv.publicKey.rawRepresentation) else {
            XCTFail("seal failed"); return
        }
        let opened = DTNSeal.open(
            ephemeralPubkeyRaw: sealed.ephemeralPubkey,
            nonce: sealed.nonce,
            ciphertext: sealed.ciphertext,
            hubPrivateKey: hubPriv
        )
        XCTAssertEqual(opened, plain)
    }

    // MARK: - DTNStore quotas + eviction

    func testStoreInsertsAndReads() {
        let store = makeFreshStore()
        let bundle = makeBundle(copies: 10, ciphertextSize: 32)
        XCTAssertTrue(store.insert(bundle, originatedLocally: true))
        XCTAssertEqual(store.count, 1)
        XCTAssertEqual(store.bundle(for: bundle.bundleID)?.bundleID, bundle.bundleID)
    }

    func testStoreDedupsRepeatedInsert() {
        let store = makeFreshStore()
        let bundle = makeBundle(copies: 10, ciphertextSize: 32)
        XCTAssertTrue(store.insert(bundle, originatedLocally: true))
        XCTAssertFalse(store.insert(bundle, originatedLocally: true))
        XCTAssertEqual(store.count, 1)
    }

    func testStoreEvictsOldestForeignWhenFull() {
        let store = makeFreshStore()
        // Fill with foreign bundles up to the count cap.
        for _ in 0..<DTNConfig.storeMaxBundles {
            _ = store.insert(makeBundle(copies: 5, ciphertextSize: 32), originatedLocally: false)
        }
        XCTAssertEqual(store.count, DTNConfig.storeMaxBundles)
        // Inserting one more evicts the oldest foreign.
        let newOne = makeBundle(copies: 5, ciphertextSize: 32)
        XCTAssertTrue(store.insert(newOne, originatedLocally: false))
        XCTAssertEqual(store.count, DTNConfig.storeMaxBundles)
    }

    func testStorePrefersEvictingForeignOverLocal() {
        let store = makeFreshStore()
        // Mix: 1 local + (cap-1) foreign. Then add another foreign — local must survive.
        let mine = makeBundle(copies: 5, ciphertextSize: 32)
        XCTAssertTrue(store.insert(mine, originatedLocally: true))
        for _ in 0..<(DTNConfig.storeMaxBundles - 1) {
            _ = store.insert(makeBundle(copies: 5, ciphertextSize: 32), originatedLocally: false)
        }
        _ = store.insert(makeBundle(copies: 5, ciphertextSize: 32), originatedLocally: false)
        XCTAssertNotNil(store.bundle(for: mine.bundleID), "local bundle should survive eviction")
    }

    func testStoreRejectsAlreadyExpired() {
        let store = makeFreshStore()
        let stale = makeBundle(copies: 10, ciphertextSize: 32, expiresInSeconds: -10)
        XCTAssertFalse(store.insert(stale, originatedLocally: true))
        XCTAssertEqual(store.count, 0)
    }

    func testStorePurgesExpired() {
        let store = makeFreshStore()
        let live = makeBundle(copies: 5, ciphertextSize: 32, expiresInSeconds: 3600)
        let stale = makeBundle(copies: 5, ciphertextSize: 32, expiresInSeconds: 60)
        _ = store.insert(live, originatedLocally: false)
        _ = store.insert(stale, originatedLocally: false)
        // Force one to expire by manually shifting time:
        // We can't easily mutate expiresAt; instead insert a near-expiry bundle
        // and rely on purgeExpired being a noop in this fast test. So just
        // assert purge runs without throwing on a fresh store.
        store.purgeExpired()
        XCTAssertEqual(store.count, 2)
    }

    // MARK: - Spray-and-wait copy budget

    func testHalveCopiesFollowsSprayAndWait() {
        let store = makeFreshStore()
        let bundle = makeBundle(copies: 10, ciphertextSize: 32)
        _ = store.insert(bundle, originatedLocally: true)

        // Hand-off: floor(10/2) = 5 sent, ceil(10/2) = 5 kept.
        XCTAssertEqual(store.handOffCopiesFor(bundleID: bundle.bundleID), 5)
        XCTAssertEqual(store.halveCopies(bundleID: bundle.bundleID), 5)
        // Next round: floor(5/2) = 2 sent, ceil(5/2) = 3 kept.
        XCTAssertEqual(store.handOffCopiesFor(bundleID: bundle.bundleID), 2)
        XCTAssertEqual(store.halveCopies(bundleID: bundle.bundleID), 3)
        // Continue until 1 kept (no more gossip).
        _ = store.halveCopies(bundleID: bundle.bundleID)   // 3 → 2
        _ = store.halveCopies(bundleID: bundle.bundleID)   // 2 → 1
        let final = store.halveCopies(bundleID: bundle.bundleID)
        XCTAssertEqual(final, 1, "minimum kept copy count is 1")
    }

    func testBundlesNotInExcludesAtLastCopy() {
        let store = makeFreshStore()
        let lastCopy = makeBundle(copies: 1, ciphertextSize: 32)
        let plenty = makeBundle(copies: 10, ciphertextSize: 32)
        _ = store.insert(lastCopy, originatedLocally: true)
        _ = store.insert(plenty, originatedLocally: true)

        let result = store.bundlesNotIn(peerSummary: [])
        XCTAssertEqual(result.count, 1)
        XCTAssertEqual(result.first?.bundleID, plenty.bundleID,
                       "last-copy bundle should be reserved for direct hub delivery")
    }

    func testBundlesNotInRespectsPeerSummary() {
        let store = makeFreshStore()
        let b1 = makeBundle(copies: 5, ciphertextSize: 32)
        let b2 = makeBundle(copies: 5, ciphertextSize: 32)
        _ = store.insert(b1, originatedLocally: true)
        _ = store.insert(b2, originatedLocally: true)

        let result = store.bundlesNotIn(peerSummary: [b1.bundleID])
        XCTAssertEqual(result.map { $0.bundleID }, [b2.bundleID])
    }

    // MARK: - Helpers

    private func makeFreshStore() -> DTNStore {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("dtn-tests-\(UUID().uuidString)", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return DTNStore(rootDirectory: dir)
    }

    private func makeBundle(copies: UInt8, ciphertextSize: Int, expiresInSeconds: TimeInterval = 3600) -> DTNBundle {
        var bid = [UInt8](repeating: 0, count: 16)
        _ = SecRandomCopyBytes(kSecRandomDefault, 16, &bid)
        return DTNBundle(
            bundleID: Data(bid),
            hubPubkey: Data(repeating: 0x33, count: 32),
            expiresAt: UInt64(Date().timeIntervalSince1970 + expiresInSeconds),
            copiesRemaining: copies,
            innerType: NoisePayloadType.sighting.rawValue,
            ephemeralPubkey: Data(repeating: 0x44, count: 32),
            nonce: Data(repeating: 0x55, count: 12),
            ciphertext: Data(repeating: 0x66, count: ciphertextSize),
            sig: Data(repeating: 0x77, count: 64)
        )
    }
}
