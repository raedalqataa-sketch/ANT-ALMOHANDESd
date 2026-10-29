"""Compact multi-node family: offset guest/family wings meet at a short crossbar.

Concept-stage topology only: no furniture or door geometry. Two short stems
end at one crossbar; room lanes meet it geometrically. Search remains free to
decline a family that cannot fit the actual customer program.
"""


def compact_fork_topology(width,depth,corridor,side_fraction,split_fraction):
    if min(width,depth,corridor)<=0:return None
    # Off-axis hubs rather than a central uninterrupted spine.
    # Keep the crossbar short even on very wide plots; exterior room
    # recesses absorb excess land, not additional circulation floor area.
    # The available inner lane must remain at least 2.8m net.
    separation=min(6.2,max(corridor+3.0,width*.38))
    center=width*(.5+.015*(side_fraction-.45))
    left_x=center-(separation+corridor)/2
    right_x=left_x+separation
    cross=right_x-left_x-corridor
    left_width=left_x
    right_width=width-right_x-corridor
    if min(cross,left_width,right_width)<2.8:return None
    junction=depth*(.51+.10*(split_fraction-.40))
    short_len=min(junction,5.2+depth*.045)
    if junction<6.5 or depth-junction-corridor<3.0 or short_len<4.8:
        return None
    # North/South labels are purely local topology coordinates.
    halls=[
        dict(x=left_x,y=0.,width=corridor,depth=junction,hub_leg='long'),
        dict(x=right_x,y=junction-short_len,width=corridor,depth=short_len,hub_leg='short'),
        dict(x=left_x,y=junction,width=right_x-left_x+corridor,
             depth=corridor,hub_leg='bridge'),
    ]
    lanes=[
        dict(x=0.,y=0.,width=left_width,depth=junction,axis='y',
             door_side='east',hub_group='outer_guest_candidate'),
        dict(x=left_x+corridor,y=0.,width=cross,depth=junction,
             axis='y',door_side='west',hub_group='inner_left'),
        dict(x=right_x+corridor,y=junction-short_len,width=right_width,
             depth=short_len,axis='y',door_side='west',hub_group='short_family'),
        dict(x=left_x,y=junction+corridor,
             width=right_x-left_x+corridor,
             depth=depth-junction-corridor,axis='x',door_side='north',
             hub_group='crossbar_family'),
    ]
    if any(min(x['width'],x['depth'])<=0 for x in halls+lanes):
        return None
    return halls,lanes
