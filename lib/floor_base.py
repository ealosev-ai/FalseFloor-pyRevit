# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import Options, PlanarFace, Solid, XYZ  # type: ignore
from revit_context import get_active_view  # type: ignore

_BASE_TOL = 1e-9


def get_top_face_and_loops(floor, view=None):
    if view is None:
        view = get_active_view()

    opt = Options()
    opt.ComputeReferences = True
    if view:
        opt.DetailLevel = view.DetailLevel

    geom = floor.get_Geometry(opt)
    if not geom:
        return None, None

    best_face = None
    best_z = None

    for geom_obj in geom:
        solid = geom_obj if isinstance(geom_obj, Solid) else None
        if not solid or solid.Volume <= 0:
            continue

        for face in solid.Faces:
            planar_face = face if isinstance(face, PlanarFace) else None
            if not planar_face:
                continue
            if abs(planar_face.FaceNormal.Z - 1.0) < 1e-6:
                z_coord = planar_face.Origin.Z
                if best_face is None or z_coord > best_z:
                    best_face = planar_face
                    best_z = z_coord

    if not best_face:
        return None, None

    try:
        return best_face, best_face.GetEdgesAsCurveLoops()
    except Exception:
        return best_face, None


def get_canonical_base_point(floor, view=None):
    face, edge_loops = get_top_face_and_loops(floor, view=view)
    if not face or not edge_loops:
        return None

    candidate = None
    for loop in edge_loops:
        for curve in loop:
            for idx in (0, 1):
                try:
                    point = curve.GetEndPoint(idx)
                except Exception:
                    continue

                if candidate is None:
                    candidate = point
                    continue

                if point.X < candidate.X - _BASE_TOL:
                    candidate = point
                    continue

                if (
                    abs(point.X - candidate.X) <= _BASE_TOL
                    and point.Y < candidate.Y - _BASE_TOL
                ):
                    candidate = point

    if candidate is None:
        return None

    z_val = getattr(candidate, "Z", face.Origin.Z)
    return XYZ(candidate.X, candidate.Y, z_val)
