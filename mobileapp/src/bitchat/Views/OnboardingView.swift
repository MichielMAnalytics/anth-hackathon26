import SwiftUI

/// First-launch flow: collect invite code + region + language, then POST to the hub.
/// On success, persists the registration and the rest of the app switches to AlertsListView.
struct OnboardingView: View {
    @EnvironmentObject var alertsVM: AlertsViewModel
    @EnvironmentObject var chatVM: ChatViewModel

    @State private var name: String = ""
    @State private var phoneNumber: String = ""
    @State private var profession: String = ""
    @State private var language: String = Locale.current.language.languageCode?.identifier ?? "en"
    @State private var isSubmitting: Bool = false
    @State private var errorText: String? = nil

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    VStack(alignment: .leading, spacing: 8) {
                        SafeThreadWordmark()
                        Text(SafeThreadBrand.tagline)
                            .font(.callout)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 4)

                    Text("Register with your NGO")
                        .font(.headline)
                    Text("So we can reach you when an alert is issued in your area.")
                        .font(.callout)
                        .foregroundStyle(.secondary)
                }
                .listRowBackground(Color.clear)

                Section("Name") {
                    TextField("Your full name", text: $name)
                        .autocorrectionDisabled()
                }

                Section("Phone number") {
                    TextField("e.g. +963 21 123 4567", text: $phoneNumber)
                        #if os(iOS)
                        .keyboardType(.phonePad)
                        .textContentType(.telephoneNumber)
                        #endif
                        .autocorrectionDisabled()
                }

                Section {
                    TextField("e.g. nurse, teacher, driver", text: $profession)
                        .autocorrectionDisabled()
                } header: {
                    Text("Profession")
                } footer: {
                    Text("Optional. Helps the NGO route relevant alerts to you.")
                }

                Section("Language") {
                    TextField("e.g. en, ar, uk", text: $language)
                        #if os(iOS)
                        .textInputAutocapitalization(.never)
                        #endif
                        .autocorrectionDisabled()
                }

                if let err = errorText {
                    Section {
                        Text(err)
                            .foregroundColor(.red)
                            .font(.callout)
                    }
                }

                Section {
                    Button {
                        Task { await submit() }
                    } label: {
                        if isSubmitting {
                            ProgressView()
                        } else {
                            Text("Register")
                                .frame(maxWidth: .infinity)
                                .fontWeight(.semibold)
                        }
                    }
                    .disabled(name.isEmpty || phoneNumber.isEmpty || isSubmitting)
                }
            }
            .navigationTitle("Welcome")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        alertsVM.enterDemoMode()
                    } label: {
                        Text("Skip")
                            .underline()
                    }
                }
            }
        }
    }

    private func submit() async {
        isSubmitting = true
        errorText = nil
        let pubkey = chatVM.meshService.getNoiseService().getStaticPublicKeyData()
        let trimmedProfession = profession.trimmingCharacters(in: .whitespaces)
        await alertsVM.register(
            name: name.trimmingCharacters(in: .whitespaces),
            phoneNumber: phoneNumber.trimmingCharacters(in: .whitespaces),
            profession: trimmedProfession.isEmpty ? nil : trimmedProfession,
            language: language.trimmingCharacters(in: .whitespaces),
            bitchatPublicKey: pubkey
        )
        isSubmitting = false
        if !alertsVM.onboarded {
            if case .failed(let msg) = alertsVM.submissionState {
                errorText = msg
            } else {
                errorText = "Registration did not complete. Try again."
            }
        }
    }
}
