import Foundation

// MARK: - HubClient
//
// Talks to the NGO hub over HTTP and a WebSocket stream when the device has
// internet. Mesh fallback (encrypting a SightingPayload to the hub's bitchat
// pubkey and pushing it into the mesh) is *not* this client's job — that's
// owned by the BLE/Noise layer.
//
// Default base URL is read from `Info.plist`'s `AmberHubBaseURL` key when present,
// otherwise falls back to a configurable constant. Override at construction time
// for tests / staging.

final class HubClient {

    enum HubError: LocalizedError {
        case badResponse(Int)
        case decoding(String)
        case transport(Error)

        var errorDescription: String? {
            switch self {
            case .badResponse(let code): return "Hub returned HTTP \(code)"
            case .decoding(let what): return "Could not decode hub response: \(what)"
            case .transport(let e): return e.localizedDescription
            }
        }
    }

    private let baseURL: URL
    private let session: URLSession

    init(baseURL: URL? = nil, session: URLSession = .shared) {
        if let baseURL = baseURL {
            self.baseURL = baseURL
        } else if let s = Bundle.main.object(forInfoDictionaryKey: "AmberHubBaseURL") as? String,
                  let url = URL(string: s) {
            self.baseURL = url
        } else {
            // Sensible default for local dev — override in Info.plist or at construction.
            self.baseURL = URL(string: "http://localhost:8000")!
        }
        self.session = session
    }

    // MARK: - HTTP

    func register(
        name: String,
        phoneNumber: String,
        profession: String?,
        language: String,
        bitchatPublicKey: Data,
        apnsToken: String?
    ) async throws -> Registration {
        struct Body: Encodable {
            let name: String
            let phone_number: String
            let profession: String?
            let language: String
            let bitchat_pubkey: String
            let apns_token: String?
        }
        struct Reply: Decodable {
            let user_id: String
            let hub_pubkey: String   // hex
            let ngo_name: String
        }
        let body = Body(
            name: name,
            phone_number: phoneNumber,
            profession: profession,
            language: language,
            bitchat_pubkey: bitchatPublicKey.hexString,
            apns_token: apnsToken
        )
        let reply: Reply = try await postJSON("/v1/register", body: body, auth: nil)
        guard let hubPubkey = Data(hexString: reply.hub_pubkey) else {
            throw HubError.decoding("hub_pubkey not hex")
        }
        return Registration(
            userId: reply.user_id,
            hubPubkey: hubPubkey,
            ngoName: reply.ngo_name
        )
    }

    func updateProfile(_ p: UserProfile, userId: String) async throws {
        struct Body: Encodable {
            let name: String
            let phone_number: String
            let profession: String?
            let language: String
        }
        struct Reply: Decodable { let ok: Bool }
        let body = Body(
            name: p.name,
            phone_number: p.phoneNumber,
            profession: p.profession,
            language: p.language
        )
        let _: Reply = try await postJSON("/v1/profile", body: body, auth: userId)
    }

    func sendMessage(body: String, clientMsgId: String, userId: String) async throws {
        struct Body: Encodable {
            let body: String
            let client_msg_id: String
            let sent_at: TimeInterval
        }
        struct Reply: Decodable { let ok: Bool }
        let req = Body(body: body, client_msg_id: clientMsgId, sent_at: Date().timeIntervalSince1970)
        let _: Reply = try await postJSON("/v1/message", body: req, auth: userId)
    }

    func reportLocation(_ r: SubmittedLocationReport, userId: String) async throws {
        struct Body: Encodable {
            let client_msg_id: String
            let lat: Double
            let lng: Double
            let safety: String
            let note: String
            let observed_at: TimeInterval
        }
        struct Reply: Decodable { let ok: Bool }
        let body = Body(
            client_msg_id: r.id,
            lat: r.lat,
            lng: r.lng,
            safety: r.safety == .safe ? "safe" : "unsafe",
            note: r.note,
            observed_at: r.observedAt.timeIntervalSince1970
        )
        let _: Reply = try await postJSON("/v1/location_report", body: body, auth: userId)
    }

