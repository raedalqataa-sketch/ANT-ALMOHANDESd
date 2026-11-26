export function planSource() {
  const params = new URLSearchParams(location.search);
  const edit = params.get("edit");
  const plan = params.get("plan");
  if (edit !== null) {
    const saved = JSON.parse(sessionStorage.getItem("ant-massing-editor:" + edit));
    if (!saved?.editor_revision || !saved.identity) {
      throw Error("افتح النسخة المختارة من المحرّر في علامة التبويب هذه.");
    }
    return {request:{editor_revision:saved.editor_revision}, identity:saved.identity,
      query:"?" + new URLSearchParams({edit})};
  }
  const cached = sessionStorage.getItem(plan === null ? "ant-massing-proposal" : "ant-facade-plan:" + plan);
  if (!cached) throw Error("اختر مسقطًا من صفحة التكوين أولًا.");
  return {request:{proposal:JSON.parse(cached)}, query:plan === null ? "" : "?" + new URLSearchParams({plan})};
}

export function verifyPlanIdentity(result, identity) {
  if (identity && (result.version_id !== identity.version_id
      || result.geometry_fingerprint !== identity.geometry_fingerprint
      || result.revision !== identity.geometry_fingerprint)) {
    throw Error("النتيجة لا تطابق النسخة المختارة من المحرّر.");
  }
}

export function facadeChoiceKey(query, style) {
  return "ant-facade-choice:" + query + ":" + style;
}
