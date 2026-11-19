import React, { useState } from 'react';
import { Satellite } from 'lucide-react';
import { api } from '../api';
import { ErrorBox, Panel, RequireAuth } from '../components/ui';
import { fmtBytes } from '../utils';

export default function ImageIntake() {
  const [image, setImage] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    if (!image) return;
    setBusy(true); setError(null); setResult(null);
    const form = new FormData();
    form.append('file', image);
    try { setResult(await api('/api/ml/analyze-image', { method: 'POST', form })); } catch (err) { setError(err); } finally { setBusy(false); }
  }

  return (
    <Panel title="Satellite image intake (validation only)" sub="This page checks that a file is a PNG, JPEG or TIFF within the size limit. It does not analyse or classify images.">
      <RequireAuth what="upload an image">
        <form onSubmit={submit} className="ingest">
          <Satellite size={34} aria-hidden="true" />
          <label htmlFor="img-file"><b>Select an image</b></label>
          <p>PNG, JPEG or TIFF, up to 20 MB. No classifier is installed: the image is checked and discarded, and no storm type, intensity or location is inferred.</p>
          <input id="img-file" type="file" accept="image/png,image/jpeg,image/tiff" onChange={(e) => { setImage(e.target.files?.[0] || null); setResult(null); setError(null); }} />
          {image && <small>{image.name} ({fmtBytes(image.size)})</small>}
          <button type="submit" disabled={!image || busy}>{busy ? 'Checking…' : 'Validate image file'}</button>
          {error && <ErrorBox error={error} />}
          {result && (
            <div className="result" role="status">
              <b>File accepted — NOT analysed</b>
              <dl className="facts">
                <div><dt>Detected type</dt><dd>{result.detected_type}</dd></div>
                <div><dt>Size</dt><dd>{fmtBytes(result.bytes_received)}</dd></div>
                <div><dt>Analysed</dt><dd>{result.analyzed ? 'yes' : 'no'}</dd></div>
                <div><dt>Stored on server</dt><dd>{result.stored ? 'yes' : 'no'}</dd></div>
                <div><dt>SHA-256</dt><dd><code>{result.sha256.slice(0, 16)}…</code></dd></div>
              </dl>
              <p className="muted">{result.message}</p>
            </div>
          )}
        </form>
      </RequireAuth>
    </Panel>
  );
}
