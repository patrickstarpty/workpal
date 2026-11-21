"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "@workpal/core/api";
import { dashboardKeys } from "@workpal/core/dashboard";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@workpal/ui/components/ui/chart";
import { Button } from "@workpal/ui/components/ui/button";
import { Skeleton } from "@workpal/ui/components/ui/skeleton";
import { KpiCard } from "../../runtimes/components/shared";
import { NumberFlow } from "@workpal/ui/components/ui/number-flow";
import { useNavigation } from "../../navigation";

const counts = { commits: z.number(), added: z.number(), deleted: z.number(), agentLines: z.number(), humanLines: z.number() };
const schema = z.object({
  totals: z.object({ ...counts, tickets: z.number() }),
  daily: z.array(z.object({ date: z.string(), commits: z.number(), agentLines: z.number(), humanLines: z.number() })),
  rows: z.array(z.object({ ...counts, id: z.string(), identifier: z.string(), title: z.string(), team: z.string() })),
  excluded: z.number(),
});
const config = { agentLines: { label: "Agent", color: "var(--chart-1)" }, humanLines: { label: "Human", color: "var(--chart-2)" } };
const num = (n: number) => n.toLocaleString("en-US");

function Share({ agent, human }: { agent: number; human: number }) {
  const total = agent + human;
  return <div role="img" aria-label={`Agent ${num(agent)}, Human ${num(human)} lines`} className="flex h-2 overflow-hidden rounded-sm bg-muted">
    <span style={{ width: `${total ? agent / total * 100 : 0}%`, background: "var(--chart-1)" }} />
    <span style={{ width: `${total ? human / total * 100 : 0}%`, background: "var(--chart-2)" }} />
  </div>;
}

