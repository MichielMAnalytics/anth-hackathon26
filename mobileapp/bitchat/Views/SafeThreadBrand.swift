import SwiftUI

// MARK: - SafeThread brand

enum SafeThreadBrand {
    /// Primary red accent (matches the NGO hub dashboard's red).
    static let red = Color(red: 0.92, green: 0.30, blue: 0.27)
    /// Soft red used for backgrounds / cards.
    static let redSoft = Color(red: 0.92, green: 0.30, blue: 0.27).opacity(0.10)

    static let appName = "SafeThread"
    static let tagline = "Reach people when nothing else can."
}

/// Compact brand chip — square red badge with a shield, plus the wordmark.
/// Designed to sit at the top of an onboarding or alerts screen.
struct SafeThreadWordmark: View {
    var compact: Bool = false

    var body: some View {
        HStack(spacing: 8) {
            ZStack {
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(SafeThreadBrand.red)
                    .frame(width: compact ? 24 : 32, height: compact ? 24 : 32)
                Image(systemName: "shield.lefthalf.filled")
                    .foregroundStyle(.white)
                    .font(compact ? .footnote : .body)
            }
            Text(SafeThreadBrand.appName)
                .font(compact ? .subheadline : .title3)
                .fontWeight(.semibold)
                .foregroundStyle(.primary)
        }
    }
}
