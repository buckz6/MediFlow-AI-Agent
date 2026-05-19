'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Upload, FileUp, Loader, CheckCircle, AlertCircle, TrendingUp, Calendar, Mic, MicOff, Brain, FileText, Download, File } from 'lucide-react';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

interface AnalysisResult {
  diagnosis: string;
  confidence: number;
  findings: string[];
  heatmap_base64: string;
  original_image_base64: string;
  finance_estimate?: {
    estimated_cost: number;
    bpjs_coverage: number;
  };
  patient_education?: string;
  transcript_summary?: {
    transcript: string;
  };
}

interface TimelineEvent {
  timestamp: string;
  event: string;
  status: 'pending' | 'completed' | 'error';
  details?: string;
}

const FileUploadZone = ({ onFilesSelected }: { onFilesSelected: (files: File[]) => void }) => {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    onFilesSelected(files);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.currentTarget.files;
    if (files) {
      onFilesSelected(Array.from(files));
    }
  };

  return (
    <div
      className={`relative border-2 border-dashed rounded-lg p-8 transition-colors ${
        isDragging
          ? 'border-blue-500 bg-blue-50 dark:bg-blue-950'
          : 'border-gray-300 dark:border-gray-600 hover:border-blue-400 hover:bg-gray-50 dark:hover:bg-gray-800'
      }`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".jpg,.jpeg,.png,.pdf"
        onChange={handleFileSelect}
        className="hidden"
      />
      <div className="flex flex-col items-center justify-center gap-3">
        <Upload className="w-12 h-12 text-blue-500" />
        <div className="text-center">
          <p className="text-lg font-semibold text-gray-900 dark:text-white">
            Drop your files here
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            or{' '}
            <button
              onClick={() => fileInputRef.current?.click()}
              className="text-blue-500 hover:underline font-medium"
            >
              browse
            </button>
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-500 mt-2">
            Supported: X-Ray images (JPG, PNG) and PDF lab results
          </p>
        </div>
      </div>
    </div>
  );
};

