# Upstream-edit notes

The forked iOS app does **not** rewrite bitchat — we kept the BLE mesh, Noise crypto, dedup, fragmentation, and Nostr fallback completely intact. Below are the four upstream files we touched, and exactly what we changed.

These files are not copied into this folder verbatim because they're large (`ChatViewModel.swift` is over 3000 lines); the originals live at https://github.com/permissionlesstech/bitchat. The deltas listed here are the only modifications.

---

## 1. `bitchat/Protocols/BitchatProtocol.swift`

Added eight cases to `NoisePayloadType` (the rest of the enum is unchanged).

```swift
enum NoisePayloadType: UInt8 {
    // Messages and status
    case privateMessage = 0x01
    case readReceipt    = 0x02
    case delivered      = 0x03
    // Verification
    case verifyChallenge = 0x10
    case verifyResponse  = 0x11
    // Amber-alert payloads (hub-and-spoke)
    case alert           = 0x20  // Hub-issued amber alert (broadcast, signed by NGO key)
    case sighting        = 0x21  // User-submitted sighting (addressed to hub)
    case locationReport  = 0x22  // User-reported safe/unsafe location (addressed to hub)
    case generalMessage  = 0x23  // Free-form user → hub message
    case profileUpdate   = 0x24  // User-initiated profile change
    // Delay-tolerant networking (DTN) — opportunistic store-and-forward
    case dtnBundle       = 0x25  // Opaque envelope gossipped phone-to-phone
    case dtnReceipt      = 0x26  // Hub-signed delivery confirmation; prunes carriers' stores
    case dtnSummary      = 0x27  // Anti-entropy summary vector (list of bundle_ids held)
}
```

A matching `description` switch case was added for each.

---

## 2. `bitchat/Services/BLE/BLEService.swift`

The exhaustive switch in the inbound payload dispatcher (around the existing `case .privateMessage`, `case .delivered`, etc.) now also includes:

```swift
case .alert:
    let ts = Date(timeIntervalSince1970: Double(packet.timestamp) / 1000)
    notifyUI { [weak self] in
        self?.delegate?.didReceiveNoisePayload(from: peerID, type: .alert,
                                               payload: Data(payloadData), timestamp: ts)
    }
case .sighting:        // ... same shape
case .locationReport:  // ... same shape
case .generalMessage:  // ... same shape
case .profileUpdate:   // ... same shape
case .dtnBundle:       // ... same shape (DTN store-and-forward)
case .dtnReceipt:      // ... same shape
case .dtnSummary:      // ... same shape
```

Pure forwarding to the existing `BitchatDelegate.didReceiveNoisePayload(...)` callback — no new logic.

---

## 3. `bitchat/ViewModels/ChatViewModel.swift`

Added a single new `case` to the existing exhaustive switch in `didReceiveNoisePayload(...)` that bridges our payload types out to `AlertsViewModel` via NotificationCenter:

```swift
case .alert, .sighting, .locationReport, .generalMessage, .profileUpdate,
     .dtnBundle, .dtnReceipt, .dtnSummary:
    NotificationCenter.default.post(
        name: .amberPayloadReceived,
        object: nil,
        userInfo: [
            "type": type.rawValue,
            "payload": payload,
            "peerID": peerID.id,
            "timestamp": timestamp
        ]
    )
    return
```

`Notification.Name.amberPayloadReceived` is defined in `AlertsViewModel.swift`, which keeps the chat layer decoupled from the alert app — the chat `ViewModel` does not import `AlertsViewModel`.

---

## 4. `bitchat/ViewModels/Extensions/ChatViewModel+Nostr.swift`

Three exhaustive switches over `NoisePayloadType` in this extension forward our payload types to the same NotificationCenter bridge — this is what enables the **third fallback path** (Nostr) when neither direct internet nor BLE mesh are available:

```swift
case .alert, .sighting, .locationReport, .generalMessage, .profileUpdate,
     .dtnBundle, .dtnReceipt, .dtnSummary:
    forwardAmberPayloadToVM(payload, senderPubkey: senderPubkey)
```

`forwardAmberPayloadToVM(...)` is a small private helper added in the same file.

---

## 5. `bitchat/BitchatApp.swift`

Two-line change to inject `AlertsViewModel` and route to `AmberRootView` instead of bitchat's `ContentView`:

```swift
@StateObject private var alertsViewModel: AlertsViewModel
// ...
_alertsViewModel = StateObject(wrappedValue: AlertsViewModel())
// ...
WindowGroup {
    AmberRootView()
        .environmentObject(chatViewModel)
        .environmentObject(alertsViewModel)
        // ... rest of the existing onAppear / onChange handlers untouched
}
```

The original `ContentView` is left in place; the app simply doesn't route to it.

---

## 6. `bitchat/Info.plist`

```diff
- <string>bitchat</string>      <!-- CFBundleDisplayName -->
+ <string>SafeThread</string>
```

That's the entire upstream surface area we touched. Everything else is greenfield code in the files copied into this folder.
