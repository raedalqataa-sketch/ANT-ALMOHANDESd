import {streamRequest} from "/composition/stream.mjs";
import {createProgressView} from "/composition/progress-view.mjs";

const get = id => document.getElementById(id);
const canvas = get("stage");
const status = get("status");
const renderPage = document.body.dataset.renderPage === "true";
const initial = {yaw:-.86, pitch:renderPage ? .24 : .52, zoom:1};
let camera = {...initial};
const progress = createProgressView({
  container:get("phase-progress"),ring:get("phase-ring"),value:get("phase-percent"),
  detail:get("phase-detail"),elapsed:get("phase-elapsed")
});
const sides={east:[-Math.PI/2,"الواجهة الشرقية"],west:[Math.PI/2,"الواجهة الغربية"],
             north:[Math.PI,"الواجهة الشمالية"],south:[0,"الواجهة الجنوبية"]};

function viewer(canvas) {
  const gl = canvas.getContext("webgl", {antialias:true,preserveDrawingBuffer:true});
  if (!gl) throw Error("عارض 3D يتطلب WebGL في هذا المتصفح.");
  const program = gl.createProgram();
  function attach(type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader,source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader,gl.COMPILE_STATUS)) throw Error(gl.getShaderInfoLog(shader));
    gl.attachShader(program,shader);
  }
  attach(gl.VERTEX_SHADER,
    "attribute vec3 point,tint; uniform vec3 center; uniform vec2 yaw,pitch,scale; uniform float depth,perspective; varying vec3 color;"
    +"void main(){vec3 p=point-center; float x=yaw.x*p.x-yaw.y*p.y; float y=yaw.y*p.x+yaw.x*p.y;"
    +"float distance=y*pitch.x-p.z*pitch.y; gl_Position=vec4(x*scale.x,(p.z*pitch.x+y*pitch.y)*scale.y,distance*depth,1.0+distance*perspective); color=tint;}");
  attach(gl.FRAGMENT_SHADER,
    "precision mediump float; varying vec3 color; void main(){gl_FragColor=vec4(color,1.0);}");
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program,gl.LINK_STATUS)) throw Error(gl.getProgramInfoLog(program));
  gl.useProgram(program);
  gl.enable(gl.DEPTH_TEST);
  const point=gl.getAttribLocation(program,"point"), tint=gl.getAttribLocation(program,"tint");
  gl.enableVertexAttribArray(point);
  gl.enableVertexAttribArray(tint);
  const uniforms=Object.fromEntries(["center","yaw","pitch","scale","depth","perspective"].map(
    key=>[key,gl.getUniformLocation(program,key)]));
  function upload(style) {
    const data=[];
    for (const [vertices,color] of style.faces) {
      const [a,b,c]=vertices;
      const u=b.map((v,i)=>v-a[i]), v=c.map((v,i)=>v-a[i]);
      const n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];
      const brightness=.63+.36*Math.abs((n[0]*.43-n[1]*.43+n[2]*.79)/(Math.hypot(...n)||1));
      const rgb=[1,3,5].map(i=>parseInt(color.slice(i,i+2),16)*brightness/255);
      const triangles=vertices.length===4?[0,1,2,0,2,3]:[0,1,2];
      for (const index of triangles) data.push(...vertices[index],...rgb);
    }
    const buffer=gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
    gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(data),gl.STATIC_DRAW);
    return {buffer,count:data.length/6};
  }
  function render(model,camera,center,diameter,width,height) {
    if(canvas.width!==width)canvas.width=width;
    if(canvas.height!==height)canvas.height=height;
    gl.viewport(0,0,width,height);
    gl.clearColor(.925,.91,.88,1);
    gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
    gl.bindBuffer(gl.ARRAY_BUFFER,model.buffer);
    gl.vertexAttribPointer(point,3,gl.FLOAT,false,24,0);
    gl.vertexAttribPointer(tint,3,gl.FLOAT,false,24,12);
    gl.uniform3fv(uniforms.center,center);
    gl.uniform2f(uniforms.yaw,Math.cos(camera.yaw),Math.sin(camera.yaw));
    gl.uniform2f(uniforms.pitch,Math.cos(camera.pitch),Math.sin(camera.pitch));
    if (renderPage) {
      const inverseDistance=camera.zoom/(diameter*1.18);
      const scale=camera.side?2*camera.zoom/(diameter*1.14):2*43/36*inverseDistance;
      gl.uniform2f(uniforms.scale,scale,scale*width/height);
      gl.uniform1f(uniforms.perspective,camera.side?0:inverseDistance);
      gl.uniform1f(uniforms.depth,.55/diameter);
    } else {
      const scale=2.25*camera.zoom/diameter;
      gl.uniform2f(uniforms.scale,scale*Math.min(1,height/width),scale*Math.min(1,width/height));
      gl.uniform1f(uniforms.perspective,0);
      gl.uniform1f(uniforms.depth,1/diameter);
    }
    gl.drawArrays(gl.TRIANGLES,0,model.count);
  }
  return {upload,render};
}

