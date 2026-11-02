"""Staff-only AKGEC map and complaint intelligence, backed by the live ticket database."""
from collections import defaultdict
from datetime import datetime, timedelta
from html import escape
import statistics
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

import sla
from database import connect
from schemas import Category, Priority, Status, User
from shared import require
from ticket_service import staff_list_tickets
from ui import h, md, page_head, tag

CENTER = (28.6756736, 77.5020041)
CONFIDENCE = {
    "unverified": "Unverified", "name_verified": "Name verified",
    "user_provided_needs_footprint_confirmation": "Coordinates supplied by user · footprint unconfirmed",
    "coordinates_verified_against_map": "Coordinates checked against map · not field verified",
    "official_geotagged_point": "Official GPS photo point · library gate, 2021; not building centroid",
    "field_verified": "Field verified",
}


def _open_ticket(ticket_id):
    st.session_state["sel"] = ticket_id
    st.session_state["page"] = "Staff workspace"


def _data():
    with connect() as conn:
        locations = [dict(r) for r in conn.execute("SELECT * FROM campus_locations ORDER BY display_name")]
        departments = [r[0] for r in conn.execute("SELECT display_name FROM academic_departments ORDER BY display_name")]
    return locations, departments


def _location_tree_ids(locations, root_id):
    """Return a catalog item and all children, so parent-block totals include room-level tickets."""
    ids = {root_id}
    changed = True
    while changed:
        changed = False
        for loc in locations:
            if loc["location_id"] not in ids and loc["parent_location_id"] in ids:
                ids.add(loc["location_id"])
                changed = True
    return ids


def _tickets_for_location(loc, locations, tickets):
    tree_ids = _location_tree_ids(locations, loc["location_id"])
    return [t for t in tickets if t.location_id in tree_ids or
            (not t.location_id and t.location and t.location.casefold().strip() == loc["display_name"].casefold().strip())]


def _render_map(locations, tickets, layer, selected_location, catalog=None, show_ticket_counts=True):
    catalog = catalog or locations
    m = folium.Map(location=CENTER, zoom_start=16, control_scale=True, tiles="OpenStreetMap")
    for loc in locations:
        if loc["latitude"] is None or loc["longitude"] is None:
            continue
        here = [loc["latitude"], loc["longitude"]]
        linked = _tickets_for_location(loc, catalog, tickets) if show_ticket_counts else []
        active = [t for t in linked if t.status in (Status.OPEN, Status.IN_PROGRESS, Status.REOPENED)]
        resolved = [t for t in linked if t.status == Status.RESOLVED]
        high = [t for t in active if t.priority == Priority.HIGH]
        overdue = [t for t in active if sla.is_overdue(t)]
        if layer == "Campus Locations":
            color = {"campus": "cadetblue", "building": "darkgreen", "facility": "orange"}.get(loc["location_type"], "blue")
            radius = 7
        else:
            color = "red" if high or overdue else "orange" if active else "green" if resolved else "blue"
            radius = min(20, 7 + round((len(linked) ** .5) * 3))
        info = (f"<b>{escape(loc['display_name'])}</b><br>Type: {escape(loc['location_type'])}<br>"
                f"Confidence: {escape(CONFIDENCE.get(loc['verification_status'], loc['verification_status']))}<br>"
                f"Source: {escape(loc['coordinate_source'] or '—')}<br>")
        if show_ticket_counts:
            info += (f"Reports: {len(linked)} · Open: {len(active)} · Resolved: {len(resolved)}<br>"
                     f"High priority: {len(high)} · Overdue: {len(overdue)}<br>")
        if loc["google_maps_url"]:
            info += f'<a href="{escape(loc["google_maps_url"], quote=True)}" target="_blank" rel="noopener">Open in Google Maps</a>'
        if loc.get("source_url"):
            info += f'<br><a href="{escape(loc["source_url"], quote=True)}" target="_blank" rel="noopener">Open official AKGEC source</a>'
        folium.CircleMarker(here, radius=radius, color=color, fill=True, fill_opacity=.8,
                            tooltip=loc["display_name"], popup=folium.Popup(info, max_width=330)).add_to(m)
    if selected_location:
        by_id = {l["location_id"]: l for l in catalog}
        selected = by_id.get(selected_location)
        visited = set()
        while selected and selected["location_id"] not in visited:
            visited.add(selected["location_id"])
            if selected["latitude"] is not None:
                m.location = [selected["latitude"], selected["longitude"]]
                m.zoom_start = 18
                break
            selected = by_id.get(selected["parent_location_id"])
    return m


