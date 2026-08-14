import Link from "next/link";
import { notFound } from "next/navigation";
import { getDistrict } from "@/lib/api";

export default async function DistrictDetailPage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  let data;
  try {
    data = await getDistrict(Number(code));
  } catch {
    notFound();
  }

  const { geography, company_status_breakdown, msme, monthly_incorporations } = data;
  const totalCompanies = company_status_breakdown.reduce((sum, s) => sum + s.count, 0);

  return (
    <div className="flex flex-col gap-8">
      <div>
        <Link href="/districts" className="text-sm text-zinc-500 hover:underline">
          ← All districts
        </Link>
        <h1 className="mt-1 text-2xl font-semibold">{geography.district_name}</h1>
        <p className="text-sm text-zinc-500">
          {geography.state_name} · LGD district code {geography.lgd_district_code}
        </p>
      </div>

      <section>
        <h2 className="text-lg font-semibold">Company status ({totalCompanies.toLocaleString()} total)</h2>
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {company_status_breakdown.map((s) => (
            <div key={s.status} className="rounded-lg border border-zinc-200 bg-white p-3">
              <div className="text-xs text-zinc-500">{s.status}</div>
              <div className="mt-1 text-xl font-semibold tabular-nums">{s.count.toLocaleString()}</div>
              <div className="text-xs text-zinc-400">{((s.count / totalCompanies) * 100).toFixed(1)}%</div>
            </div>
          ))}
        </div>
      </section>

      {msme && (
        <section>
          <h2 className="text-lg font-semibold">MSME (Udyam, cumulative-to-date)</h2>
          <p className="mt-1 text-sm text-zinc-500">
            manufacturing is derived as total − services (no Udyam manufacturing-specific resource
            exists — see STATUS.md item 15).
          </p>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div className="rounded-lg border border-zinc-200 bg-white p-3">
              <div className="text-xs text-zinc-500">Micro</div>
              <div className="mt-1 text-xl font-semibold tabular-nums">{msme.micro.toLocaleString()}</div>
            </div>
            <div className="rounded-lg border border-zinc-200 bg-white p-3">
              <div className="text-xs text-zinc-500">Small</div>
              <div className="mt-1 text-xl font-semibold tabular-nums">{msme.small.toLocaleString()}</div>
            </div>
            <div className="rounded-lg border border-zinc-200 bg-white p-3">
              <div className="text-xs text-zinc-500">Medium</div>
              <div className="mt-1 text-xl font-semibold tabular-nums">{msme.medium.toLocaleString()}</div>
            </div>
            <div className="rounded-lg border border-zinc-200 bg-white p-3">
              <div className="text-xs text-zinc-500">Manufacturing (derived)</div>
              <div className="mt-1 text-xl font-semibold tabular-nums">{msme.manufacturing.toLocaleString()}</div>
            </div>
            <div className="rounded-lg border border-zinc-200 bg-white p-3">
              <div className="text-xs text-zinc-500">Services</div>
              <div className="mt-1 text-xl font-semibold tabular-nums">{msme.services.toLocaleString()}</div>
            </div>
          </div>
        </section>
      )}

      {monthly_incorporations.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold">Recent monthly incorporations</h2>
          <p className="mt-1 text-sm text-zinc-500">
            Raw new-company counts by month (date-outlier rows excluded, per quality_flags).
          </p>
          <div className="mt-4 overflow-x-auto rounded-lg border border-zinc-200 bg-white">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-200 text-left text-zinc-500">
                  <th className="px-4 py-2 font-medium">Month</th>
                  <th className="px-4 py-2 font-medium text-right">New incorporations</th>
                </tr>
              </thead>
              <tbody>
                {monthly_incorporations.map((m) => (
                  <tr key={m.month} className="border-b border-zinc-100 last:border-0">
                    <td className="px-4 py-2">{m.month.slice(0, 7)}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{m.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
