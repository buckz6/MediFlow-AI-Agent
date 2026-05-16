"use client";

import React from 'react';

const XRayViewer = () => {
  return (
    <div className="p-6 bg-slate-900 text-white rounded-xl shadow-2xl border border-slate-700">
      <h2 className="text-2xl font-bold mb-4 bg-gradient-to-r from-blue-400 to-teal-300 bg-clip-text text-transparent">
        Advanced X-Ray Viewer
      </h2>
      <div className="aspect-video bg-black rounded-lg flex items-center justify-center border border-slate-800">
        <p className="text-slate-500 italic">No imaging data loaded</p>
      </div>
      <div className="mt-4 flex gap-3">
        <button className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-md transition-colors font-medium">
          Upload Scan
        </button>
        <button className="px-4 py-2 bg-slate-800 hover:bg-slate-700 rounded-md transition-colors font-medium border border-slate-600">
          Analyze AI
        </button>
      </div>
    </div>
  );
};

export default XRayViewer;
