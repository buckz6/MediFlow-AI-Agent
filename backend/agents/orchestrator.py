"""
MediFlow LangGraph Workflow
────────────────────────────────────────────────────────────────
Orchestrator → fusion_layer → clinical ──(>90%)──► emergency_handler → END
                                        └──(≤90%)──► finance → education → END

Orchestrator → finance   (query keuangan langsung)
Orchestrator → education (query edukasi langsung)
Orchestrator → admin
────────────────────────────────────────────────────────────────
Semua payload yang ditulis ke AgentState dienkripsi dengan Fernet
(MEDIFLOW_ENCRYPTION_KEY) sebelum disimpan dan didekripsi saat dibaca.
"""

import operator
import os
from typing import Annotated, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from models.xray_analyzer import XRayAnalyzer
from agents.security import decrypt_payload, encrypt_payload


# ── Shared LLM ────────────────────────────────────────────────────────────────

def _llm() -> ChatGoogleGenerativeAI:
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        return ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            google_api_key=api_key,
            temperature=0.2,
        )

    class DummyResponse:
        def __init__(self, content: str):
            self.content = content

    class DummyLLM:
        def __init__(self):
            self.system_text = None

        def invoke(self, messages):
            prompt = messages[-1].content if messages else ""
            system = messages[0].content if messages else ""

            if "orchestrator" in system and "MediFlow" in system:
                return DummyResponse("clinical")
            if "Clinical Agent" in system or "DIAGNOSIS_JSON" in system:
                return DummyResponse(
                    "Diagnosis: Suspected TBC. DIAGNOSIS_JSON: {\"diagnosis\": \"Tuberculosis\", \"severity\": \"moderate\", \"tbc_confirmed\": true, \"recommended_treatment\": \"Rujuk ke TBC klinik dan mulailah terapi antibiotik\", \"confidence_score\": 0.85}"
                )
            if "Finance" in system or "FINANCE_JSON" in system:
                return DummyResponse(
                    "Finance estimates. FINANCE_JSON: {\"consultation_idr\": 50000, \"xray_idr\": 100000, \"lab_idr\": 75000, \"total_idr\": 225000, \"bpjs_covered\": true, \"bpjs_coverage_pct\": 80}"
                )
            if "Patient Literacy Agent" in system or "penjelasan medis sederhana" in system:
                return DummyResponse(
                    "Penting untuk segera mengobati TBC dengan obat yang diresepkan dokter. Minum obat secara teratur dan ikuti anjuran medis sampai selesai."
                )
            if "administratif" in system:
                return DummyResponse("Maaf, saya tidak bisa memproses permintaan administratif saat ini.")
            return DummyResponse("clinical")

    return DummyLLM()


# ── State ─────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages:             Annotated[list[BaseMessage], operator.add]
    next_agent:           str
    emergency_flag:       bool
    tbc_confidence:       float
    xray_image_path:      str | None

    # Payload terenkripsi — hanya boleh dibaca via decrypt_payload()
    encrypted_fused_context:   str | None   # diisi oleh fusion_layer
    encrypted_clinical_result: str | None   # diisi oleh clinical_agent
    encrypted_finance_result:  str | None   # diisi oleh finance_agent
    encrypted_education_result: str | None  # diisi oleh education_agent

    agent_response:       str   # respons akhir untuk dikembalikan ke API


# ── Orchestrator ──────────────────────────────────────────────────────────────

_ORCHESTRATOR_SYSTEM = """Kamu adalah orchestrator triase MediFlow untuk sistem AI rumah sakit.
Klasifikasikan permintaan pengguna ke dalam tepat satu dari: clinical, finance, education, admin.

Aturan:
- clinical  → analisis X-ray, TBC, diagnosis, gejala, hasil lab, resep
- finance   → tagihan, asuransi, pembayaran, estimasi biaya, invoice
- education → edukasi pasien, informasi penyakit, panduan obat, FAQ
- admin     → janji temu, penjadwalan, manajemen bangsal, staf, rekam medis

Balas HANYA dengan satu kata huruf kecil. Tanpa tanda baca, tanpa penjelasan."""

