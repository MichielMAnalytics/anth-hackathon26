import XCTest
@testable import bitchat

final class AmberPacketsTests: XCTestCase {

    func testAlertPayloadRoundTrip() {
        let original = AlertPayload(
            caseId: "c-2026-0481",
            title: "Maryam, 11",
            summary: "last seen Aleppo bus stn",
            issuedAt: 1_745_590_320,
            version: 1,
            category: nil
        )

        guard let encoded = original.encode() else {
            XCTFail("encode returned nil")
            return
        }
        guard let decoded = AlertPayload.decode(from: encoded) else {
            XCTFail("decode returned nil")
            return
        }

        XCTAssertEqual(decoded.caseId, original.caseId)
        XCTAssertEqual(decoded.title, original.title)
        XCTAssertEqual(decoded.summary, original.summary)
        XCTAssertEqual(decoded.issuedAt, original.issuedAt)
        XCTAssertEqual(decoded.version, original.version)
    }

    func testSightingPayloadRoundTripWithLocation() {
        let original = SightingPayload(
            caseId: "c-2026-0481",
            clientMsgId: "0c5b2a4e-1e0c-4b1c-8f3a-3d7d3a3e2c11",
            freeText: "saw her at homs market wearing red",
            observedAt: 1_745_600_000,
            locationLat: 36.7233,
            locationLng: 36.9923
        )

        guard let encoded = original.encode() else {
            XCTFail("encode returned nil")
            return
        }
        guard let decoded = SightingPayload.decode(from: encoded) else {
            XCTFail("decode returned nil")
            return
        }

        XCTAssertEqual(decoded.caseId, original.caseId)
        XCTAssertEqual(decoded.clientMsgId, original.clientMsgId)
        XCTAssertEqual(decoded.freeText, original.freeText)
        XCTAssertEqual(decoded.observedAt, original.observedAt)
        XCTAssertEqual(decoded.locationLat ?? 0, original.locationLat ?? 0, accuracy: 0.0000001)
        XCTAssertEqual(decoded.locationLng ?? 0, original.locationLng ?? 0, accuracy: 0.0000001)
    }

    func testSightingPayloadRoundTripWithoutLocation() {
        let original = SightingPayload(
            caseId: "c-2026-0481",
            clientMsgId: "abc123",
            freeText: "no location",
            observedAt: 1_745_600_000,
            locationLat: nil,
            locationLng: nil
        )

        guard let encoded = original.encode() else {
            XCTFail("encode returned nil")
            return
        }
        guard let decoded = SightingPayload.decode(from: encoded) else {
            XCTFail("decode returned nil")
            return
        }

        XCTAssertNil(decoded.locationLat)
        XCTAssertNil(decoded.locationLng)
        XCTAssertEqual(decoded.freeText, original.freeText)
    }

    func testTolerantDecoderSkipsUnknownTLV() {
        // Build a valid AlertPayload byte stream and append an unknown TLV (type 0xFE, len 1).
        let valid = AlertPayload(
            caseId: "c-2026-0001",
            title: "X",
            summary: "y",
            issuedAt: 1,
            version: 1,
            category: nil
        )
        guard var bytes = valid.encode() else {
            XCTFail("encode returned nil")
            return
        }
        bytes.append(0xFE)
        bytes.append(UInt8(1))
        bytes.append(0xAA)

        let decoded = AlertPayload.decode(from: bytes)
        XCTAssertNotNil(decoded, "Decoder must skip unknown TLVs and still return a value")
        XCTAssertEqual(decoded?.caseId, "c-2026-0001")
    }
}
