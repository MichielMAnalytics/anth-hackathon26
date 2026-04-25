import Foundation

// MARK: - Amber Alert TLV Packets
//
// Mirrors the TLV pattern in `Packets.swift` (1-byte type + 1-byte length + value).
// The decoder is tolerant — unknown TLV fields are skipped, so new fields can be
// added on either side without breaking older clients.

/// Hub-issued amber alert. Broadcast across the mesh by the NGO hub.
/// Verified at the receiver against the hub's signing key.
struct AlertPayload {
    let caseId: String          // e.g. "c-2026-0481"
    let title: String           // e.g. "Maryam, 11"
    let summary: String         // e.g. "last seen Aleppo bus stn"
    let issuedAt: UInt32        // unix seconds
    let version: UInt8          // increments when hub revises the alert
    let category: AlertCategory?  // optional — older clients silently default to missingPerson

    private enum TLVType: UInt8 {
        case caseId = 0x01
        case title = 0x02
        case summary = 0x03
        case issuedAt = 0x04
        case version = 0x05
        case category = 0x06
    }

    func encode() -> Data? {
        var data = Data()

        guard let caseIdData = caseId.data(using: .utf8), caseIdData.count <= 255 else { return nil }
        data.append(TLVType.caseId.rawValue)
        data.append(UInt8(caseIdData.count))
        data.append(caseIdData)

        guard let titleData = title.data(using: .utf8), titleData.count <= 255 else { return nil }
        data.append(TLVType.title.rawValue)
        data.append(UInt8(titleData.count))
        data.append(titleData)

        guard let summaryData = summary.data(using: .utf8), summaryData.count <= 255 else { return nil }
        data.append(TLVType.summary.rawValue)
        data.append(UInt8(summaryData.count))
        data.append(summaryData)

        var ts = issuedAt.bigEndian
        let tsData = Data(bytes: &ts, count: 4)
        data.append(TLVType.issuedAt.rawValue)
        data.append(UInt8(4))
        data.append(tsData)

        data.append(TLVType.version.rawValue)
        data.append(UInt8(1))
        data.append(version)

        if let category = category {
            data.append(TLVType.category.rawValue)
            data.append(UInt8(1))
            data.append(category.rawValue)
        }

        return data
    }

    static func decode(from data: Data) -> AlertPayload? {
        var offset = 0
        var caseId: String?
        var title: String?
        var summary: String?
        var issuedAt: UInt32?
        var version: UInt8?
        var category: AlertCategory?

        while offset + 2 <= data.count {
            let typeRaw = data[data.startIndex + offset]
            offset += 1
            let length = Int(data[data.startIndex + offset])
            offset += 1

            guard offset + length <= data.count else { return nil }
            let value = data[data.startIndex + offset..<data.startIndex + offset + length]
            offset += length

            guard let type = TLVType(rawValue: typeRaw) else {
                continue // tolerant decoder: skip unknown TLVs
            }

            switch type {
            case .caseId:
                caseId = String(data: value, encoding: .utf8)
            case .title:
                title = String(data: value, encoding: .utf8)
            case .summary:
                summary = String(data: value, encoding: .utf8)
            case .issuedAt:
                guard length == 4 else { continue }
                let bytes = Array(value)
                issuedAt = UInt32(bytes[0]) << 24
                    | UInt32(bytes[1]) << 16
                    | UInt32(bytes[2]) << 8
                    | UInt32(bytes[3])
            case .version:
                guard length == 1, let v = value.first else { continue }
                version = v
            case .category:
                guard length == 1, let v = value.first, let c = AlertCategory(rawValue: v) else { continue }
                category = c
            }
        }

        guard
            let caseId = caseId,
            let title = title,
            let summary = summary,
            let issuedAt = issuedAt,
            let version = version
        else { return nil }

        return AlertPayload(
            caseId: caseId,
            title: title,
            summary: summary,
            issuedAt: issuedAt,
            version: version,
            category: category
        )
    }
}

/// User-reported location with a safety flag (safe / unsafe). Addressed to the NGO hub.
struct LocationReportPayload {
    let clientMsgId: String
    let lat: Double
    let lng: Double
    let safety: Safety        // safe / unsafe
    let note: String          // free-form, can be empty
    let observedAt: UInt32

    enum Safety: UInt8 {
        case safe = 0x01
        case unsafe = 0x02
    }

    private enum TLVType: UInt8 {
        case clientMsgId = 0x01
        case lat = 0x02
        case lng = 0x03
        case safety = 0x04
        case note = 0x05
        case observedAt = 0x06
    }