    func submitSighting(_ s: SightingDraft, userId: String) async throws {
        // If there's no media, JSON is fine.
        if s.photoJPEG == nil && s.voiceM4A == nil {
            struct Body: Encodable {
                let case_id: String
                let free_text: String
                let location: [Double]?
                let client_msg_id: String
                let observed_at: TimeInterval
            }
            struct Reply: Decodable { let sighting_id: String; let ack: Bool }
            let body = Body(
                case_id: s.caseId,
                free_text: s.freeText,
                location: s.location.map { [$0.0, $0.1] },
                client_msg_id: s.clientMsgId,
                observed_at: s.observedAt.timeIntervalSince1970
            )
            let _: Reply = try await postJSON("/v1/sighting", body: body, auth: userId)
            return
        }
        // Otherwise, use a multipart/form-data POST.
        try await postSightingMultipart(s, userId: userId)
    }

    private func postSightingMultipart(_ s: SightingDraft, userId: String) async throws {
        let boundary = "Boundary-\(UUID().uuidString)"
        var req = URLRequest(url: baseURL.amberAppending(path: "/v1/sighting"))
        req.httpMethod = "POST"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        req.setValue("Bearer \(userId)", forHTTPHeaderField: "Authorization")

        var body = Data()
        func appendField(_ name: String, _ value: String) {
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n".data(using: .utf8)!)
            body.append("\(value)\r\n".data(using: .utf8)!)
        }
        func appendFile(_ name: String, filename: String, mime: String, data: Data) {
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"\(name)\"; filename=\"\(filename)\"\r\n".data(using: .utf8)!)
            body.append("Content-Type: \(mime)\r\n\r\n".data(using: .utf8)!)
            body.append(data)
            body.append("\r\n".data(using: .utf8)!)
        }

