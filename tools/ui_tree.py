import os
import re
import time
from typing import Dict, Any, List, Optional, Tuple

try:
    import dbus
    HAS_DBUS = True
except ImportError:
    HAS_DBUS = False


class AccessibleNode:
    """Normalized structured representation of an AT-SPI accessible UI element."""

    def __init__(
        self,
        name: str,
        role: str,
        description: str = "",
        x: int = 0,
        y: int = 0,
        width: int = 0,
        height: int = 0,
        states: Optional[List[str]] = None,
        app_name: str = "",
        bus_name: str = "",
        path: str = "",
        depth: int = 0,
    ):
        self.name = str(name).strip()
        self.role = str(role).strip().lower()
        self.description = str(description).strip()
        self.x = int(x)
        self.y = int(y)
        self.width = int(width)
        self.height = int(height)
        self.center_x = self.x + (self.width // 2) if self.width > 0 else self.x
        self.center_y = self.y + (self.height // 2) if self.height > 0 else self.y
        self.states = states or []
        self.app_name = str(app_name).strip()
        self.bus_name = str(bus_name).strip()
        self.path = str(path).strip()
        self.depth = int(depth)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "description": self.description,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "states": self.states,
            "app_name": self.app_name,
            "depth": self.depth,
        }

    def __repr__(self) -> str:
        return f"<AccessibleNode '{self.name}' role='{self.role}' bounds=[{self.x},{self.y},{self.width},{self.height}]>"


class LinuxAccessibilityTree:
    """
    Direct client for Linux AT-SPI (Assistive Technology Service Provider Interface) via D-Bus.
    Provides sub-5ms inspection of native desktop applications, windows, and UI widgets
    without invoking GPU, OCR, or pixel guesswork.
    """

    def __init__(self):
        self._a11y_bus: Optional[Any] = None
        self._last_bus_check = 0.0

    def get_a11y_bus(self) -> Optional[Any]:
        """Connects to the active AT-SPI bus instance with graceful reconnect and caching."""
        if os.environ.get("BRAIN_MOCK_GUI") == "1" or not HAS_DBUS:
            return None

        now = time.time()
        if self._a11y_bus is not None and (now - self._last_bus_check < 60.0):
            return self._a11y_bus

        try:
            session_bus = dbus.SessionBus()
            a11y_bus_obj = session_bus.get_object("org.a11y.Bus", "/org/a11y/bus")
            a11y_bus_iface = dbus.Interface(a11y_bus_obj, "org.a11y.Bus")
            address = str(a11y_bus_iface.GetAddress())
            self._a11y_bus = dbus.bus.BusConnection(address)
            self._last_bus_check = now
            return self._a11y_bus
        except Exception:
            self._a11y_bus = None
            return None

    def list_accessible_apps(self) -> List[Dict[str, Any]]:
        """
        Lists all desktop applications currently registered on the AT-SPI bus.
        Returns application names, bus names, and active window summaries.
        """
        if os.environ.get("BRAIN_MOCK_GUI") == "1" or not HAS_DBUS:
            return self._get_mock_apps()

        bus = self.get_a11y_bus()
        if not bus:
            return self._get_mock_apps()

        apps = []
        try:
            root = bus.get_object("org.a11y.atspi.Registry", "/org/a11y/atspi/accessible/root")
            acc = dbus.Interface(root, "org.a11y.atspi.Accessible")
            children = acc.GetChildren()

            for s, p in children:
                try:
                    obj = bus.get_object(s, p)
                    props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
                    app_name = str(props.Get("org.a11y.atspi.Accessible", "Name"))
                    if not app_name:
                        continue

                    app_acc = dbus.Interface(obj, "org.a11y.atspi.Accessible")
                    win_children = app_acc.GetChildren()
                    windows = []

                    for ws, wp in win_children:
                        try:
                            wobj = bus.get_object(ws, wp)
                            wprops = dbus.Interface(wobj, "org.freedesktop.DBus.Properties")
                            wname = str(wprops.Get("org.a11y.atspi.Accessible", "Name"))
                            wcomp = dbus.Interface(wobj, "org.a11y.atspi.Component")
                            x, y, w, h = wcomp.GetExtents(0)
                            if w > 10 and h > 10:
                                windows.append({
                                    "title": wname,
                                    "x": int(x),
                                    "y": int(y),
                                    "width": int(w),
                                    "height": int(h),
                                })
                        except Exception:
                            pass

                    apps.append({
                        "app_name": app_name,
                        "bus_name": str(s),
                        "window_count": len(windows),
                        "windows": windows,
                    })
                except Exception:
                    pass
        except Exception:
            return self._get_mock_apps()

        return apps

    def inspect_tree(
        self,
        app_name: Optional[str] = None,
        max_depth: int = 4,
        max_elements: int = 60,
    ) -> List[AccessibleNode]:
        """
        Traverses accessible UI components for the specified application or all visible windows.
        Returns a list of AccessibleNode objects with screen coordinates and roles.
        """
        if os.environ.get("BRAIN_MOCK_GUI") == "1" or not HAS_DBUS:
            return self._get_mock_nodes(app_name)

        bus = self.get_a11y_bus()
        if not bus:
            return self._get_mock_nodes(app_name)

        nodes: List[AccessibleNode] = []

        def walk(service: str, path: str, current_app: str, depth: int):
            if len(nodes) >= max_elements or depth > max_depth:
                return
            try:
                obj = bus.get_object(service, path)
                acc_iface = dbus.Interface(obj, "org.a11y.atspi.Accessible")

                # Name
                name = ""
                try:
                    props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
                    name = str(props.Get("org.a11y.atspi.Accessible", "Name"))
                except Exception:
                    pass

                # Role
                role = "unknown"
                try:
                    role = str(acc_iface.GetRoleName()).lower()
                except Exception:
                    pass

                # Description
                description = ""
                try:
                    props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
                    description = str(props.Get("org.a11y.atspi.Accessible", "Description"))
                except Exception:
                    pass

                # Geometry
                x, y, w, h = 0, 0, 0, 0
                try:
                    comp = dbus.Interface(obj, "org.a11y.atspi.Component")
                    x, y, w, h = comp.GetExtents(0)  # 0 = ATSPI_COORD_TYPE_SCREEN
                except Exception:
                    pass

                # Filter out zero-dimension internal helper nodes
                if (w > 0 and h > 0) or name:
                    node = AccessibleNode(
                        name=name,
                        role=role,
                        description=description,
                        x=int(x),
                        y=int(y),
                        width=int(w),
                        height=int(h),
                        app_name=current_app,
                        bus_name=str(service),
                        path=str(path),
                        depth=depth,
                    )
                    nodes.append(node)

                # Traverse children
                children = acc_iface.GetChildren()
                for cs, cp in children:
                    walk(str(cs), str(cp), current_app, depth + 1)
            except Exception:
                pass

        try:
            root = bus.get_object("org.a11y.atspi.Registry", "/org/a11y/atspi/accessible/root")
            acc = dbus.Interface(root, "org.a11y.atspi.Accessible")
            app_entries = acc.GetChildren()

            # Separate applications with windows from background daemons
            active_app_nodes = []
            bg_app_nodes = []

            for s, p in app_entries:
                try:
                    obj = bus.get_object(s, p)
                    props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
                    cur_app = str(props.Get("org.a11y.atspi.Accessible", "Name"))
                    if not cur_app:
                        continue

                    if app_name and app_name.lower() not in cur_app.lower():
                        continue

                    app_acc = dbus.Interface(obj, "org.a11y.atspi.Accessible")
                    has_windows = len(app_acc.GetChildren()) > 0
                    if has_windows:
                        active_app_nodes.append((s, p, cur_app))
                    else:
                        bg_app_nodes.append((s, p, cur_app))
                except Exception:
                    pass

            # Prioritize active windowed applications first
            ordered_apps = active_app_nodes + ([] if app_name else bg_app_nodes)
            for s, p, cur_app in ordered_apps:
                walk(str(s), str(p), cur_app, depth=0)
                if len(nodes) >= max_elements:
                    break
        except Exception:
            return self._get_mock_nodes(app_name)

        return nodes

    def find_element(
        self,
        query: str,
        role: Optional[str] = None,
        app_name: Optional[str] = None,
    ) -> Optional[AccessibleNode]:
        """
        Locates a specific accessible UI element matching the name query or role.
        Prefers exact name matches, then substring matches, prioritizing interactive roles.
        """
        if not query and not role:
            return None

        clean_query = str(query).strip().lower() if query else ""
        clean_role = str(role).strip().lower() if role else None

        nodes = self.inspect_tree(app_name=app_name, max_depth=4, max_elements=80)
        if not nodes:
            return None

        exact_matches = []
        substring_matches = []
        role_matches = []

        interactive_roles = {
            "push button", "button", "entry", "text", "menu item", "page tab",
            "check box", "radio button", "link", "combo box", "list item"
        }

        for node in nodes:
            node_name = node.name.lower()
            node_role = node.role.lower()

            # Role filter check if requested
            if clean_role and clean_role not in node_role:
                continue

            # Check matches
            if clean_query and node_name == clean_query:
                exact_matches.append(node)
            elif clean_query and (clean_query in node_name or clean_query in node.description.lower()):
                substring_matches.append(node)
            elif not clean_query and clean_role and clean_role in node_role:
                role_matches.append(node)

        # Prioritize interactive elements among candidates
        for candidates in [exact_matches, substring_matches, role_matches]:
            if candidates:
                interactive = [c for c in candidates if c.role in interactive_roles]
                if interactive:
                    return interactive[0]
                return candidates[0]

        return None

    def click_element(
        self,
        query: str,
        role: Optional[str] = None,
        app_name: Optional[str] = None,
        button: str = "left",
    ) -> Dict[str, Any]:
        """
        Resolves the screen coordinates of a matching accessible element and clicks its center.
        Bypasses visual OCR latency and ambiguity.
        """
        node = self.find_element(query, role=role, app_name=app_name)
        if not node:
            return {
                "success": False,
                "tool": "CLICK_ACCESSIBLE_ELEMENT",
                "error": f"Accessible element '{query}' (role={role}) not found.",
            }

        if node.width <= 0 or node.height <= 0:
            return {
                "success": False,
                "tool": "CLICK_ACCESSIBLE_ELEMENT",
                "error": f"Element '{node.name}' has invalid dimensions [{node.width}x{node.height}].",
            }

        from tools.input import click_mouse
        res = click_mouse(node.center_x, node.center_y, button=button)
        return {
            "success": True,
            "tool": "CLICK_ACCESSIBLE_ELEMENT",
            "clicked": {
                "name": node.name,
                "role": node.role,
                "center_x": node.center_x,
                "center_y": node.center_y,
                "bounds": [node.x, node.y, node.width, node.height],
                "app_name": node.app_name,
            },
            "input_result": res,
        }

    def type_in_element(
        self,
        query: str,
        text: str,
        role: Optional[str] = None,
        app_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Clicks an accessible element to focus it, then types the specified text.
        """
        click_res = self.click_element(query, role=role, app_name=app_name)
        if not click_res.get("success"):
            return click_res

        time.sleep(0.1)
        from tools.input import type_text
        type_res = type_text(text)
        return {
            "success": True,
            "tool": "TYPE_ACCESSIBLE_ELEMENT",
            "element": click_res.get("clicked"),
            "text": text,
            "input_result": type_res,
        }

    def _get_mock_apps(self) -> List[Dict[str, Any]]:
        """Mock applications for CI or headless environments."""
        return [
            {
                "app_name": "Brave Browser",
                "bus_name": ":1.31",
                "window_count": 1,
                "windows": [
                    {
                        "title": "YouTube - Brave",
                        "x": 0,
                        "y": 0,
                        "width": 1345,
                        "height": 757,
                    }
                ],
            },
            {
                "app_name": "xfce4-terminal",
                "bus_name": ":1.40",
                "window_count": 1,
                "windows": [
                    {
                        "title": "Terminal - jai@linux",
                        "x": 100,
                        "y": 100,
                        "width": 800,
                        "height": 500,
                    }
                ],
            },
        ]

    def _get_mock_nodes(self, app_name: Optional[str] = None) -> List[AccessibleNode]:
        """Mock accessible nodes for unit testing."""
        return [
            AccessibleNode(
                name="YouTube - Brave",
                role="frame",
                x=0,
                y=0,
                width=1345,
                height=757,
                app_name="Brave Browser",
                depth=0,
            ),
            AccessibleNode(
                name="Search",
                role="entry",
                description="Search query input",
                x=420,
                y=12,
                width=450,
                height=38,
                app_name="Brave Browser",
                depth=1,
            ),
            AccessibleNode(
                name="Search",
                role="push button",
                description="Perform search",
                x=875,
                y=12,
                width=65,
                height=38,
                app_name="Brave Browser",
                depth=1,
            ),
            AccessibleNode(
                name="Play",
                role="push button",
                description="Play video",
                x=250,
                y=350,
                width=50,
                height=50,
                app_name="Brave Browser",
                depth=2,
            ),
        ]


# Singleton instance
default_ui_tree = LinuxAccessibilityTree()


# Exported tool functions for ToolRegistry
def inspect_accessible_tree(
    app_name: Optional[str] = None,
    max_depth: int = 4,
    max_elements: int = 50,
) -> Dict[str, Any]:
    """Inspects visible UI components and their bounding boxes via Linux AT-SPI."""
    nodes = default_ui_tree.inspect_tree(
        app_name=app_name,
        max_depth=int(max_depth),
        max_elements=int(max_elements),
    )
    return {
        "success": True,
        "tool": "INSPECT_ACCESSIBLE_TREE",
        "app_filter": app_name,
        "count": len(nodes),
        "elements": [n.to_dict() for n in nodes],
    }


def find_accessible_element(
    query: str,
    role: Optional[str] = None,
    app_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Finds an element by accessible name or role and returns its exact screen coordinates."""
    node = default_ui_tree.find_element(query, role=role, app_name=app_name)
    if node:
        return {
            "success": True,
            "tool": "FIND_ACCESSIBLE_ELEMENT",
            "found": True,
            "element": node.to_dict(),
        }
    return {
        "success": False,
        "tool": "FIND_ACCESSIBLE_ELEMENT",
        "found": False,
        "error": f"Element matching query='{query}' role='{role}' not found.",
    }


def click_accessible_element(
    query: str,
    role: Optional[str] = None,
    app_name: Optional[str] = None,
    button: str = "left",
) -> Dict[str, Any]:
    """Clicks an element by accessible name or role using AT-SPI coordinates."""
    return default_ui_tree.click_element(
        query=query,
        role=role,
        app_name=app_name,
        button=button,
    )


def type_accessible_element(
    query: str,
    text: str,
    role: Optional[str] = None,
    app_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Focuses an accessible element and types text into it."""
    return default_ui_tree.type_in_element(
        query=query,
        text=text,
        role=role,
        app_name=app_name,
    )
