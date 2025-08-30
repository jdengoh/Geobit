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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ChevronDown,
  ChevronUp,
  Search,
  Filter,
  ArrowUpDown,
} from "lucide-react";

interface FeatureData {
  id: number;
  featureName: string;
  description: string;
  complianceFlag: "compliant" | "no-compliance" | "needs-review";
  reasoning: string;
  regulation: string;
  reviewedStatus: "auto" | "pending" | "human-reviewed";
}

interface ResultsTableProps {
  data: FeatureData[];
  onExport: () => void;
}

export function ResultsTable({ data, onExport }: ResultsTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [searchTerm, setSearchTerm] = useState("");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [sortField, setSortField] = useState<keyof FeatureData>("featureName");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  const toggleRowExpansion = (id: number) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  const getComplianceBadge = (flag: string) => {
    switch (flag) {
      case "compliant":
        return (
          <Badge className="bg-green-100 text-green-800 hover:bg-green-100 border-green-200">
            ✅ Requires Compliance
          </Badge>
        );
      case "no-compliance":
        return (
          <Badge
            variant="secondary"
            className="bg-gray-100 text-gray-800 hover:bg-gray-100 border-gray-200"
          >
            ❌ No Compliance
          </Badge>
        );
      case "needs-review":
        return (
          <Badge className="bg-yellow-100 text-yellow-800 hover:bg-yellow-100 border-yellow-200">
            ❓ Needs Human Review
          </Badge>
        );
      default:
        return <Badge variant="outline">Unknown</Badge>;
    }
  };

  const handleSort = (field: keyof FeatureData) => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  };

  // Filter and sort data
  const filteredAndSortedData = data
    .filter((item) => {
      const matchesSearch =
        item.featureName.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.reasoning.toLowerCase().includes(searchTerm.toLowerCase()) ||
        item.regulation.toLowerCase().includes(searchTerm.toLowerCase());

      const matchesFilter =
        filterStatus === "all" || item.complianceFlag === filterStatus;

      return matchesSearch && matchesFilter;
    })
    .sort((a, b) => {
      const aValue = a[sortField];
      const bValue = b[sortField];

      if (typeof aValue === "string" && typeof bValue === "string") {
        const comparison = aValue.localeCompare(bValue);
        return sortDirection === "asc" ? comparison : -comparison;
      }

      return 0;
    });

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <CardTitle>Compliance Analysis Results</CardTitle>
            <CardDescription>
              Feature compliance status with reasoning and regulatory mapping (
              {filteredAndSortedData.length} of {data.length} features)
            </CardDescription>
          </div>
        </div>

        {/* Search and Filter Controls */}
        <div className="flex flex-col sm:flex-row gap-4 pt-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground w-4 h-4" />
            <Input
              placeholder="Search features, descriptions, reasoning, or regulations..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-muted-foreground" />
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="compliant">Requires Compliance</SelectItem>
                <SelectItem value="no-compliance">No Compliance</SelectItem>
                <SelectItem value="needs-review">Needs Review</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead className="w-[300px]">
                  <Button
                    variant="ghost"
                    onClick={() => handleSort("featureName")}
                    className="h-auto p-0 font-semibold hover:bg-transparent"
                  >
                    Feature Name
                    <ArrowUpDown className="ml-2 h-4 w-4" />
                  </Button>
                </TableHead>
                <TableHead className="w-[120px] text-center">
                  Description
                </TableHead>
                <TableHead className="w-[180px]">
                  <Button
                    variant="ghost"
                    onClick={() => handleSort("complianceFlag")}
                    className="h-auto p-0 font-semibold hover:bg-transparent"
                  >
                    Compliance Flag
                    <ArrowUpDown className="ml-2 h-4 w-4" />
                  </Button>
                </TableHead>
                <TableHead>Reasoning</TableHead>
                <TableHead className="w-[200px]">
                  <Button
                    variant="ghost"
                    onClick={() => handleSort("regulation")}
                    className="h-auto p-0 font-semibold hover:bg-transparent"
                  >
                    Regulation
                    <ArrowUpDown className="ml-2 h-4 w-4" />
                  </Button>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredAndSortedData.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={5}
                    className="text-center py-8 text-muted-foreground"
                  >
                    No features match your search criteria
                  </TableCell>
                </TableRow>
              ) : (
                filteredAndSortedData.map((item) => (
                  <TableRow key={item.id} className="hover:bg-muted/30">
                    <TableCell className="font-medium">
                      <div className="max-w-[280px]">
                        <p className="font-semibold text-sm leading-tight">
                          {item.featureName}
                        </p>
                        {item.reviewedStatus === "human-reviewed" && (
                          <Badge variant="outline" className="mt-1 text-xs">
                            Human Reviewed
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleRowExpansion(item.id)}
                        className="h-8 w-8 p-0"
                      >
                        {expandedRows.has(item.id) ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <ChevronDown className="h-4 w-4" />
                        )}
                      </Button>
                    </TableCell>
                    <TableCell>
                      {getComplianceBadge(item.complianceFlag)}
                    </TableCell>
                    <TableCell>
                      <div className="max-w-[300px]">
                        <p className="text-sm text-muted-foreground line-clamp-2">
                          {item.reasoning}
                        </p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="max-w-[180px]">
                        <p
                          className="text-sm font-medium truncate"
                          title={item.regulation}
                        >
                          {item.regulation}
                        </p>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>

        {/* Expanded Row Details */}
        {filteredAndSortedData.map((item) =>
          expandedRows.has(item.id) ? (
            <div
              key={`expanded-${item.id}`}
              className="mt-4 p-4 bg-muted/30 rounded-lg border"
            >
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div>
                  <h4 className="font-semibold text-sm text-muted-foreground mb-2">
                    Full Description
                  </h4>
                  <p className="text-sm leading-relaxed">{item.description}</p>
                </div>
                <div>
                  <h4 className="font-semibold text-sm text-muted-foreground mb-2">
                    Detailed Reasoning
                  </h4>
                  <p className="text-sm leading-relaxed">{item.reasoning}</p>
                  <div className="mt-3 pt-3 border-t">
                    <p className="text-xs text-muted-foreground">
                      Classification:{" "}
                      {item.reviewedStatus === "auto"
                        ? "Automated"
                        : item.reviewedStatus === "pending"
                        ? "Pending Review"
                        : "Human Reviewed"}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : null
        )}
      </CardContent>
    </Card>
  );
}
