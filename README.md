flowchart TD
    subgraph UI["💬 React Frontend (Vite)"]
        U1["AI Triage Chat UI"]
        U2["Gemini Status Badge (/ai/ping)"]
    end

    subgraph API["⚙️ FastAPI Backend (port 8000)"]
        A1["/triage-dyn/start – Begin Session"]
        A2["/triage-dyn/{id}/answer – Dynamic Q&A"]
        A3["/triage-dyn/{id}/summary – SNOW Summary"]
        A4["/webhook/logs – Log Ingestion"]
        A5["/labeler/analyze – AI Log Labeling"]
        A6["/labeler/stats – Log Statistics"]
        A7["/ai/ping – Gemini Health"]
    end

    subgraph DB["🗄️ SQLite Database (triage.db)"]
        D1["sessions"]
        D2["answers"]
        D3["logs"]
    end

    subgraph AI["🧠 AI / Analysis Layer"]
        G1["Labeler AI"]
        G2["Gemini Summarizer"]
        G3["Dynamic Question Generator"]
    end

    subgraph EXT["🌐 External Integrations (optional future)"]
        X1["ServiceNow (SNOW)"]
        X2["ELK / CloudWatch Logs"]
        X3["External Gemini ChatBot"]
    end

    %% UI to Backend
    U1 -->|REST| A1
    U1 -->|REST| A2
    U1 -->|GET Summary| A3
    U2 -->|Health Check| A7

    %% Backend to DB
    A1 -->|Create session| D1
    A2 -->|Store Q&A| D2
    A4 -->|Insert Logs| D3
    A5 -->|Read/Label Logs| D3
    A6 -->|Read Stats| D3

    %% Backend to AI
    A2 -->|Summarize & Context| G2
    A2 -->|Next Question| G3
    A5 -->|Labeling| G1

    %% AI ↔ DB context
    G1 -->|Write labels| D3
    G2 -->|Summarize POF| D3
    G3 -->|Reads Answers| D2

    %% Future integrations
    A3 -->|Export Summary| X1
    A4 -->|Ingest Real Logs| X2
    G2 -->|Extended Reasoning| X3

    %% Styling
    classDef core fill:#F8FAFC,stroke:#1E3A8A,stroke-width:1.5px,color:#111;
    classDef ai fill:#E0F2FE,stroke:#0369A1,stroke-width:1.5px,color:#111;
    classDef db fill:#FEF9C3,stroke:#A16207,stroke-width:1.5px,color:#111;
    classDef ext fill:#FCE7F3,stroke:#9D174D,stroke-width:1.5px,color:#111;

    class U1,U2,API core
    class A1,A2,A3,A4,A5,A6,A7 core
    class D1,D2,D3 db
    class G1,G2,G3 ai
    class X1,X2,X3 ext