def orchestrator(state: AgentState) -> dict:
    last = state["messages"][-1].content
    result = _llm().invoke([
        SystemMessage(content=_ORCHESTRATOR_SYSTEM),
        HumanMessage(content=last),
    ])
    route = result.content.strip().lower()
    if route not in {"clinical", "finance", "education", "admin"}:
        route = "admin"
    return {"next_agent": route}


# ── Fusion Layer ──────────────────────────────────────────────────────────────

def fusion_layer(state: AgentState) -> dict:
    """Gabungkan semua input multimodal menjadi satu konteks terenkripsi."""
    xray_path   = state.get("xray_image_path")
    confidence  = state.get("tbc_confidence", 0.0)
    label       = "N/A"

    if xray_path:
        result     = XRayAnalyzer().analyze_image(xray_path)
        confidence = result["confidence"]
        label      = result["prediction"]

    context = (
        f"--- MULTIMODAL FUSION CONTEXT ---\n"
        f"X-RAY: Label={label}, Confidence={confidence:.2%}\n"
        f"Query awal: {state['messages'][-1].content}\n"
        f"---------------------------------"
    )

    return {
        "encrypted_fused_context": encrypt_payload(context),
        "tbc_confidence": confidence,
    }


# ── Clinical Agent ────────────────────────────────────────────────────────────

_CLINICAL_SYSTEM = """Kamu adalah asisten AI klinis di rumah sakit (Gemini Pro).
Berdasarkan MULTIMODAL FUSION CONTEXT yang diberikan:
1. Buat Ringkasan Diagnosis yang jelas dan terstruktur.
2. Rekomendasikan langkah Pengobatan.
3. MANDATORY: Sertakan Skor Keyakinan transparan (misalnya: [Skor Keyakinan: 92%]) untuk menunjukkan akurasi sistem.
4. Sebutkan secara eksplisit apakah Emergency Flag diperlukan.
5. Sertakan field JSON di akhir respons dengan format:
   DIAGNOSIS_JSON: {"diagnosis": "<nama_penyakit>", "severity": "<mild|moderate|severe>", "tbc_confirmed": <true|false>, "recommended_treatment": "<ringkasan_singkat>", "confidence_score": <float>}

Aturan:
- Jika confidence TBC atau skor keyakinan > 90%, WAJIB nyatakan Emergency Flag.
- Gunakan bahasa profesional dan klinis."""

def clinical_agent(state: AgentState) -> dict:
    fused = decrypt_payload(state["encrypted_fused_context"])
    confidence = state.get("tbc_confidence", 0.0)
    emergency  = confidence > 0.90

    response = _llm().invoke([
        SystemMessage(content=_CLINICAL_SYSTEM),
        HumanMessage(content=fused),
    ])

    encrypted_result = encrypt_payload(response.content)

    return {
        "messages":                [AIMessage(content=response.content)],
        "encrypted_clinical_result": encrypted_result,
        "emergency_flag":          emergency,
        "agent_response":          response.content,
    }


# ── Emergency Handler ─────────────────────────────────────────────────────────

_EMERGENCY_SYSTEM = """Kamu adalah sistem eskalasi darurat MediFlow.
Kasus TBC dengan confidence tinggi (>90%) telah terdeteksi.
Buat checklist tindakan darurat untuk tim klinis:
- Protokol isolasi segera
- Notifikasi wajib (dokter, pengendalian infeksi, kesehatan masyarakat)
- Tes konfirmasi mendesak yang harus dipesan
- Langkah komunikasi dengan pasien
Format sebagai daftar bernomor. Langsung dan klinis."""

def emergency_handler(state: AgentState) -> dict:
    clinical_text = decrypt_payload(state["encrypted_clinical_result"])
    response = _llm().invoke([
        SystemMessage(content=_EMERGENCY_SYSTEM),
        HumanMessage(
            content=f"TBC confidence: {state['tbc_confidence']:.2%}\n"
                    f"Penilaian klinis:\n{clinical_text}"
        ),
    ])
    msg = f"🚨 EMERGENCY ESCALATION TRIGGERED\n\n{response.content}"
    return {
        "messages":      [AIMessage(content=msg)],
        "agent_response": msg,
    }


