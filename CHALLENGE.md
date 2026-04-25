# Hackathon challenge: Reimagining case management in low-connectivity humanitarian settings

> Anthropic 2026 hackathon brief. Source: [Google Doc](https://docs.google.com/document/d/1ylYx4X0JuYrFEpaf2Vn-pBAglzZ8lEwX/edit). This is the brief our solution is judged against.

## Background

In acute humanitarian crises, children face heightened risks of violence, abuse, exploitation and separation. **Child protection case management** is a frontline response — identifying at-risk children, assessing their needs, connecting them to services, and ensuring ongoing support. When done well, it can be life-saving. Yet in many emergency contexts, the systems designed to protect children are strained or break down entirely.

## Why this matters now

Originally, child protection case management was largely paper-based and made very limited use of digital tools. In high-income countries, this has changed in recent years, with organisations increasingly exploring digital and AI-enabled solutions to support case management and reduce administrative burden.

These approaches rely on connectivity and trained personnel. But in many humanitarian settings:

- Internet access is unreliable or non-existent.
- Electricity is inconsistent.
- Staff turnover is high.
- Data protection risks are elevated.

Despite growing investment in digital innovation, solutions that are low-tech, offline-capable, and context-resilient remain underdeveloped.

## The opportunity

Bold, practical innovations that work without relying on constant connectivity or advanced infrastructure. Solutions must be:

- **Safe and confidential.**
- **Easy to use** in high-pressure environments.
- **Adaptable** to low-resource settings.
- **Supportive** of, not burdensome to, frontline workers.

## The challenge

> Design a solution that strengthens child protection case management in acute humanitarian settings while preserving quality, confidentiality, and safety, especially when internet access is limited and technology may not always be available. The solution should be practical, low-tech or offline-capable and should improve one or more stages of the case management process.

## What is child protection case management?

Case management follows a structured process:

1. **Identification & Registration** — Recognising children at risk and safely documenting their situation.
2. **Assessment** — Understanding the child's needs, risks, and strengths.
3. **Case Planning** — Developing a tailored plan with clear actions and services.
4. **Referral & Service Provision** — Connecting children to appropriate support (health, psychosocial, legal, etc.).
5. **Follow-up & Review** — Monitoring progress and adapting the plan as needed.
6. **Case Closure** — Safely closing the case when risks are reduced and objectives are met.

At every step, principles of **confidentiality**, **informed consent**, **do no harm**, and **best interest of the child** must guide decisions.

## How SafeThread maps to the brief

| Stage | How we address it (today) | Where we'd like to go |
|-------|---------------------------|------------------------|
| **Identification & Registration** | Civilians signed into the bitchat-fork app submit incident reports (text + photo + voice). Routing agent classifies them into structured cases (e.g. "Lost: Diala — missing person"). Geohash captured per message. | Per-child profile schema with consent flags; QR check-in for kiosks. |
| **Assessment** | Cases auto-rank by an urgency score combining anomaly, distress, open cases, distinct reporters, and severity. Per-region patterns (e.g. "12 reports of water from 8 senders near Block 4") surface as themes. | Structured assessment forms loaded into the case profile, fillable offline. |
| **Case Planning** | Operators see a recommended action per theme (Send Amber Alert / Request Doctors / Request water delivery) pre-wired with a likely audience and channel. | Plan templates per case type; assign tasks to specific field staff with due dates. |
| **Referral & Service Provision** | Audience-based broadcasts (Doctors near Sana'a / NGO field staff / Civilians) over App / SMS / Fallback. Junior operators are region-scoped and cannot broadcast to civilian masses without escalation. | Two-way referral receipts: "Dr Karim accepted — ETA 30m". |
| **Follow-up & Review** | Live message thread per case with operator outbound + civilian inbound interleaved. Per-region message timeline + sparkline shows trend over the last 60 minutes. | Scheduled check-ins, automatic escalation if stale. |
| **Case Closure** | (Open work — currently `status: "open" / "found" / "deceased"` on missing-person cases.) | Structured closure flow with reasons + audit log. |

### How we hit the constraints

- **Offline-capable** — built on top of [bitchat](https://github.com/permissionlesstech/bitchat) BLE mesh; alerts hop phone-to-phone over Bluetooth (7-hop TTL) when no internet, fall back to Nostr relays when one node has internet, fall back to SMS for dumbphones.
- **Safe & confidential** — Noise XX end-to-end encryption inherited from bitchat. Hub-and-spoke is enforced at the protocol layer, not the UI: civilians can only ever message the NGO, never each other.
- **Easy to use under pressure** — operator console is single-task per surface (one primary CTA per pane). One-click suggested broadcasts on every dashboard insight.
- **Frontline-supportive** — junior/senior operator roles with region scoping; backend gates broadcasts so a junior can't accidentally page 18,000 civilians.
- **Adaptable** — light backend (FastAPI), one Docker image, deploys on a single Linux VM (boxd.sh) in seconds. No reliance on a managed cloud.

## Relevant resources (cited in the brief)

- **Alma** — IRC's free multilingual virtual assistant for newcomers in the US. <https://welcome.rescue.org/us/en/services/alma>
- **Child Protection Case Management Resource Hub** — Alliance for Child Protection in Humanitarian Action. <https://alliancecpha.org/en/alliance-special-sections/child-protection-case-management-resource-hub>
- **Signpost** — IRC's digital information and referral platform. <https://www.signpost.ngo/>

## Contact (per the brief)

Rinske Ellermeijer — available via Signal during the weekend on **+31 6 1378 7021**.