async function load() {
  const cached=sessionStorage.getItem("ant-massing-proposal");
  if (!cached) throw Error("اختر مسقطًا من صفحة التكوين أولًا.");
  const proposal=JSON.parse(cached);
  progress.start();
  const project=await streamRequest("/api/v3/concepts/massing/stream",{proposal},progress.update);
  const choiceKey="ant-massing-style:"+project.revision;
  const saved=localStorage.getItem(choiceKey);
  if (renderPage) {
    project.styles=project.styles.filter(style=>style.id===saved);
    if (!project.styles.length) throw Error("اختر الطراز قبل فتح الرندر.");
  }
  const render=viewer(canvas), min=[Infinity,Infinity,Infinity], max=[-Infinity,-Infinity,-Infinity];
  for (const style of project.styles) {
    style.model=render.upload(style);
    for (const [vertices] of style.faces) for (const vertex of vertices) for(let axis=0;axis<3;axis++) {
      min[axis]=Math.min(min[axis],vertex[axis]);
      max[axis]=Math.max(max[axis],vertex[axis]);
    }
  }
  const center=min.map((value,i)=>(value+max[i])/2);
  const diameter=Math.hypot(...max.map((value,i)=>value-min[i]));
  const list=get("styles");
  let active=project.styles[0];
  function paint() {
    const ratio=Math.min(devicePixelRatio,2);
    render.render(active.model,camera,center,diameter,
      Math.max(1,Math.round(canvas.clientWidth*ratio)),Math.max(1,Math.round(canvas.clientHeight*ratio)));
  }
  active=project.styles.find(style=>style.id===saved)||active;
  status.textContent="المسقط المختار · عدد الأدوار "+project.floors+" · مراجعة "+project.revision.slice(0,10);
  if (renderPage) {
    get("render-style").textContent=active.title+" · زاوية التصوير";
    configureCapture(project, proposal, active);
  } else {
    function select(style) {
      active=style;
      for (const button of list.querySelectorAll("button")) {
        button.setAttribute("aria-pressed",String(button.dataset.style===style.id));
      }
      get("choice").textContent=style.caption;
      paint();
    }
    for (const style of project.styles) {
      const button=document.createElement("button");
      button.dataset.style=style.id;
      render.render(style.model,initial,center,diameter,230,174);
      const thumb=new Image();
      thumb.src=canvas.toDataURL();
      thumb.alt="";
      const title=document.createElement("strong");
      title.textContent=style.title;
      button.append(thumb,title);
      button.onclick=()=>select(style);
      list.append(button);
    }
    select(active);
    get("save").onclick=()=>{
      try {
        localStorage.setItem(choiceKey,active.id);
        location.href="/render/";
      } catch {
        get("choice").textContent="تعذّر حفظ الطراز في هذا المتصفح.";
      }
    };
  }
  get("workspace").hidden=false;
  paint();
  progress.complete();
  get("phase-detail").textContent="اكتمل رفع المسقط";
  function chooseView(side) {
    camera.side=side;
    for(const button of document.querySelectorAll("[data-side]"))
      button.setAttribute("aria-pressed",String(button.dataset.side===side));
    if(renderPage)get("camera-label").textContent=side?sides[side][1]+" · إسقاط مستقيم":"منظور حر";
  }
  for(const button of document.querySelectorAll("[data-side]")){
    button.onclick=()=>{
      const side=button.dataset.side;
      camera.yaw=sides[side][0];camera.pitch=0;
      chooseView(side);
      paint();
    };
  }
  const orbit=delta=>{chooseView(null);camera.yaw+=delta;paint();};
  const zoom=factor=>{camera.zoom=Math.max(.6,Math.min(2.5,camera.zoom*factor));paint();};
  get("left").onclick=()=>orbit(-.25);
  get("right").onclick=()=>orbit(.25);
  get("zoom-in").onclick=()=>zoom(1.15);
  get("zoom-out").onclick=()=>zoom(1/1.15);
  get("reset").onclick=()=>{camera={...initial};chooseView(null);paint();};
  let down;
  canvas.onpointerdown=e=>{down=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);};
  canvas.onpointermove=e=>{
    if (!down) return;
    chooseView(null);
    camera.yaw+=(e.clientX-down[0])*.013;
    camera.pitch=Math.max(.09,Math.min(1.4,camera.pitch+(e.clientY-down[1])*.01));
    down=[e.clientX,e.clientY];
    paint();
  };
  canvas.onpointerup=canvas.onlostpointercapture=()=>{down=null;};
  canvas.onkeydown=e=>{
    if (["ArrowLeft","ArrowRight"].includes(e.key)) {
      e.preventDefault();
      orbit(e.key==="ArrowLeft"?-.2:.2);
    }
  };
  new ResizeObserver(paint).observe(canvas);
}