const XRayCanvas = ({ result }: { result?: AnalysisResult }) => {
  const [showHeatmap, setShowHeatmap] = useState(true);

  if (!result) {
    return (
      <div className="flex flex-col items-center justify-center h-full bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-8 min-h-96">
        <Upload className="w-16 h-16 text-gray-400 dark:text-gray-600 mb-4" />
        <p className="text-gray-500 dark:text-gray-400 text-lg font-medium">Upload X-Ray to Begin</p>
        <p className="text-gray-400 dark:text-gray-500 text-sm mt-2">Drag and drop to analyze</p>
      </div>
    );
  }

  return (
    <div className="space-y-4 h-full flex flex-col">
      {/* Main Image Display */}
      <div className="flex-1 bg-gray-100 dark:bg-gray-800 rounded-lg overflow-hidden border-2 border-gray-200 dark:border-gray-700 flex items-center justify-center relative min-h-96">
        {/* Original Image */}
        <img
          src={result.original_image_base64}
          alt="Original X-Ray"
          className="max-w-full max-h-full object-contain"
        />

        {/* Heatmap Overlay */}
        {showHeatmap && (
          <img
            src={result.heatmap_base64}
            alt="Heatmap Overlay"
            className="absolute inset-0 max-w-full max-h-full object-contain opacity-60"
          />
        )}

        {/* Toggle Button */}
        <div className="absolute top-4 right-4">
          <button
            onClick={() => setShowHeatmap(!showHeatmap)}
            className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
              showHeatmap
                ? 'bg-red-500 hover:bg-red-600 text-white'
                : 'bg-blue-500 hover:bg-blue-600 text-white'
            }`}
          >
            {showHeatmap ? 'Hide Heatmap' : 'Show Heatmap'}
          </button>
        </div>

        {/* Diagnosis Badge */}
        <div className="absolute top-4 left-4 px-4 py-2 rounded-full text-sm font-bold bg-gray-900/80 text-white backdrop-blur-sm">
          {result.diagnosis}
        </div>
      </div>

      {/* Findings List */}
      <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">Clinical Findings</h3>
        <ul className="space-y-2">
          {result.findings.map((finding, idx) => (
            <li key={idx} className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300">
              <span className="text-blue-500 font-bold mt-0.5">•</span>
              <span>{finding}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Finance & Education Cards */}
      <div className="grid grid-cols-2 gap-4">
        {result.finance_estimate && (
          <div className="bg-green-50 dark:bg-green-950 rounded-lg border border-green-200 dark:border-green-800 p-4">
            <p className="text-xs font-medium text-green-600 dark:text-green-400 uppercase mb-2">Cost Estimate</p>
            <p className="text-lg font-bold text-green-700 dark:text-green-300">
              Rp {(result.finance_estimate?.estimated_cost || 0).toLocaleString('id-ID')}
            </p>
            <p className="text-xs text-green-600 dark:text-green-400 mt-1">
              BPJS Coverage: {result.finance_estimate?.bpjs_coverage || 0}%
            </p>
          </div>
        )}
        {result.patient_education && (
          <div className="bg-blue-50 dark:bg-blue-950 rounded-lg border border-blue-200 dark:border-blue-800 p-4">
            <p className="text-xs font-medium text-blue-600 dark:text-blue-400 uppercase mb-2">Education</p>
            <p className="text-sm text-blue-900 dark:text-blue-100 line-clamp-3">{result.patient_education}</p>
          </div>
        )}
      </div>
    </div>
  );
};

const PatientTimeline = ({ events }: { events: TimelineEvent[] }) => {
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
        <Brain className="w-5 h-5 text-purple-500" />
        Agent Coordination Timeline
      </h3>

      <div className="space-y-3 max-h-96 overflow-y-auto">
        {events.map((event, index) => (
          <div key={index} className="flex gap-4">
            {/* Timeline indicator */}
            <div className="flex flex-col items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                event.status === 'completed' ? 'bg-green-100 dark:bg-green-900' :
                event.status === 'error' ? 'bg-red-100 dark:bg-red-900' :
                'bg-purple-100 dark:bg-purple-900'
              }`}>
                {event.status === 'completed' && <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400" />}
                {event.status === 'error' && <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400" />}
                {event.status === 'pending' && <Loader className="w-5 h-5 text-purple-600 dark:text-purple-400 animate-spin" />}
              </div>
              {index < events.length - 1 && (
                <div className={`w-1 h-8 ${event.status === 'completed' ? 'bg-green-300 dark:bg-green-700' : 'bg-gray-300 dark:bg-gray-600'}`} />
              )}
            </div>

            {/* Timeline content */}
            <div className="flex-1 pb-2 min-w-0">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1">
                  <p className="font-semibold text-gray-900 dark:text-white text-sm">{event.event}</p>
                  {event.details && (
                    <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 line-clamp-2">{event.details}</p>
                  )}
                  {/* Agent indicator */}
                  {event.event.includes('Clinical Agent') && (
                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 mt-1">
                      <Brain className="w-3 h-3" />
                      Clinical Agent
                    </span>
                  )}
                  {event.event.includes('Education Agent') && (
                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200 mt-1">
                      <TrendingUp className="w-3 h-3" />
                      Education Agent
                    </span>
                  )}
                </div>
                <span className="text-xs text-gray-500 dark:text-gray-500 whitespace-nowrap">{event.timestamp}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="text-xs bg-purple-50 dark:bg-purple-950 border border-purple-200 dark:border-purple-800 rounded p-3 text-purple-800 dark:text-purple-200">
        <p className="font-medium mb-1">Agent Coordination</p>
        <p>Clinical Agent analyzes medical data while Education Agent provides contextual learning and recommendations.</p>
      </div>
    </div>
  );
};

