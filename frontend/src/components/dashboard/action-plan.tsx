"use client";

import { Check, Info, Trash2, TrendingUp, AlertCircle, Clock } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { ActionItem } from "@/lib/types";
import { useActiveBusiness } from "@/components/providers/workspace-provider";
import { cn } from "@/lib/utils";

interface Props {
  action: ActionItem;
  onUpdate: () => void;
}

export function ActionItemCard({ action, onUpdate }: Props) {
  const business = useActiveBusiness();
  const [updating, setUpdating] = useState(false);

  const updateStatus = async (status: ActionItem["status"]) => {
    setUpdating(true);
    try {
      await api.fetch(`/${business.id}/actions/${action.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      toast.success(status === "completed" ? "Action completed" : "Action dismissed");
      onUpdate();
    } catch {
      toast.error("Could not update action");
    } finally {
      setUpdating(false);
    }
  };

  const Icon = action.type === "overdue" ? AlertCircle : action.type === "upcoming" ? Clock : action.type === "anomaly" ? TrendingUp : Info;

  const copyReminder = () => {
    if (action.type !== "overdue") return;
    const text = `Hi, this is a friendly reminder regarding our recent invoice. ${action.reason}. Please arrange for payment at your earliest convenience. Thank you!`;
    navigator.clipboard.writeText(text);
    toast.success("Reminder copied to clipboard!");
  };

  return (
    <div className="flex gap-4 rounded-xl border bg-card p-4 shadow-sm">
      <div className={cn(
        "flex h-10 w-10 shrink-0 items-center justify-center rounded-full",
        action.priority === "high" ? "bg-red-100 text-red-600" : action.priority === "medium" ? "bg-amber-100 text-amber-600" : "bg-blue-100 text-blue-600"
      )}>
        <Icon className="h-5 w-5" />
      </div>
      <div className="flex-1 space-y-2">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h4 className="font-semibold text-foreground">{action.title}</h4>
            <p className="text-sm text-muted-foreground">{action.description}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {action.type === "overdue" && (
              <Button variant="outline" size="sm" onClick={copyReminder}>
                Draft Reminder
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={() => updateStatus("completed")} disabled={updating}>
              <Check className="h-4 w-4 mr-1" /> Complete
            </Button>
            <Button variant="ghost" size="icon" onClick={() => updateStatus("dismissed")} disabled={updating}>
              <Trash2 className="h-4 w-4 text-muted-foreground" />
              <span className="sr-only">Dismiss</span>
            </Button>
          </div>
        </div>
        
        <div className="rounded-lg bg-muted/50 p-3 text-sm">
          <p className="font-medium">Why we&apos;re suggesting this:</p>
          <p className="text-muted-foreground mt-1">{action.reason}</p>
          {action.suggestedDeadline && (
            <p className="mt-2 text-xs font-medium text-amber-600">
              Suggested deadline: {new Date(action.suggestedDeadline).toLocaleDateString()}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export function ActionPlanWidget({ actions, onRefresh }: { actions: ActionItem[], onRefresh: () => void }) {
  const business = useActiveBusiness();
  const [generating, setGenerating] = useState(false);

  const generatePlan = async () => {
    setGenerating(true);
    try {
      await api.fetch(`/${business.id}/actions/generate`, { method: "POST" });
      toast.success("Action plan generated");
      onRefresh();
    } catch {
      toast.error("Failed to generate action plan");
    } finally {
      setGenerating(false);
    }
  };

  const pendingActions = actions.filter((a) => a.status === "pending");

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle>Weekly Action Plan</CardTitle>
          <CardDescription>AI-generated tasks based on your business records</CardDescription>
        </div>
        <Button variant="outline" onClick={generatePlan} disabled={generating}>
          {generating ? "Generating..." : pendingActions.length === 0 ? "Generate plan" : "Regenerate"}
        </Button>
      </CardHeader>
      <CardContent>
        {pendingActions.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">
            No pending actions for this week.
          </div>
        ) : (
          <div className="space-y-4">
            {pendingActions.map((action) => (
              <ActionItemCard key={action.id} action={action} onUpdate={onRefresh} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