def render():
    staff = require("staff", "Campus Intelligence", "Staff sign in to view complaint patterns and campus locations.")
    actor = User(**staff)
    locations, departments = _data()
    all_tickets = staff_list_tickets(actor=actor)
    md('<section class="campus-intro"><div><div class="eyebrow">AKGEC · OPERATIONS VIEW</div>'
       '<div class="pgh">Campus Intelligence</div>'
       '<p>See reported issues across campus, find buildings and facilities, and spot locations that may need attention. Map pins represent catalogued points, not surveyed building footprints.</p>'
       '</div><span class="campus-badge">● Live ticket data</span></section>')

    layers = ["Campus Locations", "Complaint Intelligence", "Recurring Issues"]
    layer = st.radio("Map view", layers, horizontal=True, key="campus_layer")
    with st.expander("Filters · adjust the locations and reports shown", expanded=False):
        a, b = st.columns(2)
        location_types = a.multiselect("Location types", sorted({x["location_type"] for x in locations}), default=sorted({x["location_type"] for x in locations}))
        search = b.text_input("Search locations", placeholder="Building or facility")
        c, d, e = st.columns(3)
        categories = c.multiselect("Categories", [x.value for x in Category], default=[x.value for x in Category])
        priorities = d.multiselect("Priorities", [x.value for x in Priority], default=[x.value for x in Priority])
        statuses = e.multiselect("Statuses", [x.value for x in Status], default=[x.value for x in Status if x != Status.WITHDRAWN])
        f, g = st.columns(2)
        department_filter = f.multiselect("Service teams", sorted({t.department for t in all_tickets}))
        date_range = g.date_input("Created between", value=(datetime.now().date() - timedelta(days=365), datetime.now().date()))
        include_samples = st.checkbox("Include clearly labelled sample tickets", value=False,
                                      help="Sample records are fictional demo examples. They are excluded from map counts unless you turn this on.")

    visible_locations = [l for l in locations if l["location_type"] in location_types and search.casefold() in l["display_name"].casefold()]
    filtered = []
    for t in all_tickets:
        if t.is_sample and not include_samples:
            continue
        created = t.created_at.date()
        if t.category.value not in categories or t.priority.value not in priorities or t.status.value not in statuses:
            continue
        if department_filter and t.department not in department_filter:
            continue
        if len(date_range) == 2 and not (date_range[0] <= created <= date_range[1]):
            continue
        if t.status == Status.WITHDRAWN:
            continue  # retained in the system but not counted as a campus incident
        filtered.append(t)
    if not filtered and any(t.is_sample for t in all_tickets) and not include_samples:
        st.info("No real reports match these filters. Turn on ‘Include clearly labelled sample tickets’ to preview the demo dataset.")

    active = [t for t in filtered if t.status in (Status.OPEN, Status.IN_PROGRESS, Status.REOPENED)]
    high = [t for t in active if t.priority == Priority.HIGH]
    overdue = [t for t in active if sla.is_overdue(t)]
    resolved = [t for t in filtered if t.status == Status.RESOLVED]
    st.markdown("#### Current picture")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Reports in range", len(filtered)); k2.metric("Open", len(active)); k3.metric("High priority", len(high)); k4.metric("Overdue", len(overdue))

    names = ["All mapped locations", *[l["display_name"] for l in visible_locations]]
    selected_name = st.selectbox("Focus location", names)
    selected = next((l for l in visible_locations if l["display_name"] == selected_name), None) if selected_name != names[0] else None
    location_activity = []
    for loc in visible_locations:
        linked = _tickets_for_location(loc, locations, filtered)
        open_count = sum(t.status in (Status.OPEN, Status.IN_PROGRESS, Status.REOPENED) for t in linked)
        if linked:
            location_activity.append((loc, len(linked), open_count))
    location_activity.sort(key=lambda row: (row[2], row[1], row[0]["display_name"]), reverse=True)
    map_col, insight_col = st.columns([2.15, 1], gap="large")
    with map_col:
        with st.container(key="campus_map_frame"):
            st_folium(_render_map(visible_locations, filtered, layer, selected["location_id"] if selected else None, catalog=locations),
                      height=500, use_container_width=True, returned_objects=[])
    with insight_col.container(key="campus_insight_panel"):
        st.markdown("#### Location pulse")
        st.caption("Busiest locations in the current filter")
        if location_activity:
            for rank, (loc, count, open_count) in enumerate(location_activity[:5], start=1):
                safe_name = h(loc["display_name"])
                st.markdown(
                    f'<div class="campus-place"><span class="campus-rank">{rank:02}</span>'
                    f'<span class="campus-place-name">{safe_name}</span>'
                    f'<span class="campus-place-count">{count}<small> reports</small></span>'
                    f'<div class="campus-place-meta">{open_count} open · {h(loc["location_type"].title())}</div></div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown('<div class="campus-empty">No location reports match these filters yet.</div>', unsafe_allow_html=True)
        st.markdown('<div class="campus-legend"><span><i class="hot"></i>Urgent / overdue</span><span><i class="open"></i>Open</span><span><i class="done"></i>Resolved</span></div>', unsafe_allow_html=True)
        st.caption("Hotspot totals include child facilities and rooms, so a building roll-up may include nested locations.")
    st.caption("Map colours: red = high-priority or overdue open reports; orange = other open reports; green = resolved reports; blue/green/orange in Campus Locations denote catalogued places by type. Marker size grows with matching report count. OpenStreetMap base tiles; Google Maps source links are listed for locations.")

    if layer == "Recurring Issues":
        grouped = defaultdict(list)
        for t in filtered:
            loc_key = t.location_id or (t.location or "Unspecified location").casefold().strip()
            grouped[(loc_key, t.category.value)].append(t)
        rows = []
        by_id = {l["location_id"]: l["display_name"] for l in locations}
        by_name = {l["display_name"].casefold().strip(): l["display_name"] for l in locations}
        for (key, category), items in grouped.items():
            if len(items) < 3:  # explicit conservative threshold
                continue
            items.sort(key=lambda x: x.created_at)
            related = [t for t in items if t.duplicate_of]
            rows.append({"Location": by_id.get(key, by_name.get(key, items[0].location or "Unspecified location")),
                         "Category": category, "Reports": len(items),
                         "Open": sum(t.status in (Status.OPEN, Status.IN_PROGRESS, Status.REOPENED) for t in items),
                         "Date range": f"{items[0].created_at.date()} – {items[-1].created_at.date()}",
                         "Ticket IDs": ", ".join(t.ticket_id for t in items),
                         "Linked duplicates": ", ".join(t.ticket_id for t in related) or "None linked"})
        st.subheader("Repeated reports")
        st.caption("A location and category are listed only when at least 3 non-withdrawn reports match the active filters. Possible duplicates are shown only when staff linked them in the ticket records.")
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            recurring_ids = list(dict.fromkeys(tid for row in rows for tid in row["Ticket IDs"].split(", ")))
            with st.expander("Open a supporting ticket"):
                for tid in recurring_ids:
                    if st.button(tid, key=f"recurring_ticket_{tid}"):
                        _open_ticket(tid)
                        st.rerun()
        else:
            st.info("No location/category has 3 or more reports in this filtered date range.")

    st.subheader("Location catalog")
    catalog_rows = []
    parent_names = {l["location_id"]: l["display_name"] for l in locations}
    for loc in visible_locations:
        linked = _tickets_for_location(loc, locations, filtered)
        catalog_rows.append({"Location": loc["display_name"], "Type": loc["location_type"],
                             "Within": parent_names.get(loc["parent_location_id"], "AKGEC campus"),
                             "Coordinates": f"{loc['latitude']:.6f}, {loc['longitude']:.6f}" if loc["latitude"] is not None else "Not mapped",
                             "Confidence": CONFIDENCE.get(loc["verification_status"], loc["verification_status"]),
                             "Reports in filter": len(linked), "Coordinate source": loc["coordinate_source"] or "—",
                             "Map link": loc["google_maps_url"] or "", "Official source": loc.get("source_url") or ""})
    st.dataframe(pd.DataFrame(catalog_rows), hide_index=True, use_container_width=True,
                 column_config={"Map link": st.column_config.LinkColumn("Map", display_text="Open map"),
                                "Official source": st.column_config.LinkColumn("AKGEC reference", display_text="Open source")})
    if selected:
        st.markdown(f"**{h(selected['display_name'])}** · {tag(CONFIDENCE.get(selected['verification_status'], selected['verification_status']), 'o')}", unsafe_allow_html=True)
        if selected["google_maps_url"]:
            st.link_button("Open in Google Maps", selected["google_maps_url"])
        if selected.get("source_url"):
            st.link_button("Open official AKGEC source", selected["source_url"])
        matches = _tickets_for_location(selected, locations, filtered)
        if matches:
            st.dataframe(pd.DataFrame([{"Ticket": t.ticket_id, "Summary": t.summary, "Category": t.category.value,
                                        "Priority": t.priority.value, "Status": t.status.value, "Created": t.created_at.date()}
                                       for t in matches]), hide_index=True, use_container_width=True)
            with st.expander("Open related ticket records"):
                for t in matches:
                    if st.button(f"{t.ticket_id} · {t.summary[:70]}", key=f"location_ticket_{t.ticket_id}"):
                        _open_ticket(t.ticket_id)
                        st.rerun()
        else:
            st.info("No matching reports at this location in the selected filters.")
    resolved_durations = [(t.resolved_at - t.created_at).total_seconds() / 3600 for t in resolved if t.resolved_at and t.resolved_at >= t.created_at]
    if resolved_durations:
        st.caption(f"Mean recorded resolution time in this filter: {statistics.mean(resolved_durations):.1f} hours · based on {len(resolved_durations)} resolved ticket(s).")
    st.caption("Academic departments are catalogued separately from operational service teams. Complaint routing continues to use the existing service-team field; location does not automatically determine who handles a ticket.")
    with st.expander("Official AKGEC academic department catalog"):
        st.write(" · ".join(departments))
        st.link_button("View AKGEC departments source", "https://www.akgec.ac.in/departments/")

    st.subheader("Campus Intelligence Agent")
    st.caption("A read-only, staff-only investigation using registered database tools. It cannot change tickets or assign work.")
    # Keep each staff member's bounded dialogue separate within this authenticated Streamlit session.
    agent_key = f"campus_agent_{actor.id}"
    state = st.session_state.setdefault(agent_key, {"ticket": "", "history": [], "result": None})
    agent_ticket = st.text_input("Ticket reference", value=state["ticket"], placeholder="RAI-2026-0001", key=f"{agent_key}_ticket").strip().upper()
    question = st.text_input("Investigation question", placeholder="What similar unresolved reports are in this location?", key=f"{agent_key}_question")
    run_col, fresh_col = st.columns([1, 1])
    run = run_col.button("Investigate / ask follow-up", type="primary", key=f"{agent_key}_run", disabled=not agent_ticket)
    fresh = fresh_col.button("Start fresh investigation", key=f"{agent_key}_fresh")
    if fresh:
        state.update(ticket="", history=[], result=None)
        st.rerun()
    if agent_ticket != state["ticket"]:
        state.update(ticket=agent_ticket, history=[], result=None)
    if run:
        from agent_service import investigate
        with st.spinner("Reviewing permitted ticket and campus records…"):
            outcome = investigate(agent_ticket, actor, question or None, state["history"])
        if isinstance(outcome, tuple):
            state["result"], state["history"] = outcome
        else:
            state["result"] = outcome
    response = state.get("result")
    if response:
        st.markdown(f"**Investigation for {h(agent_ticket)}** · {h(response.status.title())}")
        st.write(response.answer)
        if response.findings:
            st.markdown("**Findings**")
            for item in response.findings: st.markdown(f"- {h(item)}")
        if response.evidence:
            st.caption("Evidence: " + ", ".join(h(x) for x in response.evidence))
        if response.related_tickets:
            st.markdown("**Related tickets:** " + ", ".join(h(x) for x in response.related_tickets))
        if response.recommendations:
            st.markdown("**Suggested next steps**")
            for item in response.recommendations: st.markdown(f"- {h(item)}")
        if response.uncertainties:
            for item in response.uncertainties: st.warning(item)
        if response.requires_human_review:
            st.info("Human review is recommended before making consequential decisions.")
