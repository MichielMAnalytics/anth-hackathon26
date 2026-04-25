import SwiftUI

/// Top-level view for the amber-alert app. Switches between onboarding and
/// the alerts list based on `AlertsViewModel.onboarded`.
///
/// The original bitchat `ContentView` is intentionally not used — this app
/// is a hub-and-spoke amber alert receiver, not a chat client.
struct AmberRootView: View {
    @EnvironmentObject var alertsVM: AlertsViewModel

    var body: some View {
        Group {
            if alertsVM.onboarded {
                MainTabView()
            } else {
                OnboardingView()
            }
        }
    }
}

private struct MainTabView: View {
    var body: some View {
        TabView {
            AlertsListView()
                .tabItem {
                    Label("Alerts", systemImage: "exclamationmark.bubble")
                }

            MapView()
                .tabItem {
                    Label("Map", systemImage: "map")
                }

            MessageNGOView()
                .tabItem {
                    Label("Message NGO", systemImage: "envelope")
                }

            ProfileView()
                .tabItem {
                    Label("Profile", systemImage: "person.crop.circle")
                }
        }
        .tint(SafeThreadBrand.red)
    }
}
