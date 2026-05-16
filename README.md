# 🫁 MediFlow Autonomous Enterprise Agent
![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-14-000000?style=flat-square&logo=nextdotjs&logoColor=white)
![Gemini Pro](https://img.shields.io/badge/Gemini_Pro-AI-4285F4?style=flat-square&logo=google&logoColor=white)
![MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Vultr](https://img.shields.io/badge/Vultr-Cloud-007BFF?style=flat-square&logo=vultr&logoColor=white)

> **Tagline**: Multimodal AI agent for autonomous clinical decision support — detecting tuberculosis from X-rays with explainable Grad-CAM heatmaps, coordinated by LangGraph multi-agent system, deployed on Vultr.

## 🎯 Problem Statement
- **Tuberculosis (TBC)** remains a major health crisis in Indonesia, with approximately **350,000 cases per year**.
- **Manual diagnosis** is time-consuming, and specialized radiologists are often scarce in rural areas.
- **MediFlow** reduces analysis time from **hours to minutes**, providing instant second opinions for clinicians.

## ✨ Key Features
- 🔬 **X-Ray Analysis**: Powered by EfficientNet-B4 with **Grad-CAM heatmap** for visual explainability.
- 🧠 **4 Specialized LangGraph Agents**:
    - **Clinical Agent**: Deep diagnosis and confidence scoring.
    - **Finance Agent**: Automated cost estimation and BPJS coverage validation.
    - **Education Agent**: Patient-friendly disease explanations and recovery steps.
    - **Workflow Agent**: Intelligent scheduling and next-step coordination.
- 🎙️ **Audio Transcription**: Seamless integration with **Speechmatics** for multi-speaker diarization of clinical notes.
- 📄 **PDF Lab Extraction**: Automated processing of medical reports via **Gemini Multimodal**.
- 💡 **Explainable AI**: Heatmaps pinpoint suspect lung regions to ensure clinician trust.
- 📱 **Real-time Dashboard**: Modern Next.js interface with dark mode and dynamic medical timelines.

## 🏗️ Architecture

![MediFlow Architecture](docs/architecture.svg)

```text
Input Layer
├── 🖼️ X-Ray → EfficientNet-B4 + Grad-CAM
├── 📄 PDF Lab → Gemini Multimodal
├── 🎙️ Audio → Speechmatics → Gemini Pro
└── 📝 Notes → Gemini Pro
         ↓
LangGraph Orchestrator
├── 🏥 Clinical Agent (diagnosis + confidence)
├── 💰 Finance Agent (biaya + BPJS)
├── 🎓 Education Agent (edukasi pasien)
└── 📅 Workflow Agent (scheduling)
         ↓
Next.js Dashboard
(Heatmap + Diagnosis + Timeline + PDF Export)
```

**Infrastructure**: Vultr VM → Docker → Nginx → SSL (Certbot)

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- API Keys: Google Gemini, Speechmatics

### Installation
```bash
git clone https://github.com/[username]/mediflow
cd mediflow
cp .env.example .env
# Edit .env with your API keys
docker-compose up -d
```

### Verify
```bash
curl https://your-domain.com/api/health
# Expected: {"status": "ok", "model_loaded": true}
```

## 🔌 API Reference

### `POST /api/analyze`
**Request (multipart/form-data):**
- `xray_image`: File (`.jpg`, `.png`, `.dcm`) **REQUIRED**
- `lab_pdf`: File (`.pdf`) *optional*
- `audio_file`: File (`.mp3`, `.wav`) *optional*
- `patient_notes`: String *optional*

**Response:**
```json
{
  "diagnosis": "Tuberculosis Suspected",
  "confidence": 0.92,
  "findings": ["Infiltrate upper lobe right"],
  "heatmap_base64": "data:image/png;base64,...",
  "finance_estimate": {"total_idr": 700000, "bpjs_covered": true},
  "patient_education": "TBC dapat disembuhkan...",
  "processing_time_ms": 14500
}
```

## 🏆 Hackathon Tracks
- ✅ **Multimodal Intelligence**: Unified processing of X-Ray, PDF, Audio, and Text.
- ✅ **Collaborative Systems**: 4 LangGraph agents working in parallel orchestrations.
- ✅ **Enterprise Utility**: Modeled after real-world hospital operational workflows.
- ✅ **Vultr Challenge**: Full-stack backend and inference engine deployed on Vultr VM.
- ✅ **Google Gemini Challenge**: Gemini Pro 1.5 serves as the reasoning core for all agents.
- ✅ **Speechmatics Challenge**: Advanced audio transcription pipeline for clinical sessions.

## 🔒 Security
- **SSRF Hardening**: Fixed relative paths for internal API communication.
- **Privacy First**: Zero logging of API keys to standard output/error.
- **Resource Management**: Strict memory control using `torch.inference_mode()` and `Image.open()` context managers.
- **Output Safety**: `max_output_tokens=1024` enforced on all Gemini calls to prevent prompt injection overflow.

## 📄 License
Distributed under the MIT License. See `LICENSE` for more information.

## 👤 Team
[Nama Anda] | [GitHub] | [LinkedIn]
