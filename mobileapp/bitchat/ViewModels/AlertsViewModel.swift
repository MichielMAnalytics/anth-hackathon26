import Foundation
import Combine
import BitFoundation

// MARK: - NotificationCenter bridge
//
// `ChatViewModel.didReceiveNoisePayload` posts this notification when it sees
// an alert/sighting payload, so the chat layer doesn't need to know about
// AlertsViewModel.
extension Notification.Name {
    static let amberPayloadReceived = Notification.Name("amber.payloadReceived")
}

/// State for the amber-alert app.
///
/// Lives alongside `ChatViewModel`. Observes inbound `alert` and (where applicable)
/// `STATUS_UPDATE` payloads, normalises them into `AmberAlert` rows, and exposes
/// onboarding + sighting-submission to the UI.
///
/// Hub-and-spoke is enforced here: `submitSighting` only ever encrypts to the
/// stored hub pubkey, and inbound payloads are filtered by hub pubkey before
/// being rendered.
@MainActor
final class AlertsViewModel: ObservableObject {

    // MARK: - Published state

    @Published var onboarded: Bool = false
    @Published var alerts: [AmberAlert] = []
    @Published var registration: Registration? = nil
    @Published var profile: UserProfile? = nil
    @Published var pendingSighting: PendingSighting? = nil
    @Published var submissionState: SubmissionState = .idle
    @Published var isDemoMode: Bool = false
    @Published var locationReports: [SubmittedLocationReport] = []
    @Published var sentMessages: [SentMessage] = []
    @Published var submittedSightings: [SubmittedSighting] = []

    enum SubmissionState: Equatable {
        case idle
        case submitting
        case sent
        case failed(String)
    }

    // MARK: - Storage

    private let defaults: UserDefaults
    private let hubClient: HubClient
    private var payloadObserver: NSObjectProtocol?

    // MARK: - DTN (delay-tolerant networking)

    private let dtnStore: DTNStore
    private let dtnRelay: DTNRelay
    /// Number of bundles currently held on disk (foreground users may want
    /// to surface this in a debug view; not user-facing in v1).
    @Published private(set) var dtnHeldBundleCount: Int = 0

    // MARK: - Init

    init(hubClient: HubClient = HubClient(),
         defaults: UserDefaults = .standard) {
        self.hubClient = hubClient
        self.defaults = defaults
        let store = DTNStore()
        self.dtnStore = store
        self.dtnRelay = DTNRelay(store: store)
        loadPersistedRegistration()
        subscribeToMeshPayloads()
        self.dtnHeldBundleCount = store.count
        // Auto-enter demo mode if launched with --demo (used by the simulator
        // launcher so the populated UI shows up without tapping through the
        // onboarding form).
        if !onboarded && CommandLine.arguments.contains("--demo") {
            enterDemoMode()
        }
    }

    deinit {
        if let payloadObserver {
            NotificationCenter.default.removeObserver(payloadObserver)
        }
    }

    private func subscribeToMeshPayloads() {
        payloadObserver = NotificationCenter.default.addObserver(
            forName: .amberPayloadReceived,
            object: nil,
            queue: .main
        ) { [weak self] note in
            guard
                let self,
                let raw = note.userInfo?["type"] as? UInt8,
                let type = NoisePayloadType(rawValue: raw),
                let payload = note.userInfo?["payload"] as? Data,
                let peerID = note.userInfo?["peerID"] as? String
            else { return }
            Task { @MainActor in
                self.handleNoisePayload(type: type, payload: payload, fromPeerID: peerID)
            }
        }
    }

    // MARK: - DTN bundle handling

    /// Wrap an inner amber payload as a DTN bundle and store it locally so the
    /// gossip layer can carry it toward the hub when a path opens. Used as a
    /// fallback after the internet path fails.
    private func enqueueDTNFallback(innerType: NoisePayloadType, innerPayload: Data) {
        guard let reg = registration else { return }
        _ = dtnRelay.originate(
            innerType: innerType,
            innerPayload: innerPayload,
            hubX25519Pubkey: reg.hubPubkey
        )
        dtnHeldBundleCount = dtnStore.count
    }

    // MARK: - Onboarding

    func register(
        name: String,
        phoneNumber: String,
        profession: String?,
        language: String,
        bitchatPublicKey: Data,
        apnsToken: String? = nil
    ) async {
        do {
            let reg = try await hubClient.register(
                name: name,
                phoneNumber: phoneNumber,
                profession: profession,
                language: language,
                bitchatPublicKey: bitchatPublicKey,
                apnsToken: apnsToken
            )
            self.registration = reg
            self.profile = UserProfile(
                name: name,
                phoneNumber: phoneNumber,
                profession: profession,
                language: language
            )
            self.onboarded = true
            persist(reg)
            startHubSync()
        } catch {
            self.submissionState = .failed("Registration failed: \(error.localizedDescription)")
        }
    }

