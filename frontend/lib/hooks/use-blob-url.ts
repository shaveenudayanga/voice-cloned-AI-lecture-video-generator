// SPDX-License-Identifier: Apache-2.0
// Fetches an authenticated blob and returns a revocable object URL.
// No synchronous setState in effect bodies — satisfies react-hooks/set-state-in-effect.
"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api-client";

interface BlobResult {
  key: string;
  url: string;
}

/**
 * Given a blob key, fetches it with the X-API-Key header and returns a
 * revocable object URL suitable for <img>, <audio>, <video>.
 * Returns null while loading, on error, or when blobKey is null.
 */
export function useBlobUrl(blobKey: string | null): string | null {
  const [result, setResult] = useState<BlobResult | null>(null);

  useEffect(() => {
    if (!blobKey) return;

    let active = true;
    let createdUrl: string | null = null;

    // setState happens in the async .then() callback — not synchronously in
    // the effect body, which satisfies react-hooks/set-state-in-effect.
    api.blobs.get(blobKey).then((blob) => {
      if (!active) return;
      createdUrl = URL.createObjectURL(blob);
      setResult({ key: blobKey, url: createdUrl });
    }).catch(() => {
      // Silently ignore — callers show a loading/placeholder state when url is null
    });

    return () => {
      active = false;
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [blobKey]);

  // Return null if the result is for a different key (key changed mid-fetch)
  return result?.key === blobKey ? result.url : null;
}
