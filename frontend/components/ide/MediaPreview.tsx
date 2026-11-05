"use client";

import { API_URL } from "@/lib/api";
import { formatBytes, type FileViewKind } from "./fileKinds";

type Props = {
  projectId: string;
  path: string;
  kind: Exclude<FileViewKind, "code">;
  size?: number;
  mime?: string;
};

export function MediaPreview({ projectId, path, kind, size, mime }: Props) {
  const rawUrl = `${API_URL}/api/projects/${projectId}/workspace/raw?path=${encodeURIComponent(path)}`;
  const name = path.split(/[\\/]/).pop() || path;

  return (
    <div className="ide-media" dir="ltr">
      <div className="ide-media__meta">
        <strong>{name}</strong>
        <span>
          {kind.toUpperCase()}
          {mime ? ` · ${mime}` : ""}
          {typeof size === "number" ? ` · ${formatBytes(size)}` : ""}
        </span>
      </div>

      {kind === "image" ? (
        <div className="ide-media__stage ide-media__stage--image">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={rawUrl} alt={name} />
        </div>
      ) : null}

      {kind === "pdf" ? (
        <div className="ide-media__stage ide-media__stage--pdf">
          <iframe title={name} src={rawUrl} />
        </div>
      ) : null}

      {kind === "audio" ? (
        <div className="ide-media__stage ide-media__stage--audio">
          <audio controls src={rawUrl} />
        </div>
      ) : null}

      {kind === "video" ? (
        <div className="ide-media__stage ide-media__stage--video">
          <video controls src={rawUrl} />
        </div>
      ) : null}

      {kind === "binary" ? (
        <div className="ide-media__stage ide-media__stage--binary">
          <div className="ide-media__binary-card">
            <h2>ملف ثنائي</h2>
            <p>هذا الملف غير نصي — لا يُفتح في محرّر الشيفرة. يمكنك تنزيله أو معاينة أنواعه المدعومة (صور، PDF، صوت، فيديو).</p>
            <a className="btn btn-primary" href={rawUrl} download={name}>
              تنزيل الملف
            </a>
          </div>
        </div>
      ) : null}
    </div>
  );
}
