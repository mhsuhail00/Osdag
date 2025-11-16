from OCC.Core.AIS import AIS_Shape
from OCC.Core.TopAbs import TopAbs_EDGE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import topods, TopoDS_Shape

import os
import os.path
import time
import sys
import math
import itertools

import OCC
from OCC.Core.Aspect import Aspect_GFM_VER
from OCC.Core.AIS import AIS_Shape, AIS_Shaded, AIS_TexturedShape, AIS_WireFrame
from OCC.Core.TopoDS import TopoDS_Shape
from OCC.Core.gp import gp_Dir, gp_Pnt, gp_Pnt2d, gp_Vec
from OCC.Core.BRepBuilderAPI import (BRepBuilderAPI_MakeVertex,
                                     BRepBuilderAPI_MakeEdge,
                                     BRepBuilderAPI_MakeEdge2d,
                                     BRepBuilderAPI_MakeFace)
from OCC.Core.TopAbs import (TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX,
                             TopAbs_SHELL, TopAbs_SOLID)
from OCC.Core.Geom import Geom_Curve, Geom_Surface
from OCC.Core.Geom2d import Geom2d_Curve
from OCC.Core.Visualization import Display3d
from OCC.Core.V3d import (V3d_ZBUFFER, V3d_Zpos, V3d_Zneg, V3d_Xpos,
                          V3d_Xneg, V3d_Ypos, V3d_Yneg, V3d_XposYnegZpos,)
from OCC.Core.TCollection import TCollection_ExtendedString, TCollection_AsciiString
from OCC.Core.Quantity import (Quantity_Color, Quantity_TOC_RGB, Quantity_NOC_WHITE,
                               Quantity_NOC_BLACK, Quantity_NOC_BLUE1,
                               Quantity_NOC_CYAN1, Quantity_NOC_RED,
                               Quantity_NOC_GREEN, Quantity_NOC_ORANGE, Quantity_NOC_YELLOW)
from OCC.Core.Prs3d import Prs3d_Arrow, Prs3d_Presentation, Prs3d_Text, Prs3d_TextAspect
from OCC.Core.Graphic3d import (Graphic3d_NOM_NEON_GNC, Graphic3d_NOT_ENV_CLOUDS,
                                Graphic3d_Camera, Graphic3d_RM_RAYTRACING,
                                Graphic3d_RM_RASTERIZATION,
                                Graphic3d_StereoMode_QuadBuffer,
                                Graphic3d_RenderingParams,
                                Graphic3d_AspectLine3d)
from OCC.Core.Aspect import Aspect_TOTP_RIGHT_LOWER, Aspect_FM_STRETCH, Aspect_FM_NONE
from OCC.Core.TopoDS import TopoDS_Shape
from OCC.Core.Quantity import Quantity_Color, Quantity_NOC_BLACK
import collections
import logging
import traceback

# copied from old osdag change it if suhail doesent allows this 

_log = logging.getLogger("osdag.utilities.osdag_display")

def color_the_edges(shp, display, color, width):
    """
    Colors the edges of a given shape.

    :param shp: The shape to color (TopoDS_Shape).
    :param display: The display context for rendering the shape.
    :param color: The color to apply to the edges (Quantity_Color or predefined constant like Quantity_NOC_BLACK).
    :param width: The width of the edges.
    """
    if not isinstance(shp, TopoDS_Shape):
        raise TypeError("The 'shp' parameter must be a valid TopoDS_Shape.")
    # shapeList = []
    try:
        # Initialize the edge explorer for the given shape
        Ex = TopExp_Explorer(shp, TopAbs_EDGE)
        # Get the display context
        ctx = display.Context
        # Iterate over the edges in the shape
        while Ex.More():
            # Extract the current edge
            aEdge = topods.Edge(Ex.Current())

            # Create an AIS_Shape for the edge
            ais_shape = AIS_Shape(aEdge)
            # Set the color
            ais_shape.SetColor(color)
            # Display the edge
            ctx.Display(ais_shape, False)

            # Store the edge for tracking
            # shapeList.append(aEdge)

            # Move to the next edge
            Ex.Next()

    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()  # This will print the full traceback

        raise RuntimeError(f"Error while coloring edges: {e}")
        
    # return shapeList