# ── Finance Agent ─────────────────────────────────────────────────────────────

_FINANCE_SYSTEM = """Kamu adalah asisten AI keuangan rumah sakit (Enterprise Value Layer).
Tugasmu adalah menghasilkan estimasi biaya perawatan OTOMATIS berdasarkan diagnosis dari Clinical Agent.

Langkah Kerja:
1. Analisis diagnosis dan pengobatan yang direkomendasikan oleh Clinical Agent.
2. Hasilkan tabel estimasi biaya yang mencakup:
   - Konsultasi Spesialis
   - Prosedur/Tes (X-Ray, Sputum, dll)
   - Paket Obat TBC (Fase Intensif & Lanjutan)
   - Biaya Administrasi
3. Berikan informasi apakah prosedur tersebut ditanggung BPJS Kesehatan.
4. Sertakan estimasi total dalam IDR.

Gunakan data biaya yang realistis untuk rumah sakit kelas B di Indonesia. Berikan nilai tambah dengan memberikan saran klaim asuransi.

MANDATORY: Sertakan field JSON di akhir respons dengan format:
FINANCE_JSON: {"consultation_idr": <int>, "xray_idr": <int>, "lab_idr": <int>, "total_idr": <int>, "bpjs_covered": <bool>, "bpjs_coverage_pct": <int>}
"""

def finance_agent(state: AgentState) -> dict:
    # Baca diagnosis dari Clinical Agent jika tersedia, fallback ke pesan langsung
    encrypted_clinical = state.get("encrypted_clinical_result")
    if encrypted_clinical:
        clinical_context = decrypt_payload(encrypted_clinical)
        prompt = (
            f"Berdasarkan hasil diagnosis berikut dari Clinical Agent:\n\n"
            f"{clinical_context}\n\n"
            f"Hitung estimasi biaya perawatan lengkap untuk pasien."
        )
    else:
        prompt = state["messages"][-1].content

    response = _llm().invoke([
        SystemMessage(content=_FINANCE_SYSTEM),
        HumanMessage(content=prompt),
    ])

    encrypted_result = encrypt_payload(response.content)

    return {
        "messages":               [AIMessage(content=response.content)],
        "encrypted_finance_result": encrypted_result,
        "agent_response":         response.content,
    }


# ── Education Agent ───────────────────────────────────────────────────────────

_EDUCATION_SYSTEM = """Kamu adalah asisten edukasi pasien (Patient Literacy Agent).
Tugasmu adalah menyederhanakan informasi medis yang kompleks (terutama TBC) menjadi penjelasan yang ramah pasien.

Fokus Edukasi TBC:
1. Penjelasan Sederhana: TBC adalah infeksi bakteri yang bisa disembuhkan, bukan penyakit keturunan atau guna-guna.
2. Cara Penularan: Menular lewat udara, namun dapat dicegah dengan masker dan ventilasi.
3. Pentingnya Kepatuhan: Jelaskan mengapa obat harus diminum sampai tuntas selama 6 bulan (mencegah resistensi).
4. Gaya Hidup: Nutrisi yang baik dan sinar matahari sangat membantu.

Gunakan bahasa yang hangat, empatik, dan mudah dipahami (tingkat literasi SD/SMP). Berikan semangat kepada pasien bahwa mereka BISA sembuh total."""

def education_agent(state: AgentState) -> dict:
    # Gabungkan konteks dari Clinical + Finance Agent
    encrypted_clinical = state.get("encrypted_clinical_result")
    encrypted_finance  = state.get("encrypted_finance_result")

    clinical_text = decrypt_payload(encrypted_clinical) if encrypted_clinical else "Tidak ada data diagnosis."
    finance_text  = decrypt_payload(encrypted_finance)  if encrypted_finance  else "Tidak ada data biaya."

    prompt = (
        f"HASIL DIAGNOSIS KLINIS:\n{clinical_text}\n\n"
        f"ESTIMASI BIAYA PERAWATAN:\n{finance_text}\n\n"
        f"Buat draf penjelasan medis sederhana untuk pasien berdasarkan informasi di atas."
    )

    response = _llm().invoke([
        SystemMessage(content=_EDUCATION_SYSTEM),
        HumanMessage(content=prompt),
    ])

    encrypted_result = encrypt_payload(response.content)

    return {
        "messages":                 [AIMessage(content=response.content)],
        "encrypted_education_result": encrypted_result,
        "agent_response":           response.content,
    }


