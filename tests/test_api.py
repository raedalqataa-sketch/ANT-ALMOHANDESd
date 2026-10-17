from io import BytesIO
from openpyxl import Workbook
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_frontend_and_template_round_trip():
    assert client.get('/').status_code == 200
    template = client.get('/api/template.xlsx')
    response = client.post('/api/import-excel', files={'file': ('template.xlsx', template.content)})
    assert response.status_code == 200
    data = response.json()
    assert len(data['rooms']) == 3
    assert data['rooms'][0]['name'] == 'مجلس'


def test_excel_three_columns_supported():
    wb = Workbook()
    for row in [('title', 'اختبار'), ('plot_width', 10), ('plot_depth', 10), (), (), ('name', 'width', 'depth'), ('غرفة', 3, 4)]:
        wb.active.append(row)
    stream = BytesIO()
    wb.save(stream)
    response = client.post('/api/import-excel', files={'file': ('rooms.xlsx', stream.getvalue())})
    assert response.status_code == 200
    assert response.json()['rooms'][0]['kind'] == 'other'


def test_generation_downloads_and_project_round_trip(tmp_path, monkeypatch):
    import backend.main as main
    monkeypatch.setattr(main, 'OUT', tmp_path)
    project = {'title': 'اختبار', 'plot_width': 10, 'plot_depth': 12, 'rooms': [{'name': 'معيشة', 'width': 4, 'depth': 5, 'kind': 'living'}]}
    response = client.post('/api/generate', json=project)
    assert response.status_code == 200
    data = response.json()
    assert data['project'] == project
    assert any(c['status'] == 'PENDING' for c in data['checks'])
    for extension, path in data['downloads'].items():
        download = client.get(path)
        assert download.status_code == 200
        assert len(download.content) > 50
        if extension == 'pdf':
            assert download.content.startswith(b'%PDF')
        if extension == 'json':
            assert download.json()['project'] == project


def test_invalid_programs_rejected():
    base = {'plot_width': 10, 'plot_depth': 10, 'rooms': []}
    assert client.post('/api/generate', json=base).status_code == 422
    base['rooms'] = [{'name': 'A', 'width': 11, 'depth': 2}]
    assert client.post('/api/generate', json=base).status_code == 422
    base['rooms'] = [{'name': 'A', 'width': -1, 'depth': 2}]
    assert client.post('/api/generate', json=base).status_code == 422
    assert client.get('/api/files/00000000000000000000000000000000.pdf').status_code == 404
    assert client.get('/api/files/main.py').status_code == 400
