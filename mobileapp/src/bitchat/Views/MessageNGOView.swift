import SwiftUI
import CoreLocation

/// Free-form message from the user to the NGO hub.
/// Always one-way (user → hub) — no recipient picker, no thread, no replies in the user UI.
struct MessageNGOView: View {
    @EnvironmentObject var alertsVM: AlertsViewModel
    @StateObject private var locator = LocationProvider()

    @State private var draft: String = ""
    @State private var attachLocation: Bool = false

    private var locationCode: String? {
        guard attachLocation, let fix = locator.lastFix else { return nil }
        return Geohash.encode(latitude: fix.latitude, longitude: fix.longitude, precision: 7).uppercased()
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                composeArea
                Divider()
                history
            }
            .navigationTitle("Message NGO")
        }
    }

    private var composeArea: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Send a message to your NGO")
                .font(.headline)
            Text("This goes only to the NGO — never to other users.")
                .font(.caption)
                .foregroundStyle(.secondary)
            TextEditor(text: $draft)
                .frame(minHeight: 100, maxHeight: 160)
                .overlay(
                    RoundedRectangle(cornerRadius: 8).stroke(Color.secondary.opacity(0.3))
                )

            HStack(spacing: 10) {
                Toggle(isOn: $attachLocation) {
                    Label("Attach location", systemImage: "location")
                        .font(.caption)
                }
                .toggleStyle(.button)
                .controlSize(.small)
                .onChange(of: attachLocation) { v in if v { locator.requestIfNeeded() } }

                if let code = locationCode {
                    Text(code)
                        .font(.system(.caption, design: .monospaced).weight(.semibold))
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(SafeThreadBrand.redSoft)
                        .foregroundStyle(SafeThreadBrand.red)
                        .clipShape(RoundedRectangle(cornerRadius: 4))
                } else if attachLocation {
                    HStack(spacing: 4) {
                        ProgressView().controlSize(.mini)
                        Text("waiting for GPS").font(.caption2).foregroundStyle(.secondary)
                    }
                }
                Spacer()
            }

            HStack {
                statusLabel
                Spacer()
                Button {
                    Task { await send() }
                } label: {
                    Text(alertsVM.submissionState == .submitting ? "Sending…" : "Send")
                        .fontWeight(.semibold)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 6)
                }
                .buttonStyle(.borderedProminent)
                .disabled(
                    draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                    || alertsVM.submissionState == .submitting
                )
            }
        }
        .padding()
    }

    @ViewBuilder
    private var statusLabel: some View {
        switch alertsVM.submissionState {
        case .sent:
            Label("Sent", systemImage: "checkmark.circle.fill")
                .foregroundStyle(.green)
                .font(.caption)
        case .failed(let msg):
            Label(msg, systemImage: "exclamationmark.triangle")
                .foregroundStyle(.orange)
                .font(.caption)
                .lineLimit(2)
        default:
            EmptyView()
        }
    }

    private var history: some View {
        Group {
            if alertsVM.sentMessages.isEmpty {
                VStack {
                    Spacer()
                    Text("No messages sent yet.")
                        .foregroundStyle(.tertiary)
                        .font(.callout)
                    Spacer()
                }
                .frame(maxWidth: .infinity)
            } else {
                List {
                    Section("Your messages to the NGO") {
                        ForEach(alertsVM.sentMessages) { msg in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(msg.body)
                                    .font(.body)
                                HStack(spacing: 6) {
                                    Text(msg.sentAt, style: .relative)
                                    Text("·")
                                    DeliveryBadge(status: msg.delivery)
                                }
                                .font(.caption)
                                .foregroundStyle(.tertiary)
                            }
                            .padding(.vertical, 4)
                        }
                    }
                }
                #if os(iOS)
                .listStyle(.insetGrouped)
                #endif
            }
        }
    }

    private func send() async {
        var toSend = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        if let code = locationCode {
            if !toSend.isEmpty { toSend += "\n\n" }
            toSend += "📍 \(code)"
        }
        await alertsVM.sendMessageToNGO(toSend)
        if alertsVM.submissionState == .sent {
            draft = ""
            // Auto-clear status after a moment so the form feels fresh.
            try? await Task.sleep(nanoseconds: 1_500_000_000)
            alertsVM.resetSubmissionState()
        }
    }
}
