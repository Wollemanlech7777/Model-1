"use client";

import { useState } from "react";
import {
  statusGlyph,
  type CapabilityGroup,
  type CapabilityStatus,
} from "@/lib/capability-map";

function ItemRow({
  label,
  status,
}: {
  label: string;
  status: CapabilityStatus;
}) {
  return (
    <li className={`cap-item cap-item--${status}`}>
      <span className="cap-item__mark" aria-hidden="true">
        {statusGlyph(status)}
      </span>
      <span className="cap-item__label">{label}</span>
    </li>
  );
}

export function SystemCapabilities({
  groups,
}: {
  groups: CapabilityGroup[];
}) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <aside className="capabilities" aria-label="System capabilities">
      <button
        type="button"
        className="capabilities__mobile-toggle"
        aria-expanded={mobileOpen}
        onClick={() => setMobileOpen((v) => !v)}
      >
        <span>System capabilities</span>
        <span aria-hidden="true">{mobileOpen ? "–" : "+"}</span>
      </button>

      <div
        className={`capabilities__body${mobileOpen ? " capabilities__body--open" : ""}`}
      >
        <h2 className="capabilities__title">System capabilities</h2>
        <div className="capabilities__groups">
          {groups.map((group) => (
            <section key={group.id} className="cap-group">
              <h3 className="cap-group__title">{group.title}</h3>
              <ul className="cap-group__list">
                {group.items.map((item) => (
                  <ItemRow key={item.id} label={item.label} status={item.status} />
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </aside>
  );
}
