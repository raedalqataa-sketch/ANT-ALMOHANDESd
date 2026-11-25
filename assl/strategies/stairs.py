"""Program-height stair reservations, not structural or headroom certification."""
import math
from shapely.geometry import Polygon,box
from .geometry import entity,shape

CLUSTERED_FLOOR_HEIGHT_M = 3.2


def require_clustered_floor_height(brief):
    if not math.isclose(brief.floor_height, CLUSTERED_FLOOR_HEIGHT_M, rel_tol=0, abs_tol=1e-6):
        raise ValueError("CLUSTERED_FLOOR_HEIGHT_MUST_BE_3_2")


def make_stair(brief,x,y,width,layout):
 t=brief.wall_thickness;flight=1.1;risers=math.ceil(brief.floor_height/.18/2)*2
 st=dict(layout=layout,floor_height_m=brief.floor_height,risers=risers,flight_width_m=flight,landing_m=1.1,entry_apron_m=1.1,straight_going_m=.28,rotation_deg=0,construction_status='REQUIRES_DETAILED_REVIEW')
 if layout=='u-shaped':
  run=(risers//2-1)*.28;depth=t+st['entry_apron_m']+run+st['landing_m']
  st.update(risers_per_flight=risers//2, riser_height_m=brief.floor_height/risers,
            intermediate_landing_count=1, intermediate_landing_level_m=brief.floor_height/2,
            run_m=run,gross_width_m=width,gross_depth_m=depth,well_width_m=width-t-2*flight)
  return entity('stair-core','stair',box(x,y,x+width,y+depth),name='درج U',zone='shared',stair=st)
 if layout!='semicircular':raise ValueError('UNSUPPORTED_STAIR_LAYOUT')
 radius=width/2;inner=radius-t/2-flight;walk=inner+flight/2
 choices=[n for n in range(5,risers,2) if .28<=math.pi*walk/n<=.34]
 if not choices or inner<=0:raise ValueError('CANNOT_FIT_RADIAL_STAIR')
 radial=min(choices,key=lambda n:abs(math.pi*walk/n-.30));straight=(risers-1-radial)//2
 apron_depth=max(2.8,st['entry_apron_m']+straight*.28+t)
 cx=x+radius;cy=y+apron_depth;cap=[(cx+radius*math.cos(math.pi*i/48),cy+radius*math.sin(math.pi*i/48)) for i in range(49)]
 st.update(radial_treads=radial,inner_radius_m=inner)
 return entity('stair-core','stair',Polygon([(x,y),(x+width,y)]+cap),name='درج منحني',zone='shared',stair=st,arcs=[dict(center=[cx,cy],radius=radius,start_angle=0,end_angle=180,computational_segments=48,max_sagitta_m=radius*(1-math.cos(math.pi/96)))])

def u_frame(r):
 st=r['stair'];angle=math.radians(st['rotation_deg']);u=(math.cos(angle),math.sin(angle));v=(-u[1],u[0]);origin=r['polygon'][0]
 # The rectangle factory starts at the local south-east corner.
 origin=(origin[0]-u[0]*st['gross_width_m'],origin[1]-u[1]*st['gross_width_m'])
 def point(x,y):return (origin[0]+x*u[0]+y*v[0],origin[1]+x*u[1]+y*v[1])
 return point

def validate_u_stair(r,brief):
 try:
  st=r['stair'];t=brief.wall_thickness;N=st['risers'];W=st['gross_width_m'];D=st['gross_depth_m'];run=(N//2-1)*st['straight_going_m']
  values=[st[k] for k in ('rotation_deg','gross_width_m','gross_depth_m','run_m','well_width_m','entry_apron_m','straight_going_m')]
  if not isinstance(N,int) or isinstance(N,bool) or not 4<=N<=64:return False
  values.extend(st[k] for k in ('flight_width_m','landing_m','floor_height_m'))
  if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in values) or N%2 or N<4 or st['straight_going_m']<.28 or st['entry_apron_m']<1.1:return False
  if st['flight_width_m']<1.1 or st['landing_m']<1.1 or abs(st['floor_height_m']-brief.floor_height)>1e-6 or brief.floor_height/N>.18+1e-6:return False
  if r.get('arcs') or abs(st['run_m']-run)>1e-6 or abs(D-(t+st['entry_apron_m']+run+st['landing_m']))>1e-6:return False
  if st['well_width_m']<.2 or abs(W-t-2*st['flight_width_m']-st['well_width_m'])>1e-6:return False
  point=u_frame(r);expected=Polygon([point(0,0),point(W,0),point(W,D),point(0,D)])
  return shape(r).symmetric_difference(expected).area<1e-6
 except (KeyError,ValueError,TypeError,ZeroDivisionError):return False

def u_treads(r,t):
 st=r['stair'];point=u_frame(r);W=st['gross_width_m'];flight=st['flight_width_m'];start=t/2+st['entry_apron_m'];run=st['run_m'];lines=[]
 for left,right in [(t/2,t/2+flight),(W-t/2-flight,W-t/2)]:
  for i in range(st['risers']//2):
   y=start+i*st['straight_going_m'];lines.append((point(left,y),point(right,y)))
 lines.extend([(point(t/2,start+run),point(W-t/2,start+run)),(point(t/2+flight,start),point(t/2+flight,start+run)),(point(W-t/2-flight,start),point(W-t/2-flight,start+run))])
 return lines
