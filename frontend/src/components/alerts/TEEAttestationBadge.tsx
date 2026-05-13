import { useEffect, useState } from 'react';
import { ShieldCheck, ShieldAlert } from 'lucide-react';
import { api } from '@/lib/api';
import type { AttestationSnapshot, NarrativeResponse } from '@/lib/api';

/**
 * Confidential-AI attestation badge for the alert investigation memo.
 *
 * When the live LLM gateway is a TEE-attested confidential enclave, this
 * surfaces a verifiable proof block: the gateway's ed25519 signing address,
 * the Intel TDX quote size + SHA-256 fingerprint, and the model slug. A
 * reviewer can independently cross-check these against /attestation.
 *
 * Renders nothing when the narrative was not TEE-attested (e.g. legacy
 * memos or the fallback path).
 */
export function TEEAttestationBadge({ narrative }: { narrative: NarrativeResponse | null | undefined }) {
  const [snap, setSnap] = useState<AttestationSnapshot | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!narrative?.tee_attested) return;
    api
      .get<AttestationSnapshot>('/attestation')
      .then((r) => setSnap(r.data))
      .catch(() => setSnap(null));
  }, [narrative?.tee_attested]);

  if (!narrative) return null;

  if (!narrative.tee_attested) {
    // Quiet line for non-TEE narratives so the absence is visible (vs missing).
    return (
      <div className="mt-2 text-2xs text-slate-600 font-mono inline-flex items-center gap-1">
        <ShieldAlert size={10} /> standard cloud inference
      </div>
    );
  }

  return (
    <div className="mt-3 rounded-lg border border-emerald-700/60 bg-emerald-900/15 p-3 space-y-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-start gap-2 text-left"
      >
        <ShieldCheck size={16} className="text-emerald-400 mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="text-xs text-emerald-200 font-medium">
            Generated in a TEE-attested confidential enclave
          </div>
          <div className="text-2xs text-emerald-100/70 leading-relaxed mt-0.5">
            This investigation memo was produced by <span className="font-mono">openai/gpt-oss-120b</span>{' '}
            running inside an <span className="font-medium">Intel TDX + NVIDIA H200 GPU</span> confidential
            compute environment on NEAR AI Cloud. Each request carries a cryptographic attestation
            proving the model and prompt executed inside a genuine, unmodified TEE — the cloud
            provider itself cannot observe the alert payload.
          </div>
        </div>
        <span className="text-2xs text-emerald-400/70 font-mono shrink-0">
          {open ? 'hide proof' : 'show proof'}
        </span>
      </button>

      {open && snap && (
        <div className="border-t border-emerald-700/40 pt-2 space-y-1 font-mono text-2xs text-emerald-100/80">
          <div className="grid grid-cols-[120px_1fr] gap-y-1 gap-x-3">
            <span className="text-emerald-400/70">gateway</span>
            <span className="break-all">{snap.gateway}</span>

            <span className="text-emerald-400/70">model</span>
            <span>{snap.model}</span>

            <span className="text-emerald-400/70">signing key</span>
            <span className="break-all">
              {snap.signing_address}
              <span className="text-emerald-400/50 ml-2">({snap.signing_algo})</span>
            </span>

            <span className="text-emerald-400/70">Intel quote</span>
            <span>
              {snap.intel_quote_bytes.toLocaleString()} bytes
              <span className="text-emerald-400/50 ml-2">prefix</span>{' '}
              <span className="break-all">{snap.intel_quote_prefix}…</span>
            </span>

            <span className="text-emerald-400/70">SHA-256</span>
            <span className="break-all">{snap.intel_quote_sha256}</span>

            <span className="text-emerald-400/70">attested at</span>
            <span>{snap.fetched_at}</span>
          </div>
          <div className="text-2xs text-emerald-400/60 pt-1">
            Reviewer can independently verify at{' '}
            <code className="text-emerald-300/80">GET /attestation</code> on this host.
          </div>
        </div>
      )}
    </div>
  );
}
