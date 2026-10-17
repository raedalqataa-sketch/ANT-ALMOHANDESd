from backend.main import Project,Room,layout,validate

def test_packing():
 p=Project(plot_width=10,plot_depth=10,rooms=[Room(name='A',width=3,depth=4),Room(name='B',width=3,depth=4)])
 assert len(layout(p))==2
 assert any(c['status']=='PENDING' for c in validate(p))
