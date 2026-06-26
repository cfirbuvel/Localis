# BotOS Future Features Backlog

This document outlines high-value feature directions for the **Global Neighborhood & Emergency Platform (BotOS)** to scale its utility, engagement, and administration.

---

## 📍 1. Interactive Real-Time Map Dashboard
*   **Status:** Next in line for implementation.
*   **Goal:** Provide regional managers and super-admins with a geographical view of community health, user distribution, and emergency incidents.
*   **Key Capabilities:**
    *   **Geographical Visualization:** Plot location nodes (Cities, Neighborhoods, Buildings) on an interactive dark-mode map (using Leaflet.js).
    *   **Live Incident Markers:** Mark active emergencies with glowing red indicators. Allow admins to click a marker to view details and mark it resolved.
    *   **User Density Heatmap:** Display heatmaps or styled cluster markers representing active verified users in different buildings or streets.
    *   **Geofenced Group Linkings:** Visually boundary neighborhoods/streets.
*   **User Value:** Translates raw database rows into immediate situational awareness during crisis situations.

---

## 🤖 2. AI-Powered Document Verification (Gemini Vision)
*   **Goal:** Automate the approval queue for private building chat verification using Gemini 1.5 Flash Vision.
*   **Key Capabilities:**
    *   **Document Parsing:** When a user uploads a utility bill or lease agreement via WhatsApp/Telegram, the backend pipes the media to the Gemini API.
    *   **Address & Identity Extraction:** Gemini extracts the applicant's name, document date, and address.
    *   **Match Verification:** Compares the extracted address to the user's claimed location node.
    *   **Trust Scoring:** Generates a confidence score (e.g., 0% to 100%) and a verification report.
    *   **Auto-Approve/Flag:** Auto-approves high-confidence matches (inviting the user directly) and queues low-confidence or mismatched uploads for manager review.
*   **User Value:** Prevents signup bottlenecks by replacing manual document reviews with instant automated verification.

---

## 🤝 3. P2P Mutual Aid & Community Request Board
*   **Goal:** Enable peer-to-peer sharing, requests, and coordination among verified neighbors, turning BotOS into an active daily network.
*   **Key Capabilities:**
    *   **Request Submission:** Citizens use the Telegram or WhatsApp bot to submit help requests under categories like *Tools/Sharing*, *Safety/Alerts*, *Lost & Found*, or *Elderly Assistance*.
    *   **Dashboard Moderation:** Requests are queued on the React Admin panel to prevent spam/abuse.
    *   **Automated Broadcasts:** Once approved, the system automatically posts the formatted request to the specific neighborhood/street chat group with a button to contact the poster.
    *   **Closed Loop:** Users can mark their requests as "Resolved" via the bot.
*   **User Value:** Drives daily user engagement and trust by facilitating peer-to-peer neighborhood support.

---

## 📝 4. AI-Powered Neighborhood Chat Summaries (Daily Digest)
*   **Goal:** Help busy community managers and residents stay informed by summarizing chat traffic into actionable digests.
*   **Key Capabilities:**
    *   **Message Aggregation:** Periodically aggregate logged messages from public/neighborhood Telegram and WhatsApp chats.
    *   **Gemini Summarization:** Prompt Gemini to extract core events, safety notices, shared requests, and general consensus topics while ignoring chatter.
    *   **Multi-Channel Digest:** Send the summary as a pinned message in the local group, a direct message digest, or display it in the React dashboard.
*   **User Value:** Solves chat fatigue. Citizens get a high-level summary of local topics without reading through thousands of messages.
