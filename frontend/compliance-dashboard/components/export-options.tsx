"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Download, FileText, CheckCircle } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"

interface FeatureData {
  id: number
  featureName: string
  description: string
  complianceFlag: "compliant" | "no-compliance" | "needs-review"
  reasoning: string
  regulation: string
  reviewedStatus: "auto" | "pending" | "human-reviewed"
  reviewedBy?: string
  reviewedAt?: string
  reviewNotes?: string
}

interface ExportOptionsProps {
  data: FeatureData[]
}

export function ExportOptions({ data }: ExportOptionsProps) {
  const [exportDialogOpen, setExportDialogOpen] = useState(false)
  const [selectedColumns, setSelectedColumns] = useState({
    featureName: true,
    description: true,
    complianceFlag: true,
    reasoning: true,
    regulation: true,
    reviewedStatus: true,
    reviewedBy: false,
    reviewedAt: false,
    reviewNotes: false,
  })
  const [filterBy, setFilterBy] = useState<string>("all")
  const [exportFormat, setExportFormat] = useState<"csv" | "json">("csv")
  const [exportFeedback, setExportFeedback] = useState<string | null>(null)

  const availableColumns = [
    { key: "featureName", label: "Feature Name", required: true },
    { key: "description", label: "Description", required: false },
    { key: "complianceFlag", label: "Compliance Flag", required: true },
    { key: "reasoning", label: "Reasoning", required: false },
    { key: "regulation", label: "Regulation", required: false },
    { key: "reviewedStatus", label: "Review Status", required: false },
    { key: "reviewedBy", label: "Reviewed By", required: false },
    { key: "reviewedAt", label: "Review Date", required: false },
    { key: "reviewNotes", label: "Review Notes", required: false },
  ]

  const handleColumnToggle = (columnKey: string, checked: boolean) => {
    setSelectedColumns((prev) => ({
      ...prev,
      [columnKey]: checked,
    }))
  }

  const getFilteredData = () => {
    switch (filterBy) {
      case "compliant":
        return data.filter((item) => item.complianceFlag === "compliant")
      case "no-compliance":
        return data.filter((item) => item.complianceFlag === "no-compliance")
      case "needs-review":
        return data.filter((item) => item.complianceFlag === "needs-review")
      case "human-reviewed":
        return data.filter((item) => item.reviewedStatus === "human-reviewed")
      default:
        return data
    }
  }

  const escapeCSVField = (field: string | undefined): string => {
    if (!field) return ""
    // Escape quotes and wrap in quotes if contains comma, quote, or newline
    if (field.includes('"') || field.includes(",") || field.includes("\n")) {
      return `"${field.replace(/"/g, '""')}"`
    }
    return field
  }

  const handleExport = () => {
    const filteredData = getFilteredData()

    if (filteredData.length === 0) {
      setExportFeedback("No data matches the selected filters")
      setTimeout(() => setExportFeedback(null), 3000)
      return
    }

    if (exportFormat === "csv") {
      exportCSV(filteredData)
    } else {
      exportJSON(filteredData)
    }

    setExportFeedback(`Successfully exported ${filteredData.length} records`)
    setTimeout(() => setExportFeedback(null), 3000)
    setExportDialogOpen(false)
  }

  const exportCSV = (filteredData: FeatureData[]) => {
    const selectedColumnKeys = Object.entries(selectedColumns)
      .filter(([_, selected]) => selected)
      .map(([key, _]) => key)

    const headers = selectedColumnKeys.map((key) => {
      switch (key) {
        case "featureName":
          return "feature_name"
        case "complianceFlag":
          return "compliance_flag"
        case "reviewedStatus":
          return "reviewed_status"
        case "reviewedBy":
          return "reviewed_by"
        case "reviewedAt":
          return "reviewed_at"
        case "reviewNotes":
          return "review_notes"
        default:
          return key
      }
    })

    const csvContent = [
      headers.join(","),
      ...filteredData.map((item) =>
        selectedColumnKeys
          .map((key) => {
            switch (key) {
              case "featureName":
                return escapeCSVField(item.featureName)
              case "description":
                return escapeCSVField(item.description)
              case "complianceFlag":
                return item.complianceFlag
              case "reasoning":
                return escapeCSVField(item.reasoning)
              case "regulation":
                return escapeCSVField(item.regulation)
              case "reviewedStatus":
                return item.reviewedStatus
              case "reviewedBy":
                return escapeCSVField(item.reviewedBy)
              case "reviewedAt":
                return item.reviewedAt ? new Date(item.reviewedAt).toISOString() : ""
              case "reviewNotes":
                return escapeCSVField(item.reviewNotes)
              default:
                return ""
            }
          })
          .join(","),
      ),
    ].join("\n")

    downloadFile(csvContent, "text/csv", "csv")
  }

  const exportJSON = (filteredData: FeatureData[]) => {
    const selectedColumnKeys = Object.entries(selectedColumns)
      .filter(([_, selected]) => selected)
      .map(([key, _]) => key)

    const jsonData = filteredData.map((item) => {
      const exportItem: any = {}
      selectedColumnKeys.forEach((key) => {
        switch (key) {
          case "featureName":
            exportItem.feature_name = item.featureName
            break
          case "description":
            exportItem.description = item.description
            break
          case "complianceFlag":
            exportItem.compliance_flag = item.complianceFlag
            break
          case "reasoning":
            exportItem.reasoning = item.reasoning
            break
          case "regulation":
            exportItem.regulation = item.regulation
            break
          case "reviewedStatus":
            exportItem.reviewed_status = item.reviewedStatus
            break
          case "reviewedBy":
            exportItem.reviewed_by = item.reviewedBy
            break
          case "reviewedAt":
            exportItem.reviewed_at = item.reviewedAt
            break
          case "reviewNotes":
            exportItem.review_notes = item.reviewNotes
            break
        }
      })
      return exportItem
    })

    const jsonContent = JSON.stringify(jsonData, null, 2)
    downloadFile(jsonContent, "application/json", "json")
  }

  const downloadFile = (content: string, mimeType: string, extension: string) => {
    const blob = new Blob([content], { type: `${mimeType};charset=utf-8;` })
    const link = document.createElement("a")
    const url = URL.createObjectURL(blob)
    link.setAttribute("href", url)

    const timestamp = new Date().toISOString().split("T")[0]
    const filterSuffix = filterBy !== "all" ? `-${filterBy}` : ""
    link.setAttribute("download", `compliance-analysis${filterSuffix}-${timestamp}.${extension}`)

    link.style.visibility = "hidden"
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  const quickExportCSV = () => {
    const headers = ["feature_name", "description", "compliance_flag", "reasoning", "regulation", "reviewed_status"]
    const csvContent = [
      headers.join(","),
      ...data.map((item) =>
        [
          escapeCSVField(item.featureName),
          escapeCSVField(item.description),
          item.complianceFlag,
          escapeCSVField(item.reasoning),
          escapeCSVField(item.regulation),
          item.reviewedStatus,
        ].join(","),
      ),
    ].join("\n")

    downloadFile(csvContent, "text/csv", "csv")

    setExportFeedback(`Successfully exported ${data.length} records`)
    setTimeout(() => setExportFeedback(null), 3000)
  }

  return (
    <div className="space-y-4">
      {exportFeedback && (
        <Alert className="border-green-200 bg-green-50">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800">{exportFeedback}</AlertDescription>
        </Alert>
      )}

      <div className="flex flex-col sm:flex-row gap-3">
        <Button onClick={quickExportCSV} className="flex items-center gap-2" disabled={data.length === 0}>
          <Download className="w-4 h-4" />
          Quick Export CSV
        </Button>

        <Dialog open={exportDialogOpen} onOpenChange={setExportDialogOpen}>
          <DialogTrigger asChild>
            <Button variant="outline" className="flex items-center gap-2 bg-transparent" disabled={data.length === 0}>
              <FileText className="w-4 h-4" />
              Advanced Export
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Export Compliance Data</DialogTitle>
              <DialogDescription>Customize your export with specific columns and filters</DialogDescription>
            </DialogHeader>

            <div className="space-y-6">
              {/* Export Format */}
              <div>
                <Label className="text-sm font-medium">Export Format</Label>
                <Select value={exportFormat} onValueChange={(value: "csv" | "json") => setExportFormat(value)}>
                  <SelectTrigger className="mt-2">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="csv">CSV (Comma Separated Values)</SelectItem>
                    <SelectItem value="json">JSON (JavaScript Object Notation)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Filter Options */}
              <div>
                <Label className="text-sm font-medium">Filter Data</Label>
                <Select value={filterBy} onValueChange={setFilterBy}>
                  <SelectTrigger className="mt-2">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Features ({data.length})</SelectItem>
                    <SelectItem value="compliant">
                      Compliant Only ({data.filter((item) => item.complianceFlag === "compliant").length})
                    </SelectItem>
                    <SelectItem value="no-compliance">
                      No Compliance ({data.filter((item) => item.complianceFlag === "no-compliance").length})
                    </SelectItem>
                    <SelectItem value="needs-review">
                      Needs Review ({data.filter((item) => item.complianceFlag === "needs-review").length})
                    </SelectItem>
                    <SelectItem value="human-reviewed">
                      Human Reviewed ({data.filter((item) => item.reviewedStatus === "human-reviewed").length})
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Column Selection */}
              <div>
                <Label className="text-sm font-medium mb-3 block">Select Columns to Export</Label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {availableColumns.map((column) => (
                    <div key={column.key} className="flex items-center space-x-2">
                      <Checkbox
                        id={column.key}
                        checked={selectedColumns[column.key as keyof typeof selectedColumns]}
                        onCheckedChange={(checked) => handleColumnToggle(column.key, checked as boolean)}
                        disabled={column.required}
                      />
                      <Label htmlFor={column.key} className={`text-sm ${column.required ? "font-medium" : ""}`}>
                        {column.label}
                        {column.required && <span className="text-red-500 ml-1">*</span>}
                      </Label>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground mt-2">* Required columns cannot be deselected</p>
              </div>

              {/* Preview */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Export Preview</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-sm space-y-1">
                    <p>
                      <strong>Format:</strong> {exportFormat.toUpperCase()}
                    </p>
                    <p>
                      <strong>Records:</strong> {getFilteredData().length} of {data.length}
                    </p>
                    <p>
                      <strong>Columns:</strong> {Object.values(selectedColumns).filter(Boolean).length}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setExportDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleExport} disabled={getFilteredData().length === 0}>
                <Download className="w-4 h-4 mr-2" />
                Export {getFilteredData().length} Records
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  )
}
