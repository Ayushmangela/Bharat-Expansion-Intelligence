import Link from "next/link";
import { listDistricts } from "@/lib/api";

export default async function DistrictsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; offset?: string }>;
}) {
  const params = await searchParams;
  const q = params.q ?? "";
  const offset = Number(params.offset ?? 0);
  const limit = 50;

  const data = await listDistricts({ q: q || undefined, limit, offset });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Districts</h1>
        <p className="mt-1 text-sm text-zinc-500">
          {data.total.toLocaleString()} districts nationally · sorted by company count loaded so far
        </p>
      </div>

      <form className="flex gap-2" action="/districts">
        <input
          type="text"
          name="q"
          defaultValue={q}
          placeholder="Search district name..."
          className="w-full max-w-sm rounded-md border border-zinc-300 px-3 py-2 text-sm"
        />
        <button
          type="submit"
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700"
        >
          Search
        </button>
      </form>

      <div className="overflow-x-auto rounded-lg border border-zinc-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-200 text-left text-zinc-500">
              <th className="px-4 py-2 font-medium">District</th>
              <th className="px-4 py-2 font-medium">State</th>
              <th className="px-4 py-2 font-medium text-right">Companies</th>
              <th className="px-4 py-2 font-medium text-right">Active</th>
              <th className="px-4 py-2 font-medium text-right">MSME (micro)</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((d) => (
              <tr key={d.lgd_district_code} className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50">
                <td className="px-4 py-2 font-medium">
                  <Link href={`/districts/${d.lgd_district_code}`} className="hover:underline">
                    {d.district_name}
                  </Link>
                </td>
                <td className="px-4 py-2 text-zinc-600">{d.state_name}</td>
                <td className="px-4 py-2 text-right tabular-nums">{d.company_count?.toLocaleString() ?? 0}</td>
                <td className="px-4 py-2 text-right tabular-nums">{d.active_company_count?.toLocaleString() ?? 0}</td>
                <td className="px-4 py-2 text-right tabular-nums">{d.msme_micro?.toLocaleString() ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex justify-between text-sm text-zinc-500">
        <span>
          Showing {offset + 1}-{Math.min(offset + limit, data.total)} of {data.total}
        </span>
        <div className="flex gap-3">
          {offset > 0 && (
            <Link
              href={`/districts?q=${q}&offset=${Math.max(0, offset - limit)}`}
              className="hover:underline"
            >
              ← Previous
            </Link>
          )}
          {offset + limit < data.total && (
            <Link href={`/districts?q=${q}&offset=${offset + limit}`} className="hover:underline">
              Next →
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
