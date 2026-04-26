import SwiftUI
import PhotosUI
import CoreLocation
#if os(iOS)
import AVFoundation
#endif

/// Modal sheet for submitting a sighting tied to a specific alert.
/// All sightings are addressed to the NGO hub — there is no recipient picker.
struct SubmitInfoView: View {
    let alert: AmberAlert

    @EnvironmentObject var alertsVM: AlertsViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var freeText: String = ""
    @State private var attachLocation: Bool = false
    @State private var manualLocationCode: String = ""

    // Photo
    @State private var photoItem: PhotosPickerItem? = nil
    @State private var photoData: Data? = nil

    // Voice
    @StateObject private var recorder = VoiceMemoRecorder()

    // Location
    @StateObject private var locator = LocationProvider()

    /// Returns (lat, lng, geohash) if a location is attached — either from GPS
    /// or from a manually-entered geohash code.
    private var resolvedLocation: (Double, Double, String)? {
        guard attachLocation else { return nil }
        // Manual code wins if the user typed one
        let trimmed = manualLocationCode.trimmingCharacters(in: .whitespaces).lowercased()
        if !trimmed.isEmpty {
            let center = Geohash.decodeCenter(trimmed)
            if center.lat != 0 || center.lon != 0 {
                return (center.lat, center.lon, trimmed.uppercased())
            }
        }
        if let fix = locator.lastFix {
            let g = Geohash.encode(latitude: fix.latitude, longitude: fix.longitude, precision: 7)
            return (fix.latitude, fix.longitude, g.uppercased())
        }
        return nil
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text(alert.title)
                        .font(.title3)
                        .fontWeight(.semibold)
                    Text(alert.summary)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                    Text(alert.caseId)
                        .font(.caption)
                        .monospaced()
                        .foregroundStyle(.tertiary)
                }

                Section("What did you see?") {
                    TextEditor(text: $freeText)
                        .frame(minHeight: 100)
                }

                Section("Photo (optional)") {
                    if let data = photoData, let image = platformImage(from: data) {
                        VStack(alignment: .leading, spacing: 8) {
                            image
                                .resizable()
                                .scaledToFit()
                                .frame(maxHeight: 180)
                                .clipShape(RoundedRectangle(cornerRadius: 10))
                            HStack {
                                Text("\(data.count / 1024) KB")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                Spacer()
                                Button("Remove", role: .destructive) {
                                    photoData = nil
                                    photoItem = nil
                                }
                                .font(.caption)
                            }
                        }
                    } else {
                        PhotosPicker(selection: $photoItem, matching: .images, photoLibrary: .shared()) {
                            Label("Add a photo", systemImage: "photo.on.rectangle.angled")
                        }
                        .onChange(of: photoItem) { newItem in
                            Task { await loadPhoto(newItem) }
                        }
                    }
                }

                Section("Voice note (optional)") {
                    voiceRecorderRow
                }

