# 🌀 **Echoes: A Soulful Audio Time Machine**

Capture moments as ambient sounds tied to emotion. Return to them when you need to remember who you are.

---

## 🧭 Overview

| Layer         | Tech Stack                                                 |
| ------------- | ---------------------------------------------------------- |
| Frontend      | React Native (Expo) or Vite + React Web                    |
| API           | FastAPI or AWS Lambda + API Gateway                        |
| Storage       | S3 for audio, DynamoDB for metadata                        |
| Auth          | Amazon Cognito                                             |
| Notifications | Amazon SNS + EventBridge                                   |
| Infra as Code | AWS CDK (Python or TypeScript)                             |
| AI Features   | Bedrock (Claude/Whisper/Polly), optional OpenAI/AssemblyAI |

---

## 1. 🎨 Frontend

### Core Screens:

* **Home:** "I feel \[x]…" → resurfaces a matching Echo
* **Record:** Choose emotion tag → capture 10–30 sec audio → save
* **Echo List:** Chronological or filtered view of past Echoes
* **Playback:** Full-screen nostalgia, minimal info (emotion, time, place)

### UI Libraries:

* Expo (`expo-av`, `expo-location`, `react-navigation`)
* Tailwind-style utility classes (e.g. `twrnc`) or Chakra for web

---

## 2. 🧠 Backend

### Audio Flow:

* Audio recorded in app
* Presigned URL from backend to upload to S3
* Metadata (emotion, timestamp, location, etc) sent to backend → stored in DynamoDB

### API Endpoints:

* `POST /echoes/init-upload`: returns S3 presigned URL
* `POST /echoes`: save metadata (emotion, location, userId, S3 URL)
* `GET /echoes?emotion=joy`: filter Echoes
* `GET /echoes/random?emotion=joy`: get one randomly-matched Echo

### FastAPI or AWS Lambda?

Choose **FastAPI + ECS Fargate** for long-term flexibility, or **pure Lambda** for cost efficiency and no-maintenance ops.

---

## 3. 🗂 Data Model

### DynamoDB: `EchoesTable`

```json
{
  "userId": "abc123",
  "echoId": "uuid-1234",
  "emotion": "Calm",
  "timestamp": "2025-06-25T15:00:00Z",
  "s3Url": "s3://echoes-audio/abc123/uuid-1234.wav",
  "location": {
    "lat": 37.5407,
    "lng": -77.4360
  },
  "tags": ["river", "kids", "outdoors"],
  "transcript": "Rio laughing and water splashing",
  "detectedMood": "joy"
}
```

---

## 4. ☁️ AWS Infrastructure

### S3

* Bucket: `echoes-audio-[env]`
* Structure: `/{userId}/{echoId}.webm`
* Permissions: user-level access via IAM roles (scoped per Cognito ID)

### DynamoDB

* Table: `EchoesTable`
* Partition key: `userId`
* Sort key: `timestamp` or `echoId`
* Global Secondary Index: `emotion-timestamp-index`

### Cognito

* User pools for signup/login
* Identity pools for presigned S3 uploads

### Lambda Functions

* `init_upload`: returns S3 presigned URL
* `save_echo`: stores metadata
* `get_echoes`: returns list
* `get_random_echo`: filtered by emotion

---

## 5. 🧠 AI + Enrichment (Phase 2)

| Feature                                              | Tool                            |
| ---------------------------------------------------- | ------------------------------- |
| Transcribe echo                                      | Whisper or Amazon Transcribe    |
| Auto-tag mood/emotion                                | Claude via Bedrock              |
| Categorize audio                                     | AssemblyAI / Audio ML           |
| Smart recall (“play something peaceful from spring”) | RAG + vector DB (e.g. Pinecone) |
| Memory stylization                                   | Claude + custom prompt chain    |

---

## 6. 🔔 Notifications

### Use Case: Time-delayed nudges

* After 1 week, 1 month, or user-chosen delay
* “An Echo from last summer wants to say hi…”

### Implementation:

* Store `nextNotificationTime` in DynamoDB
* Schedule via EventBridge + Lambda → SNS or email
* Optional: local notifications for mobile (via Expo Push)

---

## 7. 📦 CDK Setup

Structure:

```
/cdk/
  ├── bin/
  ├── lib/
      ├── echoes_stack.ts
  ├── context/
  └── cdk.json
```

Stacks:

* `EchoesStorageStack`: S3, DynamoDB
* `EchoesApiStack`: API Gateway, Lambdas
* `EchoesAuthStack`: Cognito setup
* `EchoesNotifStack`: EventBridge + SNS

---

## 8. 🧪 Testing & Observability

* Unit tests for API
* Postman collection or Pytest integration tests
* CloudWatch logs + X-Ray traces for all Lambda
* App-wide feature flagging via SSM Parameter Store

---

## 9. 🧰 Dev Experience

* GitHub Actions to deploy infra + frontend
* `.env` config system across Lambda + client
* Local dev with `sam local` or `localstack`
* GitHub Codespaces setup (optional)

---

## 10. 🌀 Roadmap

### Phase 1: MVP (2 weeks)

* Auth, record, tag, playback, list
* Presigned upload + DynamoDB
* Mobile + web support

### Phase 2: Memory Recall

* Filter by emotion
* Play random Echo
* Scheduled resurfacing

### Phase 3: AI Layer

* Transcripts + ML mood tagging
* “Ask my memories” style recall
* Personalized emotional analytics

### Phase 4: Sharing + Community

* Share Echoes with close friends/family
* Commenting or reactions (private)
* Optional private feed (e.g. “Echoes from Brigid”)
