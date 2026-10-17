"""Bounded multi-order MaxRects search. Fixed orientation, no architectural claim."""
from itertools import permutations

EPS = 1e-8


def overlaps(a, b):
    return min(a[0]+a[2], b[0]+b[2])-max(a[0], b[0]) > EPS and min(a[1]+a[3], b[1]+b[3])-max(a[1], b[1]) > EPS


def pack_order(project, order, strategy):
    free = [(0.0, 0.0, project.plot_width, project.plot_depth)]
    placed = []
    for room in order:
        options = []
        for x, y, w, h in free:
            if room.width <= w+EPS and room.depth <= h+EPS:
                residual = (w-room.width, h-room.depth)
                score = (y+room.depth, x) if strategy == 'bottom_left' else (min(residual), max(residual), y, x)
                options.append((score, x, y))
        if not options:
            return None
        _, x, y = min(options)
        used = (x, y, room.width, room.depth)
        next_free = []
        for rect in free:
            if not overlaps(rect, used):
                next_free.append(rect)
                continue
            fx, fy, fw, fh = rect
            if x > fx+EPS:
                next_free.append((fx, fy, x-fx, fh))
            if x+room.width < fx+fw-EPS:
                next_free.append((x+room.width, fy, fx+fw-x-room.width, fh))
            if y > fy+EPS:
                next_free.append((fx, fy, fw, y-fy))
            if y+room.depth < fy+fh-EPS:
                next_free.append((fx, y+room.depth, fw, fy+fh-y-room.depth))
        unique = list(dict.fromkeys(next_free))
        free = [r for i, r in enumerate(unique) if not any(i != j and r[0] >= s[0]-EPS and r[1] >= s[1]-EPS and r[0]+r[2] <= s[0]+s[2]+EPS and r[1]+r[3] <= s[1]+s[3]+EPS for j, s in enumerate(unique))]
        placed.append(dict(name=room.name, kind=room.kind, x=x, y=y, width=room.width, depth=room.depth))
    return placed


def layout(project):
    for room in project.rooms:
        if room.width > project.plot_width+EPS or room.depth > project.plot_depth+EPS:
            raise ValueError('أبعاد أحد الفراغات أكبر من الأرض؛ لم يُسمح بتدوير الغرف')
    if sum(r.width*r.depth for r in project.rooms) > project.plot_width*project.plot_depth+EPS:
        raise ValueError('مجموع مساحات الفراغات أكبر من مساحة الأرض')
    keys = [lambda r: (-r.depth, -r.width, r.name), lambda r: (-r.width*r.depth, -r.depth, r.name),
            lambda r: (-r.width, -r.depth, r.name), lambda r: (-max(r.width, r.depth), -min(r.width, r.depth), r.name)]
    orders = [sorted(project.rooms, key=key) for key in keys]
    if len(project.rooms) <= 6:
        orders.extend(permutations(sorted(project.rooms, key=lambda r: (r.name, r.width, r.depth))))
    for order in orders:
        for strategy in ('short_side', 'bottom_left'):
            result = pack_order(project, order, strategy)
            if result is not None:
                return result
    raise ValueError('لم تعثر المحاولات المحدودة على توزيع؛ هذه النتيجة لا تثبت استحالة الحل. جرّب تعديل الأبعاد أو البرنامج')