                Section {
                    Toggle("Attach my approximate location", isOn: $attachLocation)
                        .onChange(of: attachLocation) { newValue in
                            if newValue { locator.requestIfNeeded() }
                        }
                    if attachLocation {
                        if let resolved = resolvedLocation {
                            HStack(spacing: 8) {
                                Image(systemName: "location.fill")
                                    .foregroundStyle(SafeThreadBrand.red)
                                Text("Location code")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                Text(resolved.2)
                                    .font(.system(.callout, design: .monospaced).weight(.semibold))
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 3)
                                    .background(SafeThreadBrand.redSoft)
                                    .foregroundStyle(SafeThreadBrand.red)
                                    .clipShape(RoundedRectangle(cornerRadius: 6))
                            }
                        } else {
                            HStack(spacing: 6) {
                                ProgressView().controlSize(.small)
                                Text("Waiting for a GPS fix…")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        TextField("Or paste a code (e.g. SY3R6X4)", text: $manualLocationCode)
                            #if os(iOS)
                            .textInputAutocapitalization(.characters)
                            #endif
                            .autocorrectionDisabled()
                            .font(.system(.callout, design: .monospaced))
                    }
                } footer: {
                    Text("Location is only sent if you opt in. The code travels in the message — readable over voice, SMS, or mesh — so it works even with no internet.")
                }

                Section {
                    submissionStatus
                }

                Section {
                    Button {
                        Task { await submit() }
                    } label: {
                        if alertsVM.submissionState == .submitting {
                            ProgressView()
                        } else {
                            Text("Send to NGO")
                                .frame(maxWidth: .infinity)
                                .fontWeight(.semibold)
                        }
                    }
                    .disabled(freeText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                              || alertsVM.submissionState == .submitting)
                }
            }
            .navigationTitle("Submit info")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
            }
        }
    }

    // MARK: - Voice row

    @ViewBuilder
    private var voiceRecorderRow: some View {
        if let url = recorder.recordedURL, let data = try? Data(contentsOf: url) {
            HStack(spacing: 12) {
                Image(systemName: "waveform")
                    .foregroundStyle(SafeThreadBrand.red)
                Text("Recording attached · \(Int(recorder.duration))s")
                    .font(.callout)
                Spacer()
                Button("Remove", role: .destructive) {
                    recorder.discard()
                }
                .font(.caption)
            }
        } else if recorder.isRecording {
            HStack(spacing: 12) {
                Circle()
                    .fill(.red)
                    .frame(width: 10, height: 10)
                    .opacity(0.8)
                Text("Recording · \(Int(recorder.duration))s")
                    .font(.callout)
                Spacer()
                Button("Stop") {
                    recorder.stop()
                }
                .buttonStyle(.borderedProminent)
                .tint(.red)
            }
        } else {
            Button {
                recorder.start()
            } label: {
                Label("Record a voice note", systemImage: "mic.fill")
            }
        }
    }

    // MARK: - Submission status

    @ViewBuilder
    private var submissionStatus: some View {
        switch alertsVM.submissionState {
        case .idle:
            EmptyView()
        case .submitting:
            HStack { ProgressView(); Text("Sending…") }
        case .sent:
            Label("Sent. Thank you.", systemImage: "checkmark.circle.fill")
                .foregroundStyle(.green)
        case .failed(let msg):
            Label(msg, systemImage: "exclamationmark.triangle")
                .foregroundStyle(.orange)
                .font(.callout)
        }
    }

    // MARK: - Helpers

    private func loadPhoto(_ item: PhotosPickerItem?) async {
        guard let item = item else { return }
        if let data = try? await item.loadTransferable(type: Data.self) {
            self.photoData = compressJPEG(data)
        }
    }

    private func compressJPEG(_ raw: Data) -> Data {
        // Cap at ~400 KB JPEG so the upload stays sane on slow networks.
        #if os(iOS)
        guard let img = UIImage(data: raw) else { return raw }
        return img.jpegData(compressionQuality: 0.6) ?? raw
        #else
        return raw
        #endif
    }

    private func platformImage(from data: Data) -> Image? {
        #if os(iOS)
        guard let ui = UIImage(data: data) else { return nil }
        return Image(uiImage: ui)
        #elseif os(macOS)
        guard let ns = NSImage(data: data) else { return nil }
        return Image(nsImage: ns)
        #else
        return nil
        #endif
    }

    private func submit() async {
        let voiceData: Data?
        if let url = recorder.recordedURL { voiceData = try? Data(contentsOf: url) } else { voiceData = nil }

        // Build the message body. When location is attached, append the geohash
        // to the free text so anyone reading the payload (over mesh, SMS, etc.)
        // sees a shareable code, not just numerical lat/lng.
        var body = freeText.trimmingCharacters(in: .whitespacesAndNewlines)
        var coords: (Double, Double)? = nil
        if let loc = resolvedLocation {
            coords = (loc.0, loc.1)
            if !body.isEmpty { body += "\n\n" }
            body += "📍 \(loc.2)"
        }

        await alertsVM.submitSighting(
            caseId: alert.caseId,
            freeText: body,
            location: coords,
            photoJPEG: photoData,
            voiceM4A: voiceData
        )
        if alertsVM.submissionState == .sent {
            try? await Task.sleep(nanoseconds: 600_000_000)
            dismiss()
        }
    }
}

// MARK: - Lightweight voice memo recorder (iOS only — macOS shows the button as no-op)

@MainActor
final class VoiceMemoRecorder: ObservableObject {
    @Published var isRecording: Bool = false
    @Published var duration: TimeInterval = 0
    @Published var recordedURL: URL? = nil

    #if os(iOS)
    private var recorder: AVAudioRecorder?
    private var timer: Timer?
    private var startTime: Date?
    #endif

    func start() {
        #if os(iOS)
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker, .allowBluetooth])
            try session.setActive(true)

            let url = FileManager.default.temporaryDirectory
                .appendingPathComponent("amber-voice-\(UUID().uuidString).m4a")
            let settings: [String: Any] = [
                AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
                AVSampleRateKey: 22_050,
                AVNumberOfChannelsKey: 1,
                AVEncoderAudioQualityKey: AVAudioQuality.medium.rawValue
            ]
            let r = try AVAudioRecorder(url: url, settings: settings)
            r.record()
            self.recorder = r
            self.startTime = Date()
            self.isRecording = true
            self.duration = 0
            self.timer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
                Task { @MainActor in
                    guard let self, let start = self.startTime else { return }
                    self.duration = Date().timeIntervalSince(start)
                }
            }
        } catch {
            isRecording = false
        }
        #endif
    }

    func stop() {
        #if os(iOS)
        recorder?.stop()
        let url = recorder?.url
        recorder = nil
        timer?.invalidate()
        timer = nil
        isRecording = false
        recordedURL = url
        #endif
    }

    func discard() {
        #if os(iOS)
        if let url = recordedURL { try? FileManager.default.removeItem(at: url) }
        #endif
        recordedURL = nil
        duration = 0
    }
}