    func encode() -> Data? {
        var data = Data()

        guard let cmidData = clientMsgId.data(using: .utf8), cmidData.count <= 255 else { return nil }
        data.append(TLVType.clientMsgId.rawValue)
        data.append(UInt8(cmidData.count))
        data.append(cmidData)

        var latBits = lat.bitPattern.bigEndian
        let latData = Data(bytes: &latBits, count: 8)
        data.append(TLVType.lat.rawValue)
        data.append(UInt8(8))
        data.append(latData)

        var lngBits = lng.bitPattern.bigEndian
        let lngData = Data(bytes: &lngBits, count: 8)
        data.append(TLVType.lng.rawValue)
        data.append(UInt8(8))
        data.append(lngData)

        data.append(TLVType.safety.rawValue)
        data.append(UInt8(1))
        data.append(safety.rawValue)

        guard let noteData = note.data(using: .utf8), noteData.count <= 255 else { return nil }
        data.append(TLVType.note.rawValue)
        data.append(UInt8(noteData.count))
        data.append(noteData)

        var ts = observedAt.bigEndian
        let tsData = Data(bytes: &ts, count: 4)
        data.append(TLVType.observedAt.rawValue)
        data.append(UInt8(4))
        data.append(tsData)

        return data
    }

    static func decode(from data: Data) -> LocationReportPayload? {
        var offset = 0
        var clientMsgId: String?
        var lat: Double?
        var lng: Double?
        var safety: Safety?
        var note: String? = ""
        var observedAt: UInt32?

        while offset + 2 <= data.count {
            let typeRaw = data[data.startIndex + offset]
            offset += 1
            let length = Int(data[data.startIndex + offset])
            offset += 1
            guard offset + length <= data.count else { return nil }
            let value = data[data.startIndex + offset..<data.startIndex + offset + length]
            offset += length

            guard let type = TLVType(rawValue: typeRaw) else { continue }

            switch type {
            case .clientMsgId:
                clientMsgId = String(data: value, encoding: .utf8)
            case .lat:
                guard length == 8 else { continue }
                var bits: UInt64 = 0
                for b in value { bits = (bits << 8) | UInt64(b) }
                lat = Double(bitPattern: bits)
            case .lng:
                guard length == 8 else { continue }
                var bits: UInt64 = 0
                for b in value { bits = (bits << 8) | UInt64(b) }
                lng = Double(bitPattern: bits)
            case .safety:
                guard length == 1, let v = value.first, let s = Safety(rawValue: v) else { continue }
                safety = s
            case .note:
                note = String(data: value, encoding: .utf8) ?? ""
            case .observedAt:
                guard length == 4 else { continue }
                let bytes = Array(value)
                observedAt = UInt32(bytes[0]) << 24 | UInt32(bytes[1]) << 16 | UInt32(bytes[2]) << 8 | UInt32(bytes[3])
            }
        }

        guard
            let clientMsgId = clientMsgId,
            let lat = lat,
            let lng = lng,
            let safety = safety,
            let observedAt = observedAt
        else { return nil }

        return LocationReportPayload(
            clientMsgId: clientMsgId,
            lat: lat,
            lng: lng,
            safety: safety,
            note: note ?? "",
            observedAt: observedAt
        )
    }
}

/// Free-form message from a user to the NGO hub. Always addressed to hub.
struct GeneralMessagePayload {
    let clientMsgId: String
    let body: String
    let sentAt: UInt32

    private enum TLVType: UInt8 {
        case clientMsgId = 0x01
        case body = 0x02
        case sentAt = 0x03
    }

    func encode() -> Data? {
        var data = Data()

        guard let cmidData = clientMsgId.data(using: .utf8), cmidData.count <= 255 else { return nil }
        data.append(TLVType.clientMsgId.rawValue)
        data.append(UInt8(cmidData.count))
        data.append(cmidData)

        guard let bodyData = body.data(using: .utf8), bodyData.count <= 255 else { return nil }
        data.append(TLVType.body.rawValue)
        data.append(UInt8(bodyData.count))
        data.append(bodyData)

        var ts = sentAt.bigEndian
        let tsData = Data(bytes: &ts, count: 4)
        data.append(TLVType.sentAt.rawValue)
        data.append(UInt8(4))
        data.append(tsData)

        return data
    }

