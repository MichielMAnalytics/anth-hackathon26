import Foundation

// MARK: - DTNStore
//
// Disk-backed storage for in-flight DTN bundles. Bundles live as raw bytes
// under `Application Support/dtn/<hex_bundle_id>.bundle`, plus a small
// `index.json` summarising what we have and how to evict.
//
// Quotas are intentionally tight (war-zone phones are storage- and battery-
// starved):
//
//   - storeMaxBytes  : 512 KB total
//   - storeMaxBundles: 15
//   - bundleTTL      : 48 h
//
// Eviction order when full: expired first, then oldest-first across foreign
// (carried-for-someone-else) bundles. Bundles we originated locally are evicted
// last — the user's *own* sighting/message is what we most want to deliver.

@MainActor
final class DTNStore {

    // MARK: - On-disk index

    private struct IndexEntry: Codable {
        let bundleID: Data
        let expiresAt: UInt64
        var copiesRemaining: UInt8
        var lastBroadcastAt: TimeInterval   // unix; 0 = never
        let originatedLocally: Bool
        let sizeBytes: Int
        let storedAt: TimeInterval          // unix; for tie-breaking eviction
    }

    private struct Index: Codable {
        var entries: [IndexEntry]
    }

    // MARK: - State

    private let directory: URL
    private let indexURL: URL
    private var index: Index
    private var purgeTimer: Timer?

    // MARK: - Init

    init(rootDirectory: URL? = nil) {
        let base = rootDirectory ?? Self.defaultRoot()
        self.directory = base.appendingPathComponent("dtn", isDirectory: true)
        self.indexURL = self.directory.appendingPathComponent("index.json")
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        self.index = Self.loadIndex(at: indexURL) ?? Index(entries: [])
        startPurgeTimer()
    }

    deinit {
        purgeTimer?.invalidate()
    }

    private static func defaultRoot() -> URL {
        if let appSupport = try? FileManager.default.url(
            for: .applicationSupportDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        ) {
            return appSupport
        }
        return FileManager.default.temporaryDirectory
    }

    // MARK: - Public API

    /// Number of bundles currently held.
    var count: Int { index.entries.count }

    /// Total bytes currently used by all stored bundles.
    var byteCount: Int { index.entries.reduce(0) { $0 + $1.sizeBytes } }

    /// IDs of every bundle we currently hold. Used to build a `DTNSummary`.
    func allBundleIDs() -> [Data] {
        index.entries.map { $0.bundleID }
    }

    /// Insert a bundle into the store. Returns `false` if it was already present
    /// or if it can't fit even after eviction. Mutates the bundle's
    /// `copiesRemaining` field on disk via the index.
    @discardableResult
    func insert(_ bundle: DTNBundle, originatedLocally: Bool) -> Bool {
        // Reject already-expired bundles.
        let now = Date().timeIntervalSince1970
        if Double(bundle.expiresAt) <= now { return false }

        // Dedup.
        if index.entries.contains(where: { $0.bundleID == bundle.bundleID }) {
            return false
        }

        let encoded = bundle.encode()

        // A single bundle that exceeds the entire byte cap can't be stored at all.
        if encoded.count > DTNConfig.storeMaxBytes { return false }

        // Make room.
        evictUntilFits(incomingBytes: encoded.count)

        // Persist bundle bytes.
        let url = bundleURL(for: bundle.bundleID)
        do {
            try encoded.write(to: url, options: .atomic)
        } catch {
            return false
        }

        // Update index.
        let entry = IndexEntry(
            bundleID: bundle.bundleID,
            expiresAt: bundle.expiresAt,
            copiesRemaining: bundle.copiesRemaining,
            lastBroadcastAt: 0,
            originatedLocally: originatedLocally,
            sizeBytes: encoded.count,
            storedAt: now
        )
        index.entries.append(entry)
        saveIndex()
        return true
    }

    /// Read back a bundle by ID. Returns `nil` if not present, expired, or unreadable.
    func bundle(for bundleID: Data) -> DTNBundle? {
        guard let entry = index.entries.first(where: { $0.bundleID == bundleID }) else {
            return nil
        }
        if Double(entry.expiresAt) <= Date().timeIntervalSince1970 {
            return nil
        }
        let url = bundleURL(for: bundleID)
        guard let data = try? Data(contentsOf: url) else { return nil }
        return DTNBundle.decode(from: data)
    }

    /// Remove a bundle. Idempotent.
    func evict(bundleID: Data) {
        guard let idx = index.entries.firstIndex(where: { $0.bundleID == bundleID }) else { return }
        let url = bundleURL(for: bundleID)
        try? FileManager.default.removeItem(at: url)
        index.entries.remove(at: idx)
        saveIndex()
    }

