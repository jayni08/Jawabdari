# Jawabdari — Architecture

## 1. Today's prototype (deployed at https://jawabdari-amc.streamlit.app)

Every page calls plain functions in `services.py`; all rules (guarantee, liability, deposit, score) live there and are covered by 59 automated tests.

```mermaid
flowchart LR
    subgraph USERS["Users"]
        C["Citizen phone"]
        E["Ward engineer"]
        K["Contractor"]
        M["Commissioner"]
    end

    QR["QR code on site"]

    subgraph APP["Streamlit app (5 pages)"]
        PB["Public board"]
        RP["Report a problem"]
        RW["Register work"]
        CD["Contractor desk"]
        DB1["Dashboard"]
    end

    subgraph SVC["services.py"]
        LE["Liability engine"]
        DR["Deposit rules"]
        CS["Contractor scoring"]
    end

    SQL[("SQLite")]

    C --> QR --> PB --> RP
    E --> RW
    E --> CD
    K --> CD
    M --> DB1
    RW --> LE
    RP --> LE
    CD --> DR
    DB1 --> CS
    LE --> SQL
    DR --> SQL
    CS --> SQL

    classDef user fill:#ffffff,stroke:#8b8fa8,color:#1c1d2b
    classDef page fill:#eef0ff,stroke:#4338ca,color:#2e2789
    classDef logic fill:#fff4e0,stroke:#e0a100,color:#4d2f00
    class C,E,K,M,QR user
    class PB,RP,RW,CD,DB1 page
    class LE,DR,CS logic
```

![Prototype architecture](architecture_prototype.png)

## 2. Production at India scale

Same rules from `services.py`, exposed as stateless FastAPI services behind a load balancer, so capacity grows by adding servers. Data is partitioned by state/city; integrations plug into India Stack.

```mermaid
flowchart LR
    subgraph CH["Channels"]
        WEB["Web / PWA"]
        QR["QR code on site"]
        WA["WhatsApp / SMS gateway"]
    end

    GW["API gateway + LB"]

    subgraph SVC["Stateless FastAPI services"]
        WK["Works"]
        DL["Defects & Liability"]
        SC["Contractor Score"]
        NT["Notifications"]
    end

    subgraph DATA["Data · partitioned by state/city"]
        PG[("PostgreSQL + PostGIS")]
        OS[("Photo object storage")]
        RD[("Redis cache")]
        MQ[["Notice message queue"]]
    end

    subgraph INT["Integrations"]
        GEM["GeM tenders"]
        DGL["DigiLocker identity"]
        GS["PM Gati Shakti GIS"]
        PFMS["PFMS deposit release"]
        BH["Bhashini translation"]
    end

    WEB --> GW
    QR --> GW
    WA --> GW
    GW --> WK
    GW --> DL
    GW --> SC
    GW --> NT
    WK -.-> GEM
    WK -.-> DGL
    WK -.-> GS
    DL -.-> PFMS
    NT -.-> BH
    WK --> PG
    DL --> PG
    DL --> OS
    SC --> RD
    NT --> MQ

    classDef ch fill:#ffffff,stroke:#8b8fa8,color:#1c1d2b
    classDef svc fill:#eef0ff,stroke:#4338ca,color:#2e2789
    classDef data fill:#f3f4f8,stroke:#8b8fa8,color:#1c1d2b
    classDef ext fill:#fff4e0,stroke:#e0a100,color:#4d2f00
    class WEB,QR,WA ch
    class GW,WK,DL,SC,NT svc
    class PG,RD,OS,MQ data
    class GEM,PFMS,DGL,BH,GS ext
```

![Production architecture](architecture_production.png)