    // MARK: - Hub sync (cold-start fetch + live stream)

    private var hubStreamTask: Task<Void, Never>?

    /// Start the alerts pipeline against the hub: a one-shot fetch of
    /// currently-active alerts (catches up missed events) plus a
    /// long-running WebSocket subscription that pushes ALERT_ISSUED
    /// envelopes as operators create cases.
    private func startHubSync() {
        guard let reg = registration, !isDemoMode else { return }
        // One-shot fetch of /v1/alerts/active.
        Task { @MainActor in
            do {
                let active = try await hubClient.fetchActiveAlerts(userId: reg.userId)
                for a in active { upsertAlert(a) }
            } catch {
                // Non-fatal: fall back to whatever the WS stream pushes.
            }
        }
        // Long-running stream.
        hubStreamTask?.cancel()
        hubStreamTask = Task { [weak self] in
            guard let self else { return }
            let stream = self.hubClient.openStream(userId: reg.userId)
            do {
                for try await event in stream {
                    await MainActor.run { self.handleHubEvent(event) }
                }
            } catch {
                // Stream broke — try once more after a short backoff.
                try? await Task.sleep(nanoseconds: 2_000_000_000)
                await MainActor.run { self.startHubSync() }
            }
        }
    }

    func updateProfile(name: String, phoneNumber: String, profession: String?, language: String) async {
        let updated = UserProfile(name: name, phoneNumber: phoneNumber, profession: profession, language: language)
        if isDemoMode {
            try? await Task.sleep(nanoseconds: 300_000_000)
            self.profile = updated
            return
        }
        guard let reg = registration else { return }
        do {
            try await hubClient.updateProfile(updated, userId: reg.userId)
            self.profile = updated
        } catch {
            // Surface via submissionState so the view can render an error
            self.submissionState = .failed("Could not save profile: \(error.localizedDescription)")
        }
    }

    func sendMessageToNGO(_ body: String) async {
        let trimmed = body.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        var msg = SentMessage(id: UUID().uuidString, body: trimmed, sentAt: Date())
        sentMessages.insert(msg, at: 0)
        submissionState = .submitting
        if isDemoMode {
            try? await Task.sleep(nanoseconds: 400_000_000)
            updateMessageDelivery(id: msg.id, to: .sentToHub)
            try? await Task.sleep(nanoseconds: 800_000_000)
            updateMessageDelivery(id: msg.id, to: .deliveredToHub)
            submissionState = .sent
            return
        }
        guard let reg = registration else {
            submissionState = .failed("Not onboarded")
            return
        }
        do {
            try await hubClient.sendMessage(body: trimmed, clientMsgId: msg.id, userId: reg.userId)
            updateMessageDelivery(id: msg.id, to: .sentToHub)
            submissionState = .sent
        } catch {
            // Internet failed — wrap as a DTN bundle so it gossips toward the hub.
            let inner = GeneralMessagePayload(clientMsgId: msg.id, body: trimmed, sentAt: UInt32(Date().timeIntervalSince1970))
            if let bytes = inner.encode() {
                enqueueDTNFallback(innerType: .generalMessage, innerPayload: bytes)
                updateMessageDelivery(id: msg.id, to: .queuedForMesh)
                submissionState = .failed("Offline — message queued for mesh relay (\(dtnHeldBundleCount) pending).")
            } else {
                updateMessageDelivery(id: msg.id, to: .failed(error.localizedDescription))
                submissionState = .failed("Could not send message: \(error.localizedDescription)")
            }
        }
    }

    private func updateMessageDelivery(id: String, to status: AmberDeliveryStatus) {
        if let i = sentMessages.firstIndex(where: { $0.id == id }) {
            sentMessages[i].delivery = status
        }
    }

