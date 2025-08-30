"use client";

import type React from "react";
import { useState, useCallback } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Upload,
  FileText,
  BarChart3,
  Users,
  Shield,
  AlertCircle,
  CheckCircle,
} from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ResultsTable } from "@/components/results-table";
import { ReviewQueue } from "@/components/review-queue";
import { DashboardCharts } from "@/components/dashboard-charts";
import { ExportOptions } from "@/components/export-options";
import { ThemeToggle } from "@/components/ui/theme-toggle";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "";

// ---- Types ----
interface FeatureData {
  id: number; // local row id
  featureId?: string; // UUID from backend FEEnvelope.feature_id
  featureName: string;
  description: string;
  complianceFlag: "compliant" | "no-compliance" | "needs-review";
  reasoning: string;
  regulation: string;
  reviewedStatus: "auto" | "pending" | "human-reviewed";
  humanDecision?: "approve" | "reject";
  humanReason?: string;
}

type ReviewDecision =
  | "requires_regulation"
  | "approve_with_conditions"
  | "auto_approve"
  | "insufficient_info";

type UIFlag = "compliant" | "no-compliance" | "needs-review";
type UIStatus = "auto" | "pending" | "human-reviewed";

interface FEUI {
  complianceFlag: UIFlag;
  reviewedStatus: UIStatus;
  regulationTag?: string | null;
}

interface FEEnvelope {
  feature_id: string;
  standardized_name: string;
  standardized_description: string;
  decision: ReviewDecision;
  confidence: number;
  justification: string;
  conditions: string[];
  citations: string[];
  open_questions: any[];
  terminating: boolean;
  ui: FEUI;
}

type StreamEvent =
  | {
      event: "stage" | "status";
      stage?: string;
      message?: string;
      payload?: any;
      terminating?: boolean;
    }
  | { event: "final"; stage?: string; payload: FEEnvelope; terminating: true }
  | { event: "error"; message: string; terminating?: boolean };