    /// Compute which of our stored bundles the peer is missing, given their
    /// summary vector. Returns at most `limit` entries to bound BLE airtime.
    func bundlesNotIn(peerSummary: [Data], limit: Int = 8) -> [DTNBundle] {
        let peerSet = Set(peerSummary)
        var out: [DTNBundle] = []
        for entry in index.entries where !peerSet.contains(entry.bundleID) {
            // Don't gossip bundles where we're at our last copy — those are reserved
            // for direct delivery to the hub.
            if entry.copiesRemaining <= 1 { continue }
            // Skip expired in case the purge timer hasn't run yet.
            if Double(entry.expiresAt) <= Date().timeIntervalSince1970 { continue }
            if let b = bundle(for: entry.bundleID) {
                out.append(b)
                if out.count >= limit { break }
            }
        }
        return out
    }

    /// Halve a bundle's `copies_remaining` after we've handed a copy to a peer.
    /// Returns the new count (kept by us).
    @discardableResult
    func halveCopies(bundleID: Data) -> UInt8? {
        guard let idx = index.entries.firstIndex(where: { $0.bundleID == bundleID }) else { return nil }
        let current = index.entries[idx].copiesRemaining
        // Original spray-and-wait: we send floor(n/2), keep ceil(n/2).
        let kept = UInt8((Int(current) + 1) / 2)
        index.entries[idx].copiesRemaining = max(kept, 1)
        // Rewrite the bundle file with the updated copies field, since the on-wire
        // bundle's `copiesRemaining` is what subsequent gossip rounds will use.
        if let bundle = bundle(for: bundleID) {
            var updated = bundle
            updated.copiesRemaining = max(kept, 1)
            try? updated.encode().write(to: bundleURL(for: bundleID), options: .atomic)
        }
        saveIndex()
        return max(kept, 1)
    }

    /// Compute the count we'd hand off to a peer (floor(n/2)) for a given bundle.
    func handOffCopiesFor(bundleID: Data) -> UInt8 {
        guard let entry = index.entries.first(where: { $0.bundleID == bundleID }) else { return 0 }
        return UInt8(Int(entry.copiesRemaining) / 2)
    }

    /// Mark that we just broadcast a bundle (used for cooldown tracking elsewhere).
    func markBroadcast(bundleID: Data) {
        guard let idx = index.entries.firstIndex(where: { $0.bundleID == bundleID }) else { return }
        index.entries[idx].lastBroadcastAt = Date().timeIntervalSince1970
        saveIndex()
    }

    /// Drop expired bundles. Called on a timer and also opportunistically.
    func purgeExpired() {
        let now = Date().timeIntervalSince1970
        let expired = index.entries.filter { Double($0.expiresAt) <= now }
        for e in expired {
            try? FileManager.default.removeItem(at: bundleURL(for: e.bundleID))
        }
        index.entries.removeAll { Double($0.expiresAt) <= now }
        if !expired.isEmpty { saveIndex() }
    }

    // MARK: - Eviction

    /// Free space until either both quotas are satisfied OR we run out of
    /// foreign bundles to evict. Local-originated bundles are evicted last.
    private func evictUntilFits(incomingBytes: Int) {
        purgeExpired()

        // Sorted by eviction priority: foreign first (older first), then local (older first).
        func sortedForEviction() -> [IndexEntry] {
            let foreign = index.entries.filter { !$0.originatedLocally }.sorted { $0.storedAt < $1.storedAt }
            let local = index.entries.filter { $0.originatedLocally }.sorted { $0.storedAt < $1.storedAt }
            return foreign + local
        }

        while (byteCount + incomingBytes > DTNConfig.storeMaxBytes
               || count >= DTNConfig.storeMaxBundles)
              && !index.entries.isEmpty {
            let candidates = sortedForEviction()
            guard let victim = candidates.first else { break }
            evict(bundleID: victim.bundleID)
        }
    }

    // MARK: - Persistence

    private func bundleURL(for bundleID: Data) -> URL {
        let hex = bundleID.map { String(format: "%02x", $0) }.joined()
        return directory.appendingPathComponent("\(hex).bundle")
    }

    private static func loadIndex(at url: URL) -> Index? {
        guard let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(Index.self, from: data)
    }

    private func saveIndex() {
        guard let data = try? JSONEncoder().encode(index) else { return }
        try? data.write(to: indexURL, options: .atomic)
    }

    // MARK: - Purge timer

    private func startPurgeTimer() {
        purgeTimer = Timer.scheduledTimer(
            withTimeInterval: DTNConfig.purgeIntervalSeconds,
            repeats: true
        ) { [weak self] _ in
            Task { @MainActor in self?.purgeExpired() }
        }
    }
}
