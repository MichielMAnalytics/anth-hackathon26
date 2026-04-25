import SwiftUI

/// Tiny inline badge that conveys whether an outbound payload was sent / acknowledged.
struct DeliveryBadge: View {
    let status: AmberDeliveryStatus

    var body: some View {
        switch status {
        case .pending:
            Label("sending", systemImage: "clock")
                .foregroundStyle(.tertiary)
        case .queuedForMesh:
            Label("queued (mesh)", systemImage: "antenna.radiowaves.left.and.right")
                .foregroundStyle(.orange)
        case .sentToHub:
            Label("sent", systemImage: "checkmark")
                .foregroundStyle(.secondary)
        case .deliveredToHub:
            Label("received by NGO", systemImage: "checkmark.circle.fill")
                .foregroundStyle(.green)
        case .failed:
            Label("failed", systemImage: "exclamationmark.triangle.fill")
                .foregroundStyle(.orange)
        }
    }
}
