import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
      <p className="text-5xl font-bold text-slate-700">404</p>
      <h1 className="text-lg font-semibold text-slate-100">Page not found</h1>
      <p className="max-w-sm text-sm muted">
        That page does not exist. The analysis may also have been deleted.
      </p>
      <Link
        href="/"
        className="mt-2 rounded-xl bg-indigo-500 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-400"
      >
        Back to ScamShield
      </Link>
    </div>
  );
}
