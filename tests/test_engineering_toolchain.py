"""Runtime smoke tests for optional architectural engineering toolchain.

These verify that the declared Python dependencies can actually be imported and
perform representative operations. They do NOT certify plans as buildable.
"""
from io import BytesIO

import cv2
import ezdxf
import networkx as nx
import numpy as np
import pypdfium2
from ortools.sat.python import cp_model
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from shapely.geometry import Polygon


def test_constraint_optimizer_can_solve_small_placement_choice():
    model = cp_model.CpModel()
    a = model.new_bool_var("a")
    b = model.new_bool_var("b")
    model.add(a + b == 1)
    model.maximize(3 * a + b)
    solver = cp_model.CpSolver()
    status = solver.solve(model)
    assert status == cp_model.OPTIMAL
    assert solver.value(a) == 1


def test_geometry_overlap_and_functional_adjacency_graph():
    living = Polygon([(0, 0), (4, 0), (4, 4), (0, 4)])
    hall = Polygon([(4, 1), (6, 1), (6, 3), (4, 3)])
    overlap = Polygon([(3, 3), (5, 3), (5, 5), (3, 5)])
    assert living.is_valid and hall.is_valid
    assert living.intersection(hall).area == 0
    assert living.touches(hall)
    assert living.intersection(overlap).area == 1
    circulation = nx.Graph()
    circulation.add_edges_from([("entrance", "hall"), ("hall", "living")])
    assert nx.shortest_path(circulation, "entrance", "living") == [
        "entrance", "hall", "living"
    ]


def test_image_processing_available_without_gui():
    image = np.zeros((20, 20), dtype=np.uint8)
    image[4:16, 5:15] = 255
    _, thresholded = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)
    assert int(np.count_nonzero(thresholded)) == 120


def test_pdf_text_and_rendering_backends_read_valid_document():
    memory = BytesIO()
    document = canvas.Canvas(memory)
    document.drawString(50, 700, "ANT ALMOHANDES PDF smoke test")
    document.save()
    content = memory.getvalue()
    assert len(PdfReader(BytesIO(content)).pages) == 1
    pdf = pypdfium2.PdfDocument(content)
    try:
        assert len(pdf) == 1
    finally:
        pdf.close()


def test_dxf_export_supports_required_autocad_2010_version():
    doc = ezdxf.new("R2010")
    assert doc.dxfversion == "AC1024"
    doc.modelspace().add_line((0, 0), (1, 1))
