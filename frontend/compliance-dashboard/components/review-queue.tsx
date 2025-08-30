"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Users,
  Clock,
  CheckCircle2,
  XCircle,
  Search,
  AlertTriangle,
  History,
} from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";

/** ---------- Types ---------- */
export interface FeatureData {
  id: number; // local row id
  featureId?: string; // UUID from backend FEEnvelope.feature_id
  featureName: string;
  description: string;
  complianceFlag: "compliant" | "no-compliance" | "needs-review";
  reasoning: string;
  regulation: string;
  reviewedStatus: "auto" | "pending" | "human-reviewed";
  reviewedBy?: string;
  reviewedAt?: string;
  reviewNotes?: string;
  humanDecision?: "approve" | "reject";
  humanReason?: string;
}

interface ReviewQueueProps {
  data: FeatureData[];
  onUpdateFeature: (id: number, updates: Partial<FeatureData>) => void;
}

/** ---------- API helpers ---------- */
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "";

async function createReview(body: {
  feature_id: string;
  action: "approve" | "reject";
  reason: string;
  reviewer?: string;
  session_id?: string;
}) {
  const r = await fetch(`${API_BASE}/reviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const txt = await r.text().catch(() => "");
    throw new Error(`Failed to create review: ${r.status} ${txt}`);
  }
  return r.json();
}

/** ---------- Component ---------- */
export function ReviewQueue({ data, onUpdateFeature }: ReviewQueueProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedItems, setSelectedItems] = useState<Set<number>>(new Set());
  const [reviewDialogOpen, setReviewDialogOpen] = useState(false);
  const [currentReviewItem, setCurrentReviewItem] =
    useState<FeatureData | null>(null);
  const [reviewNotes, setReviewNotes] = useState("");
  const [selectedRegulation, setSelectedRegulation] = useState("");
  const [customReasoning, setCustomReasoning] = useState("");
  const [reviewAction, setReviewAction] = useState<"approve" | "reject">(
    "approve"
  );
  const [activeTab, setActiveTab] = useState("pending");
  const [actionFeedback, setActionFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);
  const [busy, setBusy] = useState(false);

  const pendingItems = data.filter(
    (item) => item.complianceFlag === "needs-review"
  );
  const reviewedItems = data.filter(
    (item) => item.reviewedStatus === "human-reviewed"
  );

  const filteredPendingItems = pendingItems.filter(
    (item) =>
      item.featureName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.reasoning.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredReviewedItems = reviewedItems.filter(
    (item) =>
      item.featureName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.description.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const regulations = [
    "Utah Social Media Regulation Act",
    "California SB976",
    "EU DSA",
    "COPPA",
    "GDPR",
    "None",
  ];

  const handleItemSelection = (id: number, checked: boolean) => {
    const newSelected = new Set(selectedItems);
    if (checked) newSelected.add(id);
    else newSelected.delete(id);
    setSelectedItems(newSelected);
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked)
      setSelectedItems(new Set(filteredPendingItems.map((item) => item.id)));
    else setSelectedItems(new Set());
  };

  const openReviewDialog = (item: FeatureData) => {
    setCurrentReviewItem(item);
    setReviewNotes("");
    setSelectedRegulation(
      item.regulation === "Pending Review" ? "" : item.regulation
    );
    setCustomReasoning(item.reasoning);
    setReviewAction("approve");
    setReviewDialogOpen(true);
  };

  const handleQuickAction = async (
    id: number,
    action: "approve" | "reject"
  ) => {
    const row = data.find((d) => d.id === id);
    if (!row?.featureId) {
      setActionFeedback({
        type: "error",
        message: "Missing feature_id — wait for analysis to finish.",
      });
      return;
    }
    try {
      setBusy(true);
      await createReview({
        feature_id: row.featureId,
        action,
        reason: action === "approve" ? "Quick approve" : "Quick reject",
        reviewer: "Current User",
      });

      const timestamp = new Date().toISOString();
      const updates: Partial<FeatureData> = {
        complianceFlag: action === "approve" ? "compliant" : "no-compliance",
        reviewedStatus: "human-reviewed",
        reviewedBy: "Current User",
        reviewedAt: timestamp,
        reviewNotes:
          action === "approve"
            ? "Approved via quick action"
            : "Rejected via quick action",
        regulation: action === "approve" ? "Manual Review - Compliant" : "None",
        reasoning:
          action === "approve"
            ? row.reasoning || "Manual approval"
            : "Reviewed and determined to have no compliance requirements",
      };
      onUpdateFeature(id, updates);

      setActionFeedback({
        type: "success",
        message: `Feature ${
          action === "approve" ? "approved" : "rejected"
        } successfully`,
      });
    } catch (e: any) {
      setActionFeedback({
        type: "error",
        message: e?.message || "Failed to save review",
      });
    } finally {
      setBusy(false);
      setTimeout(() => setActionFeedback(null), 3000);
    }
  };

  const handleBulkAction = async (action: "approve" | "reject") => {
    if (selectedItems.size === 0) return;
    setBusy(true);
    try {
      const ts = new Date().toISOString();
      const ops = Array.from(selectedItems).map(async (id) => {
        const row = data.find((d) => d.id === id);
        if (!row?.featureId) return;
        await createReview({
          feature_id: row.featureId,
          action,
          reason: `Bulk ${action}`,
          reviewer: "Current User",
        });
        const u: Partial<FeatureData> = {
          complianceFlag: action === "approve" ? "compliant" : "no-compliance",
          reviewedStatus: "human-reviewed",
          reviewedBy: "Current User",
          reviewedAt: ts,
          reviewNotes: `Bulk ${action}`,
          regulation:
            action === "approve" ? "Manual Review - Compliant" : "None",
          reasoning:
            action === "approve"
              ? row.reasoning || "Manual approval (bulk)"
              : "Bulk reviewed - no compliance requirements",
        };
        onUpdateFeature(id, u);
      });
      await Promise.allSettled(ops);
      setActionFeedback({
        type: "success",
        message: `${selectedItems.size} features ${
          action === "approve" ? "approved" : "rejected"
        } successfully`,
      });
      setSelectedItems(new Set());
    } catch (e: any) {
      setActionFeedback({
        type: "error",
        message: e?.message || "Bulk action failed",
      });
    } finally {
      setBusy(false);
      setTimeout(() => setActionFeedback(null), 3000);
    }
  };

  const handleDetailedReview = async () => {
    if (!currentReviewItem) return;
    if (!currentReviewItem.featureId) {
      setActionFeedback({
        type: "error",
        message: "Missing feature_id — wait for analysis.",
      });
      return;
    }
    try {
      setBusy(true);
      await createReview({
        feature_id: currentReviewItem.featureId,
        action: reviewAction,
        reason: reviewNotes || `Detailed ${reviewAction}`,
        reviewer: "Current User",
      });

      const timestamp = new Date().toISOString();
      const updates: Partial<FeatureData> = {
        reviewedStatus: "human-reviewed",
        reviewedBy: "Current User",
        reviewedAt: timestamp,
        reviewNotes,
        regulation: selectedRegulation || "Manual Review",
        reasoning: customReasoning || currentReviewItem.reasoning,
        complianceFlag:
          reviewAction === "approve" ? "compliant" : "no-compliance",
      };
      onUpdateFeature(currentReviewItem.id, updates);
      setReviewDialogOpen(false);

      setActionFeedback({
        type: "success",
        message: "Detailed review completed successfully",
      });
    } catch (e: any) {
      setActionFeedback({
        type: "error",
        message: e?.message || "Failed to save detailed review",
      });
    } finally {
      setBusy(false);
      setTimeout(() => setActionFeedback(null), 3000);
    }
  };

  return (
    <div className="space-y-6">
      {actionFeedback && (
        <Alert
          className={`border-2 ${
            actionFeedback.type === "success"
              ? "border-green-200 bg-green-50"
              : "border-red-200 bg-red-50"
          }`}
        >
          {actionFeedback.type === "success" ? (
            <CheckCircle2 className="h-4 w-4 text-green-600" />
          ) : (
            <XCircle className="h-4 w-4 text-red-600" />
          )}
          <AlertDescription
            className={
              actionFeedback.type === "success"
                ? "text-green-800"
                : "text-red-800"
            }
          >
            {actionFeedback.message}
          </AlertDescription>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="pending" className="flex items-center gap-2">
            <Clock className="w-4 h-4" />
            Pending Review ({pendingItems.length})
          </TabsTrigger>
          <TabsTrigger value="reviewed" className="flex items-center gap-2">
            <History className="w-4 h-4" />
            Reviewed Items ({reviewedItems.length})
          </TabsTrigger>
        </TabsList>

        {/* ---------- Pending Tab ---------- */}
        <TabsContent value="pending" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Users className="w-5 h-5" />
                    Human Review Queue
                  </CardTitle>
                  <CardDescription>
                    Features requiring manual compliance review and approval (
                    {filteredPendingItems.length} of {pendingItems.length}{" "}
                    items)
                  </CardDescription>
                </div>

                {selectedItems.size > 0 && (
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={() => handleBulkAction("approve")}
                      className="bg-green-600 hover:bg-green-700"
                      disabled={busy}
                    >
                      Bulk Approve ({selectedItems.size})
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleBulkAction("reject")}
                      disabled={busy}
                    >
                      Bulk Reject ({selectedItems.size})
                    </Button>
                  </div>
                )}
              </div>

              <div className="flex flex-col sm:flex-row gap-4 pt-4">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
                  <Input
                    placeholder="Search pending reviews..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-10"
                  />
                </div>

                {filteredPendingItems.length > 0 && (
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={
                        selectedItems.size === filteredPendingItems.length
                      }
                      onChange={(e) => handleSelectAll(e.target.checked)}
                      className="rounded border-gray-300"
                    />
                    <span className="text-sm text-muted-foreground">
                      Select All
                    </span>
                  </div>
                )}
              </div>
            </CardHeader>

            <CardContent>
              {filteredPendingItems.length === 0 ? (
                <div className="text-center py-8">
                  {pendingItems.length === 0 ? (
                    <>
                      <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-4" />
                      <p className="text-lg font-medium">
                        No items pending review
                      </p>
                      <p className="text-sm text-muted-foreground">
                        All features have been reviewed
                      </p>
                    </>
                  ) : (
                    <>
                      <Search className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                      <p className="text-lg font-medium">
                        No items match your search
                      </p>
                      <p className="text-sm text-muted-foreground">
                        Try adjusting your search terms
                      </p>
                    </>
                  )}
                </div>
              ) : (
                <div className="space-y-4">
                  {filteredPendingItems.map((item) => (
                    <div
                      key={item.id}
                      className="border rounded-lg p-4 space-y-4 hover:bg-muted/30 transition-colors"
                    >
                      <div className="flex items-start gap-3">
                        <input
                          type="checkbox"
                          checked={selectedItems.has(item.id)}
                          onChange={(e) =>
                            handleItemSelection(item.id, e.target.checked)
                          }
                          className="mt-1 rounded border-gray-300"
                        />
                        <div className="flex-1">
                          <div className="flex items-start justify-between mb-2">
                            <div>
                              <h3 className="font-semibold text-lg">
                                {item.featureName}
                              </h3>
                              <p className="text-sm text-muted-foreground mt-1">
                                {item.description}
                              </p>
                            </div>
                            <Badge className="bg-yellow-100 text-yellow-800 border-yellow-200 ml-4">
                              <AlertTriangle className="w-3 h-3 mr-1" />
                              Needs Review
                            </Badge>
                          </div>

                          <div className="bg-muted/50 p-3 rounded-lg mb-4">
                            <p className="text-sm font-medium text-muted-foreground mb-1">
                              AI Analysis
                            </p>
                            <p className="text-sm">{item.reasoning}</p>
                          </div>

                          <div className="flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              onClick={() =>
                                handleQuickAction(item.id, "approve")
                              }
                              className="bg-green-600 hover:bg-green-700"
                              disabled={busy}
                            >
                              <CheckCircle2 className="w-4 h-4 mr-1" />
                              Quick Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() =>
                                handleQuickAction(item.id, "reject")
                              }
                              disabled={busy}
                            >
                              <XCircle className="w-4 h-4 mr-1" />
                              Quick Reject
                            </Button>

                            <Dialog
                              open={reviewDialogOpen}
                              onOpenChange={setReviewDialogOpen}
                            >
                              <DialogTrigger asChild>
                                <Button
                                  size="sm"
                                  variant="secondary"
                                  onClick={() => openReviewDialog(item)}
                                >
                                  Detailed Review
                                </Button>
                              </DialogTrigger>

                              <DialogContent className="max-w-2xl">
                                <DialogHeader>
                                  <DialogTitle>
                                    Detailed Compliance Review
                                  </DialogTitle>
                                  <DialogDescription>
                                    Provide detailed analysis for:{" "}
                                    {currentReviewItem?.featureName}
                                  </DialogDescription>
                                </DialogHeader>

                                <div className="space-y-4">
                                  <div>
                                    <Label>Decision</Label>
                                    <div className="mt-2 flex gap-2">
                                      <Button
                                        type="button"
                                        variant={
                                          reviewAction === "approve"
                                            ? "default"
                                            : "outline"
                                        }
                                        onClick={() =>
                                          setReviewAction("approve")
                                        }
                                      >
                                        Approve
                                      </Button>
                                      <Button
                                        type="button"
                                        variant={
                                          reviewAction === "reject"
                                            ? "destructive"
                                            : "outline"
                                        }
                                        onClick={() =>
                                          setReviewAction("reject")
                                        }
                                      >
                                        Reject
                                      </Button>
                                    </div>
                                  </div>

                                  <div>
                                    <Label htmlFor="regulation">
                                      Applicable Regulation
                                    </Label>
                                    <Select
                                      value={selectedRegulation}
                                      onValueChange={setSelectedRegulation}
                                    >
                                      <SelectTrigger>
                                        <SelectValue placeholder="Select regulation" />
                                      </SelectTrigger>
                                      <SelectContent>
                                        {regulations.map((reg) => (
                                          <SelectItem key={reg} value={reg}>
                                            {reg}
                                          </SelectItem>
                                        ))}
                                      </SelectContent>
                                    </Select>
                                  </div>

                                  <div>
                                    <Label htmlFor="reasoning">
                                      Updated Reasoning
                                    </Label>
                                    <Textarea
                                      id="reasoning"
                                      value={customReasoning}
                                      onChange={(e) =>
                                        setCustomReasoning(e.target.value)
                                      }
                                      placeholder="Provide detailed reasoning for compliance decision..."
                                      rows={3}
                                    />
                                  </div>

                                  <div>
                                    <Label htmlFor="notes">Review Notes</Label>
                                    <Textarea
                                      id="notes"
                                      value={reviewNotes}
                                      onChange={(e) =>
                                        setReviewNotes(e.target.value)
                                      }
                                      placeholder="Add internal notes about this review..."
                                      rows={2}
                                    />
                                  </div>
                                </div>

                                <DialogFooter>
                                  <Button
                                    variant="outline"
                                    onClick={() => setReviewDialogOpen(false)}
                                  >
                                    Cancel
                                  </Button>
                                  <Button
                                    onClick={handleDetailedReview}
                                    disabled={busy}
                                  >
                                    Complete Review
                                  </Button>
                                </DialogFooter>
                              </DialogContent>
                            </Dialog>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ---------- Reviewed Tab ---------- */}
        <TabsContent value="reviewed" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <History className="w-5 h-5" />
                Review History
              </CardTitle>
              <CardDescription>
                Previously reviewed features with human oversight (
                {filteredReviewedItems.length} of {reviewedItems.length} items)
              </CardDescription>

              <div className="pt-4">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
                  <Input
                    placeholder="Search reviewed items..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-10"
                  />
                </div>
              </div>
            </CardHeader>

            <CardContent>
              {filteredReviewedItems.length === 0 ? (
                <div className="text-center py-8">
                  <History className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-lg font-medium">No reviewed items found</p>
                  <p className="text-sm text-muted-foreground">
                    {reviewedItems.length === 0
                      ? "No items have been reviewed yet"
                      : "No items match your search"}
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {filteredReviewedItems.map((item) => (
                    <div
                      key={item.id}
                      className="border rounded-lg p-4 space-y-3"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <h3 className="font-semibold text-lg">
                            {item.featureName}
                          </h3>
                          <p className="text-sm text-muted-foreground mt-1">
                            {item.description}
                          </p>
                        </div>
                        <div className="ml-4 text-right">
                          <Badge
                            className={
                              item.complianceFlag === "compliant"
                                ? "bg-green-100 text-green-800 border-green-200"
                                : "bg-gray-100 text-gray-800 border-gray-200"
                            }
                          >
                            {item.complianceFlag === "compliant"
                              ? "✅ Approved"
                              : "❌ Rejected"}
                          </Badge>
                          <p className="text-xs text-muted-foreground mt-1">
                            by {item.reviewedBy || "—"} •{" "}
                            {item.reviewedAt
                              ? new Date(item.reviewedAt).toLocaleDateString()
                              : "—"}
                          </p>
                        </div>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t">
                        <div>
                          <p className="text-sm font-medium text-muted-foreground">
                            Final Reasoning
                          </p>
                          <p className="text-sm mt-1">{item.reasoning}</p>
                        </div>
                        <div>
                          <p className="text-sm font-medium text-muted-foreground">
                            Regulation
                          </p>
                          <p className="text-sm mt-1 font-medium">
                            {item.regulation}
                          </p>
                          {item.reviewNotes && (
                            <>
                              <p className="text-sm font-medium text-muted-foreground mt-2">
                                Review Notes
                              </p>
                              <p className="text-sm mt-1 italic">
                                {item.reviewNotes}
                              </p>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
