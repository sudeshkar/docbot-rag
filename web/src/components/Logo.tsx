import Link from "next/link";

export function LogoMark({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="#2a78d6" />
      <path
        d="M8 8.5h16a2.5 2.5 0 0 1 2.5 2.5v8a2.5 2.5 0 0 1-2.5 2.5h-9.2l-4.6 3.7a.6.6 0 0 1-1-.47V21.5H8A2.5 2.5 0 0 1 5.5 19v-8A2.5 2.5 0 0 1 8 8.5z"
        fill="#fff"
      />
      <rect x="9.5" y="12" width="10" height="2" rx="1" fill="#2a78d6" />
      <rect x="9.5" y="16" width="6.5" height="2" rx="1" fill="#2a78d6" />
      <circle cx="21.5" cy="17" r="2" fill="#eb6834" />
    </svg>
  );
}

export default function Logo({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="inline-flex items-center gap-2 text-lg font-semibold">
      <LogoMark />
      DocBot
    </Link>
  );
}
