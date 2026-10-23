"""Multi-cluster meandering corridor with independently shifted room bands.

Cells are orthogonal and only meet at full shared boundary runs. This offers
a genuine alternate corridor topology, not a cosmetic outline variant.
It is still a bounded rectangular-plot topology, not arbitrary polygons.
"""
def meander_topology(width, depth, corridor, front_fraction, split_fraction):
    if min(width,depth,corridor)<=0:return None
    front=width*front_fraction-corridor/2
    middle=width*(1-front_fraction)-corridor/2
    rear=width*(.46 + .12*(split_fraction-.35))-corridor/2
    lefts=(front,middle,rear)
    if any(min(x,width-x-corridor)<2.8 for x in lefts):return None
    a=depth*split_fraction
    b=a+corridor+(depth-a-2*corridor)*.52
    spans=((0.,a),(a+corridor,b),(b+corridor,depth))
    if min(end-start for start,end in spans)<4.8:return None
    halls=[dict(x=x,y=y,width=corridor,depth=end-y)
           for x,(y,end) in zip(lefts,spans)]
    for y,x1,x2 in ((a,front,middle),(b,middle,rear)):
        left=min(x1,x2)
        right=max(x1,x2)+corridor
        halls.append(dict(x=left,y=y,width=right-left,depth=corridor))
    lanes=[]
    for x,(y,end) in zip(lefts,spans):
        lanes.extend((dict(x=0.,y=y,width=x,depth=end-y,axis='y',door_side='east'),
                      dict(x=x+corridor,y=y,width=width-x-corridor,depth=end-y,
                           axis='y',door_side='west')))
    return halls,lanes