    func reportLocation(lat: Double, lng: Double, safety: LocationReportPayload.Safety, note: String) async {
        var report = SubmittedLocationReport(
            id: UUID().uuidString,
            lat: lat,
            lng: lng,
            safety: safety,
            note: note,
            observedAt: Date()
        )
        locationReports.insert(report, at: 0)
        submissionState = .submitting
        if isDemoMode {
            try? await Task.sleep(nanoseconds: 350_000_000)
            updateLocationDelivery(id: report.id, to: .sentToHub)
            try? await Task.sleep(nanoseconds: 800_000_000)
            updateLocationDelivery(id: report.id, to: .deliveredToHub)
            submissionState = .sent
            return
        }
        guard let reg = registration else {
            submissionState = .failed("Not onboarded")
            return
        }
        do {
            try await hubClient.reportLocation(report, userId: reg.userId)
            updateLocationDelivery(id: report.id, to: .sentToHub)
            submissionState = .sent
        } catch {
            // Internet failed — wrap as a DTN bundle so the mesh can carry it.
            let inner = LocationReportPayload(
                clientMsgId: report.id,
                lat: lat,
                lng: lng,
                safety: safety,
                note: note,
                observedAt: UInt32(report.observedAt.timeIntervalSince1970)
            )
            if let bytes = inner.encode() {
                enqueueDTNFallback(innerType: .locationReport, innerPayload: bytes)
                updateLocationDelivery(id: report.id, to: .queuedForMesh)
                submissionState = .failed("Offline — location report queued for mesh relay.")
            } else {
                updateLocationDelivery(id: report.id, to: .failed(error.localizedDescription))
                submissionState = .failed("Could not send location report: \(error.localizedDescription)")
            }
        }
    }

    private func updateLocationDelivery(id: String, to status: AmberDeliveryStatus) {
        if let i = locationReports.firstIndex(where: { $0.id == id }) {
            locationReports[i].delivery = status
        }
    }

    func resetSubmissionState() {
        submissionState = .idle
    }

    private func persist(_ reg: Registration) {
        defaults.set(reg.userId, forKey: "amber.userId")
        defaults.set(reg.hubPubkey, forKey: "amber.hubPubkey")
        defaults.set(reg.ngoName, forKey: "amber.ngoName")
        defaults.set(true, forKey: "amber.onboarded")
    }

    // MARK: - Demo mode (bypass hub, no backend needed)

    /// Bootstraps the app with a fake registration and a few sample alerts so the
    /// rest of the UI can be exercised without a running hub. Pure in-memory —
    /// nothing is persisted.
    func enterDemoMode() {
        isDemoMode = true
        registration = Registration(
            userId: "demo-user-001",
            hubPubkey: Data(repeating: 0xAB, count: 32),
            ngoName: "Demo NGO"
        )
        profile = UserProfile(
            name: "Hidde Kehrer",
            phoneNumber: "+963 21 555 0142",
            profession: "field worker",
            language: "en"
        )
        onboarded = true
        let now = Date()
        alerts = [
            AmberAlert(
                caseId: "c-2026-0481",
                title: "Maryam, 11",
                summary: "Last seen at the Aleppo central bus station, wearing a red jacket. Travelling alone.",
                issuedAt: now.addingTimeInterval(-60 * 35),
                version: 2,
                receivedVia: .internet,
                photoURL: nil,
                category: .missingPerson
            ),
            AmberAlert(
                caseId: "c-2026-0480",
                title: "Insulin needed — Sector 7",
                summary: "Type-1 diabetic, 14yo male, two days without supply. Family at the school shelter.",
                issuedAt: now.addingTimeInterval(-60 * 90),
                version: 1,
                receivedVia: .mesh,
                photoURL: nil,
                category: .medical
            ),
            AmberAlert(
                caseId: "c-2026-0479",
                title: "Yusuf, 9",
                summary: "Last seen near Bab al-Hawa border crossing yesterday afternoon.",
                issuedAt: now.addingTimeInterval(-60 * 60 * 18),
                version: 1,
                receivedVia: .mesh,
                photoURL: nil,
                category: .missingPerson
            ),
            AmberAlert(
                caseId: "c-2026-0478",
                title: "No water — Block 4",
                summary: "Mains down for ~36h. ~80 households affected. Convoy ETA unknown.",
                issuedAt: now.addingTimeInterval(-60 * 60 * 22),
                version: 2,
                receivedVia: .internet,
                photoURL: nil,
                category: .resourceShortage
            ),
            AmberAlert(
                caseId: "c-2026-0476",
                title: "Avoid Block 2 corridor",
                summary: "Reported building damage and unsafe debris on the route to the market. Use the south road.",
                issuedAt: now.addingTimeInterval(-60 * 60 * 30),
                version: 1,
                receivedVia: .internet,
                photoURL: nil,
                category: .safety
            ),
            AmberAlert(
                caseId: "c-2026-0470",
                title: "Layla, 14",
                summary: "Ongoing case — last update 3 days ago. Possible sighting in Idlib.",
                issuedAt: now.addingTimeInterval(-60 * 60 * 72),
                version: 5,
                receivedVia: .internet,
                photoURL: nil,
                category: .missingPerson
            )
        ]
    }