function configureCapture(project,proposal,style) {
  const button=get("capture");
  let imageUrl;
  button.onclick=async()=>{
    button.disabled=true;
    progress.start();
    get("phase-detail").textContent="بدء الرندر";
    const side=camera.side||null;
    const snapshot={mode:side?"elevation":"orbit",side,
      yaw:Math.atan2(Math.sin(camera.yaw),Math.cos(camera.yaw)),pitch:camera.pitch,zoom:camera.zoom};
    const description=side?sides[side][1]:"المنظور الملتقط";
    try {
      const image=await streamRequest("/api/v3/concepts/render/stream",{
        proposal,revision:project.revision,style:style.id,camera:snapshot
      },progress.update);
      if(image.revision!==project.revision||image.style!==style.id)throw Error("الصورة لا تطابق المراجعة المختارة.");
      const bytes=Uint8Array.from(atob(image.image),character=>character.charCodeAt(0));
      const nextUrl=URL.createObjectURL(new Blob([bytes],{type:"image/png"}));
      const preview=get("render-image");
      preview.src=nextUrl;
      await preview.decode();
      if(imageUrl)URL.revokeObjectURL(imageUrl);
      imageUrl=nextUrl;
      const download=get("render-download");
      download.href=imageUrl;
      download.download="ANT-"+style.id+"-"+(side||"orbit")+"-"+project.revision.slice(0,10)+".png";
      get("render-caption").textContent=style.title+" · "+description+" · "+image.width+" × "+image.height;
      get("render-result").hidden=false;
      progress.complete();
      get("phase-detail").textContent="اكتمل الرندر والصورة جاهزة للتحميل";
    } catch(error) {
      progress.fail();
      get("phase-detail").textContent=error.message;
    } finally {
      button.disabled=false;
    }
  };
}

load().catch(error=>{
  if (!get("phase-progress").hidden) progress.fail();
  status.textContent=error.message;
});