// ---- API helpers ----
async function callAnalyzeStream(item: {
  featureName: string;
  description: string;
}): Promise<FEEnvelope> {
  const res = await fetch(`${API_BASE}/analyze/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    body: JSON.stringify({
      standardized_name: item.featureName,
      standardized_description: item.description,
    }),
  });
  if (!res.body) throw new Error("No stream");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  return new Promise<FEEnvelope>((resolve, reject) => {
    function pump(): any {
      reader
        .read()
        .then(({ done, value }) => {
          if (done) return;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";
          for (const line of lines) {
            if (!line.trim()) continue;
            const evt = JSON.parse(line) as StreamEvent;
            if (evt.event === "final" && evt.payload?.ui?.complianceFlag) {
              resolve(evt.payload as FEEnvelope);
            }
          }
          pump();
        })
        .catch(reject);
    }
    pump();
  });
}

// ---- Component ----
export default function ComplianceDashboard() {
  const [data, setData] = useState<FeatureData[]>([]);
  const [activeTab, setActiveTab] = useState("results");

  // CSV flow
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<
    "idle" | "success" | "error"
  >("idle");
  const [uploadMessage, setUploadMessage] = useState("");
  const [isDragOver, setIsDragOver] = useState(false);

  // Quick analyze flow
  const [quickName, setQuickName] = useState("");
  const [quickDesc, setQuickDesc] = useState("");
  const [isAnalyzingOne, setIsAnalyzingOne] = useState(false);
  const [quickError, setQuickError] = useState<string | null>(null);

  // ---- CSV parsing ----
  const parseCSV = (
    csvText: string
  ): { featureName: string; description: string }[] => {
    const lines = csvText.trim().split("\n");
    const headers = lines[0].split(",").map((h) => h.trim().replace(/"/g, ""));

    const nameIndex = headers.findIndex(
      (h) =>
        h.toLowerCase().includes("name") || h.toLowerCase().includes("feature")
    );
    const descIndex = headers.findIndex(
      (h) =>
        h.toLowerCase().includes("desc") ||
        h.toLowerCase().includes("description")
    );

    if (nameIndex === -1 || descIndex === -1) {
      throw new Error(
        "CSV must contain columns for feature name and description"
      );
    }

    return lines
      .slice(1)
      .map((line) => {
        const columns = line
          .split(",")
          .map((col) => col.trim().replace(/"/g, ""));
        return {
          featureName: columns[nameIndex] || "",
          description: columns[descIndex] || "",
        };
      })
      .filter((item) => item.featureName && item.description);
  };

  // ---- CSV handlers ----
  const processFile = async (file: File) => {
    setIsUploading(true);
    setUploadStatus("idle");

    try {
      if (!file.name.toLowerCase().endsWith(".csv")) {
        throw new Error("Please upload a CSV file");
      }

      const text = await file.text();
      const parsedData = parseCSV(text);
      if (parsedData.length === 0)
        throw new Error("No valid data found in CSV file");

      const classifiedData: FeatureData[] = parsedData.map((item, index) => ({
        id: Date.now() + index,
        featureName: item.featureName,
        description: item.description,
        complianceFlag: "needs-review",
        reasoning: "Analyzing...",
        regulation: "Analyzing...",
        reviewedStatus: "pending",
      }));

      setData(classifiedData);
      setUploadStatus("success");
      setUploadMessage(
        `Processing ${classifiedData.length} features. Results will update as analysis completes.`
      );
      setIsUploading(false);

      classifiedData.forEach(async (row) => {
        try {
          const fe = await callAnalyzeStream({
            featureName: row.featureName,
            description: row.description,
          });

          setData((prev) =>
            prev.map((x) =>
              x.id === row.id
                ? {
                    ...x,
                    featureId: fe.feature_id,
                    description: fe.standardized_description ?? x.description,
                    complianceFlag: fe.ui.complianceFlag,
                    reasoning: fe.justification,
                    regulation: fe.ui.regulationTag ?? "None",
                    reviewedStatus: fe.ui.reviewedStatus ?? "auto",
                  }
                : x
            )
          );
        } catch {
          setData((prev) =>
            prev.map((x) =>
              x.id === row.id
                ? {
                    ...x,
                    complianceFlag: "needs-review",
                    reasoning: "Analysis failed - requires manual review",
                    regulation: "Error",
                    reviewedStatus: "pending",
                  }
                : x
            )
          );
        }
      });
    } catch (error) {
      setUploadStatus("error");
      setUploadMessage(
        error instanceof Error ? error.message : "Failed to process file"
      );
      setIsUploading(false);
    }
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);
  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) processFile(files[0]);
  }, []);
  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) processFile(files[0]);
  };

  // ---- Quick analyze (single item) ----
  const handleQuickAnalyze = async () => {
    if (!quickName.trim() || !quickDesc.trim()) {
      setQuickError("Please fill in both fields.");
      return;
    }
    setQuickError(null);

    const id = Date.now();
    // insert optimistic row
    const optimistic: FeatureData = {
      id,
      featureName: quickName.trim(),
      description: quickDesc.trim(),
      complianceFlag: "needs-review",
      reasoning: "Analyzing...",
      regulation: "Analyzing...",
      reviewedStatus: "pending",
    };
    setData((prev) => [optimistic, ...prev]);
    setIsAnalyzingOne(true);

    try {
      const fe = await callAnalyzeStream({
        featureName: optimistic.featureName,
        description: optimistic.description,
      });

      setData((prev) =>
        prev.map((x) =>
          x.id === id
            ? {
                ...x,
                featureId: fe.feature_id,
                description: fe.standardized_description ?? x.description,
                complianceFlag: fe.ui.complianceFlag,
                reasoning: fe.justification,
                regulation: fe.ui.regulationTag ?? "None",
                reviewedStatus: fe.ui.reviewedStatus ?? "auto",
              }
            : x
        )
      );
      setQuickName("");
      setQuickDesc("");
    } catch {
      setData((prev) =>
        prev.map((x) =>
          x.id === id
            ? {
                ...x,
                complianceFlag: "needs-review",
                reasoning: "Analysis failed - requires manual review",
                regulation: "Error",
                reviewedStatus: "pending",
              }
            : x
        )
      );
    } finally {
      setIsAnalyzingOne(false);
    }
  };

  // ---- Export & Clear ----
  const handleExportCSV = () => {
    const headers = [
      "feature_name",
      "description",
      "compliance_flag",
      "reasoning",
      "regulation",
      "reviewed_status",
    ];
    const csvContent = [
      headers.join(","),
      ...data.map((item) =>
        [
          `"${item.featureName}"`,
          `"${item.description}"`,
          item.complianceFlag,
          `"${item.reasoning}"`,
          `"${item.regulation}"`,
          item.reviewedStatus,
        ].join(",")
      ),
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    const url = URL.createObjectURL(blob);
    link.setAttribute("href", url);
    link.setAttribute(
      "download",
      `compliance-analysis-${new Date().toISOString().split("T")[0]}.csv`
    );
    link.style.visibility = "hidden";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleClearTable = () => setData([]);

  // ---- UI helpers ----
  const complianceStats = {
    compliant: data.filter((item) => item.complianceFlag === "compliant")
      .length,
    noCompliance: data.filter((item) => item.complianceFlag === "no-compliance")
      .length,
    needsReview: data.filter(
      (item) =>
        item.complianceFlag === "needs-review" &&
        item.reasoning !== "Analyzing..."
    ).length,
    analyzing: data.filter((item) => item.reasoning === "Analyzing...").length,
  };

  const reviewQueue = data.filter(
    (item) =>
      item.complianceFlag === "needs-review" &&
      item.reasoning !== "Analyzing..."
  );

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card/50 backdrop-blur supports-[backdrop-filter]:bg-card/50">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-10 h-10 bg-primary rounded-lg">
                <Shield className="w-6 h-6 text-primary-foreground" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-foreground">
                  ComplianceGuardAI+
                </h1>
                <p className="text-sm text-muted-foreground">
                  Feature Compliance Analysis Dashboard
                </p>
              </div>
            </div>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Total Features
              </CardTitle>
              <FileText className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{data.length}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Compliant</CardTitle>
              <div className="w-3 h-3 bg-green-500 rounded-full" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">
                {complianceStats.compliant}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                No Compliance
              </CardTitle>
              <div className="w-3 h-3 bg-gray-400 rounded-full" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-gray-600">
                {complianceStats.noCompliance}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                {complianceStats.analyzing > 0 ? "Analyzing" : "Needs Review"}
              </CardTitle>
              <div
                className={`w-3 h-3 rounded-full ${
                  complianceStats.analyzing > 0
                    ? "bg-blue-500 animate-pulse"
                    : "bg-yellow-500"
                }`}
              />
            </CardHeader>
            <CardContent>
              <div
                className={`text-2xl font-bold ${
                  complianceStats.analyzing > 0
                    ? "text-blue-600"
                    : "text-yellow-600"
                }`}
              >
                {complianceStats.analyzing > 0
                  ? complianceStats.analyzing
                  : complianceStats.needsReview}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Export + Clear */}
        <div className="mb-6">
          <Card>
            <CardHeader className="flex items-center justify-between">
              <div>
                <CardTitle className="text-lg">Export Data</CardTitle>
                <CardDescription>
                  Download your compliance analysis results in various formats
                </CardDescription>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={handleClearTable}
                  disabled={data.length === 0}
                >
                  Clear Table
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <ExportOptions data={data} />
            </CardContent>
          </Card>
        </div>

        {/* Main */}
        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          className="space-y-6"
        >
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="results" className="flex items-center gap-2">
              <FileText className="w-4 h-4" /> Results Table
            </TabsTrigger>
            <TabsTrigger value="review" className="flex items-center gap-2">
              <Users className="w-4 h-4" /> Review Queue ({reviewQueue.length})
            </TabsTrigger>
            <TabsTrigger value="dashboard" className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4" /> Dashboard
            </TabsTrigger>
          </TabsList>

          <TabsContent value="results" className="space-y-6">
            {/* Quick analyze (single feature) */}
            <Card>
              <CardHeader>
                <CardTitle>Quick analyze a single feature</CardTitle>
                <CardDescription>
                  Enter a feature name and description to analyze without
                  uploading a CSV.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <Input
                    placeholder="Feature name"
                    value={quickName}
                    onChange={(e) => setQuickName(e.target.value)}
                  />
                  <div className="md:col-span-2">
                    <Textarea
                      placeholder="Feature description"
                      rows={2}
                      value={quickDesc}
                      onChange={(e) => setQuickDesc(e.target.value)}
                    />
                  </div>
                </div>
                {quickError && (
                  <Alert className="border-red-200 bg-red-50">
                    <AlertCircle className="h-4 w-4 text-red-600" />
                    <AlertDescription className="text-red-800">
                      {quickError}
                    </AlertDescription>
                  </Alert>
                )}
                <div className="flex gap-2">
                  <Button
                    onClick={handleQuickAnalyze}
                    disabled={isAnalyzingOne}
                  >
                    {isAnalyzingOne ? "Analyzing…" : "Analyze"}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setQuickName("");
                      setQuickDesc("");
                      setQuickError(null);
                    }}
                  >
                    Reset
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Upload CSV */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Upload className="w-5 h-5" />
                  Upload CSV File
                </CardTitle>
                <CardDescription>
                  Upload a CSV file containing TikTok feature descriptions for
                  compliance analysis
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div
                  className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer ${
                    isDragOver
                      ? "border-primary bg-primary/5"
                      : isUploading
                      ? "border-muted-foreground bg-muted/50"
                      : "border-border hover:border-primary/50"
                  }`}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() =>
                    !isUploading &&
                    document.getElementById("file-input")?.click()
                  }
                >
                  {isUploading ? (
                    <div className="flex flex-col items-center">
                      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mb-4" />
                      <p className="text-lg font-medium">
                        Processing CSV file...
                      </p>
                      <p className="text-sm text-muted-foreground">
                        Analyzing features for compliance
                      </p>
                    </div>
                  ) : (
                    <>
                      <Upload className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                      <p className="text-lg font-medium mb-2">
                        {isDragOver
                          ? "Drop your CSV file here"
                          : "Drag and drop your CSV file here"}
                      </p>
                      <p className="text-sm text-muted-foreground mb-4">
                        or click to browse files (CSV format required)
                      </p>
                      <Button disabled={isUploading}>Choose File</Button>
                    </>
                  )}
                </div>

                <input
                  id="file-input"
                  type="file"
                  accept=".csv"
                  onChange={handleFileInput}
                  className="hidden"
                  disabled={isUploading}
                />

                {uploadStatus === "success" && (
                  <Alert className="border-green-200 bg-green-50">
                    <CheckCircle className="h-4 w-4 text-green-600" />
                    <AlertDescription className="text-green-800">
                      {uploadMessage}
                      {complianceStats.analyzing > 0 && (
                        <div className="mt-2 text-sm">
                          <div className="flex items-center gap-2">
                            <div className="w-2 h-2 bg-blue-600 rounded-full animate-pulse" />
                            {complianceStats.analyzing} features still
                            analyzing...
                          </div>
                        </div>
                      )}
                    </AlertDescription>
                  </Alert>
                )}

                {uploadStatus === "error" && (
                  <Alert className="border-red-200 bg-red-50">
                    <AlertCircle className="h-4 w-4 text-red-600" />
                    <AlertDescription className="text-red-800">
                      {uploadMessage}
                    </AlertDescription>
                  </Alert>
                )}

                <div className="text-sm text-muted-foreground bg-muted/30 p-3 rounded-lg">
                  <p className="font-medium mb-1">CSV Format Requirements:</p>
                  <p>• Must contain columns for feature name and description</p>
                  <p>
                    • Supported column names: "name", "feature", "description",
                    "desc"
                  </p>
                  <p>• Example: feature_name,description</p>
                </div>
              </CardContent>
            </Card>

            {/* Results Table */}
            <ResultsTable data={data} onExport={handleExportCSV} />
          </TabsContent>

          <TabsContent value="review" className="space-y-6">
            <ReviewQueue
              data={data}
              onUpdateFeature={(id, updates) =>
                setData((prev) =>
                  prev.map((row) =>
                    row.id === id ? { ...row, ...updates } : row
                  )
                )
              }
            />
          </TabsContent>

          <TabsContent value="dashboard" className="space-y-6">
            <DashboardCharts data={data} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