def set_default_edge_style(shapes, display):
    """Apply default edge style to a sequence of shapes or a single TopoDS_Shape.

    Accepts:
      - an iterable of TopoDS_Shape (list/tuple/etc.)
      - a single TopoDS_Shape (including TopoDS_Compound)
    """
    # normalize: if a single TopoDS_Shape is passed, make it iterable
    if isinstance(shapes, TopoDS_Shape):
        shapes_iter = [shapes]
    else:
        shapes_iter = shapes

    # If shapes_iter is still not iterable (None or weird type), bail gracefully
    try:
        iterator = iter(shapes_iter)
    except TypeError:
        # nothing sensible to do
        print(f"⚠️ set_default_edge_style: expected iterable or TopoDS_Shape, got {type(shapes).__name__}")
        return

    for shp in iterator:
        if shp is None:
            continue
        try:
            # ensure shp is a TopoDS_Shape before passing on
            if not isinstance(shp, TopoDS_Shape):
                # sometimes osdag passes wrapper objects (they may expose .Shape()); try to extract
                try:
                    candidate = shp.Shape() if hasattr(shp, "Shape") else getattr(shp, "Shape", None)
                    if isinstance(candidate, TopoDS_Shape):
                        shp = candidate
                    else:
                        print(f"⚠️ set_default_edge_style: skipping non-shape item of type {type(shp).__name__}")
                        continue
                except Exception:
                    print(f"⚠️ set_default_edge_style: failed to extract TopoDS_Shape from {type(shp).__name__}")
                    continue

            # safe call to color edges (existing function)
            color_the_edges(shp, display, Quantity_Color(Quantity_NOC_BLACK), 0.5)
        except Exception as e:
            # don't let coloring break the whole display flow
            print(f"⚠️ set_default_edge_style: error while styling shape: {e}")
            continue