export function ContributionTab({ wsId, days, projectId, tz }: { wsId: string; days: number; projectId: string | null; tz: string }) {
  const client = useQueryClient(), navigation = useNavigation();
  const [status, setStatus] = useState(""), [importing, setImporting] = useState(false);
  const params = new URLSearchParams({ days: String(days), tz });
  if (projectId) params.set("project_id", projectId);
  const query = useQuery({
    queryKey: [...dashboardKeys.all(wsId), "contribution", days, projectId, tz],
    queryFn: async () => schema.parse(await api.request(`/api/dashboard/contribution?${params}`)),
    enabled: !!wsId, staleTime: 60_000,
  });
  async function importFile(file: File | undefined) {
    if (!file) return;
    setImporting(true); setStatus("");
    try {
      if (file.size > 900_000) throw new Error("Choose a JSON file smaller than 900 KB.");
      const commits: unknown = JSON.parse(await file.text());
      const result = z.object({ count: z.number() }).parse(await api.request("/api/dashboard/contribution", { method: "PUT", body: JSON.stringify({ commits }) }));
      await client.invalidateQueries({ queryKey: [...dashboardKeys.all(wsId), "contribution"] });
      setStatus(`Imported ${num(result.count)} commit records.`);
    } catch (error) { setStatus(error instanceof Error ? error.message : "Could not import commits."); }
    finally { setImporting(false); }
  }
  if (query.isPending) return <div aria-label="Loading contribution" className="space-y-5"><Skeleton className="h-28" /><Skeleton className="h-64" /></div>;
  if (query.isError) return <div role="alert" className="rounded-lg border p-6">Could not load contribution. <Button variant="ghost" onClick={() => void query.refetch()}>Retry</Button></div>;
  const { totals, daily, rows, excluded } = query.data;
  const total = totals.added + totals.deleted, share = total ? totals.agentLines / total * 100 : 0;
  const maxCommits = Math.max(1, ...daily.map(d => d.commits));
  const offset = daily.length ? (new Date(daily[0]!.date + "T12:00:00Z").getUTCDay() + 6) % 7 : 0;
  const issueHref = (id: string) => `${navigation.pathname.replace(/\/usage$/, "")}/issues/${encodeURIComponent(id)}`;
  return <div className="space-y-5">
    <div className="grid grid-cols-1 divide-y rounded-lg border bg-card sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-4">
      <KpiCard label={`Tickets · ${days}D`} value={<NumberFlow value={totals.tickets} />} />
      <KpiCard label={`Commits · ${days}D`} value={<NumberFlow value={totals.commits} />} />
      <KpiCard label="Lines changed" value={<NumberFlow value={total} />} />
      <KpiCard label="Agent contribution" value={total ? <NumberFlow value={share} suffix="%" format={{ minimumFractionDigits: 1, maximumFractionDigits: 1 }} /> : "—"} />
    </div>
    <div className="grid gap-5 lg:grid-cols-2">
      <section className="rounded-lg border bg-card p-4" aria-label="Contribution summary">
        <h4 className="mb-5 text-body font-semibold">Contribution summary</h4>
        <Share agent={totals.agentLines} human={totals.humanLines} />
        <div className="mt-3 flex flex-wrap gap-5 text-caption tabular-nums">
          <span>Agent {num(totals.agentLines)}</span><span>Human {num(totals.humanLines)}</span>
        </div>
        <p className="mt-4 text-caption text-muted-foreground">Added +{num(totals.added)} · Deleted −{num(totals.deleted)}</p>
      </section>
      <section className="min-w-0 rounded-lg border bg-card p-4">
        <h4 className="mb-3 text-body font-semibold">Commit activity</h4>
        <div role="region" aria-label="Commit calendar" tabIndex={0} className="overflow-x-auto pb-2">
          <div className="grid w-max grid-flow-col grid-rows-7 gap-[3px]">
            {Array.from({ length: offset }, (_, i) => <span key={`pad-${i}`} className="size-4" />)}
            {daily.map(d => <button key={d.date} type="button" aria-label={`${d.date}: ${d.commits} commits`} title={`${d.date}: ${d.commits} commits`} onFocus={() => setStatus(`${d.date}: ${d.commits} commits`)} onClick={() => setStatus(`${d.date}: ${d.commits} commits`)} className="size-4 rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring" style={{ background: d.commits ? `color-mix(in oklch, var(--chart-1) ${20 + 80 * d.commits / maxCommits}%, transparent)` : "var(--muted)" }} />)}
          </div>
        </div>
        <p className="mt-2 text-caption text-muted-foreground">{daily[0]?.date} – {daily.at(-1)?.date} · Mon–Sun, top to bottom · Less → More</p>
      </section>
    </div>
    {rows.length ? <>
      <section className="rounded-lg border bg-card p-4">
        <h4 className="mb-3 text-body font-semibold">Daily contribution</h4>
        <ChartContainer config={config} className="h-64 w-full">
          <BarChart data={daily} margin={{ left: 0, right: 0, top: 4, bottom: 0 }}>
            <CartesianGrid vertical={false} /><XAxis dataKey="date" tickFormatter={v => String(v).slice(5)} tickLine={false} axisLine={false} tickMargin={8} interval="preserveStartEnd" />
            <YAxis tickLine={false} axisLine={false} tickMargin={8} allowDecimals={false} width={55} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <Bar dataKey="agentLines" stackId="lines" fill="var(--color-agentLines)" />
            <Bar dataKey="humanLines" stackId="lines" fill="var(--color-humanLines)" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ChartContainer>
      </section>
      <section className="min-w-0 rounded-lg border bg-card p-4">
        <h4 className="mb-3 text-body font-semibold">Contribution by ticket</h4>
        <div role="region" aria-label="Ticket contribution" tabIndex={0} className="overflow-x-auto">
          <table className="w-full text-left text-caption"><thead className="border-b text-muted-foreground"><tr>{["Ticket", "Team / squad", "Total", "Agent", "Human", "Contribution", "Commits"].map(label => <th key={label} className="whitespace-nowrap px-3 py-2 font-medium">{label}</th>)}</tr></thead>
            <tbody>{rows.map(row => <tr key={row.id} className="border-b last:border-0 hover:bg-muted/40">
              <td className="max-w-72 px-3 py-2"><button type="button" className="text-left hover:underline focus-visible:outline-ring" onClick={() => navigation.push(issueHref(row.id))}><span className="font-medium">{row.identifier}</span><span className="block truncate text-muted-foreground">{row.title}</span></button></td>
              <td className="whitespace-nowrap px-3 py-2">{row.team}</td>
              <td className="px-3 py-2 tabular-nums">{num(row.added + row.deleted)}<small className="block whitespace-nowrap text-muted-foreground">+{num(row.added)} / −{num(row.deleted)}</small></td>
              <td className="px-3 py-2 tabular-nums">{num(row.agentLines)}</td><td className="px-3 py-2 tabular-nums">{num(row.humanLines)}</td>
              <td className="min-w-28 px-3 py-2"><Share agent={row.agentLines} human={row.humanLines} /></td><td className="px-3 py-2 tabular-nums">{num(row.commits)}</td>
            </tr>)}</tbody>
          </table>
        </div>
      </section>
    </> : <div className="rounded-lg border p-8 text-center"><h4 className="text-body font-medium">No linked tickets</h4><p className="mt-2 text-caption text-muted-foreground">Change the period or import commit data.</p></div>}
    <p className="text-caption text-muted-foreground">Total lines = additions + deletions. Agent + Human = Total. Shared commits appear under each linked ticket and only once in the summary. Team follows the assigned squad or nearest parent assigned to a squad. {num(excluded)} commits without a ticket in scope are excluded.</p>
    <details className="rounded-lg border bg-card p-4 text-caption">
      <summary className="cursor-pointer font-medium">Attribution rules &amp; import</summary>
      <div className="mt-3 space-y-3 text-muted-foreground">
        <p>Reference a ticket number in each commit message. Add the Workpal trailer when Workpal contributes. Explicit agentLines and humanLines take priority; remaining changes follow the commit classification.</p>
        <pre className="overflow-x-auto rounded-md bg-muted p-3">{"TAP-027 Improve search feedback\n\nCo-authored-by: Workpal <workpal@users.noreply.github.com>"}</pre>
        <p>Workpal-tagged changes count toward Agent; other changes count toward Human. Line counts describe attribution, not productivity or code quality.</p>
        <p>Import a JSON array to replace this workspace’s saved commit data. Required fields: repository, sha, message, at (ISO date), additions, deletions. Optional: agentLines and humanLines.</p>
        <label className="block">Replace commit data (JSON)<input aria-label="Import commit data" type="file" accept=".json,application/json" disabled={importing} className="mt-2 block max-w-full" onChange={event => { void importFile(event.target.files?.[0]); event.target.value = ""; }} /></label>
      </div>
    </details>
    <p role="status" className="text-caption text-muted-foreground">{status}</p>
  </div>;
}
