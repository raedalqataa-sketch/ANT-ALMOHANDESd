"""Portable cubic vector outlines for R2010 polylines and filled boundaries."""
import math


def flatten_path(commands,tolerance=.0008):
    points=[];current=None;closed=False
    def cubic(a,b,c,d,depth=0):
        dx,dy=d[0]-a[0],d[1]-a[1];length=math.hypot(dx,dy)
        def distance(p):
            if length<1e-12:return math.dist(a,p)
            return abs(dy*(p[0]-a[0])-dx*(p[1]-a[1]))/length
        if max(distance(b),distance(c))<=tolerance or depth>=14:
            points.append(d);return
        def mid(p,q):return((p[0]+q[0])/2,(p[1]+q[1])/2)
        ab,bc,cd=mid(a,b),mid(b,c),mid(c,d);abc,bcd=mid(ab,bc),mid(bc,cd);center=mid(abc,bcd)
        cubic(a,ab,abc,center,depth+1);cubic(center,bcd,cd,d,depth+1)
    for cmd in commands:
        if cmd[0]=='M':
            if points:raise ValueError('Each portable path must have one contour')
            current=(cmd[1],cmd[2]);points.append(current)
        elif cmd[0]=='L':current=(cmd[1],cmd[2]);points.append(current)
        elif cmd[0]=='C':
            end=(cmd[5],cmd[6]);cubic(current,(cmd[1],cmd[2]),(cmd[3],cmd[4]),end);current=end
        elif cmd[0]=='Z':closed=True
        else:raise ValueError('Unsupported path command')
    if closed and len(points)>1 and math.dist(points[0],points[-1])<1e-10:points.pop()
    return points,closed


def rounded_rect_path(x,y,w,h,r):
    r=min(r,w/2,h/2);k=.5522847498307936
    return [('M',x+r,y),('L',x+w-r,y),('C',x+w-r+k*r,y,x+w,y+r-k*r,x+w,y+r),('L',x+w,y+h-r),('C',x+w,y+h-r+k*r,x+w-r+k*r,y+h,x+w-r,y+h),('L',x+r,y+h),('C',x+r-k*r,y+h,x,y+h-r+k*r,x,y+h-r),('L',x,y+r),('C',x,y+r-k*r,x+r-k*r,y,x+r,y),('Z',)]
