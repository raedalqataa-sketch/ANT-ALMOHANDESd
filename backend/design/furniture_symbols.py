"""Detailed furniture in plan, fitted to the unchanged model envelopes.

Original vector artwork; no downloaded blocks, brands or raster furniture.
Local shapes rotate with their fixture, including loose pillows and tableware.
"""
import math

SYMBOL_VERSION='atelier-1.0'
INK='#625b53'
SEAM='#a59a8b'
BRASS='#aa8b57'
IVORY='#f6f1e6'
WALNUT='#75604c'


class Painter:
    def __init__(self,scene,fixture):
        self.scene=scene;self.q=fixture;self.rotation=fixture.get('rotation',0)
        self.w,self.h=(fixture['depth'],fixture['width']) if self.rotation in (90,270) else (fixture['width'],fixture['depth'])

    def pt(self,x,y):
        q=self.q
        if self.rotation==0:return q['x']+x,q['y']+y
        if self.rotation==90:return q['x']+q['width']-y,q['y']+x
        if self.rotation==180:return q['x']+q['width']-x,q['y']+q['depth']-y
        return q['x']+y,q['y']+q['depth']-x

    def path(self,commands,fill='none',stroke=INK,lw=.012):
        transformed=[]
        for command in commands:
            coords=[]
            for i in range(1,len(command),2):coords.extend(self.pt(command[i],command[i+1]))
            transformed.append((command[0],*coords))
        self.scene.path(transformed,fill,stroke,lw,'FURNITURE')

    def line(self,a,b,stroke=SEAM,lw=.009):self.scene.line(self.pt(*a),self.pt(*b),stroke,lw,'FURNITURE')

    def oval(self,x,y,w,h,fill=IVORY,stroke=INK,lw=.012):
        a=self.pt(x,y);b=self.pt(x+w,y+h)
        self.scene.ellipse(min(a[0],b[0]),min(a[1],b[1]),abs(b[0]-a[0]),abs(b[1]-a[1]),fill,stroke,lw,'FURNITURE')

    def rounded(self,x,y,w,h,r=.04,fill=IVORY,stroke=INK,lw=.012,angle=0):
        r=min(r,w/2,h/2);k=.5522847498307936
        commands=[('M',x+r,y),('L',x+w-r,y),('C',x+w-r+k*r,y,x+w,y+r-k*r,x+w,y+r),('L',x+w,y+h-r),('C',x+w,y+h-r+k*r,x+w-r+k*r,y+h,x+w-r,y+h),('L',x+r,y+h),('C',x+r-k*r,y+h,x,y+h-r+k*r,x,y+h-r),('L',x,y+r),('C',x,y+r-k*r,x+r-k*r,y,x+r,y),('Z',)]
        if angle:
            cx,cy=x+w/2,y+h/2;a=math.radians(angle);co,si=math.cos(a),math.sin(a)
            rotated=[]
            for c in commands:
                coords=[]
                for i in range(1,len(c),2):
                    dx,dy=c[i]-cx,c[i+1]-cy;coords.extend((cx+dx*co-dy*si,cy+dx*si+dy*co))
                rotated.append((c[0],*coords))
            commands=rotated
        self.path(commands,fill,stroke,lw)

    def pillow(self,x,y,w,h,angle=0,fill=IVORY):
        # Soft bowed edges, flange and a short central fabric crease.
        cx,cy=x+w/2,y+h/2;a=math.radians(angle);co,si=math.cos(a),math.sin(a)
        def shape(inset,color,stroke,lw):
            xx,yy=x+inset,y+inset;ww,hh=w-2*inset,h-2*inset
            cmds=[('M',xx+.10*ww,yy+.08*hh),('C',xx+.34*ww,yy-.035*hh,xx+.70*ww,yy-.035*hh,xx+.90*ww,yy+.08*hh),('C',xx+1.025*ww,yy+.35*hh,xx+1.025*ww,yy+.70*hh,xx+.90*ww,yy+.92*hh),('C',xx+.66*ww,yy+1.035*hh,xx+.30*ww,yy+1.035*hh,xx+.10*ww,yy+.92*hh),('C',xx-.025*ww,yy+.66*hh,xx-.025*ww,yy+.30*hh,xx+.10*ww,yy+.08*hh),('Z',)]
            transformed=[]
            for c in cmds:
                coords=[]
                for i in range(1,len(c),2):
                    dx,dy=c[i]-cx,c[i+1]-cy;coords.extend((cx+dx*co-dy*si,cy+dx*si+dy*co))
                transformed.append((c[0],*coords))
            self.path(transformed,color,stroke,lw)
        shape(0,'#d4c8b7',SEAM,.010);shape(min(w,h)*.06,fill,'#c4b8a5',.006)

    def marble(self,x,y,w,h,light=True):
        if getattr(self.scene,'linework_only',False):return
        vein='#d3c9b9' if light else '#98806b'
        # Curves stay in the central rectangle, inside even a racetrack top.
        for f in (.32,.68):
            self.path([('M',x+w*.18,y+h*f),('C',x+w*.36,y+h*(f-.13),x+w*.45,y+h*(f+.16),x+w*.58,y+h*f),('C',x+w*.68,y+h*(f-.11),x+w*.76,y+h*(f+.06),x+w*.82,y+h*(f-.02))],stroke=vein,lw=.007)


