# Second Opinion: AI Infrastructure Overview

This document describes the high-level architecture of the "Second Opinion" ecosystem. The system is designed for maximum scalability, data privacy, and cost-efficiency.

# 1. Architectural Layers

To understand how the system operates, we divide it into three distinct layers:

Infrastructure Layer (The Foundation):

Google Cloud & Firebase: Provides serverless computing, secure document storage (Firestore), and encrypted file hosting (Cloud Storage). This is where the data "lives."

Intelligence Layer (The Brain):

Google Gemini 2.5 Flash: The generative AI engine responsible for OCR, medical data structuring, and semantic analysis. It processes but does not permanently store user data.

Interface Layer (The Gateway):

Telegram Bot API: Our primary mobile interface for instant user engagement.

React Web Portal: A secondary interface for desktop users and data visualization.


# 2. Business Use Cases

Use Case Diagram

```mermaid 
graph TD
    subgraph Users
        P[User]
        A[Administrator]
        D[Future Role]
    end

    subgraph "Second Opinion System"
        UC1(Upload Analysis via Telegram/Web)
        UC2(Get AI Insights via Gemini)
        UC3(View History via Firestore)
        UC4(API Load Monitoring)
        UC5(Manage Personal Data)
    end

    P --> UC1
    P --> UC2
    P --> UC3
    P --> UC5
    A --> UC4
```


# 3. System Flow (Sequence Diagram)

How data moves between components in real-time.

```mermaid
sequenceDiagram
    participant P as User
    participant E as Second Opinion Engine
    participant G as Google AI (Gemini)
    participant S as Secure Storage (Firestore)

    P->>E: Uploads Analysis (Photo/PDF)
    E->>G: Request Native OCR & Structuring
    G-->>E: Returns Structured JSON Facts
    E->>S: Archives Data (User-Specific Doc)
    S-->>E: Confirmation
    E->>G: Request Comparative Summary
    G-->>E: Generates Patient-Friendly Report
    E-->>P: Delivers Result via Telegram
```


# 4. Document Lifecycle (State Diagram)

State Diagram v2

```mermaid
stateDiagram-v2
    [*] --> Telegram: User Sends File
    Telegram --> CloudStorage: Secure Upload
    CloudStorage --> Gemini: Processing Request
    Gemini --> Firestore: Store Structured JSON
    Firestore --> User: Results Delivered
    User --> [*]
```

# 5. The Technology Stack

Cloud Ecosystem: Google Firebase (NoSQL database, Auth, Storage).

AI Engine: Google Gemini API (High-performance multimodal LLM).

Messenger API: Telegram (Universal delivery channel).

# 6. Security Principles

End-to-End Logic: Data is encrypted during transit from Telegram to Google Cloud.

User Isolation: Firestore rules ensure that a user can only access data associated with their unique Telegram ID.

Data Sovereignty: Users can trigger a full wipe of their medical records via a simple command.

Metadata: Updated April 2024 | Author: M. M. Bolshedvorskii