    static func decode(from data: Data) -> GeneralMessagePayload? {
        var offset = 0
        var clientMsgId: String?
        var body: String?
        var sentAt: UInt32?

        while offset + 2 <= data.count {
            let typeRaw = data[data.startIndex + offset]
            offset += 1
            let length = Int(data[data.startIndex + offset])
            offset += 1
            guard offset + length <= data.count else { return nil }
            let value = data[data.startIndex + offset..<data.startIndex + offset + length]
            offset += length

            guard let type = TLVType(rawValue: typeRaw) else { continue }

            switch type {
            case .clientMsgId:
                clientMsgId = String(data: value, encoding: .utf8)
            case .body:
                body = String(data: value, encoding: .utf8)
            case .sentAt:
                guard length == 4 else { continue }
                let bytes = Array(value)
                sentAt = UInt32(bytes[0]) << 24 | UInt32(bytes[1]) << 16 | UInt32(bytes[2]) << 8 | UInt32(bytes[3])
            }
        }

        guard let clientMsgId, let body, let sentAt else { return nil }
        return GeneralMessagePayload(clientMsgId: clientMsgId, body: body, sentAt: sentAt)
    }
}

/// User-submitted sighting. Addressed to the NGO hub; never to other users.
struct SightingPayload {
    let caseId: String          // which alert this is in response to
    let clientMsgId: String     // for idempotency / dedup at hub
    let freeText: String        // what the user saw (free-form)
    let observedAt: UInt32      // unix seconds when observed
    let locationLat: Double?    // optional
    let locationLng: Double?    // optional

    private enum TLVType: UInt8 {
        case caseId = 0x01
        case clientMsgId = 0x02
        case freeText = 0x03
        case observedAt = 0x04
        case locationLat = 0x05
        case locationLng = 0x06
    }

    func encode() -> Data? {
        var data = Data()

        guard let caseIdData = caseId.data(using: .utf8), caseIdData.count <= 255 else { return nil }
        data.append(TLVType.caseId.rawValue)
        data.append(UInt8(caseIdData.count))
        data.append(caseIdData)

        guard let cmidData = clientMsgId.data(using: .utf8), cmidData.count <= 255 else { return nil }
        data.append(TLVType.clientMsgId.rawValue)
        data.append(UInt8(cmidData.count))
        data.append(cmidData)

        guard let textData = freeText.data(using: .utf8), textData.count <= 255 else { return nil }
        data.append(TLVType.freeText.rawValue)
        data.append(UInt8(textData.count))
        data.append(textData)

        var ts = observedAt.bigEndian
        let tsData = Data(bytes: &ts, count: 4)
        data.append(TLVType.observedAt.rawValue)
        data.append(UInt8(4))
        data.append(tsData)

        if let lat = locationLat {
            var bits = lat.bitPattern.bigEndian
            let latData = Data(bytes: &bits, count: 8)
            data.append(TLVType.locationLat.rawValue)
            data.append(UInt8(8))
            data.append(latData)
        }
        if let lng = locationLng {
            var bits = lng.bitPattern.bigEndian
            let lngData = Data(bytes: &bits, count: 8)
            data.append(TLVType.locationLng.rawValue)
            data.append(UInt8(8))
            data.append(lngData)
        }

        return data
    }

    static func decode(from data: Data) -> SightingPayload? {
        var offset = 0
        var caseId: String?
        var clientMsgId: String?
        var freeText: String?
        var observedAt: UInt32?
        var locationLat: Double?
        var locationLng: Double?

        while offset + 2 <= data.count {
            let typeRaw = data[data.startIndex + offset]
            offset += 1
            let length = Int(data[data.startIndex + offset])
            offset += 1

            guard offset + length <= data.count else { return nil }
            let value = data[data.startIndex + offset..<data.startIndex + offset + length]
            offset += length

            guard let type = TLVType(rawValue: typeRaw) else {
                continue
            }

            switch type {
            case .caseId:
                caseId = String(data: value, encoding: .utf8)
            case .clientMsgId:
                clientMsgId = String(data: value, encoding: .utf8)
            case .freeText:
                freeText = String(data: value, encoding: .utf8)
            case .observedAt:
                guard length == 4 else { continue }
                let bytes = Array(value)
                observedAt = UInt32(bytes[0]) << 24
                    | UInt32(bytes[1]) << 16
                    | UInt32(bytes[2]) << 8
                    | UInt32(bytes[3])
            case .locationLat:
                guard length == 8 else { continue }
                let bytes = Array(value)
                var bits: UInt64 = 0
                for b in bytes { bits = (bits << 8) | UInt64(b) }
                locationLat = Double(bitPattern: bits)
            case .locationLng:
                guard length == 8 else { continue }
                let bytes = Array(value)
                var bits: UInt64 = 0
                for b in bytes { bits = (bits << 8) | UInt64(b) }
                locationLng = Double(bitPattern: bits)
            }
        }

        guard
            let caseId = caseId,
            let clientMsgId = clientMsgId,
            let freeText = freeText,
            let observedAt = observedAt
        else { return nil }

        return SightingPayload(
            caseId: caseId,
            clientMsgId: clientMsgId,
            freeText: freeText,
            observedAt: observedAt,
            locationLat: locationLat,
            locationLng: locationLng
        )
    }
}