def draw_furniture(scene,q):
    kind=q['kind']
    if kind not in {'single_bed','double_bed','sofa','dining_table','dining_chair','coffee_table','bedside','wardrobe','storage','desk','kitchen_counter','kitchen_island','basin'}:return False
    p=Painter(scene,q);W,H=p.w,p.h
    if kind in ('single_bed','double_bed'):
        p.rounded(.012,.012,W-.024,H-.024,.07,'#8b7862',INK,.016)
        # Upholstered channel headboard and inset mattress.
        p.rounded(.025,.018,W-.05,.18,.045,'#a9977f',INK,.013)
        for i in range(1,max(4,int(W/.18))):
            x=.03+(W-.06)*i/max(4,int(W/.18));p.line((x,.045),(x,.17),'#c8baa6',.008)
        p.rounded(.055,.20,W-.11,H-.26,.07,'#c9bba7','#827462',.012)
        p.rounded(.085,.225,W-.17,H-.32,.06,'#f7f2e6','#c4b8a4',.010)
        # Full bed linen, folded duvet, layered pillows and a woven foot runner.
        p.rounded(.09,.70,W-.18,H-.80,.045,'#e4d9c5','#b9a88f',.011)
        p.path([('M',.10,.72),('C',W*.30,.68,W*.65,.77,W-.10,.71)],stroke='#b5a489',lw=.012)
        p.path([('M',.12,.79),('C',W*.32,.75,W*.62,.84,W-.12,.78)],stroke='#f8f3e7',lw=.012)
        n=2 if kind=='double_bed' else 1;pw=(W-.24)/n
        for i in range(n):
            p.pillow(.12+i*pw,.25,pw-.025,.30,angle=-3 if i==0 else 3)
            p.pillow(.16+i*pw,.45,pw-.105,.25,angle=3 if i==0 else -4,fill='#ddccb1')
        if kind=='double_bed':p.pillow(W/2-.26,.60,.52,.20,fill='#a18c70')
        runner_y=H-.53
        p.rounded(.10,runner_y,W-.20,.31,.02,'#a78c6b','#8a7358',.009)
        for i in range(8):
            yy=runner_y+.035+i*.033;p.line((.14,yy),(W-.14,yy),'#bdab90',.006)
        p.path([('M',W*.22,.94),('C',W*.16,1.1,W*.24,1.20,W*.18,1.36)],stroke='#c3b59d',lw=.008)
    elif kind=='sofa':
        # Walnut/brass plinth, continuous upholstered body and tailored cushions.
        p.rounded(.015,.015,W-.03,H-.03,.10,'#8c7b68',INK,.016)
        p.rounded(.045,.035,W-.09,H-.085,.09,'#c9bcaa','#8d7c66',.012)
        p.rounded(.06,.045,W-.12,.19,.065,'#b5a38c','#8b7962',.010)
        p.line((.14,.10),(W-.14,.10),'#e9ddc9',.008)
        arm=min(.19,W*.09)
        for xx in (.055,W-.055-arm):
            p.rounded(xx,.12,arm,H-.18,.065,'#d3c7b6','#95846d',.012)
            p.line((xx+arm*.33,.22),(xx+arm*.33,H-.15),'#ede3d2',.008)
        n=max(2,q.get('seats',3));sw=(W-2*(arm+.065))/n
        for i in range(n):
            xx=arm+.065+i*sw
            p.rounded(xx,.25,sw-.018,H-.32,.055,'#ece2d2','#ad9d85',.010)
            p.path([('M',xx+.07,H-.14),('C',xx+sw*.30,H-.12,xx+sw*.62,H-.16,xx+sw-.08,H-.14)],stroke='#d2c5b0',lw=.007)
        size=min(.30,H*.35)
        p.pillow(arm+.08,.19,size,size,-13,'#9a8466')
        p.pillow(W-arm-.08-size,.20,size,size,12,'#eee5d3')
        if W>2.0:p.pillow(W-arm-.18-size*1.55,.27,size*.90,size*.88,-8,'#b7a080')
        p.line((.16,H-.045),(W-.16,H-.045),BRASS,.013)
    elif kind=='dining_table':
        p.rounded(.012,.012,W-.024,H-.024,min(W,H)*.36,WALNUT,INK,.016)
        p.rounded(.045,.045,W-.09,H-.09,min(W,H)*.34,BRASS,'#a58b65',.010)
        p.rounded(.062,.062,W-.124,H-.124,min(W,H)*.32,IVORY,'#c4b397',.009)
        p.marble(.08,.08,W-.16,H-.16)
        # Place settings remain artwork, not extra physical chairs or capacity.
        n=max(2,min(4,int(W/.55)))
        for i in range(n):
            cx=.34+(W-.68)*(i+.5)/n
            for cy in (.22,H-.22):
                p.oval(cx-.105,cy-.105,.21,.21,'#e8decc',BRASS,.007)
                p.oval(cx-.080,cy-.080,.16,.16,'#fffaf0','#bfb09a',.005)
                p.line((cx+.125,cy-.08),(cx+.125,cy+.08),'#9d8b70',.008)
        p.oval(W*.44,H*.38,W*.12,H*.24,'#b7a382',BRASS,.009)
        for i in range(3):p.oval(W*.47+i*.035,H*.44,.045,.045,'#eee3c9','#b7a382',.005)
    elif kind=='dining_chair':
        p.rounded(.025,.025,W-.05,H-.05,.13,WALNUT,INK,.013)
        # Curved wraparound back and upholstered shell instead of a square block.
        p.path([('M',.045,H*.75),('C',.015,H*.43,.025,.025,W*.25,.025),('L',W*.75,.025),('C',W-.025,.025,W-.015,H*.43,W-.045,H*.75),('L',W-.10,H*.69),('C',W-.08,H*.35,W-.10,.10,W*.72,.10),('L',W*.28,.10),('C',.10,.10,.08,H*.35,.10,H*.69),('Z',)],'#ab9578','#8c775e',.009)
        p.rounded(.10,.14,W-.20,H-.20,.10,'#eee4d2','#b4a287',.009)
        p.line((W*.34,.06),(W*.66,.06),BRASS,.009)
    elif kind=='coffee_table':
        # Two nesting oval tops fit in the original conservative table envelope.
        p.oval(W*.025,H*.10,W*.65,H*.84,'#5f5143',INK,.014)
        p.oval(W*.045,H*.12,W*.61,H*.78,BRASS,'#a58b62',.008)
        p.oval(W*.06,H*.14,W*.58,H*.74,'#e9e0ce','#b9a585',.008)
        p.marble(W*.10,H*.23,W*.50,H*.48)
        p.oval(W*.51,H*.04,W*.465,H*.62,'#79634e',INK,.012)
        p.oval(W*.53,H*.06,W*.425,H*.56,'#a58b69',BRASS,.008)
        p.marble(W*.56,H*.16,W*.35,H*.32,False)
        p.rounded(W*.16,H*.36,W*.16,H*.20,.01,'#8c7a63','#71614f',.007,angle=-9)
        p.rounded(W*.18,H*.39,W*.16,H*.20,.01,'#f4ecdb','#b8a88f',.007,angle=4)
        p.oval(W*.70,H*.22,W*.10,H*.17,'#eae1cb','#907d60',.008)
    elif kind=='bedside':
        p.rounded(.015,.015,W-.03,H-.03,.065,WALNUT,INK,.013)
        p.rounded(.045,.045,W-.09,H-.09,.04,'#e7dcc8',BRASS,.009)
        p.marble(.045,.045,W-.09,H-.09)
        p.oval(W*.27,H*.27,W*.46,H*.46,'#bba47c',BRASS,.009)
        p.oval(W*.34,H*.34,W*.32,H*.32,'#f7edd8','#c0ae8d',.007)
    elif kind in ('wardrobe','storage'):
        p.rounded(.01,.01,W-.02,H-.02,.01,WALNUT,INK,.013)
        n=max(2,int(W/.5));sw=(W-.04)/n
        for i in range(n):
            xx=.02+i*sw
            p.rounded(xx+.007,.025,sw-.014,H-.05,.008,'#b6a087','#8f785d',.008)
            for k in range(1,5):p.line((xx+sw*k/5,.045),(xx+sw*k/5,H-.045),'#c6b49b',.004)
            p.line((xx+sw-.06,H*.38),(xx+sw-.06,H*.67),BRASS,.014)
        p.line((.04,H-.055),(W-.04,H-.055),'#725e47',.012)
    elif kind=='desk':
        p.rounded(.015,.015,W-.03,H-.03,.06,WALNUT,INK,.015)
        p.rounded(.05,.05,W-.10,H-.10,.04,'#b4a18a','#8f7c64',.009)
        p.rounded(W*.30,H*.16,W*.40,H*.58,.025,'#80735e','#a58f6d',.008)
        p.rounded(W*.35,H*.18,W*.30,H*.30,.015,'#d5ddd7','#77877c',.009)
        p.line((W*.40,H*.60),(W*.60,H*.60),'#c5baa5',.014)
        p.oval(W*.09,H*.22,W*.11,H*.25,'#e9ddc7',BRASS,.009)
    elif kind in ('kitchen_counter','kitchen_island'):
        p.rounded(.008,.008,W-.016,H-.016,.025,'#77634c',INK,.014)
        p.rounded(.025,.025,W-.05,H-.05,.018,'#f0e8d9','#c1b296',.009)
        p.marble(.04,.04,W-.08,H-.08)
        if kind=='kitchen_counter':
            n=max(1,int(W/.6))
            for i in range(1,n):p.line((W*i/n,H-.14),(W*i/n,H-.035),'#a99779',.007)
            p.line((.05,H-.075),(W-.05,H-.075),BRASS,.010)
    elif kind=='basin':
        p.rounded(.008,.008,W-.016,H-.016,.025,WALNUT,INK,.014)
        p.rounded(.028,.028,W-.056,H-.056,.018,'#eee5d4',BRASS,.008)
        p.marble(.04,.04,W-.08,H-.08)
        p.oval(W*.18,H*.22,W*.64,H*.65,'#fffaf0','#aa9a7f',.010)
        p.oval(W*.25,H*.28,W*.50,H*.50,'#e4e7de','#c2c5b8',.007)
        p.line((W/2,H*.03),(W/2,H*.30),BRASS,.025)
    return True