def osdag_display_shape(display, shapes, material=None, texture=None, color=None, transparency=None, update=False, label=None, canvas=None):
    """
    Safe wrapper around the display's DisplayShape call.
    - normalizes canvas (creates a dummy if missing)
    - avoids passing strings / None into OCC display
    - accepts single TopoDS_Shape or iterables of shapes
    - stores AIS objects in canvas.model_ais_objects if available
    """

    # --- normalize label ---
    if label is None:
        label = []
    # ensure label is a sequence for indexing
    if not isinstance(label, (list, tuple)):
        label = [label]

    # --- normalize canvas ---
    if canvas is None:
        # try to obtain canvas from display if available
        canvas_candidate = getattr(display, "canvas", None)
        if canvas_candidate is not None:
            canvas = canvas_candidate

    if canvas is None:
        # fallback dummy canvas to avoid AttributeError
        class _DummyCanvas:
            def __init__(self):
                self.model_ais_objects = {}
                self.model_ais_locked = set()
        canvas = _DummyCanvas()
    else:
        # ensure required attributes exist
        if not hasattr(canvas, "model_ais_objects") or canvas.model_ais_objects is None:
            try:
                canvas.model_ais_objects = {}
            except Exception:
                canvas.model_ais_objects = {}
        if not hasattr(canvas, "model_ais_locked") or canvas.model_ais_locked is None:
            try:
                canvas.model_ais_locked = set()
            except Exception:
                canvas.model_ais_locked = set()

    # --- small helper to detect shape-likeness ---
    def _is_topodsshape(obj):
        return isinstance(obj, TopoDS_Shape)

    # --- If shapes is a simple string or None, skip initial DisplayShape and return ---
    if shapes is None:
        _log.debug("osdag_display_shape: shapes is None — nothing to display.")
        return

    if isinstance(shapes, str):
        _log.debug("osdag_display_shape: shapes is a string (%s) — skipping direct DisplayShape call; relying on caller's logic.", shapes)
        return

    # --- If shapes is a single TopoDS_Shape, convert to single item list for consistent handling ---
    if _is_topodsshape(shapes):
        shapes_to_draw = [shapes]
    # If it's an iterable (list/tuple/set), keep it
    elif isinstance(shapes, (list, tuple, set, collections.deque)):
        shapes_to_draw = list(shapes)
    else:
        # Try to extract a shape from common wrapper objects (.Shape() or .Shape attr)
        extracted = None
        try:
            if hasattr(shapes, "Shape") and callable(getattr(shapes, "Shape")):
                extracted = shapes.Shape()
            elif hasattr(shapes, "Shape"):
                extracted = getattr(shapes, "Shape")
        except Exception:
            extracted = None

        if extracted is not None and _is_topodsshape(extracted):
            shapes_to_draw = [extracted]
        else:
            # As a last resort, attempt to let display handle it (may raise TypeError)
            shapes_to_draw = [shapes]

    # --- Apply default edge style if available (guarded) ---
    try:
        # If set_default_edge_style is available in this module, call it; otherwise skip
        if "set_default_edge_style" in globals():
            try:
                set_default_edge_style(shapes_to_draw, display)
            except Exception as e:
                _log.debug("osdag_display_shape: set_default_edge_style skipped/failed: %s", e)
    except Exception:
        pass

    # --- Now call display.DisplayShape for each shape / collection safely ---
    # Some display implementations accept a list, some require single shape; handle both.
    try:
        # If shapes_to_draw contains exactly one item that is a TopoDS_Shape, pass it directly
        item_to_pass = shapes_to_draw[0] if len(shapes_to_draw) == 1 else shapes_to_draw
        ais_object = display.DisplayShape(item_to_pass, material, texture, color, transparency, update=update)
    except TypeError as te:
        # DisplayShape rejected the object type — log and skip drawing
        _log.warning("osdag_display_shape: display.DisplayShape rejected object (%s): %s", type(item_to_pass), te)
        return
    except Exception as e:
        _log.exception("osdag_display_shape: unexpected error from display.DisplayShape: %s", e)
        return

    # Normalize ais_object to a single AIS entry or list
    ais_list = ais_object if isinstance(ais_object, list) else [ais_object]

    # Store AIS references in canvas.model_ais_objects under the label key (if provided)
    try:
        if label and len(label) > 0 and label[0] is not None:
            key = label[0]
            if canvas.model_ais_objects.get(key) is None:
                canvas.model_ais_objects[key] = list(ais_list)
            else:
                canvas.model_ais_objects[key] += list(ais_list)
    except Exception:
        _log.debug("osdag_display_shape: could not store AIS objects on canvas.model_ais_objects (continuing)")

    # Activate selection mode for whole entity if display context exists
    try:
        for ais in ais_list:
            if ais is not None and hasattr(display, "Context") and getattr(display, "Context") is not None:
                try:
                    display.Context.Activate(ais, 0)
                except Exception:
                    # some AIS objects may not be activatable; ignore
                    pass
    except Exception:
        _log.debug("osdag_display_shape: error while activating AIS objects (ignored)")

def rgb_color(r, g, b):
    return Quantity_Color(r, g, b, Quantity_NOC_BLACK)

def to_string(_string):
    return TCollection_ExtendedString(_string)


def DisplayMsg(display, point, text_to_write, height=None, message_color=None, update=False):
    """
    :point: a gp_Pnt or gp_Pnt2d instance
    :text_to_write: a string
    :message_color: triple with the range 0-1
    """
    aPresentation = Prs3d_Presentation(display._struc_mgr)
    text_aspect = Prs3d_TextAspect()

    if message_color is not None:
        text_aspect.SetColor(rgb_color("RED"))
    # if height is not None:
    text_aspect.Aspect()
    # if isinstance(point, None):
    point = gp_Pnt(point.X(), point.Y(), point.Z())
    Prs3d_Text.Draw(aPresentation,
                    text_aspect,
                    to_string(text_to_write),
                    point)
    aPresentation.Display()
    # @TODO: it would be more coherent if a AIS_InteractiveObject
    # is be returned
    if update:
        display.Repaint()
    return aPresentation

# def osdag_display_msg(display, shapes, material=None, texture=None, color=None, transparency=None, update=False):
#     set_default_edge_style(shapes, display)
#     display.DisplayShape(shapes, material, texture, color, transparency, update=update)