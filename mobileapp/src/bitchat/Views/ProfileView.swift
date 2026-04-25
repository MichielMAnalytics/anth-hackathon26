import SwiftUI

/// Edit-form for the user's profile. Pre-filled from `alertsVM.profile`.
struct ProfileView: View {
    @EnvironmentObject var alertsVM: AlertsViewModel

    @State private var name: String = ""
    @State private var phoneNumber: String = ""
    @State private var profession: String = ""
    @State private var language: String = ""
    @State private var saving: Bool = false
    @State private var savedFlash: Bool = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    HStack(spacing: 12) {
                        Image(systemName: "person.crop.circle.fill")
                            .resizable()
                            .frame(width: 44, height: 44)
                            .foregroundStyle(.tertiary)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(alertsVM.registration?.ngoName ?? "—")
                                .font(.headline)
                            Text("Registered with this NGO")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }

                Section("Name") {
                    TextField("Your full name", text: $name)
                        .autocorrectionDisabled()
                }

                Section("Phone number") {
                    TextField("+963 21 123 4567", text: $phoneNumber)
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
                    Text("Optional.")
                }

                Section("Language") {
                    TextField("e.g. en, ar, uk", text: $language)
                        #if os(iOS)
                        .textInputAutocapitalization(.never)
                        #endif
                        .autocorrectionDisabled()
                }

                if savedFlash {
                    Section {
                        Label("Saved", systemImage: "checkmark.circle.fill")
                            .foregroundStyle(.green)
                    }
                }

                Section {
                    Button {
                        Task { await save() }
                    } label: {
                        if saving {
                            ProgressView()
                        } else {
                            Text("Save changes")
                                .frame(maxWidth: .infinity)
                                .fontWeight(.semibold)
                        }
                    }
                    .disabled(name.isEmpty || phoneNumber.isEmpty || saving)
                }
            }
            .navigationTitle("Profile")
            .onAppear(perform: loadFromVM)
        }
    }

    private func loadFromVM() {
        guard let p = alertsVM.profile else { return }
        name = p.name
        phoneNumber = p.phoneNumber
        profession = p.profession ?? ""
        language = p.language
    }

    private func save() async {
        saving = true
        savedFlash = false
        let trimmedProfession = profession.trimmingCharacters(in: .whitespaces)
        await alertsVM.updateProfile(
            name: name.trimmingCharacters(in: .whitespaces),
            phoneNumber: phoneNumber.trimmingCharacters(in: .whitespaces),
            profession: trimmedProfession.isEmpty ? nil : trimmedProfession,
            language: language.trimmingCharacters(in: .whitespaces)
        )
        saving = false
        savedFlash = true
        try? await Task.sleep(nanoseconds: 1_500_000_000)
        savedFlash = false
    }
}
