const $ = (id) => document.getElementById(id),
  NS = "http://www.w3.org/2000/svg";
const ui = {
  sid: null,
  floor: 0,
  version: 0,
  savedIdentity: null,
  savedMassingReady: false,
  model: null,
  areas: {},
  ops: [],
  cursor: 0,
  saved: "[]",
  selected: null,
  edge: null,
  tool: "move",
  view: null,
  initial: null,
  drag: null,
  busy: false,
  checked: false,
  exportable: false,
  issues: [],
};
let proposals = [],
  activeProposal = 0;
function canOpen() {
  return (
    !dirty() ||
    confirm("يوجد تعديل غير محفوظ. هل تريد فتح مقترح آخر وترك هذه التغييرات؟")
  );
}
function objects() {
  return ui.model
    ? [...ui.model.rooms_by_floor[ui.floor], ...ui.model.halls_by_floor[ui.floor]]
    : [];
}
function selected() {
  return objects().find((r) => r.id === ui.selected);
}
function operations() {
  return ui.ops.slice(0, ui.cursor);
}
function dirty() {
  return JSON.stringify(operations()) !== ui.saved;
}
function svg(tag, attrs = {}, text) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  if (text !== undefined) node.textContent = text;
  return node;
}
function toast(text) {
  $("toast").textContent = text;
  $("toast").hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => ($("toast").hidden = true), 6500);
}
async function request(url, body) {
  const r = await fetch(url, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    let msg;
    try {
      msg = (await r.json()).detail;
    } catch {
      msg = "تعذر الاتصال بالخادم";
    }
    if (r.status === 409)
      throw Error(
        "حُفظت نسخة أحدث من نافذة أخرى. أعد فتح الجلسة قبل متابعة الحفظ.",
      );
    throw Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return r.json();
}
async function busy(action, label = "جارٍ تحديث المسقط…") {
  if (ui.busy) return;
  ui.busy = true;
  $("busy").hidden = false;
  $("busy").querySelector("strong").textContent = label;
  controls();
  try {
    return await action();
  } catch (e) {
    toast(friendly(e.message));
    return false;
  } finally {
    ui.busy = false;
    $("busy").hidden = true;
    controls();
  }
}
function friendly(s) {
  if (s.includes("LOCKED_STAIR"))
    return "الدرج محمي. هذا التعديل يمس حدوده؛ اختر جدارًا آخر.";
  if (s.includes("UNSUPPORTED_EDITOR_SCHEMA"))
    return "هذه النسخة تدعم ملفات الاستراتيجية الثانية فقط. افتح ملف GROUND_FLOOR.json.";
  if (s.includes("EDITOR_PARTITION_REQUIRES_FAMILY_CONNECTION"))
    return "اختر فاصلًا مشتركًا بين فراغين عائليين، من دون مساس بباب خصوصية.";
  if (s.includes("EDITOR_ACTIVITY_LINKED"))
    return "الفراغ مرتبط بمجموعة ضيافة أو حمام خاص أو علاقة مطلوبة. راجع البرنامج قبل حذفه.";
  if (s.includes("EDITOR_SELECT_FAMILY_HOST"))
    return "اختر فراغًا عائليًا مضيفًا للنشاط الجديد.";
  if (s.includes("INVALID_EDITED_POLYGON"))
    return "ينتج عن الإزاحة مضلع غير صالح. جرّب مسافة أصغر.";
  return s;
}
function roomLabel(id) {
  return objects().find((r) => r.id === id)?.name || id;
}
function issueLabel(code) {
  const labels = {
    ROOM_NET_AREA: "المساحة أقل من الحد المطلوب",
    ROOM_MIN_SIDE: "أحد الأبعاد أقل من الحد المطلوب",
    GEOMETRY_OVERLAP: "يوجد تداخل بين الفراغات",
    OUTSIDE_BUILDABLE_ENVELOPE: "فراغ يتجاوز حدود البناء",
    DISCONNECTED_BUILDING_FOOTPRINT: "انفصلت كتلة عن بقية المبنى",
    NO_BODY_ROUTE: "انقطع مسار الوصول",
    NO_OUTDOOR_APPROACH: "المدخل غير قابل للوصول من الخارج",
    NO_FEASIBLE_HOSTED_DOOR: "لا يمكن وضع باب صالح على هذا الاتصال",
    NO_VERIFIED_EXTERIOR_WINDOW: "تعذّر توفير نافذة خارجية صالحة",
    NO_EXTERIOR_WINDOW: "تعذّر توفير نافذة خارجية",
    NO_USABLE_FURNISHING: "التأثيث وخلوص الاستعمال يحتاجان معالجة",
    LONG_CORRIDOR: "امتداد الحركة المستقيم يتجاوز الحد",
    CLIENT_ADJACENT: "لا يتحقق الالتصاق المطلوب بين الفراغات",
    CLIENT_NEAR: "مسار الوصول أطول من المسافة التي طلبها العميل",
    CLIENT_SEPARATE: "يتلامس فراغان طلب العميل فصلهما",
    FUNCTIONAL_DISTANCE: "المسافة بين الفراغات الوظيفية طويلة",
    CENTRAL_UNSUPPORTED_PROGRAM: "نوع النشاط المضاف خارج نطاق الفحص الحالي",
    MASSING_UPPER_BEDROOM_DIMENSIONS: "تعديل تجاوز الحد الأدنى لغرفة في الدور الأول",
    ROOM_PROPORTION_OR_EXCESS: "نسب الغرفة أو الزيادة في مساحتها تحتاج مراجعة",
  };
  const [key, ...rest] = code.split(":");
  return (
    (labels[key] || "يحتاج التعديل إلى مراجعة هندسية") +
    (rest.length ? " — " + rest.map(roomLabel).join(" / ") : "")
  );
}
function controls() {
  const ready = !!ui.model && !ui.busy,
    r = selected(),
    editable = ready && r && r.kind !== "stair";
  for (const id of ["save", "apply-edits", "check", "zoom-in", "zoom-out", "fit"])
    $(id).disabled = !ready;
  for (const el of document.querySelectorAll("[data-tool]"))
    el.disabled = !ready;
  const approve = $("approve-massing");
  approve.hidden = !(ui.version > 0 && ui.savedMassingReady && ui.checked && !dirty());
  approve.disabled = !ready || approve.hidden;
  $("undo").disabled = !ready || ui.cursor === 0;
  $("redo").disabled = !ready || ui.cursor >= ui.ops.length;
  for (const id of ["x", "y", "width", "depth", "apply-position", "apply-size"])
    $(id).disabled = !editable;
  $("apply-wall").disabled = !editable || ui.edge === null;
  $("editor-floor").disabled = !ready;
  $("activity-control").hidden = ui.floor !== 0;
  for (const id of ["open-partition","close-partition"])
    $(id).disabled = !editable || ui.edge === null || ui.floor !== 0;
  $("add-activity").disabled = !editable || ui.floor !== 0;
  $("delete-activity").disabled = !editable || !r?.request_id || ui.floor !== 0;
  $("file").disabled = ui.busy;
  $("sample").disabled = ui.busy;
  $("welcome-sample").disabled = ui.busy;
  $("proposals").disabled = ui.busy || !proposals.length;
  $("save-state").textContent = !ui.model
    ? "ابدأ هنا"
    : dirty()
      ? "غير محفوظ"
      : "محفوظ";
  $("revision").textContent = ui.sid
    ? `المراجعة ${ui.version} · ${ui.checked ? "فُحصت الهندسة" : "تعديلات تنتظر الفحص"}`
    : "لم يُفتح مقترح بعد";
}
function inspection() {
  const r = selected();
  $("room-name").textContent = r ? r.name || r.id : "اختر فراغًا من المسقط";
  $("lock").textContent = r?.kind === "stair" ? "مقفول" : "";
  $("room-area").textContent =
    r && ui.areas[r.id] !== undefined ? ui.areas[r.id].toFixed(2) : "—";
  for (const id of ["x", "y", "width", "depth"]) {
    $(id).value = r ? Number(r[id].toFixed(3)) : "";
    $(id).dataset.exact = r ? String(r[id]) : "";
    $(id).dataset.display = $(id).value;
  }
  document
    .querySelector(".wall-controls")
    .classList.toggle("open", ui.tool === "wall");
  controls();
}
function verdict() {
  const box = $("validation");
  box.className =
    "validation" + (!ui.checked ? " neutral" : ui.exportable ? "" : " fail");
  box.textContent = !ui.checked
    ? "توجد تغييرات لم تُفحص بعد. اضغط «افحص الآن» أو احفظ لفحصها."
    : ui.exportable
      ? "اجتاز فحوص التكوين والحركة والتأثيث. متاح للحفظ والتصدير كمقترح تصوري."
      : "توجد مشكلات تحتاج معالجة. يمكن حفظ المسودة، ويُحجب تصدير الرسم.";
  $("issues").replaceChildren();
  if (ui.checked)
    for (const issue of [...new Set(ui.issues)].slice(0, 15)) {
      const li = document.createElement("li");
      li.textContent = issueLabel(issue);
      li.title = issue;
      $("issues").append(li);
    }
  const downloads = $("downloads");
  downloads.replaceChildren();
  if (ui.sid && ui.checked && !dirty())
    for (const ext of ui.exportable && ui.model.rooms_by_floor.length === 1
      ? (ui.model.brief_snapshot.setbacks ? ["json","pdf","dxf"] : ["json","dxf"]) : ["json"]) {
      const a = document.createElement("a");
      a.href = `/api/editor/sessions/${ui.sid}/revisions/${ui.version}/files/${ext}`;
      a.textContent = "↓ " + ext.toUpperCase();
      a.setAttribute("download", "");
      downloads.append(a);
    }
}
function bounds() {
  let xs = [],
    ys = [];
  for (const r of objects())
    for (const [x, y] of r.polygon) {
      xs.push(x);
      ys.push(y);
    }
  return [
    Math.min(...xs) - 1.2,
    -Math.max(...ys) - 1.2,
    Math.max(...xs) - Math.min(...xs) + 2.4,
    Math.max(...ys) - Math.min(...ys) + 2.4,
  ];
}
function fit() {
  if (!ui.model) return;
  const b = bounds(),
    canvas = $("canvas"),
    ratio = canvas.clientWidth / canvas.clientHeight;
  let [x, y, w, h] = b;
  if (w / h > ratio) {
    const next = w / ratio;
    y -= (next - h) / 2;
    h = next;
  } else {
    const next = h * ratio;
    x -= (next - w) / 2;
    w = next;
  }
  ui.view = [x, y, w, h];
  ui.initial = [...ui.view];
  draw();
}
function updateBBox(r) {
  const xs = r.polygon.map((p) => p[0]),
    ys = r.polygon.map((p) => p[1]);
  r.x = Math.min(...xs);
  r.y = Math.min(...ys);
  r.width = Math.max(...xs) - r.x;
  r.depth = Math.max(...ys) - r.y;
}
function draw() {
  const canvas = $("canvas");
  canvas.replaceChildren();
  if (!ui.model) return;
  if (!ui.view) {
    fit();
    return;
  }
  canvas.setAttribute("viewBox", ui.view.join(" "));
  canvas.style.cursor = ui.tool === "pan" ? "grab" : "default";
  const defs = svg("defs"),
    pattern = svg("pattern", {
      id: "grid",
      width: 0.5,
      height: 0.5,
      patternUnits: "userSpaceOnUse",
    });
  pattern.append(
    svg("path", {
      d: "M .5 0 L 0 0 0 .5",
      fill: "none",
      stroke: "#dfe5d5",
      "stroke-width": 0.008,
    }),
  );
  defs.append(pattern);
  canvas.append(
    defs,
    svg("rect", {
      x: ui.view[0],
      y: ui.view[1],
      width: ui.view[2],
      height: ui.view[3],
      fill: "url(#grid)",
    }),
  );
  const b = ui.model.brief_snapshot;
  if (b.setbacks) {
    const W = b.plot_width - b.setbacks.west - b.setbacks.east - b.wall_thickness;
    const D = b.plot_depth - b.setbacks.north - b.setbacks.south - b.wall_thickness;
    canvas.append(
    svg("rect", {
      x: 0,
      y: -D,
      width: W,
      height: D,
      fill: "none",
      stroke: "#b7c5aa",
      "stroke-width": 0.025,
      "stroke-dasharray": ".2 .15",
    }),
    );
  }
  for (const r of objects()) {
    const color =
      r.kind === "corridor"
        ? "#f0eee3"
        : r.kind === "stair"
          ? "#e9e6dc"
          : r.kind === "majlis"
            ? "#e9e0ce"
            : ["kitchen", "bathroom", "storage"].includes(r.kind)
              ? "#e1e8e6"
              : "#dfe9dc";
    const poly = svg("polygon", {
      points: r.polygon.map(([x, y]) => `${x},${-y}`).join(" "),
      fill: color,
      stroke: "#30463d",
      "stroke-width": b.wall_thickness,
      "stroke-linejoin": "round",
      "data-room": r.id,
      class: "room" + (r.id === ui.selected ? " selected" : ""),
    });
    canvas.append(poly);
  }
  for (const q of ui.model.furniture_by_floor?.[ui.floor] || [])
    canvas.append(
      svg("rect", {
        x: q.x,
        y: -q.y - q.depth,
        width: q.width,
        height: q.depth,
        fill: ["sofa", "dining_chair"].includes(q.kind) ? "#cfc5b0" : "#fafbf6",
        stroke: "#98a28f",
        "stroke-width": 0.018,
        rx: 0.045,
        "pointer-events": "none",
      }),
    );
  const ids = Object.fromEntries(objects().map((r) => [r.id, r]));
  for (const o of [
    ...(ui.model.opening_model_009?.[ui.floor]?.doors || []),
    ...(ui.model.opening_model_009?.[ui.floor]?.windows || []),
  ]) {
    const x = o.center[0],
      y = o.center[1],
      a = o.axis === "x" ? 0 : 1,
      w = o.width,
      first = [x, y],
      last = [x, y];
    first[a] -= w / 2;
    last[a] += w / 2;
    canvas.append(
      svg("line", {
        x1: first[0],
        y1: -first[1],
        x2: last[0],
        y2: -last[1],
        stroke: o.kind === "window" ? "#9ebec1" : "#f7f7f1",
        "stroke-width": b.wall_thickness * 1.15,
        "pointer-events": "none",
      }),
    );
    if (o.kind !== "door") continue;
    const r = ids[o.receiving_room];
    if (!r) continue;
    const normal = 1 - a,
      mid = normal ? r.y + r.depth / 2 : r.x + r.width / 2,
      sign = mid > o.center[normal] ? 1 : -1;
    for (const [index, leafWidth] of (o.leaf_widths || [w]).entries()) {
      const direction = index ? -1 : 1, hinge = [x, y];
      hinge[normal] += sign * (b.wall_thickness / 2 + 0.001);
      hinge[a] += index ? w / 2 : -w / 2;
      const pts = [];
      for (let i = 0; i <= 18; i++) {
        const q = [...hinge], angle = ((Math.PI / 2) * i) / 18;
        q[a] += direction * leafWidth * Math.cos(angle);
        q[normal] += sign * leafWidth * Math.sin(angle);pts.push(q);
      }
      canvas.append(svg("polyline", {points:pts.map(p=>`${p[0]},${-p[1]}`).join(" "),fill:"none",stroke:"#87957f","stroke-width":.02,"pointer-events":"none"}),
        svg("line",{x1:hinge[0],y1:-hinge[1],x2:pts[18][0],y2:-pts[18][1],stroke:"#4e6653","stroke-width":.035,"pointer-events":"none"}));
    }
  }
  for (const platform of ui.floor === 0 ? ui.model.entrance_platforms || [] : []) {
    for(const polygon of [platform.landing_polygon,...platform.treads.map(q=>q.polygon)])
      canvas.append(svg("polygon",{points:polygon.map(q=>`${q[0]},${-q[1]}`).join(" "),fill:"#e9dfca",stroke:"#7c806c","stroke-width":.025,"pointer-events":"none"}));
    for(const riser of platform.riser_lines){const [a,c]=riser.points;canvas.append(svg("line",{x1:a[0],y1:-a[1],x2:c[0],y2:-c[1],stroke:"#646b5a","stroke-width":.025}));}
  }

  for (const r of objects()) {
    const x = r.x + r.width / 2,
      y = r.y + r.depth / 2;
    let label = r.kind === "bathroom" ? "حمام ومغاسل" : r.name || r.id;
    if (r.kind === "corridor") label = label.length > 20 ? "بهو ومدخل" : label;
    canvas.append(svg("text", { x, y: -y - 0.08, class: "plan-label" }, label));
    if (r.request_id && ui.areas[r.id] !== undefined)
      canvas.append(
        svg(
          "text",
          { x, y: -y + 0.25, class: "plan-area" },
          `${ui.areas[r.id].toFixed(1)} m²`,
        ),
      );
    if(r.kind==='stair' && r.stair?.layout==='u-shaped') {
      const st=r.stair,theta=st.rotation_deg*Math.PI/180,u=[Math.cos(theta),Math.sin(theta)],v=[-u[1],u[0]],W=st.gross_width_m,t=b.wall_thickness;
      const origin=[r.polygon[0][0]-u[0]*W,r.polygon[0][1]-u[1]*W];
      const point=(x,y)=>[origin[0]+u[0]*x+v[0]*y,origin[1]+u[1]*x+v[1]*y];
      const line=(a,z)=>canvas.append(svg('line',{x1:a[0],y1:-a[1],x2:z[0],y2:-z[1],stroke:'#9caa94','stroke-width':.02,'pointer-events':'none','data-stair-tread':'u'}));
      for(const [left,right] of [[t/2,t/2+st.flight_width_m],[W-t/2-st.flight_width_m,W-t/2]])
        for(let i=0;i<st.risers/2;i++){const y=t/2+st.entry_apron_m+i*st.straight_going_m;line(point(left,y),point(right,y))}
      const y=t/2+st.entry_apron_m+st.run_m;line(point(t/2,y),point(W-t/2,y));
    }
    if (r.kind === "stair" && r.arcs?.length) {
      const arc = r.arcs[0],
        rad = arc.radius - b.wall_thickness/2,
        radial=r.stair.radial_treads, inner=r.stair.inner_radius_m;
      for (let i = 0; i <= radial; i++) {
        const angle = ((arc.start_angle + (180 * i) / radial) * Math.PI) / 180;
        canvas.append(
          svg("line", {
            x1: arc.center[0] + inner * Math.cos(angle),
            y1: -(arc.center[1] + inner * Math.sin(angle)),
            x2: arc.center[0] + rad * Math.cos(angle),
            y2: -(arc.center[1] + rad * Math.sin(angle)),
            stroke: "#9caa94",
            "stroke-width": 0.02,
            "pointer-events": "none",
          }),
        );
      }
    }
  }
  const r = selected();
  if (r && r.kind !== "stair" && ui.tool === "resize")
    canvas.append(
      svg("rect", {
        x: r.x + r.width - 0.13,
        y: -r.y - r.depth - 0.13,
        width: 0.26,
        height: 0.26,
        class: "handle",
        "data-resize": "1",
      }),
    );
  if (r && r.kind !== "stair" && ui.tool === "wall")
    r.polygon.forEach((a, i) => {
      const b = r.polygon[(i + 1) % r.polygon.length];
      canvas.append(
        svg("line", {
          x1: a[0],
          y1: -a[1],
          x2: b[0],
          y2: -b[1],
          class: "wall-handle",
          "stroke-opacity": ui.edge === i ? 1 : 0.5,
          "data-edge": i,
        }),
        svg("line", {
          x1: a[0],
          y1: -a[1],
          x2: b[0],
          y2: -b[1],
          class: "wall-hit",
          "data-edge": i,
        }),
      );
    });
  $("zoom-label").textContent =
    Math.round(((ui.initial?.[2] || ui.view[2]) / ui.view[2]) * 100) + "%";
}
function showBrief() {
  const b=ui.model.brief_snapshot,faces={south:'جنوبي',north:'شمالي',east:'شرقي',west:'غربي'};
  $('client-brief').hidden=false;
  $('brief-summary').replaceChildren();
  const lines=[`المدخل: ${faces[b.entrance_face]} · الأدوار: ${ui.model.rooms_by_floor.length}`];
  if(b.setbacks)lines.push(`الأرض: ${b.plot_width} × ${b.plot_depth} م`,
   `الارتدادات: شمال ${b.setbacks.north}، جنوب ${b.setbacks.south}، شرق ${b.setbacks.east}، غرب ${b.setbacks.west} م`);
  else lines.push('دراسة من دون حدود أرض');

  for(const text of lines){const row=document.createElement('div');row.textContent=text;$('brief-summary').append(row)}
  $('brief-rooms').replaceChildren();
  for(const room of b.rooms){const row=document.createElement('tr'),name=document.createElement('td'),area=document.createElement('td');name.textContent=room.name+(room.count>1?` × ${room.count}`:'');area.textContent=`${room.min_area} م²`;row.append(name,area);$('brief-rooms').append(row)}
}
function setResult(data, { saved = false } = {}) {
  const previousSession = ui.sid;
  ui.model = data.proposal;
  if ((saved && previousSession !== data.session_id) || ui.floor >= ui.model.rooms_by_floor.length) ui.floor = 0;
  $("editor-floor-control").hidden = ui.model.rooms_by_floor.length === 1;
  $("editor-floor").value = ui.floor;
  ui.areas = data.areas || {};
  ui.checked = data.verified !== false;
  ui.exportable = !!data.exportable;
  ui.issues = data.issues || [];
  if (saved) {
    ui.sid = data.session_id;
    ui.version = data.version;
    ui.savedMassingReady = data.massing_ready;
    ui.savedIdentity = {
      version_id: data.version_id,
      geometry_fingerprint: data.geometry_fingerprint,
    };
    ui.saved = JSON.stringify(data.operations);
    ui.ops = data.operations;
    ui.cursor = ui.ops.length;
    history.replaceState(null, "", "/editor?session=" + ui.sid);
    localStorage.setItem("ant-editor-session", ui.sid);
  }
  $("project-title").textContent = ui.model.brief_snapshot.project_name;
  showBrief();
  $("welcome").hidden = true;
  $("legend").hidden = false;
  draw();
  inspection();
  verdict();
}
async function openProposal(p, confirmed = false) {
  if (!confirmed && !canOpen()) return false;
  return await busy(async () => {
    const data = await request("/api/editor/sessions", { proposal: p });
    ui.selected = null;
    ui.edge = null;
    ui.view = null;
    setResult(data, { saved: true });
    activeProposal = Math.max(0, proposals.indexOf(p));
    toast("فُتحت نسخة مستقلة. المقترح الأصلي محفوظ دون تغيير.");
    return true;
  }, "جارٍ فتح المقترح وفحصه…");
}
async function sample() {
  if (!canOpen()) return;
  await busy(async () => {
    const data = await request("/composition/editor-reference.json");
    const saved = await request("/api/editor/sessions", { proposal: data });
    ui.selected = null;
    ui.edge = null;
    ui.view = null;
    proposals = [data];
    activeProposal = 0;
    proposalOptions();
    setResult(saved, { saved: true });
  }, "جارٍ فتح مسقط المرجع…");
}
function proposalOptions() {
  $("proposals").replaceChildren();
  proposals.forEach((p, i) => {
    const option = document.createElement("option");
    option.value = i;
    option.textContent = `المقترح ${i + 1} · ${p.id || "مسقط"}`;
    $("proposals").append(option);
  });
  controls();
}
async function geometry() {
  const data = await request(`/api/editor/sessions/${ui.sid}/geometry`, {
    base_version: ui.version,
    operations: operations(),
  });
  setResult(data);
}
function fieldValue(id) {
  const input = $(id);
  return Number(
    input.value === input.dataset.display ? input.dataset.exact : input.value,
  );
}
async function commit(op) {
  if (ui.busy) return;
  const r = selected();
  if (op.type === "move" && Math.abs(op.dx) + Math.abs(op.dy) < 1e-9) return;
  if (op.type === "wall" && Math.abs(op.offset) < 1e-9) return;
  if (
    op.type === "resize" &&
    r &&
    Math.abs(op.width - r.width) + Math.abs(op.depth - r.depth) < 1e-9
  )
    return;
  await busy(async () => {
    const previous = ui.ops,
      position = ui.cursor;
    ui.ops = [...operations(), {...op, floor:ui.floor}];
    ui.cursor = ui.ops.length;
    try {
      await geometry();
    } catch (e) {
      ui.ops = previous;
      ui.cursor = position;
      inspection();
      verdict();
      throw e;
    }
  });
}
async function navigate(delta) {
  if (ui.busy) return;
  await busy(async () => {
    const previous = ui.cursor;
    ui.cursor += delta;
    try {
      await geometry();
    } catch (e) {
      ui.cursor = previous;
      inspection();
      verdict();
      throw e;
    }
  });
}
function zoom(factor, cx, cy) {
  if (!ui.view) return;
  const [x, y, w, h] = ui.view;
  cx ??= x + w / 2;
  cy ??= y + h / 2;
  const nw = Math.min(200, Math.max(3, w * factor)),
    ratio = nw / w;
  ui.view = [cx + (x - cx) * ratio, cy + (y - cy) * ratio, nw, h * ratio];
  draw();
}
function world(event) {
  const pt = $("canvas").createSVGPoint();
  pt.x = event.clientX;
  pt.y = event.clientY;
  const q = pt.matrixTransform($("canvas").getScreenCTM().inverse());
  return [q.x, -q.y];
}
function quantize(v) {
  return $("snap").checked ? Math.round(v / 0.05) * 0.05 : v;
}
$("canvas").addEventListener("pointerdown", (e) => {
  if (ui.busy || !ui.model || e.button !== 0) return;
  const point = world(e);
  if (ui.tool === "pan") {
    ui.drag = { type: "pan", start: point, view: [...ui.view] };
    $("canvas").setPointerCapture(e.pointerId);
    return;
  }
  const hit = e.target.closest("[data-room]");
  if (hit && ui.selected !== hit.dataset.room) {
    ui.selected = hit.dataset.room;
    ui.edge = null;
    draw();
    inspection();
  }
  const r = selected();
  if (!r || r.kind === "stair") return;
  let type = ui.tool;
  if (type === "wall") {
    if (e.target.dataset.edge === undefined) return;
    ui.edge = Number(e.target.dataset.edge);
  }
  if (type === "resize" && e.target.dataset.resize === undefined) return;
  if (type === "move" && !hit) return;
  ui.drag = {
    type,
    start: point,
    model: structuredClone(ui.model),
    areas: structuredClone(ui.areas),
    checked: ui.checked,
    exportable: ui.exportable,
    r: structuredClone(r),
    edge: ui.edge,
  };
  $("canvas").setPointerCapture(e.pointerId);
  draw();
  controls();
});
$("canvas").addEventListener("pointermove", (e) => {
  const d = ui.drag;
  if (!d) return;
  if (d.type === "pan") {
    const current = world(e);
    ui.view[0] += d.start[0] - current[0];
    ui.view[1] -= d.start[1] - current[1];
    draw();
    return;
  }
  const [x, y] = world(e),
    dx = quantize(x - d.start[0]),
    dy = quantize(y - d.start[1]);
  ui.model = structuredClone(d.model);
  ui.model.furniture_by_floor = [];
  ui.model.opening_model_009 = [];
  const r = selected();
  if (d.type === "move") {
    r.polygon = r.polygon.map(([a, b]) => [a + dx, b + dy]);
    d.operation = { type: "move", room_id: r.id, dx, dy };
  } else if (d.type === "resize") {
    const width = Math.max(0.5, d.r.width + dx),
      depth = Math.max(0.5, d.r.depth + dy);
    r.polygon = r.polygon.map(([a, b]) => [
      r.x + ((a - r.x) * width) / r.width,
      r.y + ((b - r.y) * depth) / r.depth,
    ]);
    d.operation = { type: "resize", room_id: r.id, width, depth };
  } else {
    const a = r.polygon[d.edge],
      b = r.polygon[(d.edge + 1) % r.polygon.length],
      length = Math.hypot(b[0] - a[0], b[1] - a[1]),
      area = r.polygon.reduce((sum, p, i) => {
        const q = r.polygon[(i + 1) % r.polygon.length];
        return sum + p[0] * q[1] - q[0] * p[1];
      }, 0),
      sign = area > 0 ? 1 : -1,
      nx = ((b[1] - a[1]) / length) * sign,
      ny = (-(b[0] - a[0]) / length) * sign,
      offset = quantize(dx * nx + dy * ny);
    r.polygon[d.edge] = [a[0] + nx * offset, a[1] + ny * offset];
    const j = (d.edge + 1) % r.polygon.length;
    r.polygon[j] = [b[0] + nx * offset, b[1] + ny * offset];
    d.operation = { type: "wall", room_id: r.id, edge: d.edge, offset };
  }
  updateBBox(r);
  ui.areas = {};
  ui.checked = false;
  ui.exportable = false;
  draw();
  inspection();
  verdict();
});
function restoreDrag(d) {
  ui.model = d.model;
  ui.areas = d.areas;
  ui.checked = d.checked;
  ui.exportable = d.exportable;
  draw();
  inspection();
  verdict();
}
async function endDrag() {
  const d = ui.drag;
  if (!d) return;
  ui.drag = null;
  if (d.type === "pan") return;
  restoreDrag(d);
  if (
    d.operation &&
    (d.operation.type !== "move" ||
      Math.abs(d.operation.dx) + Math.abs(d.operation.dy) > 0.0001)
  )
    await commit(d.operation);
  else inspection();
}
$("canvas").addEventListener("pointerup", endDrag);
$("canvas").addEventListener("pointercancel", () => {
  if (ui.drag?.model) restoreDrag(ui.drag);
  ui.drag = null;
});
$("canvas").addEventListener(
  "wheel",
  (e) => {
    if (!ui.model || ui.busy) return;
    e.preventDefault();
    const [x, y] = world(e);
    zoom(e.deltaY > 0 ? 1.12 : 1 / 1.12, x, -y);
  },
  { passive: false },
);
for (const button of document.querySelectorAll("[data-tool]"))
  button.onclick = () => {
    ui.tool = button.dataset.tool;
    document
      .querySelectorAll("[data-tool]")
      .forEach((b) => b.classList.toggle("active", b === button));
    $("hint").textContent = {
      move: "اسحب الفراغ. تُكشف أي فجوة أو تداخل عند الفحص.",
      resize: "اسحب المقبض لتغيير حجم المضلع، أو أدخل الأبعاد.",
      wall: "اختر جدارًا برتقاليًا واسحبه؛ يتغير الفراغ المجاور أيضًا.",
      pan: "اسحب اللوحة للتنقل، واستخدم عجلة الفأرة للتقريب.",
    }[ui.tool];
    draw();
    inspection();
  };
$("apply-position").onclick = () => {
  const r = selected();
  commit({
    type: "move",
    room_id: r.id,
    dx: fieldValue("x") - r.x,
    dy: fieldValue("y") - r.y,
  });
};
$("apply-size").onclick = () => {
  const r = selected();
  commit({
    type: "resize",
    room_id: r.id,
    width: fieldValue("width"),
    depth: fieldValue("depth"),
  });
};
$("apply-wall").onclick = () =>
  commit({
    type: "wall",
    room_id: ui.selected,
    edge: ui.edge,
    offset: Number($("wall-offset").value),
  });
$("undo").onclick = () => navigate(-1);
$("redo").onclick = () => navigate(1);
$("fit").onclick = fit;
$("zoom-in").onclick = () => zoom(1 / 1.2);
$("zoom-out").onclick = () => zoom(1.2);
$("sample").onclick = sample;
$("welcome-sample").onclick = sample;
$("check").onclick = () =>
  busy(async () => {
    const data = await request(`/api/editor/sessions/${ui.sid}/preview`, {
      base_version: ui.version,
      operations: operations(),
    });
    setResult(data);
    toast(
      data.exportable
        ? "اجتاز التعديل الفحوص. احفظ لإصدار النسخة الجديدة."
        : "ظهرت مشكلات؛ راجع الملاحظات الجانبية.",
    );
  }, "جارٍ فحص الحركة والأبواب والتأثيث…");
function openFacades(){
  const handoff=crypto.randomUUID();
  sessionStorage.setItem("ant-massing-editor:"+handoff,JSON.stringify({
    editor_revision:{session_id:ui.sid,version:ui.version},
    identity:ui.savedIdentity,
  }));
  location.href="/facades/?edit="+handoff;
}
function saveEdits(continueToFacades){
  return busy(async()=>{
    const data=await request(`/api/editor/sessions/${ui.sid}/revisions`,{
      base_version:ui.version,operations:operations(),
    });
    setResult(data,{saved:true});
    if(continueToFacades&&data.massing_ready){openFacades();return;}
    toast(data.massing_ready
      ?"حُفظ المسقط المعدّل واجتاز فحوص الانتقال للواجهات."
      :"حُفظت المسودة. راجع نتائج الفحص قبل الانتقال للواجهات.");
  },"جارٍ فحص النسخة وحفظها…");
}
$("save").onclick=()=>saveEdits(false);
$("apply-edits").onclick=()=>saveEdits(true);
$("approve-massing").onclick=()=>busy(openFacades);
$("editor-floor").onchange=()=>{
 ui.floor=Number($("editor-floor").value);
 ui.selected=null;ui.edge=null;ui.view=null;ui.initial=null;
 draw();inspection();verdict();
};
$("open-partition").onclick=()=>commit({type:"partition",room_id:ui.selected,edge:ui.edge,open:true});
$("close-partition").onclick=()=>commit({type:"partition",room_id:ui.selected,edge:ui.edge,open:false});
$("delete-activity").onclick=()=>{
 if(confirm("هل تريد حذف الفراغ المحدد من المسقط والبرنامج؟"))commit({type:"delete_space",room_id:ui.selected});
};
$("add-activity").onclick=()=>{
 const host=selected();
 if(!host)return;
 const value=(id,fallback)=>$(id).value===""?fallback:$(id).valueAsNumber;
 commit({type:"add_space",room_id:host.id,name:$("activity-name").value.trim(),kind:$("activity-kind").value,
   x:value("activity-x",host.x+host.width),y:value("activity-y",host.y),
   width:$("activity-width").valueAsNumber,depth:$("activity-depth").valueAsNumber});
};
$("file").onchange = async (e) => {
  try {
    const file = e.target.files[0];
    if (!file) return;
    if (file.size > 2_000_000) throw Error("الملف أكبر من الحد المسموح.");
    const data = JSON.parse(await file.text()),
      incoming = Array.isArray(data.proposals) ? data.proposals : [data];
    if (
      !incoming.length ||
      incoming.some((p) => !["assl-clustered-1","assl-clustered-2","assl-relational-1"].includes(p.schema))
    )
      throw Error("UNSUPPORTED_EDITOR_SCHEMA");
    if (incoming.length > 12) throw Error("اختر ملفًا لا يتجاوز 12 مقترحًا.");
    if (!canOpen()) return;
    if (await openProposal(incoming[0], true)) {
      proposals = incoming;
      activeProposal = 0;
      proposalOptions();
    }
  } catch (error) {
    toast(friendly(error.message));
  } finally {
    e.target.value = "";
  }
};
$("proposals").onchange = async (e) => {
  const target = Number(e.target.value);
  if (await openProposal(proposals[target])) activeProposal = target;
  else $("proposals").value = activeProposal;
};
window.addEventListener("keydown", (e) => {
  if (e.target.matches("input,select,textarea") || ui.busy) return;
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
    e.preventDefault();
    if (e.shiftKey && ui.cursor < ui.ops.length) navigate(1);
    else if (!e.shiftKey && ui.cursor > 0) navigate(-1);
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
    e.preventDefault();
    if (ui.model) $("save").click();
  }
});
window.addEventListener("beforeunload", (e) => {
  if (dirty()) {
    e.preventDefault();
    e.returnValue = "";
  }
});
const sid = new URLSearchParams(location.search).get("session");
if (sid)
  busy(async () => {
    const data = await request(
      "/api/editor/sessions/" + encodeURIComponent(sid),
    );
    setResult(data, { saved: true });
  }, "جارٍ استعادة التعديلات المحفوظة…");
controls();
