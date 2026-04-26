import SwiftUI

/// Home screen after onboarding: a read-only list of inbound amber alerts.
/// Tapping an alert opens `SubmitInfoView` so the user can send a sighting.
struct AlertsListView: View {
    @EnvironmentObject var alertsVM: AlertsViewModel
    @State private var selectedAlert: AmberAlert? = nil
    @State private var selectedCategory: AlertCategory? = nil

    private var filteredAlerts: [AmberAlert] {
        guard let cat = selectedCategory else { return alertsVM.alerts }
        return alertsVM.alerts.filter { $0.category == cat }
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                brandBar
                FilterPillsRow(
                    selected: $selectedCategory,
                    counts: counts(in: alertsVM.alerts)
                )
                Group {
                    if filteredAlerts.isEmpty {
                        emptyState
                    } else {
                        List {
                            ForEach(filteredAlerts) { alert in
                                Button {
                                    selectedAlert = alert
                                } label: {
                                    AlertRow(alert: alert)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        #if os(iOS)
                        .listStyle(.insetGrouped)
                        #else
                        .listStyle(.inset)
                        #endif
                    }
                }
            }
            .navigationTitle("Alerts")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .principal) {
                    SafeThreadWordmark(compact: true)
                }
            }
            .sheet(item: $selectedAlert) { alert in
                SubmitInfoView(alert: alert)
                    .environmentObject(alertsVM)
            }
        }
    }

    private var brandBar: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(SafeThreadBrand.red)
                .frame(width: 6, height: 6)
            Text(alertsVM.registration?.ngoName ?? "")
                .font(.caption)
                .foregroundStyle(.secondary)
            Spacer()
            Text("\(filteredAlerts.count) of \(alertsVM.alerts.count) shown")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(SafeThreadBrand.redSoft)
    }

    private func counts(in alerts: [AmberAlert]) -> [AlertCategory: Int] {
        var dict: [AlertCategory: Int] = [:]
        for a in alerts { dict[a.category, default: 0] += 1 }
        return dict
    }

    private var emptyState: some View {
        VStack(spacing: 12) {
            Image(systemName: "antenna.radiowaves.left.and.right")
                .font(.system(size: 40))
                .foregroundStyle(.tertiary)
            Text("No active alerts")
                .font(.headline)
            Text("You'll see alerts from your NGO here. They arrive over the bitchat mesh even when you don't have internet.")
                .font(.callout)
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 32)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

private struct AlertRow: View {
    let alert: AmberAlert

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline) {
                CategoryBadge(category: alert.category)
                Text(alert.title)
                    .font(.headline)
                Spacer()
                ChannelBadge(via: alert.receivedVia)
            }
            Text(alert.summary)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .lineLimit(3)
            HStack(spacing: 6) {
                Text(alert.issuedAt, style: .relative)
                Text("ago")
                Text("·")
                Text(alert.caseId)
                    .monospaced()
            }
            .font(.caption)
            .foregroundStyle(.tertiary)
        }
        .padding(.vertical, 6)
    }
}

private struct CategoryBadge: View {
    let category: AlertCategory

    var body: some View {
        Image(systemName: category.systemIcon)
            .font(.caption)
            .foregroundStyle(SafeThreadBrand.red)
            .padding(6)
            .background(Circle().fill(SafeThreadBrand.redSoft))
    }
}

private struct FilterPillsRow: View {
    @Binding var selected: AlertCategory?
    let counts: [AlertCategory: Int]

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                FilterPill(
                    label: "All",
                    icon: nil,
                    count: counts.values.reduce(0, +),
                    isOn: selected == nil
                ) { selected = nil }

                ForEach(AlertCategory.allCases) { cat in
                    FilterPill(
                        label: cat.shortName,
                        icon: cat.systemIcon,
                        count: counts[cat] ?? 0,
                        isOn: selected == cat
                    ) {
                        selected = (selected == cat) ? nil : cat
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
        }
        .background(.ultraThinMaterial)
    }
}

private struct FilterPill: View {
    let label: String
    let icon: String?
    let count: Int
    let isOn: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                if let icon = icon {
                    Image(systemName: icon)
                        .font(.caption)
                }
                Text(label)
                    .font(.subheadline)
                if count > 0 {
                    Text("\(count)")
                        .font(.caption)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 1)
                        .background(
                            Capsule().fill(
                                isOn ? Color.white.opacity(0.25) : Color.secondary.opacity(0.18)
                            )
                        )
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(
                Capsule().fill(isOn ? SafeThreadBrand.red : Color.secondary.opacity(0.10))
            )
            .foregroundStyle(isOn ? .white : .primary)
        }
        .buttonStyle(.plain)
    }
}

private struct ChannelBadge: View {
    let via: AmberAlert.ReceivedVia

    var body: some View {
        Text(via == .internet ? "internet" : "mesh")
            .font(.caption2)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(via == .internet ? Color.blue.opacity(0.15) : Color.orange.opacity(0.15))
            .foregroundStyle(via == .internet ? Color.blue : Color.orange)
            .clipShape(Capsule())
    }
}