const generateMedicalReport = async (result: AnalysisResult, imageBase64: string, heatmapBase64: string) => {
  const pdf = new jsPDF('p', 'mm', 'a4');
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 20;
  let yPosition = margin;

  // Header
  pdf.setFontSize(20);
  pdf.setFont('helvetica', 'bold');
  pdf.setTextColor(0, 51, 102); // Dark blue
  pdf.text('MEDICAL DIAGNOSTIC REPORT', pageWidth / 2, yPosition, { align: 'center' });
  yPosition += 15;

  // Hospital Info
  pdf.setFontSize(12);
  pdf.setFont('helvetica', 'normal');
  pdf.setTextColor(0, 0, 0);
  pdf.text('MediFlow AI Medical Center', pageWidth / 2, yPosition, { align: 'center' });
  yPosition += 10;
  pdf.text('Advanced AI-Powered Diagnostic Services', pageWidth / 2, yPosition, { align: 'center' });
  yPosition += 15;

  // Report Details
  pdf.setFontSize(10);
  pdf.setTextColor(100, 100, 100);
  pdf.text(`Report Generated: ${new Date().toLocaleDateString()} ${new Date().toLocaleTimeString()}`, margin, yPosition);
  pdf.text(`Patient ID: ${Math.random().toString(36).substr(2, 9).toUpperCase()}`, pageWidth - margin, yPosition, { align: 'right' });
  yPosition += 20;

  // Patient Information Section
  pdf.setFontSize(14);
  pdf.setFont('helvetica', 'bold');
  pdf.setTextColor(0, 51, 102);
  pdf.text('PATIENT INFORMATION', margin, yPosition);
  yPosition += 10;

  pdf.setFontSize(10);
  pdf.setFont('helvetica', 'normal');
  pdf.setTextColor(0, 0, 0);
  pdf.text('Name: [Patient Name]', margin, yPosition);
  pdf.text('Age: [Patient Age]', margin + 80, yPosition);
  pdf.text('Gender: [Patient Gender]', margin + 140, yPosition);
  yPosition += 8;
  pdf.text('Medical Record #: [MRN]', margin, yPosition);
  pdf.text('Date of Birth: [DOB]', margin + 80, yPosition);
  yPosition += 20;

  // Diagnostic Results Section
  pdf.setFontSize(14);
  pdf.setFont('helvetica', 'bold');
  pdf.setTextColor(0, 51, 102);
  pdf.text('DIAGNOSTIC RESULTS', margin, yPosition);
  yPosition += 15;

  // Results Table
  const tableData = [
    ['Test Type', 'Tuberculosis Detection (Chest X-Ray)'],
    ['AI Model', 'EfficientNet-B4 with Grad-CAM'],
    ['Prediction', result.diagnosis],
    ['Confidence Score', `${(result.confidence * 100).toFixed(1)}%`],
    ['Raw Probability', `${(result.confidence * 100).toFixed(1)}%`],
    ['Analysis Date', new Date().toLocaleString()],
  ];

  pdf.setFontSize(10);
  pdf.setFont('helvetica', 'normal');
  tableData.forEach(([label, value]) => {
    pdf.setTextColor(100, 100, 100);
    pdf.text(`${label}:`, margin, yPosition);
    pdf.setTextColor(0, 0, 0);
    pdf.text(value, margin + 50, yPosition);
    yPosition += 8;
  });
  yPosition += 10;

  // Clinical Interpretation
  pdf.setFontSize(12);
  pdf.setFont('helvetica', 'bold');
  pdf.setTextColor(0, 51, 102);
  pdf.text('CLINICAL INTERPRETATION', margin, yPosition);
  yPosition += 10;

  pdf.setFontSize(10);
  pdf.setFont('helvetica', 'normal');
  pdf.setTextColor(0, 0, 0);

  let interpretation = '';
 if (result.diagnosis === 'Tuberculosis') {
    interpretation = `The AI analysis indicates a ${result.confidence > 0.8 ? 'high' : result.confidence > 0.6 ? 'moderate' : 'low'} probability of tuberculosis infection. `;
    interpretation += 'The Grad-CAM heatmap highlights suspicious areas that require immediate clinical attention. ';
    interpretation += 'Further diagnostic tests including sputum culture, PCR testing, and clinical evaluation are strongly recommended.';
  } else {
    interpretation = `The AI analysis indicates a ${result.confidence > 0.8 ? 'high' : result.confidence > 0.6 ? 'moderate' : 'low'} confidence that tuberculosis is not present. `;
    interpretation += 'However, clinical correlation is essential. Regular monitoring and follow-up are advised if symptoms persist.';
  }

  const splitInterpretation = pdf.splitTextToSize(interpretation, pageWidth - 2 * margin);
  pdf.text(splitInterpretation, margin, yPosition);
  yPosition += splitInterpretation.length * 5 + 10;

  // Recommendations
  pdf.setFontSize(12);
  pdf.setFont('helvetica', 'bold');
  pdf.setTextColor(0, 51, 102);
  pdf.text('RECOMMENDATIONS', margin, yPosition);
  yPosition += 10;

  pdf.setFontSize(10);
  pdf.setFont('helvetica', 'normal');
  pdf.setTextColor(0, 0, 0);

  const recommendations = [
    '1. Clinical correlation with patient symptoms and history',
    '2. Additional diagnostic tests as indicated',
    '3. Specialist consultation if tuberculosis is suspected',
    '4. Follow-up imaging in 3-6 months if risk factors present',
    '5. Patient education regarding tuberculosis prevention'
  ];

  recommendations.forEach(rec => {
    pdf.text(rec, margin, yPosition);
    yPosition += 6;
  });
  yPosition += 15;

  // Footer
  pdf.setFontSize(8);
  pdf.setTextColor(100, 100, 100);
  pdf.text('This report was generated by MediFlow AI Diagnostic System. AI predictions should be used as a supplement to clinical judgment.', margin, pageHeight - 20);
  pdf.text('Page 1 of 1', pageWidth - margin, pageHeight - 20, { align: 'right' });

  // Add hospital logo placeholder
  pdf.setFillColor(0, 51, 102);
  pdf.rect(margin, margin - 10, 15, 8, 'F');
  pdf.setTextColor(255, 255, 255);
  pdf.setFontSize(6);
  pdf.text('MediFlow', margin + 2, margin - 4);

  return pdf;
};

