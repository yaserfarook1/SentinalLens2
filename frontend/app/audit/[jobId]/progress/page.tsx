"use client";

import React, { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { api } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AuditProgress } from "@/lib/types";

export default function ProgressPage() {
  const router = useRouter();
  const params = useParams();
  const jobId = params.jobId as string;

  const [progress, setProgress] = useState<AuditProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [startTime] = useState<number>(Date.now());
  const [elapsedTime, setElapsedTime] = useState<number>(0);

  useEffect(() => {
    let cleanupSse: (() => void) | null = null;

    const startTracking = () => {
      try {
        cleanupSse = api.streamAuditProgress(
          jobId,
          (prog) => {
            setProgress(prog);
            // Auto-redirect on completion
            if (prog.status === "COMPLETED" && prog.job_id === jobId) {
              setTimeout(() => {
                router.push(`/audit/${jobId}/report`);
              }, 1500);
            }
          },
          () => {
            // On complete
          },
          (err) => {
            setError(err);
          }
        );
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "Failed to connect to progress stream";
        setError(errorMessage);
      }
    };

    startTracking();

    const timer = setInterval(() => {
      setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    return () => {
      clearInterval(timer);
      if (cleanupSse) {
        cleanupSse();
      }
    };
  }, [jobId, api, router, startTime]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  };

  const progressPercent = progress?.progress_percentage || 0;
  const currentStepName = progress?.current_step || "Initializing";

  return (
    <ProtectedRoute>
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900">Audit in Progress</h1>
          <p className="text-gray-600 mt-1">
            Analyzing your Sentinel workspace...
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Progress</CardTitle>
          </CardHeader>
          <CardContent>
            {error ? (
              <div className="text-red-600 py-4 text-center">{error}</div>
            ) : (
              <div className="space-y-6">
                {/* Progress Bar */}
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-gray-900">
                      Overall Progress
                    </span>
                    <span className="text-sm font-semibold text-blue-600">
                      {progressPercent}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-3">
                    <div
                      className="bg-blue-600 h-3 rounded-full transition-all duration-300"
                      style={{ width: `${progressPercent}%` }}
                    ></div>
                  </div>
                </div>

                {/* Current Step */}
                <div>
                  <p className="text-sm font-medium text-gray-900 mb-2">
                    Current Step
                  </p>
                  <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                    <p className="font-semibold text-gray-900">
                      {currentStepName || "Initializing..."}
                    </p>
                    <p className="text-sm text-gray-600 mt-1">
                      {progress?.message || "Setting up audit..."}
                    </p>
                    {progress?.total_steps && (
                      <p className="text-xs text-gray-500 mt-2">
                        {progress.message}
                      </p>
                    )}
                  </div>
                </div>

                {/* Elapsed Time */}
                <div className="flex items-center justify-between p-4 bg-blue-50 rounded-lg border border-blue-200">
                  <span className="text-gray-700">Elapsed Time:</span>
                  <span className="font-semibold text-blue-600">
                    {formatTime(elapsedTime)}
                  </span>
                </div>

                {/* Status */}
                <div>
                  <p className="text-sm font-medium text-gray-900 mb-2">
                    Status
                  </p>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-blue-600 animate-pulse"></div>
                    <span className="text-gray-700">
                      {progress?.status === "COMPLETED"
                        ? "Audit Complete"
                        : "Audit Running"}
                    </span>
                  </div>
                </div>

                {/* Info Box */}
                <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                  <p className="text-sm text-gray-600">
                    ℹ️ This process typically takes 1-2 minutes for large
                    workspaces. Do not close this window.
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </ProtectedRoute>
  );
}
