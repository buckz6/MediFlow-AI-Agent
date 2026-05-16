import os
import uuid
import time
import json
import re
import shutil
import logging
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_422_UNPROCESSABLE_ENTITY, HTTP_503_SERVICE_UNAVAILABLE, HTTP_504_GATEWAY_TIMEOUT

from models.xray_analyzer import analyze_xray
from agents.orchestrator import run_workflow
from utils.audio_transcriber import transcribe_consultation, AudioTranscriptionError
from utils.queue import inference_slot, queue_status

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MediFlow-API")

app = FastAPI(title="MediFlow AI Agent API")

# CORS Configuration
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://mediflow-vultr.com", # Placeholder for user's Vultr domain
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Model Ready Flag
MODEL_READY = False

@app.on_event("startup")
async def startup_event():
    global MODEL_READY
    try:
        from backend.models.load_model import get_model
        get_model()
        MODEL_READY = True
        logger.info("✅ Model loaded and cached at startup")
    except Exception as e:
        logger.error(f"❌ Failed to load model: {e}")
        MODEL_READY = False

TEMP_DIR = "/tmp/mediflow"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR, exist_ok=True)

def cleanup_temp(path: str):
    """Background task to remove temp files."""
    try:
        if os.path.exists(path):
            shutil.rmtree(path)
            logger.info(f"Cleaned up temp directory: {path}")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

def parse_json_block(text: str, marker: str) -> dict:
    """Helper to extract JSON from LLM response."""
    try:
        pattern = f"{marker}:\\s*({{.*?}})"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except Exception as e:
        logger.warning(f"Failed to parse {marker} from text: {e}")
    return {}

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "model_loaded": MODEL_READY,
        "timestamp": datetime.utcnow().isoformat(),
        **queue_status(),
    }

