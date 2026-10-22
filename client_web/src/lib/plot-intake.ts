/**
 * Local-only preliminary plot measurements. This is NOT a cadastral or legal
 * boundary extractor. Corners must follow the uploaded sketch A→B→C→D
 * (top-left, top-right, bottom-right, bottom-left), with no perspective skew.
 */
export type Point = {x:number;y:number};
export type GeoCorner = {lat:number;lon:number};
export type Edge = 'top'|'right'|'bottom'|'left';
export type SiteEvidence = {
  source:'scaled_image'|'gps_corners';
  area_m2:number;
  point_count:4;
  review_required:true;
};
export type PlotMeasurement = {
  width:number;depth:number;area:number;north_edge?:Edge;
  evidence:SiteEvidence;
};

const EARTH_RADIUS_M=6371008.8;
const RAD=Math.PI/180;
const dist=(a:Point,b:Point)=>Math.hypot(a.x-b.x,a.y-b.y);
const cross=(a:Point,b:Point,c:Point)=>(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
const dot=(a:Point,b:Point)=>a.x*b.x+a.y*b.y;
const minus=(a:Point,b:Point):Point=>({x:a.x-b.x,y:a.y-b.y});
const near=(a:number,b:number,allowed:number)=>Math.abs(a-b)/Math.max(a,b)<=allowed;
const round=(n:number)=>Math.round(n*100)/100;

function inspectQuadrilateral(points:Point[]):{top:number;right:number;bottom:number;left:number;area:number}{
  if(points.length!==4||points.some(p=>!Number.isFinite(p.x)||!Number.isFinite(p.y)))
    throw new Error('أدخل أربع زوايا صحيحة مرتبة A ثم B ثم C ثم D.');
  const [a,b,c,d]=points;
  const sides=[dist(a,b),dist(b,c),dist(c,d),dist(d,a)];
  if(sides.some(v=>v<=1e-8))throw new Error('يوجد ضلع صفري؛ راجع نقاط حدود الأرض.');
  // Require convex clockwise order in the sketch, to reject crossings and
  // ambiguous reverse/rotated vertex order.
  const turns=[cross(a,b,c),cross(b,c,d),cross(c,d,a),cross(d,a,b)];
  if(turns.some(v=>v<=1e-8))throw new Error('النقاط متقاطعة أو ليست بترتيب محيط الأرض A-B-C-D.');
  const area=Math.abs(points.reduce((s,p,i)=>s+p.x*points[(i+1)%4].y-p.y*points[(i+1)%4].x,0)/2);
  if(area<=1e-8)throw new Error('حدود الأرض لا تصنع مساحة صحيحة.');
  if(!near(sides[0],sides[2],.08)||!near(sides[1],sides[3],.08))
    throw new Error('الأرض ليست مستطيلة بما يكفي؛ يلزم مسقط حدود هندسي مستقل.');
  const vectors=[minus(b,a),minus(c,b),minus(d,c),minus(a,d)];
  for(let i=0;i<4;i++){
    const v=vectors[i],w=vectors[(i+1)%4];
    if(Math.abs(dot(v,w)/(sides[i]*sides[(i+1)%4]))>.12)
      throw new Error('الزوايا ليست قائمة؛ لا يمكن تحويل هذه القطعة إلى مستطيل بأمان.');
  }
  return {top:sides[0],right:sides[1],bottom:sides[2],left:sides[3],area};
}
function finish(width:number,depth:number,area:number,source:SiteEvidence['source'],north_edge?:Edge):PlotMeasurement{
  const w=round(width),d=round(depth);
  if(w<8||w>60||d<8||d>80)
    throw new Error('الأبعاد المحسوبة خارج نطاق المحرك الحالي (عرض 8–60م وعمق 8–80م).');
  return {width:w,depth:d,area:round(area),north_edge,
    evidence:{source,area_m2:round(area),point_count:4,review_required:true}};
}
export function measureImageCorners(points:Point[],knownTopWidthM:number):PlotMeasurement{
  if(!Number.isFinite(knownTopWidthM)||knownTopWidthM<=0)
    throw new Error('أدخل الطول الحقيقي للضلع A-B من مخطط موثوق لمعايرة الصورة.');
  if(points.some(p=>p.x<0||p.x>1||p.y<0||p.y>1))
    throw new Error('كل نقطة يجب أن تكون داخل الصورة.');
  const sides=inspectQuadrilateral(points);
  const scale=knownTopWidthM/sides.top;
  const width=(sides.top+sides.bottom)/2*scale;
  const depth=(sides.right+sides.left)/2*scale;
  return finish(width,depth,sides.area*scale*scale,'scaled_image');
}
export function measureGeoCorners(corners:GeoCorner[]):PlotMeasurement{
  if(corners.length!==4||corners.some(c=>!Number.isFinite(c.lat)||!Number.isFinite(c.lon)||
    Math.abs(c.lat)>90||Math.abs(c.lon)>180))
    throw new Error('أدخل إحداثيات صحيحة لأركان الأرض الأربعة.');
  const lat0=corners.reduce((s,c)=>s+c.lat,0)/4;
  const lon0=corners.reduce((s,c)=>s+c.lon,0)/4;
  // Local tangent approximation; valid only for small parcels, not survey-grade.
  const points=corners.map(c=>({
    x:EARTH_RADIUS_M*Math.cos(lat0*RAD)*(c.lon-lon0)*RAD,
    y:-EARTH_RADIUS_M*(c.lat-lat0)*RAD
  }));
  const sides=inspectQuadrilateral(points);
  const [a,b,,d]=points;
  const right=minus(b,a),down=minus(d,a);
  const rightLength=dist(a,b),downLength=dist(a,d);
  const unitR={x:right.x/rightLength,y:right.y/rightLength};
  const unitD={x:down.x/downLength,y:down.y/downLength};
  const scores:[Edge,number][]=[
    ['top',unitD.y],['right',-unitR.y],['bottom',-unitD.y],['left',unitR.y]
  ];
  scores.sort((x,y)=>y[1]-x[1]);
  if(scores[0][1]<Math.cos(12*RAD))
    throw new Error('الأرض مائلة عن الجهات الرئيسية؛ المحرك يحتاج زاوية دوران دقيقة قبل اعتماد الأبعاد.');
  return finish((sides.top+sides.bottom)/2,(sides.left+sides.right)/2,
    sides.area,'gps_corners',scores[0][0]);
}