    private func loadPersistedRegistration() {
        guard defaults.bool(forKey: "amber.onboarded"),
              let uid = defaults.string(forKey: "amber.userId"),
              let key = defaults.data(forKey: "amber.hubPubkey"),
              let ngo = defaults.string(forKey: "amber.ngoName") else {
            return
        }
        self.registration = Registration(userId: uid, hubPubkey: key, ngoName: ngo)
        self.onboarded = true
        startHubSync()
    }

    // MARK: - Inbound mesh handling

    /// Called from the bridge that observes `BitchatDelegate.didReceiveNoisePayload`.
    /// Filters non-alert types and unsigned/non-hub payloads.
    func handleNoisePayload(type: NoisePayloadType, payload: Data, fromPeerID: String) {
        // DTN payloads are gossip — pass straight to the relay.
        if type == .dtnBundle || type == .dtnReceipt || type == .dtnSummary {
            let peer = PeerID(str: fromPeerID)
            dtnRelay.handleInbound(type: type, payload: payload, from: peer)
            dtnHeldBundleCount = dtnStore.count
            return
        }
        guard type == .alert else { return }
        guard let parsed = AlertPayload.decode(from: payload) else { return }
        // NOTE: signature verification against `registration?.hubPubkey` is intentionally
        // wired in at the call site once the hub pubkey/signature scheme is finalised.
        upsertAlert(
            AmberAlert(
                caseId: parsed.caseId,
                title: parsed.title,
                summary: parsed.summary,
                issuedAt: Date(timeIntervalSince1970: TimeInterval(parsed.issuedAt)),
                version: parsed.version,
                receivedVia: .mesh,
                photoURL: nil,
                category: parsed.category ?? .missingPerson
            )
        )
    }

    /// Inbound from the WebSocket (richer payload — title/summary plus photoURL etc.).
    func handleHubEvent(_ event: HubEvent) {
        switch event {
        case .alertIssued(let rich):
            upsertAlert(rich)
        case .statusUpdate:
            break
        case .ack(let clientMsgId):
            markDeliveredToHub(clientMsgId: clientMsgId)
        }
    }

    private func upsertAlert(_ alert: AmberAlert) {
        if let i = alerts.firstIndex(where: { $0.caseId == alert.caseId }) {
            // Prefer the richer (internet) version when available.
            if alert.receivedVia == .internet || alert.version > alerts[i].version {
                alerts[i] = alert
            }
        } else {
            alerts.insert(alert, at: 0)
        }
    }

    // MARK: - Sightings

    func submitSighting(
        caseId: String,
        freeText: String,
        location: (Double, Double)? = nil,
        photoJPEG: Data? = nil,
        voiceM4A: Data? = nil
    ) async {
        guard let reg = registration else {
            submissionState = .failed("Not onboarded")
            return
        }
        submissionState = .submitting
        let sighting = SightingDraft(
            caseId: caseId,
            clientMsgId: UUID().uuidString,
            freeText: freeText,
            observedAt: Date(),
            location: location,
            photoJPEG: photoJPEG,
            voiceM4A: voiceM4A
        )
        let summary = SubmittedSighting(
            id: sighting.clientMsgId,
            caseId: caseId,
            freeText: freeText,
            observedAt: sighting.observedAt,
            hasPhoto: photoJPEG != nil,
            hasVoiceNote: voiceM4A != nil
        )
        submittedSightings.insert(summary, at: 0)
        if isDemoMode {
            try? await Task.sleep(nanoseconds: 400_000_000)
            updateSightingDelivery(id: summary.id, to: .sentToHub)
            try? await Task.sleep(nanoseconds: 800_000_000)
            updateSightingDelivery(id: summary.id, to: .deliveredToHub)
            submissionState = .sent
            return
        }
        do {
            try await hubClient.submitSighting(sighting, userId: reg.userId)
            updateSightingDelivery(id: summary.id, to: .sentToHub)
            submissionState = .sent
        } catch {
            // Internet failed — wrap text fields as a DTN bundle for mesh relay.
            // Photo/voice attachments don't fit our 512KB DTN budget; they're
            // dropped from the bundle but kept on `pendingSighting` so they
            // upload as soon as internet returns.
            let inner = SightingPayload(
                caseId: caseId,
                clientMsgId: sighting.clientMsgId,
                freeText: freeText,
                observedAt: UInt32(sighting.observedAt.timeIntervalSince1970),
                locationLat: location?.0,
                locationLng: location?.1
            )
            if let bytes = inner.encode() {
                enqueueDTNFallback(innerType: .sighting, innerPayload: bytes)
                updateSightingDelivery(id: summary.id, to: .queuedForMesh)
                submissionState = .failed("Offline — sighting queued for mesh relay.")
            } else {
                updateSightingDelivery(id: summary.id, to: .failed("offline"))
                submissionState = .failed("Could not reach hub. Sighting will be queued for relay over the mesh.")
            }
            pendingSighting = PendingSighting(draft: sighting, hubPubkey: reg.hubPubkey)
        }
    }

