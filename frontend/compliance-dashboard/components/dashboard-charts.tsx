"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ChartContainer, ChartTooltip } from "@/components/ui/chart"
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, ResponsiveContainer } from "recharts"
import { TrendingUp, PieChartIcon, BarChart3 } from "lucide-react"

interface FeatureData {
  id: number
  featureName: string
  description: string
  complianceFlag: "compliant" | "no-compliance" | "needs-review"
  reasoning: string
  regulation: string
  reviewedStatus: "auto" | "pending" | "human-reviewed"
}

interface DashboardChartsProps {
  data: FeatureData[]
}

const COMPLIANCE_COLORS = {
  compliant: "#22c55e", // green-500
  "no-compliance": "#9ca3af", // gray-400
  "needs-review": "#eab308", // yellow-500
}

const REGULATION_COLORS = [
  "#15803d", // green-700 - primary
  "#84cc16", // lime-500 - secondary
  "#0891b2", // cyan-600 - chart-4
  "#f59e0b", // amber-500 - chart-5
  "#dc2626", // red-600 - chart-3
  "#7c3aed", // violet-600
  "#db2777", // pink-600
]

export function DashboardCharts({ data }: DashboardChartsProps) {
  // Prepare compliance status data for pie chart
  const complianceData = [
    {
      name: "Requires Compliance",
      value: data.filter((item) => item.complianceFlag === "compliant").length,
      color: COMPLIANCE_COLORS.compliant,
      percentage: Math.round((data.filter((item) => item.complianceFlag === "compliant").length / data.length) * 100),
    },
    {
      name: "No Compliance",
      value: data.filter((item) => item.complianceFlag === "no-compliance").length,
      color: COMPLIANCE_COLORS["no-compliance"],
      percentage: Math.round(
        (data.filter((item) => item.complianceFlag === "no-compliance").length / data.length) * 100,
      ),
    },
    {
      name: "Needs Review",
      value: data.filter((item) => item.complianceFlag === "needs-review").length,
      color: COMPLIANCE_COLORS["needs-review"],
      percentage: Math.round(
        (data.filter((item) => item.complianceFlag === "needs-review").length / data.length) * 100,
      ),
    },
  ].filter((item) => item.value > 0)

  // Prepare regulation mapping data for bar chart
  const regulationCounts = data.reduce(
    (acc, item) => {
      const regulation =
        item.regulation === "None"
          ? "No Regulation"
          : item.regulation === "Pending Review"
            ? "Pending Review"
            : item.regulation
      acc[regulation] = (acc[regulation] || 0) + 1
      return acc
    },
    {} as Record<string, number>,
  )

  const regulationData = Object.entries(regulationCounts)
    .map(([name, count], index) => ({
      name: name.length > 25 ? `${name.substring(0, 25)}...` : name,
      fullName: name,
      count,
      color: REGULATION_COLORS[index % REGULATION_COLORS.length],
    }))
    .sort((a, b) => b.count - a.count)

  const totalFeatures = data.length
  const complianceRate =
    totalFeatures > 0
      ? Math.round(((complianceData.find((d) => d.name === "Requires Compliance")?.value || 0) / totalFeatures) * 100)
      : 0

  const CustomPieTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload
      return (
        <div className="bg-background border border-border rounded-lg shadow-lg p-3">
          <p className="font-medium">{data.name}</p>
          <p className="text-sm text-muted-foreground">
            {data.value} features ({data.percentage}%)
          </p>
        </div>
      )
    }
    return null
  }

  const CustomBarTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload
      return (
        <div className="bg-background border border-border rounded-lg shadow-lg p-3 max-w-xs">
          <p className="font-medium">{data.fullName}</p>
          <p className="text-sm text-muted-foreground">
            {data.count} feature{data.count !== 1 ? "s" : ""}
          </p>
        </div>
      )
    }
    return null
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Compliance Status Pie Chart */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <div>
            <CardTitle className="flex items-center gap-2">
              <PieChartIcon className="w-5 h-5" />
              Compliance Status Distribution
            </CardTitle>
            <CardDescription>Overview of feature compliance classification</CardDescription>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-primary">{complianceRate}%</div>
            <p className="text-xs text-muted-foreground">Compliance Rate</p>
          </div>
        </CardHeader>
        <CardContent>
          {totalFeatures === 0 ? (
            <div className="flex items-center justify-center h-[300px] text-muted-foreground">
              <div className="text-center">
                <PieChartIcon className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>No data to display</p>
                <p className="text-sm">Upload a CSV file to see compliance distribution</p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <ChartContainer
                config={{
                  compliant: { label: "Requires Compliance", color: COMPLIANCE_COLORS.compliant },
                  "no-compliance": { label: "No Compliance", color: COMPLIANCE_COLORS["no-compliance"] },
                  "needs-review": { label: "Needs Review", color: COMPLIANCE_COLORS["needs-review"] },
                }}
                className="h-[300px]"
              >
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={complianceData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={120}
                      paddingAngle={2}
                      dataKey="value"
                    >
                      {complianceData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <ChartTooltip content={<CustomPieTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              </ChartContainer>

              {/* Legend */}
              <div className="flex flex-wrap justify-center gap-4">
                {complianceData.map((item, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                    <span className="text-sm font-medium">{item.name}</span>
                    <span className="text-sm text-muted-foreground">({item.value})</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Regulation Mapping Bar Chart */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <div>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5" />
              Regulation Mapping
            </CardTitle>
            <CardDescription>Number of features mapped per regulation</CardDescription>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-secondary">{regulationData.length}</div>
            <p className="text-xs text-muted-foreground">Regulations</p>
          </div>
        </CardHeader>
        <CardContent>
          {totalFeatures === 0 ? (
            <div className="flex items-center justify-center h-[300px] text-muted-foreground">
              <div className="text-center">
                <BarChart3 className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>No data to display</p>
                <p className="text-sm">Upload a CSV file to see regulation mapping</p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <ChartContainer
                config={regulationData.reduce((acc, item, index) => {
                  acc[`reg-${index}`] = {
                    label: item.fullName,
                    color: item.color,
                  }
                  return acc
                }, {} as any)}
                className="h-[300px]"
              >
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={regulationData} margin={{ top: 20, right: 30, left: 20, bottom: 60 }}>
                    <XAxis dataKey="name" angle={-45} textAnchor="end" height={80} fontSize={12} interval={0} />
                    <YAxis fontSize={12} />
                    <ChartTooltip content={<CustomBarTooltip />} />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]} fill={(entry: any) => entry.color}>
                      {regulationData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </ChartContainer>

              {/* Top Regulations Summary */}
              <div className="border-t pt-4">
                <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4" />
                  Top Regulations
                </h4>
                <div className="space-y-2">
                  {regulationData.slice(0, 3).map((item, index) => (
                    <div key={index} className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
                        <span className="truncate max-w-[200px]" title={item.fullName}>
                          {item.fullName}
                        </span>
                      </div>
                      <span className="font-medium">{item.count}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Additional Metrics Cards */}
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Compliance Insights</CardTitle>
          <CardDescription>Key metrics and trends from your compliance analysis</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="text-center">
              <div className="text-3xl font-bold text-primary mb-1">{totalFeatures}</div>
              <p className="text-sm text-muted-foreground">Total Features Analyzed</p>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-green-600 mb-1">
                {complianceData.find((d) => d.name === "Requires Compliance")?.value || 0}
              </div>
              <p className="text-sm text-muted-foreground">Compliance Required</p>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-yellow-600 mb-1">
                {complianceData.find((d) => d.name === "Needs Review")?.value || 0}
              </div>
              <p className="text-sm text-muted-foreground">Pending Review</p>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-secondary mb-1">
                {data.filter((item) => item.reviewedStatus === "human-reviewed").length}
              </div>
              <p className="text-sm text-muted-foreground">Human Reviewed</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