        appendField("case_id", s.caseId)
        appendField("free_text", s.freeText)
        appendField("client_msg_id", s.clientMsgId)
        appendField("observed_at", String(s.observedAt.timeIntervalSince1970))
        if let loc = s.location {
            appendField("location_lat", String(loc.0))
            appendField("location_lng", String(loc.1))
        }
        if let photo = s.photoJPEG {
            appendFile("photo", filename: "sighting.jpg", mime: "image/jpeg", data: photo)
        }
        if let voice = s.voiceM4A {
            appendFile("voice", filename: "sighting.m4a", mime: "audio/m4a", data: voice)
        }
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)
        req.httpBody = body

        do {
            let (_, resp) = try await session.data(for: req)
            guard let http = resp as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                throw HubError.badResponse((resp as? HTTPURLResponse)?.statusCode ?? -1)
            }
        } catch let e as HubError {
            throw e
        } catch {
            throw HubError.transport(error)
        }
    }

    func fetchActiveAlerts(userId: String) async throws -> [AmberAlert] {
        struct Reply: Decodable {
            struct Item: Decodable {
                let case_id: String
                let title: String
                let summary: String
                let issued_at: TimeInterval
                let version: Int
                let photo_url: String?
                let category: String?
            }
            let alerts: [Item]
        }
        let reply: Reply = try await getJSON("/v1/alerts/active", auth: userId)
        return reply.alerts.map { item in
            AmberAlert(
                caseId: item.case_id,
                title: item.title,
                summary: item.summary,
                issuedAt: Date(timeIntervalSince1970: item.issued_at),
                version: UInt8(clamping: item.version),
                receivedVia: .internet,
                photoURL: item.photo_url.flatMap { URL(string: $0) },
                category: parseCategory(item.category)
            )
        }
    }

    private func parseCategory(_ s: String?) -> AlertCategory {
        Self.parseCategoryStatic(s)
    }

    static func parseCategoryStatic(_ s: String?) -> AlertCategory {
        switch s {
        case "missing_person":     return .missingPerson
        case "medical":            return .medical
        case "resource_shortage":  return .resourceShortage
        case "safety":             return .safety
        default:                   return .missingPerson
        }
    }

    // MARK: - WebSocket stream

    /// Opens a long-running stream of hub events. Caller is responsible for
    /// re-opening on disconnect.
    func openStream(userId: String) -> AsyncThrowingStream<HubEvent, Error> {
        let url = baseURL
            .amberAppending(path: "/v1/stream")
        var request = URLRequest(url: url)
        request.setValue("Bearer \(userId)", forHTTPHeaderField: "Authorization")
        let task = session.webSocketTask(with: request)
        task.resume()

        return AsyncThrowingStream { continuation in
            func receive() {
                task.receive { result in
                    switch result {
                    case .failure(let err):
                        continuation.finish(throwing: err)
                    case .success(let message):
                        if let event = Self.parseStreamMessage(message) {
                            continuation.yield(event)
                        }
                        receive()
                    }
                }
            }
            receive()
            continuation.onTermination = { _ in task.cancel(with: .goingAway, reason: nil) }
        }
    }

    private static func parseStreamMessage(_ msg: URLSessionWebSocketTask.Message) -> HubEvent? {
        let data: Data
        switch msg {
        case .data(let d): data = d
        case .string(let s): data = Data(s.utf8)
        @unknown default: return nil
        }
        struct Wire: Decodable {
            let type: String
            let case_id: String?
            let title: String?
            let summary: String?
            let issued_at: TimeInterval?
            let version: Int?
            let photo_url: String?
            let category: String?
            let client_msg_id: String?
        }
        guard let wire = try? JSONDecoder().decode(Wire.self, from: data) else { return nil }
        switch wire.type {
        case "ALERT_ISSUED":
            guard let cid = wire.case_id,
                  let title = wire.title,
                  let summary = wire.summary,
                  let ts = wire.issued_at,
                  let v = wire.version
            else { return nil }
            return .alertIssued(AmberAlert(
                caseId: cid,
                title: title,
                summary: summary,
                issuedAt: Date(timeIntervalSince1970: ts),
                version: UInt8(clamping: v),
                receivedVia: .internet,
                photoURL: wire.photo_url.flatMap { URL(string: $0) },
                category: Self.parseCategoryStatic(wire.category)
            ))
        case "STATUS_UPDATE":
            if let cid = wire.case_id, let s = wire.summary {
                return .statusUpdate(caseId: cid, summary: s)
            }
            return nil
        case "ACK":
            if let cmid = wire.client_msg_id { return .ack(clientMsgId: cmid) }
            return nil
        default:
            return nil
        }
    }

    // MARK: - HTTP helpers

    private func postJSON<B: Encodable, R: Decodable>(_ path: String, body: B, auth: String?) async throws -> R {
        var req = URLRequest(url: baseURL.amberAppending(path: path))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let auth = auth { req.setValue("Bearer \(auth)", forHTTPHeaderField: "Authorization") }
        req.httpBody = try JSONEncoder().encode(body)
        return try await sendDecoding(req)
    }

    private func getJSON<R: Decodable>(_ path: String, auth: String?) async throws -> R {
        var req = URLRequest(url: baseURL.amberAppending(path: path))
        req.httpMethod = "GET"
        if let auth = auth { req.setValue("Bearer \(auth)", forHTTPHeaderField: "Authorization") }
        return try await sendDecoding(req)
    }

    private func sendDecoding<R: Decodable>(_ req: URLRequest) async throws -> R {
        do {
            let (data, resp) = try await session.data(for: req)
            guard let http = resp as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                throw HubError.badResponse((resp as? HTTPURLResponse)?.statusCode ?? -1)
            }
            do {
                return try JSONDecoder().decode(R.self, from: data)
            } catch {
                throw HubError.decoding(String(describing: error))
            }
        } catch let e as HubError {
            throw e
        } catch {
            throw HubError.transport(error)
        }
    }
}

// MARK: - Hex helpers

private extension Data {
    var hexString: String {
        map { String(format: "%02x", $0) }.joined()
    }

    init?(hexString: String) {
        let cleaned = hexString.lowercased().filter { "0123456789abcdef".contains($0) }
        guard cleaned.count % 2 == 0 else { return nil }
        var bytes = [UInt8]()
        bytes.reserveCapacity(cleaned.count / 2)
        var idx = cleaned.startIndex
        while idx < cleaned.endIndex {
            let next = cleaned.index(idx, offsetBy: 2)
            guard let b = UInt8(cleaned[idx..<next], radix: 16) else { return nil }
            bytes.append(b)
            idx = next
        }
        self.init(bytes)
    }
}

private extension URL {
    func amberAppending(path: String) -> URL {
        let trimmed = path.hasPrefix("/") ? String(path.dropFirst()) : path
        return self.appendingPathComponent(trimmed)
    }
}