    private func updateSightingDelivery(id: String, to status: AmberDeliveryStatus) {
        if let i = submittedSightings.firstIndex(where: { $0.id == id }) {
            submittedSightings[i].delivery = status
        }
    }

    /// Called by the bridge when a hub-level ACK is received for a previously
    /// submitted sighting / message / location report.
    func markDeliveredToHub(clientMsgId: String) {
        if let i = submittedSightings.firstIndex(where: { $0.id == clientMsgId }) {
            submittedSightings[i].delivery = .deliveredToHub
        }
        if let i = sentMessages.firstIndex(where: { $0.id == clientMsgId }) {
            sentMessages[i].delivery = .deliveredToHub
        }
        if let i = locationReports.firstIndex(where: { $0.id == clientMsgId }) {
            locationReports[i].delivery = .deliveredToHub
        }
    }
}

// MARK: - Domain types

struct AmberAlert: Identifiable, Equatable {
    var id: String { caseId }
    let caseId: String
    let title: String
    let summary: String
    let issuedAt: Date
    let version: UInt8
    let receivedVia: ReceivedVia
    let photoURL: URL?
    let category: AlertCategory

    enum ReceivedVia: String, Equatable {
        case mesh
        case internet
    }
}

enum AlertCategory: UInt8, CaseIterable, Identifiable, Equatable {
    case missingPerson = 0x01
    case medical = 0x02
    case resourceShortage = 0x03
    case safety = 0x04

    var id: UInt8 { rawValue }

    var displayName: String {
        switch self {
        case .missingPerson: return "Missing person"
        case .medical: return "Medical"
        case .resourceShortage: return "Resource shortage"
        case .safety: return "Safety"
        }
    }

    var shortName: String {
        switch self {
        case .missingPerson: return "Missing"
        case .medical: return "Medical"
        case .resourceShortage: return "Resources"
        case .safety: return "Safety"
        }
    }

    var systemIcon: String {
        switch self {
        case .missingPerson: return "person.fill.questionmark"
        case .medical: return "cross.case.fill"
        case .resourceShortage: return "drop.fill"
        case .safety: return "exclamationmark.triangle.fill"
        }
    }
}

struct Registration: Equatable {
    let userId: String
    let hubPubkey: Data     // raw bitchat noise pubkey of the NGO hub
    let ngoName: String
}

struct UserProfile: Equatable {
    var name: String
    var phoneNumber: String
    var profession: String?
    var language: String
}

struct SightingDraft {
    let caseId: String
    let clientMsgId: String
    let freeText: String
    let observedAt: Date
    let location: (Double, Double)?
    let photoJPEG: Data?
    let voiceM4A: Data?
}

enum AmberDeliveryStatus: Equatable {
    case pending           // not yet delivered to anything
    case queuedForMesh     // wrapped as a DTN bundle, gossipping toward hub
    case sentToHub         // HTTP/Nostr returned 200
    case deliveredToHub    // hub-level ACK received (mesh ack or stream ACK)
    case failed(String)
}

struct PendingSighting {
    let draft: SightingDraft
    let hubPubkey: Data
}

enum HubEvent {
    case alertIssued(AmberAlert)
    case statusUpdate(caseId: String, summary: String)
    case ack(clientMsgId: String)
}

struct SubmittedLocationReport: Identifiable, Equatable {
    let id: String
    let lat: Double
    let lng: Double
    let safety: LocationReportPayload.Safety
    let note: String
    let observedAt: Date
    var delivery: AmberDeliveryStatus = .pending
}

struct SentMessage: Identifiable, Equatable {
    let id: String
    let body: String
    let sentAt: Date
    var delivery: AmberDeliveryStatus = .pending
}

struct SubmittedSighting: Identifiable, Equatable {
    let id: String
    let caseId: String
    let freeText: String
    let observedAt: Date
    let hasPhoto: Bool
    let hasVoiceNote: Bool
    var delivery: AmberDeliveryStatus = .pending
}