// ── AnalysisProgressSteps ─────────────────────────────────────────────────────
const AnalysisProgressSteps = ({ currentStep, isAnalyzing }: { currentStep: number; isAnalyzing: boolean }) => {
  const steps = [
    { num: 1, label: '🔬 Analyzing X-Ray', completed: currentStep > 1 },
    { num: 2, label: '🧠 Running AI Models', completed: currentStep > 2 },
    { num: 3, label: '👥 Coordinating Agents', completed: currentStep > 3 },
    { num: 4, label: '📊 Generating Report', completed: currentStep > 4 },
  ];

  const progress = Math.min((currentStep / steps.length) * 100, 100);

  return (
    <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 shadow-sm">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Analysis Progress</h3>
      
      <div className="space-y-4">
        {steps.map((step) => (
          <div key={step.num} className="flex items-center gap-3">
            <div
              className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm transition-all ${
                step.completed
                  ? 'bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-200'
                  : currentStep === step.num
                  ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-200 animate-pulse'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
              }`}
            >
              {step.completed ? '✓' : step.num}
            </div>
            <span className={`text-sm font-medium ${
              step.completed || currentStep === step.num
                ? 'text-gray-900 dark:text-white'
                : 'text-gray-500 dark:text-gray-400'
            }`}>
              {step.label}
            </span>
          </div>
        ))}
      </div>

      {isAnalyzing && (
        <div className="mt-6 space-y-2">
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 overflow-hidden">
            <div
              className="bg-gradient-to-r from-blue-500 to-purple-500 h-full transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-xs text-gray-600 dark:text-gray-400 text-center">
            {progress.toFixed(0)}%
          </p>
        </div>
      )}
    </div>
  );
};

// ── ConfidenceArcGauge ─────────────────────────────────────────────────────
const ConfidenceArcGauge = ({ diagnosis, confidence }: { diagnosis: string; confidence: number }) => {
  const percentage = confidence * 100;
  const isAbnormal = diagnosis === 'Tuberculosis';
  const color = isAbnormal ? '#EF4444' : '#10B981';
  const circumference = 2 * Math.PI * 45; // radius = 45
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative w-48 h-32">
        <svg className="w-full h-full" viewBox="0 0 200 120">
          {/* Background arc */}
          <path
            d="M 20 100 A 90 90 0 0 1 180 100"
            fill="none"
            stroke="#e5e7eb"
            strokeWidth="8"
            strokeLinecap="round"
          />
          {/* Progress arc */}
          <path
            d="M 20 100 A 90 90 0 0 1 180 100"
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={`${(percentage / 100) * 502} 502`}
            className="transition-all duration-1000 ease-out"
          />
          {/* Center text */}
          <text x="100" y="70" textAnchor="middle" className="text-4xl font-bold fill-gray-900 dark:fill-white">
            {percentage.toFixed(0)}%
          </text>
        </svg>
      </div>
      <div className="text-center">
        <p className="text-lg font-bold text-gray-900 dark:text-white">{diagnosis}</p>
        <p className={`text-xs font-medium ${isAbnormal ? 'text-red-600' : 'text-green-600'}`}>
          {isAbnormal ? 'High Risk' : 'Normal'}
        </p>
      </div>
    </div>
  );
};


// ── TranscriptionPanel (was referenced but never defined) ─────────────────────
const TranscriptionPanel = ({ isRecording, transcript, onToggleRecording }: {
  isRecording: boolean;
  transcript: string;
  onToggleRecording: () => void;
}) => (
  <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 shadow-sm h-full">
    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
      <Mic className="w-5 h-5 text-blue-500" />
      Consultation Audio
    </h3>
    <button
      onClick={onToggleRecording}
      className={`w-full flex items-center justify-center gap-2 py-3 rounded-lg font-medium transition-colors ${
        isRecording
          ? 'bg-red-500 hover:bg-red-600 text-white'
          : 'bg-blue-500 hover:bg-blue-600 text-white'
      }`}
    >
      {isRecording ? <><MicOff className="w-4 h-4" /> Stop Recording</> : <><Mic className="w-4 h-4" /> Start Recording</>}
    </button>
    {transcript && (
      <div className="mt-4 p-3 bg-gray-50 dark:bg-gray-900 rounded-lg text-sm text-gray-700 dark:text-gray-300 max-h-64 overflow-y-auto">
        {transcript}
      </div>
    )}
    {!transcript && !isRecording && (
      <p className="mt-4 text-xs text-gray-500 dark:text-gray-400 text-center">
        Record a consultation to generate a transcript via Speechmatics.
      </p>
    )}
  </div>
);

const AudioUploadZone = ({ onAudioSelected }: { onAudioSelected: (file: File) => void }) => {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    const audioFile = files.find(f => f.type.startsWith('audio/'));
    if (audioFile) {
      onAudioSelected(audioFile);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.currentTarget.files;
    if (files && files.length > 0) {
      onAudioSelected(files[0]);
    }
  };

  return (
    <div
      className={`relative border-2 border-dashed rounded-lg p-8 transition-colors ${
        isDragging
          ? 'border-blue-500 bg-blue-50 dark:bg-blue-950'
          : 'border-gray-300 dark:border-gray-600 hover:border-blue-400 hover:bg-gray-50 dark:hover:bg-gray-800'
      }`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept=".mp3,.wav,.m4a,.ogg,.webm"
        onChange={handleFileSelect}
        className="hidden"
      />
      <div className="flex flex-col items-center justify-center gap-3">
        <Mic className="w-12 h-12 text-blue-500" />
        <div className="text-center">
          <p className="text-lg font-semibold text-gray-900 dark:text-white">
            Drop consultation audio here
          </p>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            or{' '}
            <button
              onClick={() => fileInputRef.current?.click()}
              className="text-blue-500 hover:underline font-medium"
            >
              browse
            </button>
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-500 mt-2">
            Supported: MP3, WAV, M4A, OGG, WebM (max 10MB)
          </p>
        </div>
      </div>
    </div>
  );
};

interface SpeakerTurn {
  speaker: string;
  label: string;
  text: string;
}

interface ClinicalExtraction {
  chief_complaint: string;
  medical_history: string[];
  symptoms: string[];
  doctor_recommendation: string;
}

const TranscriptionDisplay = ({ transcript, clinicalExtraction, isLoading }: {
  transcript?: { speakers: SpeakerTurn[]; raw_transcript: string; duration_seconds: number };
  clinicalExtraction?: ClinicalExtraction;
  isLoading: boolean;
}) => {
  if (!transcript && !isLoading) {
    return (
      <div className="text-center py-8">
        <p className="text-gray-500 dark:text-gray-400">No transcription available</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {isLoading && (
        <div className="flex items-center justify-center py-8">
          <Loader className="w-6 h-6 animate-spin text-blue-500 mr-2" />
          <p className="text-sm text-gray-600 dark:text-gray-400">Processing audio transcription...</p>
        </div>
      )}

      {transcript && (
        <div className="space-y-4">
          {/* Transcript with speaker labels */}
          <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-4 space-y-3 max-h-96 overflow-y-auto">
            {transcript.speakers.map((turn, idx) => (
              <div key={idx} className="space-y-1">
                <div className={`flex items-center gap-2 text-xs font-semibold ${
                  turn.label === 'Dokter' 
                    ? 'text-blue-600 dark:text-blue-400' 
                    : 'text-green-600 dark:text-green-400'
                }`}>
                  <div className={`w-2 h-2 rounded-full ${
                    turn.label === 'Dokter' ? 'bg-blue-500' : 'bg-green-500'
                  }`} />
                  {turn.label}
                </div>
                <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                  {turn.text}
                </p>
              </div>
            ))}
          </div>

          <div className="text-xs text-gray-500 dark:text-gray-400">
            Duration: {Math.round(transcript.duration_seconds)}s
          </div>
        </div>
      )}

      {clinicalExtraction && (
        <div className="space-y-3">
          <h4 className="font-semibold text-gray-900 dark:text-white text-sm">
            Clinical Extraction
          </h4>

          {clinicalExtraction.chief_complaint && (
            <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-3">
              <p className="text-xs font-medium text-blue-600 dark:text-blue-400 uppercase">Chief Complaint</p>
              <p className="text-sm text-blue-900 dark:text-blue-100 mt-1">
                {clinicalExtraction.chief_complaint}
              </p>
            </div>
          )}

          {clinicalExtraction.medical_history && clinicalExtraction.medical_history.length > 0 && (
            <div className="bg-purple-50 dark:bg-purple-950 border border-purple-200 dark:border-purple-800 rounded-lg p-3">
              <p className="text-xs font-medium text-purple-600 dark:text-purple-400 uppercase">Medical History</p>
              <ul className="text-sm text-purple-900 dark:text-purple-100 mt-2 space-y-1">
                {clinicalExtraction.medical_history.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="text-purple-500 mt-1">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {clinicalExtraction.symptoms && clinicalExtraction.symptoms.length > 0 && (
            <div className="bg-orange-50 dark:bg-orange-950 border border-orange-200 dark:border-orange-800 rounded-lg p-3">
              <p className="text-xs font-medium text-orange-600 dark:text-orange-400 uppercase">Symptoms Reported</p>
              <ul className="text-sm text-orange-900 dark:text-orange-100 mt-2 space-y-1">
                {clinicalExtraction.symptoms.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="text-orange-500 mt-1">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {clinicalExtraction.doctor_recommendation && (
            <div className="bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded-lg p-3">
              <p className="text-xs font-medium text-green-600 dark:text-green-400 uppercase">Doctor Recommendation</p>
              <p className="text-sm text-green-900 dark:text-green-100 mt-1">
                {clinicalExtraction.doctor_recommendation}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const StatCard = ({ label, value, icon: Icon, color }: { label: string; value: string | number; icon: React.ComponentType<any>; color: string }) => {
  const colorClasses = {
    blue: 'from-blue-500 to-blue-600 dark:from-blue-600 dark:to-blue-700',
    green: 'from-green-500 to-green-600 dark:from-green-600 dark:to-green-700',
    red: 'from-red-500 to-red-600 dark:from-red-600 dark:to-red-700',
    purple: 'from-purple-500 to-purple-600 dark:from-purple-600 dark:to-purple-700',
  };

  return (
    <div className={`bg-gradient-to-br ${colorClasses[color as keyof typeof colorClasses]} rounded-lg p-4 text-white`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium opacity-90">{label}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
        </div>
        <Icon className="w-8 h-8 opacity-50" />
      </div>
    </div>
  );
};

export default function Home() {
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [transcriptionData, setTranscriptionData] = useState<{ speakers: SpeakerTurn[]; raw_transcript: string; duration_seconds: number } | null>(null);
  const [clinicalExtraction, setClinicalExtraction] = useState<ClinicalExtraction | null>(null);
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);

  // Simulate loading steps
  useEffect(() => {
    if (!isAnalyzing) return;

    const steps = [
      { step: 1, delay: 0 },
      { step: 2, delay: 3000 },
      { step: 3, delay: 6000 },
      { step: 4, delay: 9000 },
    ];

    const timers = steps.map(({ step, delay }) =>
      setTimeout(() => setCurrentStep(step), delay)
    );

    return () => timers.forEach(timer => clearTimeout(timer));
  }, [isAnalyzing]);

  const handleFilesSelected = async (files: File[]) => {
    setError(null);
    setUploadedFiles(files);

    const imageFile = files.find(f => f.type.startsWith('image/'));
    const pdfFile = files.find(f => f.type === 'application/pdf');
    const audioFile = files.find(f => f.type.startsWith('audio/'));

    if (!imageFile) {
      setError('Please upload an X-ray image file');
      return;
    }

    setIsAnalyzing(true);
    setCurrentStep(1);

    try {
      const formData = new FormData();
      formData.append('xray_image', imageFile);
      if (pdfFile) formData.append('lab_pdf', pdfFile);
      if (audioFile) formData.append('audio_file', audioFile);

      // Use relative path — proxied via Nginx
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000);

      const response = await fetch('/api/analyze', {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (response.status === 503) {
        throw new Error('Server sedang sibuk. Coba beberapa saat lagi.');
      }

      if (response.status === 504) {
        throw new Error('Analisis memakan waktu terlalu lama. Coba lagi.');
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || `Server error: ${response.status}`
        );
      }

      const data = await response.json();
      setAnalysisResult(data);
      setCurrentStep(5); // Complete
    } catch (err) {
      let errorMessage = 'Terjadi kesalahan saat menganalisis';

      if (err instanceof TypeError) {
        errorMessage = 'Koneksi ke server gagal. Pastikan backend berjalan.';
      } else if (err instanceof Error) {
        if (err.name === 'AbortError') {
          errorMessage = 'Analisis memakan waktu terlalu lama. Coba lagi.';
        } else {
          errorMessage = err.message;
        }
      }

      setError(errorMessage);
      setCurrentStep(0);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleAudioSelected = async (file: File) => {
    setAudioFile(file);
    setIsTranscribing(true);

    // Mock transcription (in real app, send to backend)
    setTimeout(() => {
      const mockTranscript = {
        speakers: [
          {
            speaker: 'S1',
            label: 'Dokter',
            text: 'Selamat pagi, apa keluhan utama Anda hari ini?'
          },
          {
            speaker: 'S2',
            label: 'Pasien',
            text: 'Dokter, saya sudah batuk selama dua minggu. Kadang ada dahak dan demam di malam hari.'
          },
        ],
        raw_transcript: 'Dokter: Selamat pagi... Pasien: Dokter, saya sudah batuk...',
        duration_seconds: 125
      };

      const mockClinical = {
        chief_complaint: 'Batuk selama 2 minggu dengan dahak',
        medical_history: ['Kakak pernah batuk beberapa bulan lalu'],
        symptoms: ['Batuk kronis', 'Demam malam hari'],
        doctor_recommendation: 'Lakukan X-ray dada dan Mantoux test.'
      };

      setTranscriptionData(mockTranscript);
      setClinicalExtraction(mockClinical);
      setIsTranscribing(false);
    }, 2000);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
      {/* Header */}
      <header className="bg-white dark:bg-slate-900 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-40">
        <div className="max-w-full mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                MediFlow AI
              </h1>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                Intelligent Medical Image Analysis with Clinical Agent Reasoning
              </p>
            </div>
            <div className="hidden sm:flex items-center gap-4">
              <div className="text-right">
                <p className="text-sm font-medium text-gray-900 dark:text-white">TBC Detection Suite</p>
                <p className="text-xs text-gray-600 dark:text-gray-400">EfficientNet-B4 + Grad-CAM + Speechmatics</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard label="Analyses Today" value="24" icon={Upload} color="blue" />
          <StatCard label="Accuracy Rate" value="94.2%" icon={TrendingUp} color="green" />
          <StatCard label="Avg. Response" value="2.3s" icon={FileUp} color="purple" />
          <StatCard label="Models Active" value="3" icon={CheckCircle} color="blue" />
        </div>

        {/* Main Dashboard Layout */}
        <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
          {/* Left Sidebar - Progress & Confidence */}
          <div className="xl:col-span-1 space-y-6">
            {/* Analysis Progress */}
            <AnalysisProgressSteps currentStep={currentStep} isAnalyzing={isAnalyzing} />

            {/* Confidence Gauge */}
            {analysisResult && (
              <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 shadow-sm">
                <ConfidenceArcGauge 
                  diagnosis={analysisResult.diagnosis}
                  confidence={analysisResult.confidence}
                />
              </div>
            )}

            {/* Agent Coordination Timeline */}
            {timelineEvents.length > 0 && (
              <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 shadow-sm max-h-96 overflow-hidden flex flex-col">
                <PatientTimeline events={timelineEvents} />
              </div>
            )}
          </div>

          {/* Center Content Area */}
          <div className="xl:col-span-3 space-y-6">
            {/* Error Alert */}
            {error && (
              <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg p-4">
                <p className="text-sm text-red-800 dark:text-red-200 font-medium">
                  ❌ {error}
                </p>
              </div>
            )}

            {/* Upload Section */}
            <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 shadow-sm">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                <FileText className="w-5 h-5 text-blue-500" />
                Medical File Upload
              </h2>
              <FileUploadZone onFilesSelected={handleFilesSelected} />

              {uploadedFiles.length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                  <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                    Uploaded Files ({uploadedFiles.length})
                  </h4>
                  <ul className="space-y-2 max-h-24 overflow-y-auto">
                    {uploadedFiles.map((file, idx) => (
                      <li key={idx} className="flex items-center gap-3 p-2 bg-gray-50 dark:bg-gray-900 rounded text-xs">
                        <FileUp className="w-4 h-4 text-gray-600 dark:text-gray-400 flex-shrink-0" />
                        <span className="text-gray-900 dark:text-white truncate">{file.name}</span>
                        <span className="text-gray-500 dark:text-gray-500 ml-auto whitespace-nowrap">
                          {(file.size / 1024).toFixed(2)} KB
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Audio Upload Section */}
            <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 shadow-sm">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                <Mic className="w-5 h-5 text-blue-500" />
                Consultation Audio
              </h2>
              <AudioUploadZone onAudioSelected={handleAudioSelected} />
            </div>

            {/* X-Ray Analysis Canvas */}
            <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 shadow-sm">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">X-Ray Analysis</h2>
              <XRayCanvas result={analysisResult || undefined} />
            </div>

            {/* Transcription Display */}
            {transcriptionData && (
              <div className="bg-white dark:bg-slate-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6 shadow-sm">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                  <Mic className="w-5 h-5 text-purple-500" />
                  Transcription & Clinical Analysis
                </h2>
                <TranscriptionDisplay
                  transcript={transcriptionData || undefined}
                  clinicalExtraction={clinicalExtraction || undefined}
                  isLoading={isTranscribing}
                />
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