@app.post("/api/analyze")
async def analyze(
    background_tasks: BackgroundTasks,
    xray_image: UploadFile = File(...),
    lab_pdf: Optional[UploadFile] = File(None),
    audio_file: Optional[UploadFile] = File(None),
    patient_notes: Optional[str] = Form(None),
    patient_name: Optional[str] = Form(None)
):
    start_time = time.time()
    session_id = str(uuid.uuid4())
    session_path = os.path.join(TEMP_DIR, session_id)
    os.makedirs(session_path, exist_ok=True)

    if not MODEL_READY:
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Vision model not ready", "code": "MODEL_NOT_READY"}
        )

    # Validate file size (approx 10MB)
    MAX_SIZE = 10 * 1024 * 1024
    
    # Process X-Ray
    if xray_image.content_type not in ["image/jpeg", "image/png", "application/dicom"]:
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail={"error": "Invalid image format. Use JPG, PNG or DICOM.", "code": "INVALID_FILE_TYPE"}
        )

    image_path = os.path.join(session_path, xray_image.filename)
    with open(image_path, "wb") as f:
        content = await xray_image.read()
        if len(content) > MAX_SIZE:
            raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_ENTITY, detail={"error": "File too large", "code": "FILE_TOO_LARGE"})
        f.write(content)

    # Process Lab PDF
    pdf_text = ""
    if lab_pdf:
        if lab_pdf.content_type != "application/pdf":
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail={"error": "Lab report must be a PDF", "code": "INVALID_PDF"})
        
        pdf_path = os.path.join(session_path, lab_pdf.filename)
        with open(pdf_path, "wb") as f:
            pdf_content = await lab_pdf.read()
            if len(pdf_content) > MAX_SIZE:
                 raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_ENTITY, detail={"error": "PDF too large", "code": "PDF_TOO_LARGE"})
            f.write(pdf_content)
        
        # Placeholder for Gemini PDF extraction
        pdf_text = f"Extracted text from {lab_pdf.filename} (Simulated)"

    # Process Audio (optional, run in parallel)
    audio_path = None
    if audio_file:
        allowed_audio_types = ["audio/mpeg", "audio/wav", "audio/mp4", "audio/ogg", "audio/webm"]
        if audio_file.content_type not in allowed_audio_types:
            logger.warning(f"Unsupported audio type: {audio_file.content_type}, continuing without audio")
        else:
            audio_path = os.path.join(session_path, audio_file.filename)
            try:
                audio_content = await audio_file.read()
                if len(audio_content) > MAX_SIZE:
                    raise HTTPException(status_code=HTTP_422_UNPROCESSABLE_ENTITY, detail={"error": "Audio file exceeds 10MB", "code": "AUDIO_TOO_LARGE"})
                with open(audio_path, "wb") as f:
                    f.write(audio_content)
            except Exception as e:
                logger.error(f"Failed to save audio file: {e}")
                audio_path = None

    try:
        # Acquire inference slot — returns 503 immediately if queue full (maxsize=5)
        async with inference_slot():
            # Run X-Ray analysis in a thread pool (CPU-bound, must not block event loop)
            xray_data = await asyncio.get_event_loop().run_in_executor(
                None, analyze_xray, image_path
            )

        # Audio transcription runs outside the inference slot (I/O-bound, not CPU-bound)
        audio_result = None
        if audio_path:
            try:
                audio_result = await transcribe_consultation(audio_path)
            except AudioTranscriptionError as e:
                logger.warning("Audio transcription failed (graceful degradation): %s", e)
            except Exception as e:
                logger.warning("Unexpected audio error (graceful degradation): %s", e)

        # 2. Agent Orchestration
        agent_results = run_workflow(
            xray_result=xray_data,
            pdf_text=pdf_text,
            notes=patient_notes or "",
            xray_path=image_path
        )

        # 3. Parse LLM structured data
        finance_data = parse_json_block(agent_results['finance_raw'], "FINANCE_JSON")
        clinical_json = parse_json_block(agent_results['clinical_summary'], "DIAGNOSIS_JSON")

        processing_time = int((time.time() - start_time) * 1000)
        
        if processing_time > 30000:
             raise HTTPException(status_code=HTTP_504_GATEWAY_TIMEOUT, detail={"error": "Request timeout", "code": "TIMEOUT"})

        # Build transcript summary if audio was processed
        transcript_summary = None
        if audio_result:
            transcript_summary = {
                "transcript": audio_result.get("transcript", {}),
                "clinical_extraction": audio_result.get("clinical_extraction", {}),
            }

        response = {
            "session_id": session_id,
            "diagnosis": clinical_json.get("diagnosis", xray_data["diagnosis"]),
            "confidence": clinical_json.get("confidence_score", xray_data["confidence"]),
            "findings": xray_data["findings"],
            "heatmap_base64": xray_data["heatmap_base64"],
            "original_image_base64": xray_data["original_image_base64"],
            "clinical_summary": agent_results["clinical_summary"],
            "finance_estimate": {
                "consultation_idr": finance_data.get("consultation_idr", 0),
                "xray_idr": finance_data.get("xray_idr", 0),
                "lab_idr": finance_data.get("lab_idr", 0),
                "total_idr": finance_data.get("total_idr", 0),
                "bpjs_covered": finance_data.get("bpjs_covered", False),
                "bpjs_coverage_pct": finance_data.get("bpjs_coverage_pct", 0)
            },
            "patient_education": agent_results["education"],
            "transcript_summary": transcript_summary,
            "processing_time_ms": processing_time,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Queue cleanup
        background_tasks.add_task(cleanup_temp, session_path)
        
        logger.info(f"Analyzed request for {patient_name or 'Anonymous'} in {processing_time}ms (audio: {'yes' if audio_result else 'no'})")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Internal processing error: {str(e)}")
        # Don't leak details if it might contain sensitive info
        raise HTTPException(
            status_code=500,
            detail={"error": "Internal Server Error", "code": "INTERNAL_ERROR"}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
