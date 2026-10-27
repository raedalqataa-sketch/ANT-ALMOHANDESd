"""Opt-in program-area growth control, before walls/furniture materialization."""


def bounded_growth(room,lane,wall_thickness,base,growth,proposed_factor):
    """Don't inflate requested rooms merely to consume unused lane capacity.

    Unchanged `length_for` still enforces requested minimum area/side. Spare
    length remains an explicit reserve; existing massing logic may remove it
    as exterior space and trims hall tails. Nothing is called recovered usable
    space until full downstream validation and measurements support it.
    """
    if not room.get('request_id') or room.get('guest_vestibule') or room.get('guest_distributor'):
        return growth
    cross=lane['width' if lane['axis']=='y' else 'depth']-wall_thickness
    factor=max(1.,proposed_factor or 1.)
    length_for_target=room['min_area']*factor/cross+wall_thickness
    return min(growth,max(0.,length_for_target-base))