# ── Admin Agent ───────────────────────────────────────────────────────────────

_ADMIN_SYSTEM = """Kamu adalah asisten administratif AI rumah sakit.
Bantu dengan penjadwalan janji temu, pertanyaan bangsal, koordinasi staf, dan permintaan rekam medis.
Bersikap efisien dan profesional."""

def admin_agent(state: AgentState) -> dict:
    response = _llm().invoke([
        SystemMessage(content=_ADMIN_SYSTEM),
        HumanMessage(content=state["messages"][-1].content),
    ])
    return {
        "messages":      [AIMessage(content=response.content)],
        "agent_response": response.content,
    }


# ── Routing ───────────────────────────────────────────────────────────────────

def _route_orchestrator(state: AgentState) -> Literal["fusion_layer", "finance", "education", "admin"]:
    route = state["next_agent"]
    return "fusion_layer" if route == "clinical" else route  # type: ignore[return-value]

def _route_clinical(state: AgentState) -> Literal["emergency_handler", "finance"]:
    return "emergency_handler" if state.get("emergency_flag") else "finance"


# ── Graph factory ─────────────────────────────────────────────────────────────

def create_medi_flow_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("orchestrator",      orchestrator)
    workflow.add_node("fusion_layer",      fusion_layer)
    workflow.add_node("clinical",          clinical_agent)
    workflow.add_node("emergency_handler", emergency_handler)
    workflow.add_node("finance",           finance_agent)
    workflow.add_node("education",         education_agent)
    workflow.add_node("admin",             admin_agent)

    workflow.set_entry_point("orchestrator")

    workflow.add_conditional_edges(
        "orchestrator",
        _route_orchestrator,
        {
            "fusion_layer": "fusion_layer",
            "finance":      "finance",
            "education":    "education",
            "admin":        "admin",
        },
    )

    workflow.add_edge("fusion_layer", "clinical")

    # Clinical → emergency (jika >90%) ATAU langsung ke finance untuk estimasi biaya
    workflow.add_conditional_edges(
        "clinical",
        _route_clinical,
        {"emergency_handler": "emergency_handler", "finance": "finance"},
    )

    # Setelah emergency, tetap lanjut ke finance dan education
    workflow.add_edge("emergency_handler", "finance")

    # Finance selalu dilanjutkan ke education untuk penjelasan pasien
    workflow.add_edge("finance",    "education")
    workflow.add_edge("education",  END)
    workflow.add_edge("admin",      END)

    return workflow.compile()


# ── Singleton graph ───────────────────────────────────────────────────────────

# ── Execution Helper ──────────────────────────────────────────────────────────

def run_workflow(xray_result: dict, pdf_text: str = "", notes: str = "", xray_path: str = None) -> dict:
    """Runs the MediFlow workflow and returns a decrypted unified response."""
    inputs = {
        "messages": [HumanMessage(content=notes or "Analyze my medical data.")],
        "xray_image_path": xray_path,
        "tbc_confidence": xray_result.get("confidence", 0.0),
        "audio_transcription": notes, # Simplified for now
        "lab_data": pdf_text,
        "emergency_flag": False,
        "next_agent": "clinical"
    }
    
    # Run the graph
    final_state = medi_flow_graph.invoke(inputs)
    
    # Decrypt results
    clinical = decrypt_payload(final_state.get("encrypted_clinical_result")) if final_state.get("encrypted_clinical_result") else ""
    finance = decrypt_payload(final_state.get("encrypted_finance_result")) if final_state.get("encrypted_finance_result") else ""
    education = decrypt_payload(final_state.get("encrypted_education_result")) if final_state.get("encrypted_education_result") else ""
    
    return {
        "clinical_summary": clinical,
        "finance_raw": finance,
        "education": education,
        "emergency": final_state.get("emergency_flag", False)
    }


medi_flow_graph = create_medi_flow_graph()
