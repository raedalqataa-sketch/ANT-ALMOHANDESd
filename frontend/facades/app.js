import {facadeChoiceKey, planSource, verifyPlanIdentity} from "/composition/selected-plan.mjs";

const get = id => document.getElementById(id);
const sideNames = {south:"الجنوبية", north:"الشمالية", east:"الشرقية", west:"الغربية"};

function drawing(view, bounds, label) {
  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  const [left, bottom, right, top] = bounds;
  svg.setAttribute("viewBox", [left-.5, -top-.5, right-left+1, top-bottom+1].join(" "));
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", label);
  svg.classList.add("facade-drawing");
  for (const surface of view.surfaces) {
    const path = document.createElementNS(svgNS, "path");
    const commands = surface.rings.map(ring =>
      "M " + ring.map(([u,z]) => u + "," + (-z)).join(" L ") + " Z"
    );
    path.setAttribute("d", commands.join(" "));
    path.setAttribute("fill", surface.color);
    path.setAttribute("fill-rule", "evenodd");
    svg.append(path);
  }
  return svg;
}

async function load() {
  const {request, identity, query} = planSource();
  if (request.editor_revision) {
    get("back").textContent = "العودة إلى المحرّر";
    get("back").href = "/editor?session=" + request.editor_revision.session_id;
  }
  const response = await fetch("/api/v3/concepts/facades", {
    method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(request)
  });
  const project = await response.json();
  if (!response.ok) throw Error(typeof project.detail === "string" ? project.detail : "تعذّر توليد الواجهات.");
  verifyPlanIdentity(project, identity);
  const cards = project.options.map(option => {
    const card = document.createElement("article");
    card.className = "facade-option";
    const heading = document.createElement("h2");
    heading.textContent = option.title;
    const description = document.createElement("p");
    description.textContent = option.caption;
    const preview = document.createElement("div");
    const choose = document.createElement("button");
    choose.type = "button";
    choose.className = "primary";
    choose.textContent = "اختيار " + option.title + " واستعراض الكتلة";
    choose.onclick = () => {
      try {
        sessionStorage.setItem(facadeChoiceKey(query, option.id), JSON.stringify({
          style:option.id, revision:project.revision, mesh_revision:option.mesh_revision,
          proposal_id:project.proposal_id
        }));
        const params = new URLSearchParams(query);
        params.set("style", option.id);
        location.href = "/massing/?" + params;
      } catch {
        get("status").textContent = "تعذّر حفظ اختيار الواجهة في هذا المتصفح.";
      }
    };
    card.append(heading, description, preview, choose);
    get("options").append(card);
    return {option, preview};
  });
  function selectSide(side) {
    const bounds = [Infinity, Infinity, -Infinity, -Infinity];
    for (const {option} of cards) {
      for (const {rings} of option.views[side].surfaces) {
        for (const [u,z] of rings[0]) {
          bounds[0] = Math.min(bounds[0],u);
          bounds[1] = Math.min(bounds[1],z);
          bounds[2] = Math.max(bounds[2],u);
          bounds[3] = Math.max(bounds[3],z);
        }
      }
    }
    for (const button of get("directions").children) {
      button.setAttribute("aria-pressed", String(button.dataset.side === side));
    }
    for (const {option, preview} of cards) {
      preview.replaceChildren(drawing(option.views[side], bounds, "الواجهة " + sideNames[side] + " · " + option.title));
    }
  }
  for (const [side, name] of Object.entries(sideNames)) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.side = side;
    button.textContent = name;
    button.onclick = () => selectSide(side);
    get("directions").append(button);
  }
  const front = project.entrance_face;
  selectSide(Object.hasOwn(sideNames, front) ? front : "south");
  get("levels").textContent = "مناسيب الأرضيات والسقف · " + project.levels_m.map(z => "+" + z.toFixed(2)).join(" / ") + " م";
  get("status").textContent = "المسقط المختار · مراجعة " + project.revision.slice(0,10);
  get("comparison").hidden = false;
}

load().catch(error => { get("status").textContent = error.message; });
